package middleware

import (
	"errors"
	"log"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/gin-gonic/gin"
)

var jwtManager *auth.Manager
var sessionStore *auth.SessionStore

func InitAuthMiddleware(cfg *config.Config) {
	if cfg != nil {
		config.ConfigInstance = cfg
	}
	effective := cfg
	if effective == nil {
		effective = config.ConfigInstance
	}
	if effective == nil {
		effective = &config.Config{}
	}

	expiryHours := (effective.Auth.AccessTokenExpireMinutes + 59) / 60
	if expiryHours <= 0 {
		expiryHours = 1
	}

	jwtManager = auth.NewManager(auth.JWTConfig{
		Secret:            auth.ResolveSharedJWTSecret(),
		ExpiryHours:       expiryHours,
		RefreshExpiryDays: effective.Auth.RefreshTokenExpireDays,
	})
	sessionStore = auth.NewSessionStore(effective)
}

func AuthSessionStore() *auth.SessionStore {
	return sessionStore
}

func setAuthContextFromSession(c *gin.Context, sessionData *auth.SessionData) {
	c.Set("user_id", sessionData.UserID)
	c.Set("username", sessionData.Username)
	c.Set("email", sessionData.Email)
	c.Set("is_admin", sessionData.IsAdmin)
	c.Set("role", sessionData.Role)
	c.Set("session_expires_at", sessionData.ExpiresAt.Format(time.RFC3339))
}

func setAuthContextFromClaims(c *gin.Context, claims *auth.TokenClaims) {
	c.Set("user_id", claims.UserID)
	c.Set("username", claims.Username)
	c.Set("email", claims.Email)
	c.Set("is_admin", claims.IsAdmin)
	c.Set("role", claims.Role)
}

func extractBearerTokenFromAuthorizationHeader(c *gin.Context) string {
	authHeader := strings.TrimSpace(c.GetHeader("Authorization"))
	if authHeader == "" {
		return ""
	}

	parts := strings.SplitN(authHeader, " ", 2)
	if len(parts) != 2 || !strings.EqualFold(strings.TrimSpace(parts[0]), "Bearer") {
		return ""
	}

	return strings.TrimSpace(parts[1])
}

// rejectPendingMFASession reports whether the session is a password-only
// pre-auth session still awaiting its TOTP challenge, and if so (and not
// allowed) responds with the mfa_challenge_required contract the frontend
// already understands.
func rejectPendingMFASession(c *gin.Context, sessionData *auth.SessionData, allowPendingMFA bool, abortOnFailure bool) bool {
	if sessionData == nil || !sessionData.MFAPending() || allowPendingMFA {
		return false
	}
	if abortOnFailure {
		c.JSON(401, gin.H{"error": "multi-factor challenge required", "code": "mfa_challenge_required"})
		c.Abort()
	}
	return true
}

func authenticateRequest(c *gin.Context, abortOnFailure bool) bool {
	return authenticateRequestAllowPendingMFA(c, abortOnFailure, false)
}

func authenticateRequestAllowPendingMFA(c *gin.Context, abortOnFailure bool, allowPendingMFA bool) bool {
	if jwtManager == nil {
		log.Printf("RequireAuth: jwt manager is not initialized")
		if abortOnFailure {
			c.JSON(500, gin.H{"error": "authentication service unavailable"})
			c.Abort()
		}
		return false
	}

	traceID := strings.TrimSpace(c.GetHeader("X-Trace-Id"))
	if traceID == "" {
		traceID = strings.TrimSpace(c.GetHeader("X-Request-Id"))
	}

	rawAuthorization := strings.TrimSpace(c.GetHeader("Authorization"))
	sessionCookie, sessionCookieErr := c.Cookie(auth.SessionCookieName)
	hasSessionCookie := sessionCookieErr == nil && strings.TrimSpace(sessionCookie) != ""
	bearerToken := extractBearerTokenFromAuthorizationHeader(c)
	if abortOnFailure {
		log.Printf(
			"RequireAuth: trace_id=%s has_authorization=%t has_session_cookie=%t has_bearer=%t RemoteAddr=%s ClientIP=%s",
			traceID,
			rawAuthorization != "",
			hasSessionCookie,
			bearerToken != "",
			c.Request.RemoteAddr,
			c.ClientIP(),
		)
	}

	if hasSessionCookie && sessionStore != nil {
		ctx := c.Request.Context()
		sessionData, err := sessionStore.Get(ctx, strings.TrimSpace(sessionCookie))
		if err == nil && sessionData != nil {
			if rejectPendingMFASession(c, sessionData, allowPendingMFA, abortOnFailure) {
				return false
			}
			if abortOnFailure {
				log.Printf("RequireAuth: trace_id=%s authenticated via session cookie", traceID)
			}
			setAuthContextFromSession(c, sessionData)
			return true
		}
		if abortOnFailure {
			if err != nil && !errors.Is(err, auth.ErrSessionNotFound) {
				log.Printf("RequireAuth: trace_id=%s session lookup failed: %v", traceID, err)
			} else {
				log.Printf("RequireAuth: trace_id=%s session cookie not found in store", traceID)
			}
		}
	}

	if bearerToken == "" {
		if abortOnFailure {
			c.JSON(401, gin.H{"error": "missing authentication credentials"})
			c.Abort()
		}
		return false
	}

	tokenString := bearerToken
	if sessionStore != nil {
		ctx := c.Request.Context()
		sessionData, err := sessionStore.Get(ctx, tokenString)
		if err == nil && sessionData != nil {
			if rejectPendingMFASession(c, sessionData, allowPendingMFA, abortOnFailure) {
				return false
			}
			if abortOnFailure {
				log.Printf("RequireAuth: trace_id=%s authenticated via bearer session token", traceID)
			}
			setAuthContextFromSession(c, sessionData)
			return true
		}
		if err != nil && !errors.Is(err, auth.ErrSessionNotFound) {
			if abortOnFailure {
				log.Printf("RequireAuth: trace_id=%s session lookup failed: %v", traceID, err)
				c.JSON(401, gin.H{"error": "invalid session"})
				c.Abort()
			}
			return false
		}
	}

	claims, err := jwtManager.VerifyToken(tokenString, "access")
	if err != nil {
		if abortOnFailure {
			log.Printf("RequireAuth: trace_id=%s token verification failed: %v", traceID, err)
			if strings.Contains(strings.ToLower(err.Error()), "token is expired") || strings.Contains(strings.ToLower(err.Error()), "token expired") {
				c.JSON(401, gin.H{"error": "access token expired", "code": "token_expired"})
				c.Abort()
				return false
			}
			c.JSON(401, gin.H{"error": "invalid token"})
			c.Abort()
		}
		return false
	}

	if abortOnFailure {
		log.Printf("RequireAuth: trace_id=%s authenticated via bearer jwt", traceID)
	}
	setAuthContextFromClaims(c, claims)
	return true
}

func TrySetAuthContext(c *gin.Context) bool {
	if _, exists := c.Get("user_id"); exists {
		return true
	}
	return authenticateRequest(c, false)
}

func RequireAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !authenticateRequest(c, true) {
			return
		}
		c.Next()
	}
}

// RequireAuthAllowPendingMFA authenticates like RequireAuth but additionally
// accepts sessions still awaiting their TOTP challenge. Reserved for the
// /auth/2fa/challenge endpoint, which is the only place a pending session may
// be used.
func RequireAuthAllowPendingMFA() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !authenticateRequestAllowPendingMFA(c, true, true) {
			return
		}
		c.Next()
	}
}
