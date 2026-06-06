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

// PostgreSQLErrorMap converts PostgreSQL error codes to MySQL error codes
// This is used for backward compatibility and error handling consistency
var PostgreSQLErrorMap = map[string]uint16{
	// Column/Table errors
	"42703": 1054, // Column does not exist → Unknown column
	"42P07": 1050, // Table already exists → Table already exists
	"42P01": 1051, // Undefined table → Unknown table

	// Constraint/Duplicate errors
	"23505": 1062, // Unique violation → Duplicate entry
	"23514": 3819, // Check violation → Check constraint violation
	"23502": 1048, // Not null violation → Column cannot be null

	// Concurrency/Lock errors
	"40P01": 1213, // Deadlock → Deadlock detected
	"40001": 1213, // Serialization failure → Deadlock detected
	"55P03": 3058, // Lock not available → Timeout acquiring lock

	// Data type errors
	"22000": 1366, // Invalid binary data → Incorrect string value
	"22003": 1264, // Numeric value out of range → Out of range value
	"22007": 1292, // Invalid datetime format → Incorrect datetime value
	"22P02": 1366, // Invalid text representation → Incorrect string value

	// Division/Math errors
	"22012": 1365, // Division by zero

	// Access errors
	"42501": 1142, // Insufficient privilege → Select command denied
	"28000": 1045, // Invalid password → Access denied

	// Parsing/Syntax errors
	"42601": 1064, // Syntax error → SQL syntax error
	"42602": 1064, // Syntax error → SQL syntax error
	"42605": 1305, // Undefined function → Function not found

	// Type errors
	"42804": 1365, // Type mismatch → Illegal mix of collations
	"42883": 1064, // Function not found → SQL syntax error

	// Catalog/Schema errors
	"3D000": 1049, // Invalid catalog name → Unknown database

	// Foreign key errors
	"23503": 1452, // Foreign key violation → Cannot add or update a child row
	"23506": 1451, // Foreign key violation → Cannot delete or update a parent row

	// General errors
	"XX000": 1105, // Internal error → Unknown error
	"XX001": 1105, // Data corrupted → Unknown error
}

// IsDuplicateKeyError checks if error is a duplicate key error (MySQL 1062 or PostgreSQL 23505)
func IsDuplicateKeyError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// MySQL: "Error 1062: Duplicate entry 'xyz' for key 'primary'"
	if strings.Contains(errStr, "1062") || strings.Contains(errStr, "Duplicate entry") {
		return true
	}

	// PostgreSQL compatibility: Check for 23505
	if strings.Contains(errStr, "23505") || strings.Contains(errStr, "unique constraint") {
		return true
	}

	return false
}

// IsDeadlockError checks if error is a deadlock error (MySQL 1213 or PostgreSQL 40P01)
func IsDeadlockError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// MySQL: "Error 1213: Deadlock found when trying to get lock"
	if strings.Contains(errStr, "1213") || strings.Contains(errStr, "Deadlock found") {
		return true
	}

	// PostgreSQL compatibility
	if strings.Contains(errStr, "40P01") || strings.Contains(errStr, "deadlock") {
		return true
	}

	return false
}

// IsUndefinedColumnError checks if error is an undefined column error (MySQL 1054 or PostgreSQL 42703)
func IsUndefinedColumnError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// MySQL: "Error 1054: Unknown column 'xyz' in 'field list'"
	if strings.Contains(errStr, "1054") || strings.Contains(errStr, "Unknown column") {
		return true
	}

	// PostgreSQL compatibility: 42703 = undefined column
	if strings.Contains(errStr, "42703") {
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
