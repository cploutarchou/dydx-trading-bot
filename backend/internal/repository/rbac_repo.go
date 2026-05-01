package repository

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
)

// RBACRepository handles persistence-backed RBAC lookups.
type RBACRepository struct {
	db *sql.DB
}

func NewRBACRepository(db *sql.DB) *RBACRepository {
	return &RBACRepository{db: db}
}

func isRBACSchemaMissing(err error) bool {
	if err == nil {
		return false
	}
	lower := strings.ToLower(err.Error())
	return strings.Contains(lower, "does not exist") || strings.Contains(lower, "no such table")
}

// GetUserPermissionOverride returns one of: "allow", "deny", "" (not found).
func (r *RBACRepository) GetUserPermissionOverride(userID int, permissionKey string) (string, error) {
	if userID <= 0 || strings.TrimSpace(permissionKey) == "" {
		return "", nil
	}

	var effect string
	err := r.db.QueryRow(
		`SELECT effect FROM user_permission_overrides WHERE user_id = $1 AND permission_key = $2 LIMIT 1`,
		userID,
		permissionKey,
	).Scan(&effect)
	if err == sql.ErrNoRows || isRBACSchemaMissing(err) {
		return "", nil
	}
	if err != nil {
		return "", fmt.Errorf("failed to read user permission override: %w", err)
	}
	return strings.ToLower(strings.TrimSpace(effect)), nil
}

// RoleHasAnyPermissions checks whether the DB has explicit role mappings.
func (r *RBACRepository) RoleHasAnyPermissions(role string) (bool, error) {
	role = strings.TrimSpace(strings.ToLower(role))
	if role == "" {
		return false, nil
	}

	var exists int
	err := r.db.QueryRow(
		`SELECT 1 FROM role_permissions WHERE role = $1 LIMIT 1`,
		role,
	).Scan(&exists)
	if err == sql.ErrNoRows || isRBACSchemaMissing(err) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("failed to inspect role permissions: %w", err)
	}
	return exists == 1, nil
}

// RoleHasPermission checks whether role has an explicit DB mapping for permission.
func (r *RBACRepository) RoleHasPermission(role, permissionKey string) (bool, error) {
	role = strings.TrimSpace(strings.ToLower(role))
	permissionKey = strings.TrimSpace(strings.ToLower(permissionKey))
	if role == "" || permissionKey == "" {
		return false, nil
	}

	var exists int
	err := r.db.QueryRow(
		`SELECT 1 FROM role_permissions WHERE role = $1 AND permission_key = $2 LIMIT 1`,
		role,
		permissionKey,
	).Scan(&exists)
	if err == sql.ErrNoRows || isRBACSchemaMissing(err) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("failed to check role permission: %w", err)
	}
	return exists == 1, nil
}

type RolePermissionRow struct {
	Role          string `json:"role"`
	PermissionKey string `json:"permission_key"`
}

type RoleRow struct {
	Role        string `json:"role"`
	DisplayName string `json:"display_name"`
	Description string `json:"description"`
	IsSystem    bool   `json:"is_system"`
}

type PermissionRow struct {
	PermissionKey string `json:"permission_key"`
	Description   string `json:"description"`
	IsSensitive   bool   `json:"is_sensitive"`
}

func (r *RBACRepository) ListCustomRoles() ([]RoleRow, error) {
	rows, err := r.db.Query(`
		SELECT role, display_name, description, is_system
		FROM custom_roles
		ORDER BY is_system DESC, role ASC
	`)
	if err != nil {
		if isRBACSchemaMissing(err) {
			return []RoleRow{}, nil
		}
		return nil, fmt.Errorf("failed to list custom roles: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close custom role rows: %v", closeErr)
		}
	}()

	roles := []RoleRow{}
	for rows.Next() {
		var role RoleRow
		if err := rows.Scan(&role.Role, &role.DisplayName, &role.Description, &role.IsSystem); err != nil {
			return nil, fmt.Errorf("failed to scan custom role: %w", err)
		}
		roles = append(roles, role)
	}
	return roles, rows.Err()
}

func (r *RBACRepository) UpsertCustomRole(role, displayName, description string) error {
	role = strings.TrimSpace(strings.ToLower(role))
	displayName = strings.TrimSpace(displayName)
	description = strings.TrimSpace(description)
	if role == "" {
		return fmt.Errorf("role is required")
	}
	if displayName == "" {
		displayName = role
	}

	_, err := r.db.Exec(`
		INSERT INTO custom_roles (role, display_name, description, is_system, created_at, updated_at)
		VALUES ($1, $2, $3, FALSE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
		ON CONFLICT (role) DO UPDATE
		SET display_name = EXCLUDED.display_name,
		    description = EXCLUDED.description,
		    updated_at = CURRENT_TIMESTAMP
		WHERE custom_roles.is_system = FALSE
	`, role, displayName, description)
	if err != nil {
		if isRBACSchemaMissing(err) {
			return fmt.Errorf("custom roles schema is not available")
		}
		return fmt.Errorf("failed to save custom role: %w", err)
	}
	return nil
}

