package repository

import (
	"database/sql"
	"fmt"
	"strings"
	"sync"
)

// schemaColumnsCache memoizes per-(database, table) column sets so schema
// compatibility probes do not run multiple schema queries per row read.
// The schema is fixed after startup migrations, so entries intentionally
// never invalidate. The database pointer is part of the key so isolated test
// databases do not observe each other's schemas; schemaColumnsPins keeps every
// keyed database reachable, because a collected database's address can be
// handed to a new one that would then read the old column set.
var (
	schemaColumnsMu    sync.RWMutex
	schemaColumnsCache = map[string]map[string]struct{}{}
	schemaColumnsPins  = map[string]SQLRunner{}
)

func cachedTableColumns(db SQLRunner, table string) (map[string]struct{}, error) {
	return cachedTableColumnsFor(db, db, table)
}

// cachedTableColumnsFor probes the schema through runner, which may be a
// transaction, and caches the result under owner, the long-lived database the
// runner belongs to, so a transaction never gets a cache entry of its own.
func cachedTableColumnsFor(runner SQLRunner, owner SQLRunner, table string) (map[string]struct{}, error) {
	key := fmt.Sprintf("%p|%s", owner, table)

	schemaColumnsMu.RLock()
	if cols, ok := schemaColumnsCache[key]; ok {
		schemaColumnsMu.RUnlock()
		return cols, nil
	}
	schemaColumnsMu.RUnlock()

	rows, err := runner.Query(fmt.Sprintf("SELECT * FROM %s LIMIT 0", table))
	if err != nil {
		return nil, fmt.Errorf("failed to inspect table %s: %w", table, err)
	}
	defer func() { _ = rows.Close() }()

	names, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("failed to inspect columns for %s: %w", table, err)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed to inspect schema rows for %s: %w", table, err)
	}

	cols := make(map[string]struct{}, len(names))
	for _, name := range names {
		cols[strings.ToLower(strings.TrimSpace(name))] = struct{}{}
	}

	schemaColumnsMu.Lock()
	schemaColumnsCache[key] = cols
	// Only a database is pinned: a transaction is short-lived and must not be
	// kept alive by the cache.
	if db, ok := owner.(*sql.DB); ok {
		schemaColumnsPins[key] = db
	}
	schemaColumnsMu.Unlock()
	return cols, nil
}

// isPostgresDriver reports whether a repository's driver name is PostgreSQL,
// the only supported database with row locks (SELECT ... FOR UPDATE).
func isPostgresDriver(driver string) bool {
	return strings.Contains(strings.ToLower(driver), "postgres")
}

// bindPlaceholders rewrites ?-style positional placeholders to PostgreSQL $n
// form, skipping ? characters inside single-quoted string literals. It is the
// single shared implementation behind every repository's bindQuery method.
func bindPlaceholders(driver, query string) string {
	if !strings.Contains(strings.ToLower(driver), "postgres") {
		return query
	}
	var b strings.Builder
	b.Grow(len(query) + 16)
	idx := 1
	inLiteral := false
	for i := 0; i < len(query); i++ {
		ch := query[i]
		switch {
		case ch == '\'' && (i == 0 || query[i-1] != '\\'):
			inLiteral = !inLiteral
			b.WriteByte(ch)
		case ch == '?' && !inLiteral:
			b.WriteString(fmt.Sprintf("$%d", idx))
			idx++
		default:
			b.WriteByte(ch)
		}
	}
	return b.String()
}
