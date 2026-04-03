package middleware

import (
	"log"
	"strings"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/gin-gonic/gin"
)

var jwtManager *auth.Manager

func InitAuthMiddleware(cfg *config.Config) {
	expiryHours := (cfg.Auth.AccessTokenExpireMinutes + 59) / 60
	if expiryHours <= 0 {
		expiryHours = 1
	}

	jwtManager = auth.NewManager(auth.JWTConfig{
		Secret:            cfg.Auth.JWTSecretKey,
		ExpiryHours:       expiryHours,
		RefreshExpiryDays: cfg.Auth.RefreshTokenExpireDays,
	})
}

func RequireAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		if jwtManager == nil {
			log.Printf("RequireAuth: jwt manager is not initialized")
			c.JSON(500, gin.H{"error": "authentication service unavailable"})
			c.Abort()
			return
		}

		rawAuthorization := strings.TrimSpace(c.GetHeader("Authorization"))
		authHeader, source := ResolveRequestAuthHeader(c)
		// Do not log raw auth header/token values.
		log.Printf("RequireAuth: has_authorization=%t, RemoteAddr=%s, ClientIP=%s", rawAuthorization != "", c.Request.RemoteAddr, c.ClientIP())

		if strings.HasPrefix(source, "cookie:") {
			log.Printf("RequireAuth: using token from cookie '%s' (masked)", strings.TrimPrefix(source, "cookie:"))
		} else if source == "query:access_token" {
			log.Printf("RequireAuth: using token from query param access_token (masked)")
		}

		if authHeader == "" {
			c.JSON(401, gin.H{"error": "missing authorization header"})
			c.Abort()
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || !strings.EqualFold(strings.TrimSpace(parts[0]), "Bearer") || strings.TrimSpace(parts[1]) == "" {
			c.JSON(401, gin.H{"error": "invalid authorization header format"})
			c.Abort()
			return
		}

		tokenString := strings.TrimSpace(parts[1])
		claims, err := jwtManager.VerifyToken(tokenString, "access")
		if err != nil {
			// Log underlying verification error as well
			log.Printf("RequireAuth: token verification failed: %v", err)
			if strings.Contains(strings.ToLower(err.Error()), "token is expired") || strings.Contains(strings.ToLower(err.Error()), "token expired") {
				c.JSON(401, gin.H{"error": "access token expired", "code": "token_expired"})
				c.Abort()
				return
			}
			c.JSON(401, gin.H{"error": "invalid token"})
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
