package db

import (
	"database/sql"
	"errors"
	"strings"
)

// SQLDriverError is a lightweight driver-agnostic SQL error shape.
type SQLDriverError struct {
	Number  uint16
	Message string
}

// Error implements the error interface
func (e *SQLDriverError) Error() string {
	return e.Message
}

// ErrorCode extracts the error code from a database error
func ErrorCode(err error) string {
	if err == nil {
		return ""
	}

	// Parse common SQL driver error formats.
	errStr := err.Error()

	// Pattern: "Error XXXX:" (legacy numeric error format)
	if strings.Contains(errStr, "Error") {
		parts := strings.Fields(errStr)
		for i, part := range parts {
			if part == "Error" && i+1 < len(parts) {
				// Extract the numeric code
				if code := strings.TrimSuffix(parts[i+1], ":"); len(code) > 0 {
					return code
				}
			}
		}
	}

	// PostgreSQL errors often embed SQLSTATE codes directly.
	for _, state := range []string{"23505", "40P01", "42703"} {
		if strings.Contains(errStr, state) {
			return state
		}
	}

	return ""
}

// IsDuplicateKeyError checks if error is a duplicate key / unique constraint violation.
func IsDuplicateKeyError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	if strings.Contains(errStr, "23505") ||
		strings.Contains(strings.ToLower(errStr), "duplicate key") ||
		strings.Contains(strings.ToLower(errStr), "unique constraint") ||
		strings.Contains(errStr, "1062") ||
		strings.Contains(errStr, "Duplicate entry") {
		return true
	}

	return false
}

// IsDeadlockError checks if error is a deadlock error.
func IsDeadlockError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	if strings.Contains(errStr, "40P01") || strings.Contains(errStr, "1213") || strings.Contains(errStr, "Deadlock found") {
		return true
	}

	if strings.Contains(errStr, "deadlock") {
		return true
	}

	return false
}

// IsUndefinedColumnError checks if error is an undefined column error.
func IsUndefinedColumnError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()
	errLower := strings.ToLower(errStr)

	if strings.Contains(errStr, "42703") ||
		(strings.Contains(errLower, "column") && strings.Contains(errLower, "does not exist")) ||
		strings.Contains(errStr, "1054") ||
		strings.Contains(errStr, "Unknown column") {
		return true
	}

	return false
}

// IsConstraintViolationError checks if error is a constraint violation
func IsConstraintViolationError(err error) bool {
	if err == nil {
		return false
	}

	return IsDuplicateKeyError(err) || IsUndefinedColumnError(err)
}

// WrapSQLError converts database errors to a standardized format
func WrapSQLError(err error) error {
	if err == nil {
		return nil
	}

	// Return sql.ErrNoRows as-is (used for checking if row exists)
	if errors.Is(err, sql.ErrNoRows) {
		return err
	}

	return err
}
