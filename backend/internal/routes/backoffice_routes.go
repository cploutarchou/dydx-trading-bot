// Package routes provides HTTP route registration and handlers for the dYdX backend API backoffice features.
package routes

import (
	"database/sql"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type registrationPolicyRequest struct {
	Mode           string `json:"mode" binding:"required"`
	InvitationCode string `json:"invitation_code"`
}

func RegisterBackofficeRoutes(router *gin.Engine, database *sql.DB) {
	backoffice := router.Group("/api/v1/backoffice")
	backoffice.Use(middleware.RequireAuth())
	backoffice.Use(middleware.RequireMFA(database))
	{
		backoffice.GET("/users", middleware.RequirePermission(database, "users.read"), listAdminUsersHandler(database))
		backoffice.POST("/users", middleware.RequirePermission(database, "roles.manage"), createAdminUserHandler(database))
		backoffice.GET("/users/:id", middleware.RequirePermission(database, "users.read"), getAdminUserHandler(database))
		backoffice.PUT("/users/:id", middleware.RequirePermission(database, "roles.manage"), updateAdminUserHandler(database))
		backoffice.PUT("/users/:id/role", middleware.RequirePermission(database, "roles.manage"), updateAdminUserRoleHandler(database))
		backoffice.PUT("/users/:id/status", middleware.RequirePermission(database, "users.disable"), updateAdminUserStatusHandler(database))
		backoffice.POST("/users/:id/reset-password", middleware.RequirePermission(database, "roles.manage"), resetAdminUserPasswordHandler(database))
		backoffice.POST("/users/:id/reset-mfa", middleware.RequirePermission(database, "roles.manage"), resetAdminUserMFAHandler(database))

		backoffice.GET("/access-control", middleware.RequirePermission(database, "roles.manage"), accessControlHandler(database))
		backoffice.POST("/roles", middleware.RequirePermission(database, "roles.manage"), createCustomRoleHandler(database))
		backoffice.PUT("/roles/:role/permissions", middleware.RequirePermission(database, "roles.manage"), updateRolePermissionsHandler(database))
		backoffice.DELETE("/roles/:role", middleware.RequirePermission(database, "roles.manage"), deleteCustomRoleHandler(database))
		backoffice.GET("/registration-policy", middleware.RequirePermission(database, "crm.admin.manage"), getRegistrationPolicyHandler(database))
		backoffice.PUT("/registration-policy", middleware.RequirePermission(database, "crm.admin.manage"), updateRegistrationPolicyHandler(database))
		backoffice.GET("/settings", middleware.RequirePermission(database, "crm.admin.manage"), backofficeSettingsHandler(database))
		backoffice.PUT("/settings", middleware.RequirePermission(database, "crm.admin.manage"), backofficeUpdateSettingsHandler(database))

		backoffice.GET("/crm/summary", middleware.RequirePermission(database, "crm.read"), crmSummaryHandler(database))
		backoffice.GET("/crm/clients", middleware.RequirePermission(database, "users.read"), crmUsersTableHandler(database))
		backoffice.GET("/crm/clients/:id", middleware.RequirePermission(database, "users.read"), crmClientDetailHandler(database))
		backoffice.GET("/crm/hierarchy", middleware.RequirePermission(database, "crm.read"), crmHierarchyTableHandler(database))
		backoffice.GET("/crm/security-events", middleware.RequirePermission(database, "security.events.read"), crmSecurityEventsHandler(database))
		backoffice.POST("/crm/applications/:id/review", middleware.RequirePermission(database, "kyc.review"), reviewPartnerApplicationHandler(database))
		backoffice.PUT("/crm/commission-metrics/:user_id", middleware.RequirePermission(database, "finance.manage"), upsertCommissionMetricsHandler(database))

		backoffice.GET("/audit-logs", middleware.RequirePermission(database, "audit.read"), backofficeAuditLogsHandler(database))

		// Bot API gateway stats (admin-only, in-memory counters)
		backoffice.GET("/bot-api-stats", middleware.RequirePermission(database, "users.read"), botAPIStatsHandler())
	}
}

func accessControlHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		repo := repository.NewRBACRepository(database)
		roleCatalog, err := listRoleCatalog(database)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load roles: %v", err)})
			return
		}
		permissions, err := repo.ListPermissions()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load permissions: %v", err)})
			return
		}
		rolePermissions, err := repo.ListRolePermissions()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load role permissions: %v", err)})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Access control loaded",
			"data": gin.H{
				"roles":            roleKeysFromCatalog(roleCatalog),
				"role_catalog":     roleCatalog,
				"permissions":      permissions,
				"role_permissions": rolePermissions,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func createCustomRoleHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req createCustomRoleRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}

		role, err := normalizeRoleKey(req.Role)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
			return
		}
		if isSystemRole(role) {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "System roles already exist and cannot be recreated as custom roles"})
			return
		}

		repo := repository.NewRBACRepository(database)
		if err := repo.UpsertCustomRole(role, req.DisplayName, req.Description); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
			return
		}

		writeAuditLog(database, c, "admin.role.create", "role", stringPointer(role), gin.H{
			"role":         role,
			"display_name": strings.TrimSpace(req.DisplayName),
		}, "success")

		accessControlHandler(database)(c)
	}
}

func updateRolePermissionsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		role, err := normalizeAssignableRole(database, c.Param("role"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
			return
		}

		var req updateRolePermissionsRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}

		repo := repository.NewRBACRepository(database)
		if err := repo.ReplaceRolePermissions(role, req.PermissionKeys); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
			return
		}

		writeAuditLog(database, c, "admin.role.permissions_update", "role", stringPointer(role), gin.H{
			"role":            role,
			"permission_keys": req.PermissionKeys,
		}, "success")

		accessControlHandler(database)(c)
	}
}

func deleteCustomRoleHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		role, err := normalizeAssignableRole(database, c.Param("role"))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
			return
		}

		repo := repository.NewRBACRepository(database)
		if err := repo.DeleteCustomRole(role); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
			return
		}

		writeAuditLog(database, c, "admin.role.delete", "role", stringPointer(role), gin.H{
			"role": role,
		}, "success")

		accessControlHandler(database)(c)
	}
}

func getRegistrationPolicyHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		policy, err := resolveRegistrationPolicy(database)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load registration policy: %v", err)})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Registration policy loaded",
			"data": gin.H{
				"mode":                string(policy.Mode),
				"enabled":             policy.Enabled,
				"reason":              policy.Reason,
				"invitation_required": policy.InvitationRequired,
				"invitation_code_set": strings.TrimSpace(policy.InvitationCode) != "",
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func updateRegistrationPolicyHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req registrationPolicyRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}

		mode := strings.TrimSpace(strings.ToLower(req.Mode))
		if mode == "public" {
			mode = string(registrationModeOpen)
		}
		if mode == "invite_only" {
			mode = string(registrationModeInvitationOnly)
		}
		if mode != string(registrationModeOpen) && mode != string(registrationModeDisabled) && mode != string(registrationModeInvitationOnly) {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "mode must be disabled, public/open, or invite_only/invitation_only"})
			return
		}
		if mode == string(registrationModeInvitationOnly) && strings.TrimSpace(req.InvitationCode) == "" {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "invitation_code is required for invite-only registration"})
			return
		}

		if err := upsertPlatformSetting(database, "registration_mode", mode, "string", "Registration mode"); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to update registration mode: %v", err)})
			return
		}
		if err := upsertPlatformSetting(database, "allow_public_registration", fmt.Sprintf("%t", mode == string(registrationModeOpen)), "boolean", "Enable public registration"); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to update public registration flag: %v", err)})
			return
		}
		if err := upsertPlatformSetting(database, "registration_invitation_code", strings.TrimSpace(req.InvitationCode), "string", "Registration invitation code"); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to update invitation code: %v", err)})
			return
		}

		writeAuditLog(database, c, "backoffice.registration_policy.update", "platform_setting", stringPointer("registration_policy"), gin.H{
			"mode":                mode,
			"invitation_code_set": strings.TrimSpace(req.InvitationCode) != "",
		}, "success")

		getRegistrationPolicyHandler(database)(c)
	}
}

func backofficeSettingsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		settings, err := repository.NewSettingsRepository(database).GetAllBotSettings()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load settings: %v", err)})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Backoffice settings loaded",
			"data":      gin.H{"settings": settings},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func backofficeUpdateSettingsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var updates map[string]interface{}
		if err := c.ShouldBindJSON(&updates); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}
		for dottedKey, value := range updates {
			parts := strings.SplitN(dottedKey, ".", 2)
			if len(parts) != 2 || strings.TrimSpace(parts[0]) == "" || strings.TrimSpace(parts[1]) == "" {
				c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid setting key %q", dottedKey)})
				return
			}
			if strings.TrimSpace(parts[0]) != "platform" {
				c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Backoffice settings endpoint only accepts platform.* keys"})
				return
			}
			valueType := "string"
			switch value.(type) {
			case bool:
				valueType = "boolean"
			case float64, int:
				valueType = "float"
			}
			if err := upsertPlatformSetting(database, parts[1], fmt.Sprint(value), valueType, "Backoffice platform setting"); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to update %s: %v", dottedKey, err)})
				return
			}
		}
		writeAuditLog(database, c, "backoffice.settings.update", "platform_setting", nil, gin.H{"keys": mapKeys(updates)}, "success")
		backofficeSettingsHandler(database)(c)
	}
}

func crmClientDetailHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		targetID, err := strconv.Atoi(c.Param("id"))
		if err != nil || targetID <= 0 {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Invalid client id"})
			return
		}
		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(targetID)
		if err != nil || user == nil {
			c.JSON(http.StatusNotFound, gin.H{"success": false, "message": "Client not found"})
			return
		}
		relationship, _ := repository.NewPartnerRelationshipRepository(database).GetByPartner(targetID)
		metric, _ := repository.NewPartnerCommissionMetricRepository(database).GetLatestByUser(targetID)
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "CRM client loaded",
			"data": gin.H{
				"user":                  toUserResponse(user, middleware.IsPrivilegedMFARequired(database)),
				"relationship":          relationship,
				"latest_commission":     metric,
				"onboarding_status":     "active",
				"verification_status":   "not_configured",
				"notes_supported":       false,
				"activity_log_endpoint": "/api/v1/backoffice/audit-logs?resource_type=user&resource_id=" + strconv.Itoa(targetID),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func backofficeAuditLogsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := parseBoundedInt(c.DefaultQuery("limit", "100"), 1, 500, 100)
		offset := parseBoundedInt(c.DefaultQuery("offset", "0"), 0, 100000, 0)
		rows, err := database.Query(`
			SELECT id, user_id, action, resource_type, resource_id, details, status, ip_address, created_at
			FROM audit_logs
			ORDER BY created_at DESC
			LIMIT $1 OFFSET $2
		`, limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load audit logs: %v", err)})
			return
		}
		defer func() { _ = rows.Close() }()

		logs := []gin.H{}
		for rows.Next() {
			var id int
			var userID sql.NullInt64
			var action, resourceType string
			var resourceID, details, status, ipAddress sql.NullString
			var createdAt sql.NullTime
			if err := rows.Scan(&id, &userID, &action, &resourceType, &resourceID, &details, &status, &ipAddress, &createdAt); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to parse audit log: %v", err)})
				return
			}
			item := gin.H{"id": id, "action": action, "resource_type": resourceType}
			if userID.Valid {
				item["user_id"] = userID.Int64
			}
			if resourceID.Valid {
				item["resource_id"] = resourceID.String
			}
			if details.Valid {
				item["details"] = details.String
			}
			if status.Valid {
				item["status"] = status.String
			}
			if ipAddress.Valid {
				item["ip_address"] = ipAddress.String
			}
			if createdAt.Valid {
				item["created_at"] = createdAt.Time.UTC().Format(time.RFC3339)
			}
			logs = append(logs, item)
		}
		if err := rows.Err(); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to iterate audit logs: %v", err)})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Audit logs loaded",
			"data":      gin.H{"audit_logs": logs},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func upsertPlatformSetting(database *sql.DB, key string, value string, valueType string, description string) error {
	_, err := database.Exec(`
		INSERT INTO bot_settings (section, key, value, value_type, description, default_value, is_active, version, created_at, updated_at)
		VALUES ('platform', $1, $2, $3, $4, $2, TRUE, 1, $5, $5)
		ON CONFLICT (section, key) DO UPDATE SET
			value = EXCLUDED.value,
			value_type = EXCLUDED.value_type,
			description = EXCLUDED.description,
			updated_at = EXCLUDED.updated_at,
			version = COALESCE(bot_settings.version, 0) + 1
	`, strings.TrimSpace(key), value, valueType, description, time.Now().UTC())
	return err
}

func mapKeys(values map[string]interface{}) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	return keys
}

// botAPIStatsHandler returns in-process counters for the Go→Bot API gateway.
func botAPIStatsHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		stats := services.BotAPIStats()
		c.JSON(http.StatusOK, gin.H{"data": stats})
	}
}
