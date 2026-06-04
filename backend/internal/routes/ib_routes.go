// Package routes provides HTTP route registration and handlers for the dYdX backend API introducing broker (IB) features.
package routes

import (
	"database/sql"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

type createIBRelationshipRequest struct {
	PartnerUserID    int    `json:"partner_user_id" binding:"required"`
	RelationshipType string `json:"relationship_type"`
}

func RegisterIBPortalRoutes(router *gin.Engine, database *sql.DB) {
	ib := router.Group("/api/v1/ib")
	ib.Use(middleware.RequireAuth())
	ib.Use(requireIBPortalAccess())
	{
		ib.GET("/profile", ibProfileHandler(database))
		ib.GET("/dashboard", ibDashboardHandler(database))
		ib.GET("/sub-ibs", ibSubIBsHandler(database))
		ib.POST("/sub-ibs", ibCreateRelationshipHandler(database, "sub_ib"))
		ib.GET("/clients", ibClientsHandler(database))
		ib.POST("/clients", ibCreateRelationshipHandler(database, "client"))
		ib.GET("/invitations", ibInvitationTokensHandler(database))
		ib.POST("/invitations", createInvitationTokenHandler(database))
		ib.GET("/invitations/:id", ibInvitationDetailHandler(database))
		ib.POST("/invitations/:id/revoke", ibRevokeInvitationTokenHandler(database))
		ib.GET("/referral-links", ibReferralLinksHandler(database))
		ib.GET("/commissions", ibCommissionsHandler(database))
		ib.GET("/reports", ibReportsHandler(database))
	}

	router.GET("/api/v1/ib/invitations/:id/validate", middleware.RequireAuth(), requireIBPortalAccess(), ibInvitationDetailHandler(database))
}

func requireIBPortalAccess() gin.HandlerFunc {
	return func(c *gin.Context) {
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		if canManageCRM(role) || role == "ib" || role == "sub_ib" {
			c.Next()
			return
		}
		c.JSON(http.StatusForbidden, gin.H{
			"success": false,
			"message": "IB portal access required",
			"code":    "ib_portal_access_required",
		})
		c.Abort()
	}
}

func ibProfileHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(c.GetInt("user_id"))
		if err != nil || user == nil {
			c.JSON(http.StatusNotFound, gin.H{"success": false, "message": "User not found"})
			return
		}
		relationship, _ := repository.NewPartnerRelationshipRepository(database).GetByPartner(user.ID)
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "IB profile loaded",
			"data": gin.H{
				"profile":      toUserResponse(user, middleware.IsPrivilegedMFARequired(database)),
				"relationship": relationship,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ibDashboardHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		portalOverviewHandler(database)(c)
	}
}

func ibSubIBsHandler(database *sql.DB) gin.HandlerFunc {
	return ibUsersByRoleHandler(database, "sub_ib")
}

func ibClientsHandler(database *sql.DB) gin.HandlerFunc {
	return ibUsersByRoleHandler(database, "client")
}

