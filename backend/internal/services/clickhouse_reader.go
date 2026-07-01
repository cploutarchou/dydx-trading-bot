package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
)

// ErrClickHouseDisabled is returned when ClickHouse reads are not enabled or the
// reader was never constructed. Callers must treat this as a fail-closed signal
// and fall back to the existing delegated read path.
var ErrClickHouseDisabled = errors.New("clickhouse analytics disabled")

// ErrClickHouseUnavailable is returned when the ClickHouse HTTP endpoint could
// not service the query (transport error, timeout, or non-2xx status). Callers
// should fail closed and fall back rather than surface partial data.
var ErrClickHouseUnavailable = errors.New("clickhouse analytics unavailable")

const (
	defaultClickHousePort    = 8123
	defaultClickHouseTimeout = 5 * time.Second
	// maxClickHouseResponseBytes bounds a single read-model response so a
	// misbehaving upstream cannot exhaust backend memory.
	maxClickHouseResponseBytes = 8 << 20
)

// ClickHouseReader queries the ClickHouse HTTP interface (default port 8123)
// without introducing a new runtime dependency, mirroring the MinIO artifact
// signer pattern. It is intentionally read-only and returns JSONEachRow rows as
// raw JSON so callers can decode into typed read models. Construct it with
// NewClickHouseReader; a nil reader means reads are disabled.
type ClickHouseReader struct {
	baseURL  string
	database string
	user     string
	password string
	client   *http.Client
}

// NewClickHouseReader returns nil when ClickHouse reads are not enabled or the
// endpoint is not resolvable. A nil reader signals callers to fall back to the
// existing delegated path.
func NewClickHouseReader(settings config.ClickHouseSettings) *ClickHouseReader {
	if !settings.Enabled {
		return nil
	}
	baseURL := buildClickHouseBaseURL(settings)
	if baseURL == "" {
		return nil
	}
	return &ClickHouseReader{
		baseURL:  baseURL,
		database: strings.TrimSpace(settings.Database),
		user:     strings.TrimSpace(settings.User),
		password: settings.Password,
		client:   &http.Client{Timeout: defaultClickHouseTimeout},
	}
}

// NewClickHouseReaderWithClient is a test seam that injects a custom HTTP client
// (for example one pointed at an httptest.Server) while keeping construction
// identical to NewClickHouseReader.
func NewClickHouseReaderWithClient(settings config.ClickHouseSettings, client *http.Client) *ClickHouseReader {
	reader := NewClickHouseReader(settings)
	if reader == nil {
		return nil
	}
	if client != nil {
		reader.client = client
	}
	return reader
}

func buildClickHouseBaseURL(settings config.ClickHouseSettings) string {
	if raw := strings.TrimSpace(settings.URL); raw != "" {
		return raw
	}
	host := strings.TrimSpace(settings.Host)
	if host == "" {
		return ""
	}
	scheme := "http"
	if settings.Secure {
		scheme = "https"
	}
	port := settings.Port
	if port <= 0 {
		port = defaultClickHousePort
	}
	return fmt.Sprintf("%s://%s:%d", scheme, host, port)
}

// Query runs a read-only ClickHouse query through the HTTP interface and returns
// each JSONEachRow row as raw JSON. Use ClickHouse {name:Type} placeholders and
// pass their values through params; values are bound server-side and are never
// interpolated into the query text. FORMAT is appended automatically.
func (r *ClickHouseReader) Query(ctx context.Context, query string, params map[string]string) ([]json.RawMessage, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}
	if ctx == nil {
		ctx = context.Background()
	}

	body := ensureJSONEachRowFormat(query)
	endpoint, err := r.buildQueryURL(params)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(body))
	if err != nil {
		return nil, err
	}
	r.applyAuth(req)
	req.Header.Set("Content-Type", "text/plain; charset=utf-8")

	resp, err := r.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrClickHouseUnavailable, err)
	}
	defer func() { _ = resp.Body.Close() }()

	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, maxClickHouseResponseBytes))
	if err != nil {
		return nil, fmt.Errorf("%w: read body: %v", ErrClickHouseUnavailable, err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("%w: clickhouse status %d: %s", ErrClickHouseUnavailable, resp.StatusCode, truncateBody(responseBody))
	}

	return decodeJSONEachRow(responseBody)
}

func (r *ClickHouseReader) buildQueryURL(params map[string]string) (string, error) {
	parsed, err := url.Parse(r.baseURL)
	if err != nil {
		return "", fmt.Errorf("invalid clickhouse base url: %w", err)
	}
	query := parsed.Query()
	if database := strings.TrimSpace(r.database); database != "" {
		query.Set("database", database)
	}
	for key, value := range params {
		if key == "" {
			continue
		}
		query.Set("param_"+key, value)
	}
	parsed.RawQuery = query.Encode()
	return parsed.String(), nil
}

func (r *ClickHouseReader) applyAuth(req *http.Request) {
	if r.user == "" && r.password == "" {
		return
	}
	req.Header.Set("X-ClickHouse-User", r.user)
	if r.password != "" {
		req.Header.Set("X-ClickHouse-Key", r.password)
	}
}

// ensureJSONEachRowFormat appends the JSONEachRow output format when the caller
// did not specify one, so Query always returns parseable JSON regardless of the
// caller. ClickHouse rejects a query that specifies FORMAT twice, so an existing
// FORMAT clause is left untouched.
func ensureJSONEachRowFormat(query string) string {
	if strings.Contains(strings.ToUpper(query), "FORMAT ") || strings.Contains(strings.ToUpper(query), "FORMAT\n") {
		return query
	}
	return strings.TrimRight(query, " \n\t;") + "\nFORMAT JSONEachRow"
}

func decodeJSONEachRow(body []byte) ([]json.RawMessage, error) {
	trimmed := strings.TrimSpace(string(body))
	if trimmed == "" {
		return nil, nil
	}
	rows := make([]json.RawMessage, 0, 16)
	decoder := json.NewDecoder(strings.NewReader(trimmed))
	for {
		var row json.RawMessage
		if err := decoder.Decode(&row); err != nil {
			if errors.Is(err, io.EOF) {
				break
			}
			return nil, fmt.Errorf("decode clickhouse row: %w", err)
		}
		rows = append(rows, row)
	}
	return rows, nil
}

func truncateBody(body []byte) string {
	const max = 512
	text := strings.TrimSpace(string(body))
	if len(text) > max {
		return text[:max] + "..."
	}
	return text
}
