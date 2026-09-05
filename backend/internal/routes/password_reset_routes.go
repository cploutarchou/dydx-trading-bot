package routes

import (
	"database/sql"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
)

func clientIPOf(c *gin.Context) string {
	forwarded := strings.TrimSpace(c.GetHeader("X-Forwarded-For"))
	if forwarded != "" {
		return strings.TrimSpace(strings.Split(forwarded, ",")[0])
	}
	return c.ClientIP()
}

func newPasswordResetService(database *sql.DB) *services.PasswordResetService {
	userRepo := repository.NewUserRepository(database)
	credentialRepo := repository.NewExternalAPICredentialRepository(database)
	settingsRepo := repository.NewSettingsRepository(database)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	mail := services.NewMailgunService(credentialService, settingsRepo, userRepo)
	return services.NewPasswordResetService(
		repository.NewPasswordResetTokenRepository(database), mail)
}

// forgotPasswordHandler issues an emailed reset token. Responses are
// identical for known and unknown accounts so the endpoint cannot be used to
// enumerate registered emails.
func forgotPasswordHandler(database *sql.DB) gin.HandlerFunc {
	type forgotPasswordRequest struct {
		Email string `json:"email" binding:"required,email"`
	}

	return func(c *gin.Context) {
		var req forgotPasswordRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "A valid email address is required",
			})
			return
		}

		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByEmail(strings.TrimSpace(strings.ToLower(req.Email)))
		if err == nil && user != nil && user.IsActive {
			if err := newPasswordResetService(database).IssueResetToken(
				c.Request.Context(), user.ID, user.Email, user.Username, clientIPOf(c)); err != nil {
				// Logged for operators; the client still gets the generic
				// response so the endpoint never reveals account state.
				log.Printf("forgotPasswordHandler: user=%d: %v", user.ID, err)
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "If an account exists for that email, a reset link is on its way. The link works for 30 minutes and can be used once.",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

// resetPasswordHandler consumes an emailed token and sets the new password,
// revoking every active session for the account (same contract as
// change-password).
func resetPasswordHandler(database *sql.DB) gin.HandlerFunc {
	type resetPasswordRequest struct {
		Token       string `json:"token" binding:"required"`
		NewPassword string `json:"new_password" binding:"required,min=8"`
	}

	return func(c *gin.Context) {
		var req resetPasswordRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "A reset token and a new password of at least 8 characters are required",
			})
			return
		}
		if strings.TrimSpace(req.NewPassword) != req.NewPassword {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "Password must not start or end with whitespace",
			})
			return
		}

		tokenRepo := repository.NewPasswordResetTokenRepository(database)
		consumed, err := tokenRepo.Consume(c.Request.Context(), services.HashForValidation(req.Token))
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "This reset link is invalid, already used, or expired. Request a new one.",
			})
			return
		}

		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(consumed.UserID)
		if err != nil || user == nil {
			log.Printf("resetPasswordHandler: load user=%d: %v", consumed.UserID, err)
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "This reset link is invalid or the account no longer exists. Request a new one.",
			})
			return
		}
		if !user.IsActive {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "This account is no longer active. Contact support.",
			})
			return
		}

		hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcrypt.DefaultCost)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to secure password",
			})
			return
		}
		user.Password = string(hashedPassword)
		user.PasswordChangeRequired = false
		if err := userRepo.Update(user); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to update password",
			})
			return
		}

		// Revoke every issued session, exactly like an interactive password
		// change; the user signs in with the new password.
		if store := middleware.AuthSessionStore(); store != nil {
			if err := store.BumpUserGeneration(c.Request.Context(), user.ID); err != nil {
				log.Printf("resetPasswordHandler: failed to revoke sessions for user=%d: %v", user.ID, err)
			}
		}
		clearAuthCookies(c)

		// Opportunistic prune; failures are non-fatal.
		_ = tokenRepo.DeleteExpired(c.Request.Context())

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Password updated. Sign in with your new password.",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}
