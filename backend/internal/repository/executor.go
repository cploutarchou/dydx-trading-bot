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
