package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// UserRepository handles all user-related database operations with pure SQL
type UserRepository struct {
	db       SQLRunner
	dbDriver string
}

// WithTx returns a copy of the repository that executes within tx.
func (r *UserRepository) WithTx(tx *sql.Tx) *UserRepository {
	return &UserRepository{db: tx, dbDriver: r.dbDriver}
}

// NewUserRepository creates a new user repository
func NewUserRepository(db *sql.DB) *UserRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}
	return &UserRepository{db: db, dbDriver: driver}
}

func (r *UserRepository) bindQuery(query string) string {
	return bindPlaceholders(r.dbDriver, query)
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

func (r *UserRepository) hasRoleColumn() bool {
	return r.hasUserColumn("role")
}

func (r *UserRepository) hasAvatarColumn() bool {
	return r.hasUserColumn("avatar")
}

func (r *UserRepository) hasLastLoginColumn() bool {
	return r.hasUserColumn("last_login")
}

func (r *UserRepository) hasUserColumn(columnName string) bool {
	columns, err := cachedTableColumns(r.db, "users")
	if err != nil {
		return false
	}
	_, ok := columns[strings.ToLower(strings.TrimSpace(columnName))]
	return ok
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

	roleExpr := "CASE WHEN is_admin THEN 'admin' ELSE 'client' END"
	if r.hasRoleColumn() {
		roleExpr = "COALESCE(role, CASE WHEN is_admin THEN 'admin' ELSE 'client' END)"
	}

	avatarExpr := "''"
	if r.hasAvatarColumn() {
		avatarExpr = "avatar"
	}

	lastLoginExpr := "NULL"
	if r.hasLastLoginColumn() {
		lastLoginExpr = "last_login"
	}

	return fmt.Sprintf(
		`id, username, email, %s, %s, %s, %s, full_name, %s, hashed_password, is_active, is_admin, %s, %s, %s, created_at, updated_at`,
		roleExpr,
		maxActiveBacktestsExpr,
		maxStrategiesExpr,
		maxBotInstancesExpr,
		avatarExpr,
		mfaEnabledExpr,
		passwordChangeExpr,
		lastLoginExpr,
	)
}

// Create inserts a new user
func (r *UserRepository) Create(user *models.User) error {
	user.Role = models.NormalizeUserRole(user.Role, user.IsAdmin)
	now := time.Now()

	columns := []string{
		"username",
		"email",
		"full_name",
		"hashed_password",
		"is_active",
		"is_admin",
	}
	args := []interface{}{
		user.Username,
		user.Email,
		user.FullName,
		user.Password,
		user.IsActive,
		user.IsAdmin,
	}

	if r.hasAvatarColumn() {
		columns = append(columns, "avatar")
		args = append(args, user.Avatar)
	}

	if r.hasRoleColumn() {
		columns = append(columns, "role")
		args = append(args, user.Role)
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

	if r.hasLastLoginColumn() {
		columns = append(columns, "last_login")
		args = append(args, user.LastLogin)
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
		RETURNING id
	`, strings.Join(columns, ", "), strings.Join(placeholders, ", "))

	if err := r.db.QueryRow(r.bindQuery(query), args...).Scan(&user.ID); err != nil {
		return fmt.Errorf("failed to create user: %w", err)
	}
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
	err := r.db.QueryRow(r.bindQuery(query), id).Scan(
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
	err := r.db.QueryRow(r.bindQuery(query), username).Scan(
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
	err := r.db.QueryRow(r.bindQuery(query), email).Scan(
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

	rows, err := r.db.Query(r.bindQuery(query), limit, offset)
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
		return "?"
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
		if r.hasRoleColumn() {
			where = append(where, fmt.Sprintf(`LOWER(COALESCE(role, 'client')) = %s`, nextArg(models.NormalizeUserRole(role, false))))
		} else {
			// Filter by is_admin when role column doesn't exist
			normalizedRole := models.NormalizeUserRole(role, false)
			if normalizedRole == "admin" {
				where = append(where, fmt.Sprintf(`is_admin = TRUE`))
			} else {
				where = append(where, fmt.Sprintf(`is_admin = FALSE`))
			}
		}
	}
	if filters.Active != nil {
		where = append(where, fmt.Sprintf(`is_active = %s`, nextArg(*filters.Active)))
	}

	whereSQL := strings.Join(where, " AND ")
	var total int
	countQuery := fmt.Sprintf(`SELECT COUNT(*) FROM users WHERE %s`, whereSQL)
	if err := r.db.QueryRow(r.bindQuery(countQuery), args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("failed to count filtered users: %w", err)
	}

	queryArgs := append([]interface{}{}, args...)
	queryArgs = append(queryArgs, limit, offset)
	query := fmt.Sprintf(`
		SELECT %s
		FROM users
		WHERE %s
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`, r.selectUserColumns(), whereSQL)

	rows, err := r.db.Query(r.bindQuery(query), queryArgs...)
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
	roleCondition := "is_admin = TRUE"
	if r.hasRoleColumn() {
		roleCondition = "(is_admin = TRUE OR COALESCE(role, '') = 'admin')"
	}

	query := fmt.Sprintf(`
		SELECT COUNT(*)
		FROM users
		WHERE is_active = TRUE
		  AND %s
	`, roleCondition)

	var count int
	if err := r.db.QueryRow(r.bindQuery(query)).Scan(&count); err != nil {
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
		user.FullName,
		user.Password,
		user.IsActive,
		user.IsAdmin,
	}
	setClauses := []string{
		"username = ?",
		"email = ?",
		"full_name = ?",
		"hashed_password = ?",
		"is_active = ?",
		"is_admin = ?",
	}

	if r.hasAvatarColumn() {
		args = append(args, user.Avatar)
		setClauses = append(setClauses, "avatar = ?")
	}

	if r.hasRoleColumn() {
		args = append(args, user.Role)
		setClauses = append(setClauses, "role = ?")
	}

	if r.hasPasswordChangeRequiredColumn() {
		args = append(args, user.PasswordChangeRequired)
		setClauses = append(setClauses, "password_change_required = ?")
	}
	if r.hasMaxActiveBacktestsColumn() {
		if user.MaxActiveBacktests <= 0 {
			user.MaxActiveBacktests = 10
		}
		args = append(args, user.MaxActiveBacktests)
		setClauses = append(setClauses, "max_active_backtests = ?")
	}
	if r.hasMaxStrategiesColumn() {
		if user.MaxStrategies <= 0 {
			user.MaxStrategies = 10
		}
		args = append(args, user.MaxStrategies)
		setClauses = append(setClauses, "max_strategies = ?")
	}
	if r.hasMaxBotInstancesColumn() {
		if user.MaxBotInstances <= 0 {
			user.MaxBotInstances = 10
		}
		args = append(args, user.MaxBotInstances)
		setClauses = append(setClauses, "max_bot_instances = ?")
	}

	if r.hasLastLoginColumn() {
		args = append(args, user.LastLogin)
		setClauses = append(setClauses, "last_login = ?")
	}

	args = append(args, now)
	setClauses = append(setClauses, "updated_at = ?")
	args = append(args, user.ID)

	query := fmt.Sprintf(`
		UPDATE users
		SET %s
		WHERE id = ?
	`, strings.Join(setClauses, ", "))

	result, err := r.db.Exec(r.bindQuery(query), args...)

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

	result, err := r.db.Exec(r.bindQuery(query), id)
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
	if !r.hasLastLoginColumn() {
		return nil
	}
	query := "UPDATE users SET last_login = ? WHERE id = ?"

	now := time.Now()
	result, err := r.db.Exec(r.bindQuery(query), now, id)
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
	result, err := r.db.Exec(r.bindQuery(`UPDATE users SET mfa_enabled = ?, updated_at = ? WHERE id = ?`), enabled, time.Now(), id)
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
	err := r.db.QueryRow(r.bindQuery(query)).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count users: %w", err)
	}

	return count, nil
}
