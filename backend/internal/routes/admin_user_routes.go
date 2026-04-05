package routes

import (
	"context"
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

func RegisterAdminUserRoutes(router *gin.Engine, database *sql.DB) {
	adminRoutes := router.Group("/api/v1/admin")
	adminRoutes.Use(middleware.RequireAuth())
	{
		adminRoutes.GET("/users", listAdminUsersHandler(database))
		adminRoutes.POST("/users", createAdminUserHandler(database))
		adminRoutes.PUT("/users/:id", updateAdminUserHandler(database))
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
