package middleware

import (
	"fmt"
	"log"
	"strings"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/gin-gonic/gin"
)

var jwtManager *auth.Manager

func InitAuthMiddleware(cfg *config.Config) {
	jwtManager = auth.NewManager(auth.JWTConfig{
		Secret:            cfg.Auth.JWTSecretKey,
		ExpiryHours:       cfg.Auth.AccessTokenExpireMinutes / 60,
		RefreshExpiryDays: cfg.Auth.RefreshTokenExpireDays,
	})
}

func RequireAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		// Debug logging to help diagnose missing/invalid tokens
		log.Printf("RequireAuth: Authorization header=%q, RemoteAddr=%s, ClientIP=%s", authHeader, c.Request.RemoteAddr, c.ClientIP())

		// If header is empty, try cookie fallback (common cookie names)
		if authHeader == "" {
			cookieNames := []string{"access_token", "token", "jwt"}
			for _, name := range cookieNames {
				if cookieVal, err := c.Cookie(name); err == nil && cookieVal != "" {
					authHeader = "Bearer " + cookieVal
					log.Printf("RequireAuth: using token from cookie '%s' (masked)", name)
					break
				}
			}
		}

		// If still empty, look for access_token query parameter (debug only)
		if authHeader == "" {
			if q := c.Query("access_token"); q != "" {
				authHeader = "Bearer " + q
				log.Printf("RequireAuth: using token from query param access_token (masked)")
			}
		}

		if authHeader == "" {
			c.JSON(401, gin.H{"error": "missing authorization header"})
			c.Abort()
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.JSON(401, gin.H{"error": "invalid authorization header format"})
			c.Abort()
			return
		}

		tokenString := parts[1]
		claims, err := jwtManager.VerifyToken(tokenString, "access")
		if err != nil {
			// Log underlying verification error as well
			log.Printf("RequireAuth: token verification failed: %v", err)
			if strings.Contains(strings.ToLower(err.Error()), "token is expired") || strings.Contains(strings.ToLower(err.Error()), "token expired") {
				c.JSON(401, gin.H{"error": "access token expired", "code": "token_expired"})
				c.Abort()
				return
			}
			c.JSON(401, gin.H{"error": fmt.Sprintf("invalid token: %v", err)})
			c.Abort()
			return
		}

		c.Set("user_id", claims.UserID)
		c.Set("username", claims.Username)
		c.Set("email", claims.Email)
		c.Set("is_admin", claims.IsAdmin)

		c.Next()
	}
}
