package repository

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// UserRepository handles all user-related database operations with pure SQL
type UserRepository struct {
	db *sql.DB
}

// NewUserRepository creates a new user repository
func NewUserRepository(db *sql.DB) *UserRepository {
	return &UserRepository{db: db}
}

func (r *UserRepository) hasPasswordChangeRequiredColumn() bool {
	rows, err := r.db.Query(`SELECT * FROM users LIMIT 0`)
	if err != nil {
		return false
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close user schema rows: %v", closeErr)
		}
	}()

	columns, err := rows.Columns()
	if err != nil {
		return false
	}
	if err := rows.Err(); err != nil {
		return false
	}

	for _, column := range columns {
		if strings.EqualFold(column, "password_change_required") {
			return true
		}
	}

	return false
}

func (r *UserRepository) selectUserColumns() string {
	passwordChangeExpr := "FALSE"
	if r.hasPasswordChangeRequiredColumn() {
		passwordChangeExpr = "COALESCE(password_change_required, FALSE)"
	}

	return fmt.Sprintf(
		`id, username, email, COALESCE(role, CASE WHEN is_admin THEN 'admin' ELSE 'client' END), full_name, avatar, hashed_password, is_active, is_admin, %s, last_login, created_at, updated_at`,
		passwordChangeExpr,
	)
}

// Create inserts a new user
func (r *UserRepository) Create(user *models.User) error {
	user.Role = models.NormalizeUserRole(user.Role, user.IsAdmin)
	now := time.Now()
	var err error

	if r.hasPasswordChangeRequiredColumn() {
		query := `
			INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, password_change_required, created_at, updated_at)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
			RETURNING id, created_at, updated_at
		`
		err = r.db.QueryRow(
			query,
			user.Username,
			user.Email,
			user.Role,
			user.FullName,
			user.Avatar,
			user.Password,
			user.IsActive,
			user.IsAdmin,
			user.PasswordChangeRequired,
			now,
			now,
		).Scan(&user.ID, &user.CreatedAt, &user.UpdatedAt)
	} else {
		query := `
			INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, created_at, updated_at)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
			RETURNING id, created_at, updated_at
		`
		err = r.db.QueryRow(
			query,
			user.Username,
			user.Email,
			user.Role,
			user.FullName,
			user.Avatar,
			user.Password,
			user.IsActive,
			user.IsAdmin,
			now,
			now,
		).Scan(&user.ID, &user.CreatedAt, &user.UpdatedAt)
	}

	if err != nil {
		return fmt.Errorf("failed to create user: %w", err)
	}

	return nil
}

