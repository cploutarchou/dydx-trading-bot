package repository

import (
	"database/sql"
	"fmt"
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
