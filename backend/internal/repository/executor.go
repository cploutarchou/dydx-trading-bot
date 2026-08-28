package repository

import (
	"context"
	"database/sql"
)

type QueryExecutor interface {
	ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error)
	QueryRowContext(ctx context.Context, query string, args ...interface{}) *sql.Row
}

type TransactionStarter interface {
	BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error)
}

type SQLExecutor interface {
	QueryExecutor
	TransactionStarter
}

var (
	_ QueryExecutor      = (*sql.DB)(nil)
	_ QueryExecutor      = (*sql.Tx)(nil)
	_ TransactionStarter = (*sql.DB)(nil)
)

// SQLRunner is the database subset shared by *sql.DB and *sql.Tx, letting
// repositories execute inside an ambient transaction via WithTx. Context
// variants are included so transactional and cancellable calls share one type.
type SQLRunner interface {
	Exec(query string, args ...interface{}) (sql.Result, error)
	Query(query string, args ...interface{}) (*sql.Rows, error)
	QueryRow(query string, args ...interface{}) *sql.Row
	ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error)
	QueryRowContext(ctx context.Context, query string, args ...interface{}) *sql.Row
}

var (
	_ SQLRunner = (*sql.DB)(nil)
	_ SQLRunner = (*sql.Tx)(nil)
)
