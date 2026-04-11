package services

import (
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type RBACService struct {
	repo *repository.RBACRepository
}

func NewRBACService(repo *repository.RBACRepository) *RBACService {
	return &RBACService{repo: repo}
}

var fallbackPermissionsByRole = map[string]map[string]struct{}{
	"admin": {
		"crm.read":             {},
		"crm.write":            {},
		"users.read":           {},
		"users.update":         {},
		"users.disable":        {},
		"kyc.read":             {},
		"kyc.review":           {},
		"finance.read":         {},
		"finance.manage":       {},
		"audit.read":           {},
		"security.events.read": {},
		"roles.manage":         {},
		"crm.admin.manage":     {},
	},
	"super_admin": {
		"crm.read":             {},
		"crm.write":            {},
		"users.read":           {},
		"users.update":         {},
		"users.disable":        {},
		"kyc.read":             {},
		"kyc.review":           {},
		"finance.read":         {},
		"finance.manage":       {},
		"audit.read":           {},
		"security.events.read": {},
		"roles.manage":         {},
		"crm.admin.manage":     {},
	},
	"backoffice": {
		"crm.read":             {},
		"crm.admin.manage":     {},
		"users.read":           {},
		"users.update":         {},
		"kyc.read":             {},
		"kyc.review":           {},
		"audit.read":           {},
		"security.events.read": {},
	},
	"operations_admin": {
		"crm.read":             {},
		"users.read":           {},
		"users.update":         {},
		"kyc.read":             {},
		"kyc.review":           {},
		"audit.read":           {},
		"security.events.read": {},
	},
	"compliance_admin": {
		"crm.read":             {},
		"users.read":           {},
		"kyc.read":             {},
		"kyc.review":           {},
		"audit.read":           {},
		"security.events.read": {},
	},
	"support_agent": {
		"crm.read":     {},
		"users.read":   {},
		"users.update": {},
		"kyc.read":     {},
	},
	"finance_admin": {
		"crm.read":       {},
		"users.read":     {},
		"finance.read":   {},
		"finance.manage": {},
		"audit.read":     {},
	},
	"read_only_auditor": {
		"crm.read":             {},
		"users.read":           {},
		"kyc.read":             {},
		"finance.read":         {},
		"audit.read":           {},
		"security.events.read": {},
	},
	"security_analyst": {
		"crm.read":             {},
		"users.read":           {},
		"audit.read":           {},
		"security.events.read": {},
	},
}

func (s *RBACService) HasPermission(userID int, role, permissionKey string) (bool, error) {
	permissionKey = strings.TrimSpace(strings.ToLower(permissionKey))
	if permissionKey == "" {
		return false, nil
	}

	normalizedRole := models.NormalizeUserRole(role, role == "admin" || role == "super_admin")
	normalizedRole = strings.TrimSpace(strings.ToLower(normalizedRole))

	override, err := s.repo.GetUserPermissionOverride(userID, permissionKey)
	if err != nil {
		return false, err
	}
	if override == "deny" {
		return false, nil
	}
	if override == "allow" {
		return true, nil
	}

	hasRoleMappings, err := s.repo.RoleHasAnyPermissions(normalizedRole)
	if err != nil {
		return false, err
	}
	if hasRoleMappings {
		allowed, roleErr := s.repo.RoleHasPermission(normalizedRole, permissionKey)
		if roleErr != nil {
			return false, roleErr
		}
		return allowed, nil
	}

	fallback, ok := fallbackPermissionsByRole[normalizedRole]
	if !ok {
		return false, nil
	}
	_, allowed := fallback[permissionKey]
	return allowed, nil
}
