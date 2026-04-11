package models

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"
)

var validUserRoles = []string{
	"admin",
	"super_admin",
	"backoffice",
	"operations_admin",
	"compliance_admin",
	"support_agent",
	"finance_admin",
	"read_only_auditor",
	"security_analyst",
	"ib",
	"sub_ib",
	"user",
	"accounting",
	"marketing",
	"agent",
	"client",
}

// ============ User Methods ============

// SetPassword hashes and stores the password
func (u *User) SetPassword(password string) error {
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return err
	}
	u.Password = string(hashedPassword)
	return nil
}

// CheckPassword verifies the provided password against the stored hash
func (u *User) CheckPassword(password string) bool {
	if u.Password == "" {
		return false
	}
	err := bcrypt.CompareHashAndPassword([]byte(u.Password), []byte(password))
	return err == nil
}

// ToDict converts User to dictionary
func (u *User) ToDict() map[string]interface{} {
	createdAtStr := ""
	if !u.CreatedAt.IsZero() {
		createdAtStr = u.CreatedAt.Format(time.RFC3339)
	}

	updatedAtStr := ""
	if !u.UpdatedAt.IsZero() {
		updatedAtStr = u.UpdatedAt.Format(time.RFC3339)
	}

	lastLoginStr := ""
	if u.LastLogin != nil && !u.LastLogin.IsZero() {
		lastLoginStr = u.LastLogin.Format(time.RFC3339)
	}

	return map[string]interface{}{
		"id":                       u.ID,
		"username":                 u.Username,
		"email":                    u.Email,
		"role":                     u.Role,
		"full_name":                u.FullName,
		"avatar":                   u.Avatar,
		"is_active":                u.IsActive,
		"is_admin":                 u.IsAdmin,
		"mfa_enabled":              u.MFAEnabled,
		"password_change_required": u.PasswordChangeRequired,
		"created_at":               createdAtStr,
		"updated_at":               updatedAtStr,
		"last_login":               lastLoginStr,
		"hashed_password":          u.Password,
	}
}

// ToPublicDict converts User to dictionary without sensitive fields
func (u *User) ToPublicDict() map[string]interface{} {
	d := u.ToDict()
	delete(d, "hashed_password")
	delete(d, "is_admin")
	return d
}

// FromDict populates User from a dictionary
func (u *User) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		u.ID = int(id)
	}
	if username, ok := data["username"].(string); ok {
		u.Username = username
	}
	if email, ok := data["email"].(string); ok {
		u.Email = email
	}
	if role, ok := data["role"].(string); ok {
		u.Role = role
	}
	if fullName, ok := data["full_name"].(string); ok {
		u.FullName = fullName
	}
	if avatar, ok := data["avatar"].(string); ok {
		u.Avatar = avatar
	}
	if isActive, ok := data["is_active"].(bool); ok {
		u.IsActive = isActive
	}
	if isAdmin, ok := data["is_admin"].(bool); ok {
		u.IsAdmin = isAdmin
	}
	if mfaEnabled, ok := data["mfa_enabled"].(bool); ok {
		u.MFAEnabled = mfaEnabled
	}
	if passwordChangeRequired, ok := data["password_change_required"].(bool); ok {
		u.PasswordChangeRequired = passwordChangeRequired
	}
	if hashedPassword, ok := data["hashed_password"].(string); ok {
		u.Password = hashedPassword
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			u.CreatedAt = t
		}
	}
	if updatedAt, ok := data["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			u.UpdatedAt = t
		}
	}
	if lastLogin, ok := data["last_login"].(string); ok {
		if t, err := time.Parse(time.RFC3339, lastLogin); err == nil {
			u.LastLogin = &t
		}
	}
}

func NormalizeUserRole(role string, isAdmin bool) string {
	role = strings.TrimSpace(strings.ToLower(role))
	if role == "super-admin" {
		role = "super_admin"
	}
	if role == "operations-admin" {
		role = "operations_admin"
	}
	if role == "compliance-admin" {
		role = "compliance_admin"
	}
	if role == "support-agent" {
		role = "support_agent"
	}
	if role == "finance-admin" {
		role = "finance_admin"
	}
	if role == "read-only-auditor" {
		role = "read_only_auditor"
	}
	if role == "security-analyst" {
		role = "security_analyst"
	}
	validRoles := map[string]struct{}{}
	for _, validRole := range validUserRoles {
		validRoles[validRole] = struct{}{}
	}
	if role == "" {
		if isAdmin {
			return "admin"
		}
		return "client"
	}
	if _, ok := validRoles[role]; ok {
		return role
	}
	if isAdmin {
		return "admin"
	}
	return "client"
}

func AvailableUserRoles() []string {
	roles := make([]string, len(validUserRoles))
	copy(roles, validUserRoles)
	return roles
}

func IsMFAMandatoryRole(role string) bool {
	switch NormalizeUserRole(role, role == "admin" || role == "super_admin") {
	case "admin", "super_admin", "backoffice", "operations_admin", "compliance_admin", "support_agent", "finance_admin", "read_only_auditor", "security_analyst":
		return true
	default:
		return false
	}
}

// ToJSON converts User to JSON bytes
func (u *User) ToJSON() ([]byte, error) {
	return json.Marshal(u.ToDict())
}

// FromJSON populates User from JSON bytes
func (u *User) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	u.FromDict(dict)
	return nil
}

// String representation
func (u *User) String() string {
	return "<User " + u.Username + ">"
}

// ============ AuditLog Methods ============

// ToDict converts AuditLog to dictionary
func (a *AuditLog) ToDict() map[string]interface{} {
	createdAtStr := ""
	if a.CreatedAt != nil && !a.CreatedAt.IsZero() {
		createdAtStr = a.CreatedAt.Format(time.RFC3339)
	}

	return map[string]interface{}{
		"id":            a.ID,
		"user_id":       a.UserID,
		"action":        a.Action,
		"resource_type": a.ResourceType,
		"resource_id":   a.ResourceID,
		"details":       a.Details,
		"status":        a.Status,
		"ip_address":    a.IPAddress,
		"created_at":    createdAtStr,
	}
}

// FromDict populates AuditLog from a dictionary
func (a *AuditLog) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		a.ID = int(id)
	}
	if userID, ok := data["user_id"].(float64); ok {
		uid := int(userID)
		a.UserID = &uid
	}
	if action, ok := data["action"].(string); ok {
		a.Action = action
	}
	if resourceType, ok := data["resource_type"].(string); ok {
		a.ResourceType = resourceType
	}
	if resourceID, ok := data["resource_id"].(string); ok {
		a.ResourceID = &resourceID
	}
	if details, ok := data["details"]; ok {
		a.Details = details
	}
	if status, ok := data["status"].(string); ok {
		a.Status = &status
	}
	if ipAddress, ok := data["ip_address"].(string); ok {
		a.IPAddress = &ipAddress
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			a.CreatedAt = &t
		}
	}
}

// ToJSON converts AuditLog to JSON bytes
func (a *AuditLog) ToJSON() ([]byte, error) {
	return json.Marshal(a.ToDict())
}

// FromJSON populates AuditLog from JSON bytes
func (a *AuditLog) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	a.FromDict(dict)
	return nil
}

// String representation
func (a *AuditLog) String() string {
	userIDStr := "nil"
	if a.UserID != nil {
		userIDStr = fmt.Sprintf("%d", *a.UserID)
	}
	return "<AuditLog action=" + a.Action + " user_id=" + userIDStr + ">"
}
