package routes

import (
	"context"
	"crypto/rand"
	"database/sql"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type adminUserListResponse struct {
	Users []UserResponse `json:"users"`
	Roles []string       `json:"roles"`
}

type createAdminUserRequest struct {
	Username string `json:"username" binding:"required"`
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=6"`
	FullName string `json:"full_name"`
	Role     string `json:"role"`
	IsActive *bool  `json:"is_active"`
}

type updateAdminUserRequest struct {
	Email    *string `json:"email"`
	FullName *string `json:"full_name"`
	Role     *string `json:"role"`
	IsActive *bool   `json:"is_active"`
}

type createInvitationTokenRequest struct {
	Label          string `json:"label"`
	IBName         string `json:"ib_name"`
	CampaignName   string `json:"campaign_name"`
	MaxUses        *int   `json:"max_uses"`
	ExpiresInHours *int   `json:"expires_in_hours"`
}

type invitationTokenResponse struct {
	ID               int     `json:"id"`
	TokenCode        string  `json:"token_code"`
	Label            string  `json:"label"`
	IBName           string  `json:"ib_name"`
	CampaignName     string  `json:"campaign_name"`
	MaxUses          int     `json:"max_uses"`
	UsedCount        int     `json:"used_count"`
	CreatedByUserID  *int    `json:"created_by_user_id"`
	LastUsedByUserID *int    `json:"last_used_by_user_id"`
	ExpiresAt        *string `json:"expires_at"`
	LastUsedAt       *string `json:"last_used_at"`
	RevokedAt        *string `json:"revoked_at"`
	CreatedAt        string  `json:"created_at"`
	UpdatedAt        string  `json:"updated_at"`
}

func RegisterAdminUserRoutes(router *gin.Engine, database *sql.DB) {
	adminRoutes := router.Group("/api/v1/admin")
	adminRoutes.Use(middleware.RequireAuth())
	{
		adminRoutes.GET("/users", listAdminUsersHandler(database))
		adminRoutes.POST("/users", createAdminUserHandler(database))
		adminRoutes.PUT("/users/:id", updateAdminUserHandler(database))
		adminRoutes.GET("/ib/invitations", listInvitationTokensHandler(database))
		adminRoutes.POST("/ib/invitations", createInvitationTokenHandler(database))
		adminRoutes.POST("/ib/invitations/:tokenCode/revoke", revokeInvitationTokenHandler(database))
	}
}

func toInvitationTokenResponse(token *models.InvitationToken) invitationTokenResponse {
	formatTime := func(value *time.Time) *string {
		if value == nil {
			return nil
		}
		formatted := value.UTC().Format(time.RFC3339)
		return &formatted
	}

	return invitationTokenResponse{
		ID:               token.ID,
		TokenCode:        token.TokenCode,
		Label:            token.Label,
		IBName:           token.IBName,
		CampaignName:     token.CampaignName,
		MaxUses:          token.MaxUses,
		UsedCount:        token.UsedCount,
		CreatedByUserID:  token.CreatedByUserID,
		LastUsedByUserID: token.LastUsedByUserID,
		ExpiresAt:        formatTime(token.ExpiresAt),
		LastUsedAt:       formatTime(token.LastUsedAt),
		RevokedAt:        formatTime(token.RevokedAt),
		CreatedAt:        token.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt:        token.UpdatedAt.UTC().Format(time.RFC3339),
	}
}

func generateInvitationTokenCode() (string, error) {
	const charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	const tokenLength = 20

	buffer := make([]byte, tokenLength)
	randBytes := make([]byte, tokenLength)
	if _, err := rand.Read(randBytes); err != nil {
		return "", fmt.Errorf("failed to generate random invitation bytes: %w", err)
	}

	for i := 0; i < tokenLength; i++ {
		buffer[i] = charset[int(randBytes[i])%len(charset)]
	}

	raw := string(buffer)
	return fmt.Sprintf("IB-%s-%s-%s", raw[:4], raw[4:12], raw[12:]), nil
}

func listInvitationTokensHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !c.GetBool("is_admin") {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "Admin access required",
			})
			return
		}

		limit := 100
		offset := 0
		if parsedLimit, err := strconv.Atoi(c.DefaultQuery("limit", "100")); err == nil && parsedLimit > 0 && parsedLimit <= 500 {
			limit = parsedLimit
		}
		if parsedOffset, err := strconv.Atoi(c.DefaultQuery("offset", "0")); err == nil && parsedOffset >= 0 {
			offset = parsedOffset
		}

		repo := repository.NewInvitationTokenRepository(database)
		tokens, err := repo.List(limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": fmt.Sprintf("Failed to list invitation tokens: %v", err),
			})
			return
		}

		total, err := repo.Count()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": fmt.Sprintf("Failed to count invitation tokens: %v", err),
			})
			return
		}

		payload := make([]invitationTokenResponse, 0, len(tokens))
		for _, token := range tokens {
			payload = append(payload, toInvitationTokenResponse(token))
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "IB invitation tokens loaded successfully",
			"data": gin.H{
				"tokens": payload,
				"total":  total,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func createInvitationTokenHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !c.GetBool("is_admin") {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "Admin access required",
			})
			return
		}

		var req createInvitationTokenRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": fmt.Sprintf("Invalid request: %v", err),
			})
			return
		}

		maxUses := 1
		if req.MaxUses != nil {
			maxUses = *req.MaxUses
		}
		if maxUses < 1 || maxUses > 1000 {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "max_uses must be between 1 and 1000",
			})
			return
		}

		var expiresAt *time.Time
		if req.ExpiresInHours != nil {
			expiresHours := *req.ExpiresInHours
			if expiresHours < 1 || expiresHours > 24*365 {
				c.JSON(http.StatusBadRequest, gin.H{
					"success": false,
					"message": "expires_in_hours must be between 1 and 8760",
				})
				return
			}
			expires := time.Now().UTC().Add(time.Duration(expiresHours) * time.Hour)
			expiresAt = &expires
		}

		actorID := c.GetInt("user_id")
		createdByUserID := &actorID

		repo := repository.NewInvitationTokenRepository(database)
		var createdToken *models.InvitationToken
		var createErr error

		for attempt := 0; attempt < 5; attempt++ {
			code, err := generateInvitationTokenCode()
			if err != nil {
				createErr = err
				break
			}

			token := &models.InvitationToken{
				TokenCode:       code,
				Label:           strings.TrimSpace(req.Label),
				IBName:          strings.TrimSpace(req.IBName),
				CampaignName:    strings.TrimSpace(req.CampaignName),
				MaxUses:         maxUses,
				UsedCount:       0,
				CreatedByUserID: createdByUserID,
				ExpiresAt:       expiresAt,
			}

			if err := repo.Create(token); err != nil {
				createErr = err
				continue
			}

			createdToken = token
			createErr = nil
			break
		}

		if createErr != nil || createdToken == nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": fmt.Sprintf("Failed to create invitation token: %v", createErr),
			})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"success": true,
			"message": "IB invitation token created successfully",
			"data": gin.H{
				"token": toInvitationTokenResponse(createdToken),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func revokeInvitationTokenHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !c.GetBool("is_admin") {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "Admin access required",
			})
			return
		}

		tokenCode := strings.TrimSpace(strings.ToUpper(c.Param("tokenCode")))
		if tokenCode == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "tokenCode is required",
			})
			return
		}

		repo := repository.NewInvitationTokenRepository(database)
		if err := repo.RevokeByTokenCode(tokenCode); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Invitation token revoked",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func listAdminUsersHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !c.GetBool("is_admin") {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "Admin access required",
			})
			return
		}

		userRepo := repository.NewUserRepository(database)
		users, err := userRepo.List(500, 0)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": fmt.Sprintf("Failed to list users: %v", err),
			})
			return
		}

		payload := make([]UserResponse, 0, len(users))
		for _, user := range users {
			payload = append(payload, toUserResponse(user))
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Users loaded successfully",
			"data": adminUserListResponse{
				Users: payload,
				Roles: models.AvailableUserRoles(),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func createAdminUserHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !c.GetBool("is_admin") {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "Admin access required",
			})
			return
		}

		var req createAdminUserRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": fmt.Sprintf("Invalid request: %v", err),
			})
			return
		}

		normalizedRole := models.NormalizeUserRole(req.Role, false)
		isAdmin := normalizedRole == "admin"
		isActive := true
		if req.IsActive != nil {
			isActive = *req.IsActive
		}

		user := &models.User{
			Username:               strings.TrimSpace(req.Username),
			Email:                  strings.TrimSpace(req.Email),
			Role:                   normalizedRole,
			FullName:               strings.TrimSpace(req.FullName),
			IsActive:               isActive,
			IsAdmin:                isAdmin,
			PasswordChangeRequired: true,
		}

		if user.Username == "" || user.Email == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "Username and email are required",
			})
			return
		}

		if err := user.SetPassword(req.Password); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to secure password",
			})
			return
		}

		userRepo := repository.NewUserRepository(database)
		if err := userRepo.Create(user); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": fmt.Sprintf("Failed to create user: %v", err),
			})
			return
		}

		mailgunService := services.NewMailgunService(
			services.NewExternalAPICredentialService(repository.NewExternalAPICredentialRepository(database)),
			repository.NewSettingsRepository(database),
			userRepo,
		)
		onboardingNotice := "User created. Share the temporary password through a secure channel."
		if result, err := mailgunService.SendPasswordRotationNotice(context.Background(), user); err == nil && result != nil {
			onboardingNotice = result.Message
		}

		c.JSON(http.StatusCreated, gin.H{
			"success": true,
			"message": "User created successfully",
			"data": gin.H{
				"user":              toUserResponse(user),
				"roles":             models.AvailableUserRoles(),
				"onboarding_notice": onboardingNotice,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func updateAdminUserHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !c.GetBool("is_admin") {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"message": "Admin access required",
			})
			return
		}

		targetID, err := strconv.Atoi(c.Param("id"))
		if err != nil || targetID <= 0 {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "Invalid user ID",
			})
			return
		}

		var req updateAdminUserRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": fmt.Sprintf("Invalid request: %v", err),
			})
			return
		}

		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(targetID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{
				"success": false,
				"message": "User not found",
			})
			return
		}

		actorID := c.GetInt("user_id")
		nextRole := models.NormalizeUserRole(user.Role, user.IsAdmin)
		if req.Role != nil {
			nextRole = models.NormalizeUserRole(*req.Role, false)
		}
		nextIsActive := user.IsActive
		if req.IsActive != nil {
			nextIsActive = *req.IsActive
		}

		if err := ensureAdminMutationIsSafe(userRepo, user, actorID, nextRole, nextIsActive); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": err.Error(),
			})
			return
		}

		if req.Email != nil {
			user.Email = strings.TrimSpace(*req.Email)
		}
		if req.FullName != nil {
			user.FullName = strings.TrimSpace(*req.FullName)
		}
		user.Role = nextRole
		user.IsAdmin = nextRole == "admin"
		user.IsActive = nextIsActive

		if user.Email == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "Email cannot be empty",
			})
			return
		}

		if err := userRepo.Update(user); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": fmt.Sprintf("Failed to update user: %v", err),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "User updated successfully",
			"data": gin.H{
				"user":  toUserResponse(user),
				"roles": models.AvailableUserRoles(),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func ensureAdminMutationIsSafe(userRepo *repository.UserRepository, target *models.User, actorID int, nextRole string, nextIsActive bool) error {
	currentRole := models.NormalizeUserRole(target.Role, target.IsAdmin)
	currentlyAdmin := currentRole == "admin" && target.IsActive
	willRemainAdmin := nextRole == "admin" && nextIsActive

	if target.ID == actorID {
		if nextRole != "admin" {
			return fmt.Errorf("use another admin account to change your own admin role")
		}
		if !nextIsActive {
			return fmt.Errorf("you cannot deactivate your own admin account")
		}
	}

	if currentlyAdmin && !willRemainAdmin {
		adminCount, err := userRepo.CountActiveAdmins()
		if err != nil {
			return fmt.Errorf("failed to verify admin safety: %w", err)
		}
		if adminCount <= 1 {
			return fmt.Errorf("at least one active admin must remain on the platform")
		}
	}

	return nil
}
