package db

import (
	"database/sql"
	"errors"
	"strings"
)

// MySQLError represents a MySQL database error
type MySQLError struct {
	Number  uint16
	Message string
}

// Error implements the error interface
func (e *MySQLError) Error() string {
	return e.Message
}

// ErrorCode extracts the error code from a database error
func ErrorCode(err error) string {
	if err == nil {
		return ""
	}

	// Check for MySQL driver error format: "*mysql.MySQLError"
	// MySQL errors come in format like "Error 1054: Unknown column 'xyz' in 'field list'"
	errStr := err.Error()

	// Pattern: "Error XXXX:" (MySQL error number)
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

	return ""
}

// IsDuplicateKeyError checks if error is a duplicate key error (MariaDB/MySQL 1062)
func IsDuplicateKeyError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// MySQL: "Error 1062: Duplicate entry 'xyz' for key 'primary'"
	if strings.Contains(errStr, "1062") || strings.Contains(errStr, "Duplicate entry") {
		return true
	}

	return false
}

// IsDeadlockError checks if error is a deadlock error (MariaDB/MySQL 1213)
func IsDeadlockError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// MySQL: "Error 1213: Deadlock found when trying to get lock"
	if strings.Contains(errStr, "1213") || strings.Contains(errStr, "Deadlock found") {
		return true
	}

	if strings.Contains(errStr, "deadlock") {
		return true
	}

	return false
}

// IsUndefinedColumnError checks if error is an undefined column error (MariaDB/MySQL 1054)
func IsUndefinedColumnError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// MySQL: "Error 1054: Unknown column 'xyz' in 'field list'"
	if strings.Contains(errStr, "1054") || strings.Contains(errStr, "Unknown column") {
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
