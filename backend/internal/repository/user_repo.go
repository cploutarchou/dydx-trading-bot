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

func (r *UserRepository) hasMaxActiveBacktestsColumn() bool {
	return r.hasUserColumn("max_active_backtests")
}

func (r *UserRepository) hasMaxStrategiesColumn() bool {
	return r.hasUserColumn("max_strategies")
}

func (r *UserRepository) hasMaxBotInstancesColumn() bool {
	return r.hasUserColumn("max_bot_instances")
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
	maxActiveBacktestsExpr := "10"
	if r.hasMaxActiveBacktestsColumn() {
		maxActiveBacktestsExpr = "COALESCE(max_active_backtests, 10)"
	}
	maxStrategiesExpr := "10"
	if r.hasMaxStrategiesColumn() {
		maxStrategiesExpr = "COALESCE(max_strategies, 10)"
	}
	maxBotInstancesExpr := "10"
	if r.hasMaxBotInstancesColumn() {
		maxBotInstancesExpr = "COALESCE(max_bot_instances, 10)"
	}

	return fmt.Sprintf(
		`id, username, email, COALESCE(role, CASE WHEN is_admin THEN 'admin' ELSE 'client' END), %s, %s, %s, full_name, avatar, hashed_password, is_active, is_admin, %s, %s, last_login, created_at, updated_at`,
		maxActiveBacktestsExpr,
		maxStrategiesExpr,
		maxBotInstancesExpr,
		mfaEnabledExpr,
		passwordChangeExpr,
	)
}

// Create inserts a new user
func (r *UserRepository) Create(user *models.User) error {
	user.Role = models.NormalizeUserRole(user.Role, user.IsAdmin)
	now := time.Now()

	columns := []string{
		"username",
		"email",
		"role",
		"full_name",
		"avatar",
		"hashed_password",
		"is_active",
		"is_admin",
	}
	args := []interface{}{
		user.Username,
		user.Email,
		user.Role,
		user.FullName,
		user.Avatar,
		user.Password,
		user.IsActive,
		user.IsAdmin,
	}

	if r.hasPasswordChangeRequiredColumn() {
		columns = append(columns, "password_change_required")
		args = append(args, user.PasswordChangeRequired)
	}
	if r.hasMaxActiveBacktestsColumn() {
		if user.MaxActiveBacktests <= 0 {
			user.MaxActiveBacktests = 10
		}
		columns = append(columns, "max_active_backtests")
		args = append(args, user.MaxActiveBacktests)
	}
	if r.hasMaxStrategiesColumn() {
		if user.MaxStrategies <= 0 {
			user.MaxStrategies = 10
		}
		columns = append(columns, "max_strategies")
		args = append(args, user.MaxStrategies)
	}
	if r.hasMaxBotInstancesColumn() {
		if user.MaxBotInstances <= 0 {
			user.MaxBotInstances = 10
		}
		columns = append(columns, "max_bot_instances")
		args = append(args, user.MaxBotInstances)
	}

	columns = append(columns, "created_at", "updated_at")
	args = append(args, now, now)

	placeholders := make([]string, len(args))
	for i := range args {
		placeholders[i] = "?"
	}

	query := fmt.Sprintf(`
		INSERT INTO users (%s)
		VALUES (%s)
	`, strings.Join(columns, ", "), strings.Join(placeholders, ", "))

	result, err := r.db.Exec(query, args...)

	if err != nil {
		return fmt.Errorf("failed to create user: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}

	user.ID = int(lastID)
	user.CreatedAt = now
	user.UpdatedAt = now

	return nil
}

// GetByID retrieves a user by ID
func (r *UserRepository) GetByID(id int) (*models.User, error) {
	query := fmt.Sprintf(`
		SELECT %s
		FROM users
		WHERE id = ?
	`, r.selectUserColumns())

	user := &models.User{}
	err := r.db.QueryRow(query, id).Scan(
		&user.ID,
		&user.Username,
		&user.Email,
		&user.Role,
		&user.MaxActiveBacktests,
		&user.MaxStrategies,
		&user.MaxBotInstances,
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
		WHERE username = ?
	`, r.selectUserColumns())

	user := &models.User{}
	err := r.db.QueryRow(query, username).Scan(
		&user.ID,
		&user.Username,
		&user.Email,
		&user.Role,
		&user.MaxActiveBacktests,
		&user.MaxStrategies,
		&user.MaxBotInstances,
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
		WHERE email = ?
	`, r.selectUserColumns())

	user := &models.User{}
	err := r.db.QueryRow(query, email).Scan(
		&user.ID,
		&user.Username,
		&user.Email,
		&user.Role,
		&user.MaxActiveBacktests,
		&user.MaxStrategies,
		&user.MaxBotInstances,
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
		LIMIT ? OFFSET ?
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
			&user.MaxActiveBacktests,
			&user.MaxStrategies,
			&user.MaxBotInstances,
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
			&user.MaxActiveBacktests,
			&user.MaxStrategies,
			&user.MaxBotInstances,
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

	args := []interface{}{
		user.Username,
		user.Email,
		user.Role,
		user.FullName,
		user.Avatar,
		user.Password,
		user.IsActive,
		user.IsAdmin,
	}
	setClauses := []string{
		"username = ?",
		"email = ?",
		"role = ?",
		"full_name = ?",
		"avatar = ?",
		"hashed_password = ?",
		"is_active = ?",
		"is_admin = ?",
	}

	if r.hasPasswordChangeRequiredColumn() {
		args = append(args, user.PasswordChangeRequired)
		setClauses = append(setClauses, fmt.Sprintf("password_change_required = $%d", len(args)))
	}
	if r.hasMaxActiveBacktestsColumn() {
		if user.MaxActiveBacktests <= 0 {
			user.MaxActiveBacktests = 10
		}
		args = append(args, user.MaxActiveBacktests)
		setClauses = append(setClauses, fmt.Sprintf("max_active_backtests = $%d", len(args)))
	}
	if r.hasMaxStrategiesColumn() {
		if user.MaxStrategies <= 0 {
			user.MaxStrategies = 10
		}
		args = append(args, user.MaxStrategies)
		setClauses = append(setClauses, fmt.Sprintf("max_strategies = $%d", len(args)))
	}
	if r.hasMaxBotInstancesColumn() {
		if user.MaxBotInstances <= 0 {
			user.MaxBotInstances = 10
		}
		args = append(args, user.MaxBotInstances)
		setClauses = append(setClauses, fmt.Sprintf("max_bot_instances = $%d", len(args)))
	}

	args = append(args, user.LastLogin)
	setClauses = append(setClauses, fmt.Sprintf("last_login = $%d", len(args)))
	args = append(args, now)
	setClauses = append(setClauses, fmt.Sprintf("updated_at = $%d", len(args)))
	args = append(args, user.ID)

	query := fmt.Sprintf(`
		UPDATE users
		SET %s
		WHERE id = $%d
	`, strings.Join(setClauses, ", "), len(args))

	result, err := r.db.Exec(query, args...)

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
	query := "DELETE FROM users WHERE id = ?"

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
	query := "UPDATE users SET last_login = ? WHERE id = ?"

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
	result, err := r.db.Exec(`UPDATE users SET mfa_enabled = ?, updated_at = ? WHERE id = ?`, enabled, time.Now(), id)
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