func ibUsersByRoleHandler(database *sql.DB, targetRole string) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		requestUserID := c.GetInt("user_id")
		allowedIDs, err := visiblePartnerIDs(database, requestUserID, role)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load IB scope: %v", err)})
			return
		}
		userRepo := repository.NewUserRepository(database)
		users, err := userRepo.List(5000, 0)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load users: %v", err)})
			return
		}
		allowed := map[int]bool{}
		for _, id := range allowedIDs {
			allowed[id] = true
		}
		payload := []UserResponse{}
		for _, user := range users {
			if models.NormalizeUserRole(user.Role, user.IsAdmin) != targetRole {
				continue
			}
			if !canManageCRM(role) && !allowed[user.ID] {
				continue
			}
			payload = append(payload, toUserResponse(user, middleware.IsPrivilegedMFARequired(database)))
		}
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "IB users loaded",
			"data": gin.H{
				"users": payload,
				"role":  targetRole,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ibCreateRelationshipHandler(database *sql.DB, defaultRelationshipType string) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		if !canManageCRM(role) && role != "ib" && role != "sub_ib" {
			c.JSON(http.StatusForbidden, gin.H{"success": false, "message": "IB relationship management requires IB access"})
			return
		}
		var req createIBRelationshipRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}
		relationshipType := strings.TrimSpace(strings.ToLower(req.RelationshipType))
		if relationshipType == "" {
			relationshipType = defaultRelationshipType
		}
		if relationshipType != "client" && relationshipType != "sub_ib" {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "relationship_type must be client or sub_ib"})
			return
		}
		sponsorID := c.GetInt("user_id")
		if canManageCRM(role) {
			if rawSponsor := strings.TrimSpace(c.Query("sponsor_user_id")); rawSponsor != "" {
				if parsed, err := strconv.Atoi(rawSponsor); err == nil && parsed > 0 {
					sponsorID = parsed
				}
			}
		}
		relationship := &models.PartnerRelationship{
			SponsorUserID:    sponsorID,
			PartnerUserID:    req.PartnerUserID,
			RelationshipType: relationshipType,
			IsActive:         true,
		}
		if err := repository.NewPartnerRelationshipRepository(database).Upsert(relationship); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to save relationship: %v", err)})
			return
		}
		writeAuditLog(database, c, "ib.relationship.upsert", "partner_relationship", stringPointer(strconv.Itoa(req.PartnerUserID)), gin.H{
			"sponsor_user_id":   sponsorID,
			"partner_user_id":   req.PartnerUserID,
			"relationship_type": relationshipType,
		}, "success")
		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "IB relationship saved",
			"data":      gin.H{"relationship": relationship},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ibInvitationDetailHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		rawID := strings.TrimSpace(c.Param("id"))
		repo := repository.NewInvitationTokenRepository(database)
		var token *models.InvitationToken
		var err error
		if id, parseErr := strconv.Atoi(rawID); parseErr == nil && id > 0 {
			token, err = repo.GetByID(id)
		} else {
			token, err = repo.GetByTokenCode(strings.ToUpper(rawID))
		}
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load invitation: %v", err)})
			return
		}
		if token == nil {
			c.JSON(http.StatusNotFound, gin.H{"success": false, "message": "Invitation not found"})
			return
		}
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		if !canManageCRM(role) && (token.CreatedByUserID == nil || *token.CreatedByUserID != c.GetInt("user_id")) {
			c.JSON(http.StatusForbidden, gin.H{"success": false, "message": "Invitation is outside your IB scope"})
			return
		}
		active := token.RevokedAt == nil && token.UsedCount < token.MaxUses && (token.ExpiresAt == nil || token.ExpiresAt.After(time.Now().UTC()))
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Invitation loaded",
			"data": gin.H{
				"token":  toInvitationTokenResponse(token),
				"active": active,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ibInvitationTokensHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := parseBoundedInt(c.DefaultQuery("limit", "100"), 1, 500, 100)
		offset := parseBoundedInt(c.DefaultQuery("offset", "0"), 0, 100000, 0)
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		actorID := c.GetInt("user_id")

		repo := repository.NewInvitationTokenRepository(database)
		tokens, err := repo.List(limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load invitations: %v", err)})
			return
		}

		payload := []invitationTokenResponse{}
		for _, token := range tokens {
			if !canManageCRM(role) && (token.CreatedByUserID == nil || *token.CreatedByUserID != actorID) {
				continue
			}
			payload = append(payload, toInvitationTokenResponse(token))
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "IB invitations loaded",
			"data": gin.H{
				"tokens": payload,
				"total":  len(payload),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ibRevokeInvitationTokenHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		rawID := strings.TrimSpace(c.Param("id"))
		repo := repository.NewInvitationTokenRepository(database)
		token, err := repo.GetByTokenCode(strings.ToUpper(rawID))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load invitation: %v", err)})
			return
		}
		if token == nil {
			c.JSON(http.StatusNotFound, gin.H{"success": false, "message": "Invitation not found"})
			return
		}
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		if !canManageCRM(role) && (token.CreatedByUserID == nil || *token.CreatedByUserID != c.GetInt("user_id")) {
			c.JSON(http.StatusForbidden, gin.H{"success": false, "message": "Invitation is outside your IB scope"})
			return
		}
		if err := repo.RevokeByTokenCode(token.TokenCode); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
			return
		}
		writeAuditLog(database, c, "ib.invitation.revoke", "invitation_token", stringPointer(token.TokenCode), gin.H{"token_id": token.ID}, "success")
		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Invitation revoked",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ibReferralLinksHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		baseURL := strings.TrimRight(c.DefaultQuery("base_url", "https://app.executionlab.io/register"), "/")
		tokenRepo := repository.NewInvitationTokenRepository(database)
		tokens, err := tokenRepo.List(500, 0)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load referral links: %v", err)})
			return
		}
		actorID := c.GetInt("user_id")
		links := []gin.H{}
		for _, token := range tokens {
			if !canManageCRM(role) && (token.CreatedByUserID == nil || *token.CreatedByUserID != actorID) {
				continue
			}
			links = append(links, gin.H{
				"token": token.TokenCode,
				"url":   baseURL + "?invitation_code=" + token.TokenCode,
				"label": token.Label,
			})
		}
		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Referral links loaded",
			"data":      gin.H{"links": links},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ibCommissionsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		portalCommissionMetricsHandler(database)(c)
	}
}

func ibReportsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		commissionRepo := repository.NewPartnerCommissionMetricRepository(database)
		userID := c.GetInt("user_id")
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		if canManageCRM(role) {
			if rawUserID := strings.TrimSpace(c.Query("user_id")); rawUserID != "" {
				if parsed, err := strconv.Atoi(rawUserID); err == nil && parsed > 0 {
					userID = parsed
				}
			}
		}
		metrics, err := commissionRepo.ListByUser(userID, parseBoundedInt(c.DefaultQuery("limit", "100"), 1, 500, 100), parseBoundedInt(c.DefaultQuery("offset", "0"), 0, 100000, 0))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load IB reports: %v", err)})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "IB reports loaded",
			"data":      gin.H{"commission_history": metrics},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func visiblePartnerIDs(database *sql.DB, sponsorUserID int, role string) ([]int, error) {
	relationshipRepo := repository.NewPartnerRelationshipRepository(database)
	relationships, err := relationshipRepo.List(10000, 0)
	if err != nil {
		return nil, err
	}
	if canManageCRM(role) {
		ids := make([]int, 0, len(relationships))
		for _, relationship := range relationships {
			ids = append(ids, relationship.PartnerUserID)
		}
		return ids, nil
	}
	children := map[int][]int{}
	for _, relationship := range relationships {
		if relationship.IsActive {
			children[relationship.SponsorUserID] = append(children[relationship.SponsorUserID], relationship.PartnerUserID)
		}
	}
	ids := []int{}
	seen := map[int]bool{}
	var walk func(int)
	walk = func(id int) {
		for _, childID := range children[id] {
			if seen[childID] {
				continue
			}
			seen[childID] = true
			ids = append(ids, childID)
			walk(childID)
		}
	}
	walk(sponsorUserID)
	return ids, nil
}
