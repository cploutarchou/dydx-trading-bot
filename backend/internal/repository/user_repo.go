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
	return r.hasUserColumn("password_change_required")
}

func (r *UserRepository) hasMFAEnabledColumn() bool {
	return r.hasUserColumn("mfa_enabled")
}

func (r *UserRepository) SupportsMFA() bool {
	return r.hasMFAEnabledColumn()
}

func (r *UserRepository) hasUserColumn(columnName string) bool {
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
		if strings.EqualFold(column, columnName) {
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
	mfaEnabledExpr := "FALSE"
	if r.hasMFAEnabledColumn() {
		mfaEnabledExpr = "COALESCE(mfa_enabled, FALSE)"
	}

	return fmt.Sprintf(
		`id, username, email, COALESCE(role, CASE WHEN is_admin THEN 'admin' ELSE 'client' END), full_name, avatar, hashed_password, is_active, is_admin, %s, %s, last_login, created_at, updated_at`,
		mfaEnabledExpr,
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
		&user.MFAEnabled,
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
		&user.MFAEnabled,
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
		&user.MFAEnabled,
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
			&user.MFAEnabled,
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

type UserListFilters struct {
	Search string
	Role   string
	Active *bool
	Limit  int
	Offset int
}

// ListFiltered retrieves users with simple CRM/backoffice search and filters.
func (r *UserRepository) ListFiltered(filters UserListFilters) ([]*models.User, int, error) {
	limit := filters.Limit
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	offset := filters.Offset
	if offset < 0 {
		offset = 0
	}

	where := []string{"1=1"}
	args := []interface{}{}
	nextArg := func(value interface{}) string {
		args = append(args, value)
		return fmt.Sprintf("$%d", len(args))
	}

	if search := strings.TrimSpace(strings.ToLower(filters.Search)); search != "" {
		placeholder := nextArg("%" + search + "%")
		where = append(where, fmt.Sprintf(
			`(LOWER(username) LIKE %s OR LOWER(email) LIKE %s OR LOWER(COALESCE(full_name, '')) LIKE %s)`,
			placeholder,
			placeholder,
			placeholder,
		))
	}
	if role := strings.TrimSpace(strings.ToLower(filters.Role)); role != "" && role != "all" {
		where = append(where, fmt.Sprintf(`LOWER(COALESCE(role, 'client')) = %s`, nextArg(models.NormalizeUserRole(role, false))))
	}
	if filters.Active != nil {
		where = append(where, fmt.Sprintf(`is_active = %s`, nextArg(*filters.Active)))
	}

	whereSQL := strings.Join(where, " AND ")
	var total int
	countQuery := fmt.Sprintf(`SELECT COUNT(*) FROM users WHERE %s`, whereSQL)
	if err := r.db.QueryRow(countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("failed to count filtered users: %w", err)
	}

	queryArgs := append([]interface{}{}, args...)
	queryArgs = append(queryArgs, limit, offset)
	query := fmt.Sprintf(`
		SELECT %s
		FROM users
		WHERE %s
		ORDER BY created_at DESC
		LIMIT $%d OFFSET $%d
	`, r.selectUserColumns(), whereSQL, len(queryArgs)-1, len(queryArgs))

	rows, err := r.db.Query(query, queryArgs...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list filtered users: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close filtered user rows: %v", closeErr)
		}
	}()

	users := []*models.User{}
	for rows.Next() {
		user := &models.User{}
		if err := rows.Scan(
			&user.ID,
			&user.Username,
			&user.Email,
			&user.Role,
			&user.FullName,
			&user.Avatar,
			&user.Password,
			&user.IsActive,
			&user.IsAdmin,
			&user.MFAEnabled,
			&user.PasswordChangeRequired,
			&user.LastLogin,
			&user.CreatedAt,
			&user.UpdatedAt,
		); err != nil {
			return nil, 0, fmt.Errorf("failed to scan filtered user: %w", err)
		}
		users = append(users, user)
	}

	return users, total, rows.Err()
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

func (r *UserRepository) SetMFAEnabled(id int, enabled bool) error {
	if !r.hasMFAEnabledColumn() {
		return nil
	}
	result, err := r.db.Exec(`UPDATE users SET mfa_enabled = $1, updated_at = $2 WHERE id = $3`, enabled, time.Now(), id)
	if err != nil {
		return fmt.Errorf("failed to update mfa_enabled: %w", err)
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