// GetByID retrieves a user by ID
func (r *UserRepository) GetByID(id int) (*models.User, error) {
	query := fmt.Sprintf(`
		SELECT %s
		FROM users
		WHERE id = $1
	`, r.selectUserColumns())

	user := &models.User{}
	err := r.db.QueryRow(query, id).Scan(
		&user.ID,
		&user.Username,
		&user.Email,
		&user.Role,
		&user.FullName,
		&user.Avatar,
		&user.Password,
		&user.IsActive,
		&user.IsAdmin,
		&user.PasswordChangeRequired,
		&user.LastLogin,
		&user.CreatedAt,
		&user.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("user not found")
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	return user, nil
}

// GetByUsername retrieves a user by username
func (r *UserRepository) GetByUsername(username string) (*models.User, error) {
	query := fmt.Sprintf(`
		SELECT %s
		FROM users
		WHERE username = $1
	`, r.selectUserColumns())

	user := &models.User{}
	err := r.db.QueryRow(query, username).Scan(
		&user.ID,
		&user.Username,
		&user.Email,
		&user.Role,
		&user.FullName,
		&user.Avatar,
		&user.Password,
		&user.IsActive,
		&user.IsAdmin,
		&user.PasswordChangeRequired,
		&user.LastLogin,
		&user.CreatedAt,
		&user.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("user not found")
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	return user, nil
}

// GetByEmail retrieves a user by email
func (r *UserRepository) GetByEmail(email string) (*models.User, error) {
	query := fmt.Sprintf(`
		SELECT %s
		FROM users
		WHERE email = $1
	`, r.selectUserColumns())

	user := &models.User{}
	err := r.db.QueryRow(query, email).Scan(
		&user.ID,
		&user.Username,
		&user.Email,
		&user.Role,
		&user.FullName,
		&user.Avatar,
		&user.Password,
		&user.IsActive,
		&user.IsAdmin,
		&user.PasswordChangeRequired,
		&user.LastLogin,
		&user.CreatedAt,
		&user.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("user not found")
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	return user, nil
}

// List retrieves all users
func (r *UserRepository) List(limit int, offset int) ([]*models.User, error) {
	query := fmt.Sprintf(`
		SELECT %s
		FROM users
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2
	`, r.selectUserColumns())

	rows, err := r.db.Query(query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list users: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close user rows: %v", closeErr)
		}
	}()

	users := []*models.User{}
	for rows.Next() {
		user := &models.User{}
		err := rows.Scan(
			&user.ID,
			&user.Username,
			&user.Email,
			&user.Role,
			&user.FullName,
			&user.Avatar,
			&user.Password,
			&user.IsActive,
			&user.IsAdmin,
			&user.PasswordChangeRequired,
			&user.LastLogin,
			&user.CreatedAt,
			&user.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan user: %w", err)
		}
		users = append(users, user)
	}

	return users, rows.Err()
}

// CountActiveAdmins returns the number of active admin users.
func (r *UserRepository) CountActiveAdmins() (int, error) {
	query := `
		SELECT COUNT(*)
		FROM users
		WHERE is_active = TRUE
		  AND (is_admin = TRUE OR COALESCE(role, '') = 'admin')
	`

	var count int
	if err := r.db.QueryRow(query).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count active admins: %w", err)
	}

	return count, nil
}

// Update updates an existing user
func (r *UserRepository) Update(user *models.User) error {
	user.Role = models.NormalizeUserRole(user.Role, user.IsAdmin)
	now := time.Now()
	var (
		result sql.Result
		err    error
	)

	if r.hasPasswordChangeRequiredColumn() {
		query := `
			UPDATE users
			SET username = $1, email = $2, role = $3, full_name = $4, avatar = $5, hashed_password = $6,
			    is_active = $7, is_admin = $8, password_change_required = $9, last_login = $10, updated_at = $11
			WHERE id = $12
		`
		result, err = r.db.Exec(
			query,
			user.Username,
			user.Email,
			user.Role,
			user.FullName,
			user.Avatar,
			user.Password,
			user.IsActive,
			user.IsAdmin,
			user.PasswordChangeRequired,
			user.LastLogin,
			now,
			user.ID,
		)
	} else {
		query := `
			UPDATE users
			SET username = $1, email = $2, role = $3, full_name = $4, avatar = $5, hashed_password = $6,
			    is_active = $7, is_admin = $8, last_login = $9, updated_at = $10
			WHERE id = $11
		`
		result, err = r.db.Exec(
			query,
			user.Username,
			user.Email,
			user.Role,
			user.FullName,
			user.Avatar,
			user.Password,
			user.IsActive,
			user.IsAdmin,
			user.LastLogin,
			now,
			user.ID,
		)
	}

	if err != nil {
		return fmt.Errorf("failed to update user: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("user not found")
	}

	user.UpdatedAt = now
	return nil
}

// Delete deletes a user by ID
func (r *UserRepository) Delete(id int) error {
	query := "DELETE FROM users WHERE id = $1"

	result, err := r.db.Exec(query, id)
	if err != nil {
		return fmt.Errorf("failed to delete user: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("user not found")
	}

	return nil
}

// UpdateLastLogin updates the last login time
func (r *UserRepository) UpdateLastLogin(id int) error {
	query := "UPDATE users SET last_login = $1 WHERE id = $2"

	now := time.Now()
	result, err := r.db.Exec(query, now, id)
	if err != nil {
		return fmt.Errorf("failed to update last login: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("user not found")
	}

	return nil
}

// Count returns the total number of users
func (r *UserRepository) Count() (int, error) {
	query := "SELECT COUNT(*) FROM users"

	var count int
	err := r.db.QueryRow(query).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count users: %w", err)
	}

	return count, nil
}
