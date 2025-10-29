package routes

import (
	"database/sql"
	"log"
	"net/http"
	"os"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
)

// RegisterAuthRoutes registers all authentication routes
func RegisterAuthRoutes(router *gin.Engine, database *sql.DB) {
	authRoutes := router.Group("/api/v1/auth")
	{
		authRoutes.POST("/register", registerHandler(database))
		authRoutes.POST("/login", loginHandler(database))
		authRoutes.POST("/refresh", refreshHandler)
	}

	// User routes (require authentication)
	userRoutes := router.Group("/api/v1/users")
	{
		userRoutes.Use(middleware.RequireAuth())
		userRoutes.GET("/me", getCurrentUserHandler)
	}

	// Profile routes (require authentication)
	profileRoutes := router.Group("/api/v1/profile")
	{
		profileRoutes.Use(middleware.RequireAuth())
		profileRoutes.PUT("", updateProfileHandler(database))
	}
}

// Request/Response models
type RegisterRequest struct {
	Username string `json:"username" binding:"required"`
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=6"`
}

type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

type TokenResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
}

type UserResponse struct {
	ID        int    `json:"id"`
	Username  string `json:"username"`
	Email     string `json:"email"`
	FullName  string `json:"full_name"`
	Avatar    string `json:"avatar"`
	IsActive  bool   `json:"is_active"`
	IsAdmin   bool   `json:"is_admin"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
}

// registerHandler handles user registration
func registerHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req RegisterRequest

		// Bind JSON with error handling
		if err := c.BindJSON(&req); err != nil {
			log.Printf("Failed to bind JSON: %v", err)
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"error":   "Invalid request format",
				"details": err.Error(),
			})
			return
		}

		// Validate input
		if req.Username == "" || req.Email == "" || req.Password == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"error":   "Username, email, and password are required",
			})
			return
		}

		// Hash password
		hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "Failed to hash password",
			})
			return
		}

		// Create user in database
		userRepo := repository.NewUserRepository(database)
		user := &models.User{
			Username: req.Username,
			Email:    req.Email,
			Password: string(hashedPassword),
			IsActive: true,
			IsAdmin:  false,
		}

		err = userRepo.Create(user)
		if err != nil {
			log.Printf("Failed to create user: %v", err)
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"error":   "User already exists",
			})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"success": true,
			"message": "User registered successfully",
			"data": gin.H{
				"user_id":  user.ID,
				"username": user.Username,
			},
		})
	}
}

// loginHandler handles user login
func loginHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req LoginRequest

		// Bind JSON with error handling
		if err := c.BindJSON(&req); err != nil {
			log.Printf("Failed to bind JSON: %v", err)
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"error":   "Invalid request format",
				"details": err.Error(),
			})
			return
		}

		// Validate input
		if req.Username == "" || req.Password == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"error":   "Username and password are required",
			})
			return
		}

		// Get user from database
		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByUsername(req.Username)
		if err != nil {
			log.Printf("User not found: %s, error: %v", req.Username, err)
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "Invalid credentials",
			})
			return
		}

		if user == nil {
			log.Printf("User not found: %s", req.Username)
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "Invalid credentials",
			})
			return
		}

		// Verify password
		err = bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(req.Password))
		if err != nil {
			log.Printf("Password mismatch for user: %s", req.Username)
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "Invalid credentials",
			})
			return
		}

		// Generate tokens
		accessToken, err := services.GenerateAccessToken(user.ID, user.Username, user.IsAdmin)
		if err != nil {
			log.Printf("Failed to generate access token: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "Failed to generate token",
			})
			return
		}

		refreshToken, err := services.GenerateRefreshToken(user.ID, user.Username)
		if err != nil {
			log.Printf("Failed to generate refresh token: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "Failed to generate refresh token",
			})
			return
		}

		// Update last_login
		_ = userRepo.UpdateLastLogin(user.ID)

		// Set access token as HttpOnly cookie (for browser clients)
		// Cookie expiry matches access token lifetime (30 minutes)
		cookieMaxAge := 30 * 60 // seconds
		secure := false
		if os.Getenv("APP_ENV") == "production" {
			secure = true
		}
		c.SetCookie("access_token", accessToken, cookieMaxAge, "/", "", secure, true)

		c.JSON(http.StatusOK, TokenResponse{
			AccessToken:  accessToken,
			RefreshToken: refreshToken,
			TokenType:    "bearer",
			ExpiresIn:    1800, // 30 minutes
		})
	}
}

// refreshHandler handles token refresh
func refreshHandler(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"message": "Token refresh not yet implemented"})
}

// getCurrentUserHandler gets current user info
func getCurrentUserHandler(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":       userID,
		"username": c.GetString("username"),
		"is_admin": c.GetBool("is_admin"),
	})
}

// updateProfileHandler updates user profile
func updateProfileHandler(_ *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "Profile update not yet implemented"})
	}
}