func (r *RBACRepository) DeleteCustomRole(role string) error {
	role = strings.TrimSpace(strings.ToLower(role))
	if role == "" {
		return fmt.Errorf("role is required")
	}

	var isSystem bool
	err := r.db.QueryRow(`SELECT is_system FROM custom_roles WHERE role = $1 LIMIT 1`, role).Scan(&isSystem)
	if err == sql.ErrNoRows {
		return nil
	}
	if err != nil {
		if isRBACSchemaMissing(err) {
			return nil
		}
		return fmt.Errorf("failed to inspect custom role: %w", err)
	}
	if isSystem {
		return fmt.Errorf("system roles cannot be deleted")
	}

	var assignedUsers int
	if err := r.db.QueryRow(`SELECT COUNT(*) FROM users WHERE LOWER(COALESCE(role, '')) = $1`, role).Scan(&assignedUsers); err != nil {
		return fmt.Errorf("failed to inspect role assignments: %w", err)
	}
	if assignedUsers > 0 {
		return fmt.Errorf("role is assigned to %d user(s)", assignedUsers)
	}

	if _, err := r.db.Exec(`DELETE FROM custom_roles WHERE role = $1 AND is_system = FALSE`, role); err != nil {
		return fmt.Errorf("failed to delete custom role: %w", err)
	}
	return nil
}

func (r *RBACRepository) ReplaceRolePermissions(role string, permissionKeys []string) error {
	role = strings.TrimSpace(strings.ToLower(role))
	if role == "" {
		return fmt.Errorf("role is required")
	}

	tx, err := r.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to start role permission update: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback()
		}
	}()

	if _, err = tx.Exec(`DELETE FROM role_permissions WHERE role = $1`, role); err != nil {
		return fmt.Errorf("failed to clear role permissions: %w", err)
	}

	seen := map[string]struct{}{}
	for _, permissionKey := range permissionKeys {
		permissionKey = strings.TrimSpace(strings.ToLower(permissionKey))
		if permissionKey == "" {
			continue
		}
		if _, ok := seen[permissionKey]; ok {
			continue
		}
		seen[permissionKey] = struct{}{}
		if _, err = tx.Exec(
			`INSERT INTO role_permissions (role, permission_key, created_at)
			 SELECT $1, permission_key, CURRENT_TIMESTAMP
			 FROM permissions
			 WHERE permission_key = $2
			 ON CONFLICT (role, permission_key) DO NOTHING`,
			role,
			permissionKey,
		); err != nil {
			return fmt.Errorf("failed to add role permission %s: %w", permissionKey, err)
		}
	}

	if err = tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit role permission update: %w", err)
	}
	return nil
}

func (r *RBACRepository) ListPermissions() ([]PermissionRow, error) {
	rows, err := r.db.Query(`SELECT permission_key, description, is_sensitive FROM permissions ORDER BY permission_key ASC`)
	if err != nil {
		if isRBACSchemaMissing(err) {
			return []PermissionRow{}, nil
		}
		return nil, fmt.Errorf("failed to list permissions: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close permissions rows: %v", closeErr)
		}
	}()

	permissions := []PermissionRow{}
	for rows.Next() {
		var permission PermissionRow
		if err := rows.Scan(&permission.PermissionKey, &permission.Description, &permission.IsSensitive); err != nil {
			return nil, fmt.Errorf("failed to scan permission: %w", err)
		}
		permissions = append(permissions, permission)
	}
	return permissions, rows.Err()
}

func (r *RBACRepository) ListRolePermissions() ([]RolePermissionRow, error) {
	rows, err := r.db.Query(`SELECT role, permission_key FROM role_permissions ORDER BY role ASC, permission_key ASC`)
	if err != nil {
		if isRBACSchemaMissing(err) {
			return []RolePermissionRow{}, nil
		}
		return nil, fmt.Errorf("failed to list role permissions: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close role permission rows: %v", closeErr)
		}
	}()

	rolePermissions := []RolePermissionRow{}
	for rows.Next() {
		var row RolePermissionRow
		if err := rows.Scan(&row.Role, &row.PermissionKey); err != nil {
			return nil, fmt.Errorf("failed to scan role permission: %w", err)
		}
		rolePermissions = append(rolePermissions, row)
	}
	return rolePermissions, rows.Err()
}
