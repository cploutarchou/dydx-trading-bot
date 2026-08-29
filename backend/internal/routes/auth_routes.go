// Package routes provides HTTP route registration and handlers for the dYdX backend API authentication features.
package routes

import (
	"crypto/subtle"
	"database/sql"
	"errors"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
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
		authRoutes.GET("/registration-status", registrationStatusHandler(database))
		authRoutes.GET("/session", middleware.RequireAuth(), authSessionHandler(database))
		authRoutes.POST("/login", loginHandler(database))
		authRoutes.POST("/refresh", refreshHandler(database))
		authRoutes.POST("/logout", logoutHandler())
		authRoutes.POST("/2fa/setup", middleware.RequireAuth(), setup2FAHandler(database))
		authRoutes.POST("/2fa/verify", middleware.RequireAuth(), verify2FAHandler(database))
		// Completes the login-time TOTP challenge for users with MFA enrolled.
		// The only route that accepts sessions still pending their challenge.
		authRoutes.POST("/2fa/challenge", middleware.RequireAuthAllowPendingMFA(), mfaChallengeHandler(database))
		authRoutes.PUT("/change-password", middleware.RequireAuth(), changePasswordHandler(database))
	}

	// User routes (require authentication)
	userRoutes := router.Group("/api/v1/users")
	{
		userRoutes.Use(middleware.RequireAuth())
		userRoutes.GET("/me", getCurrentUserHandler(database))
	}

	meRoutes := router.Group("/api/v1")
	{
		meRoutes.Use(middleware.RequireAuth())
		meRoutes.GET("/me", getCurrentUserHandler(database))
	}

	// Profile routes (require authentication)
	profileRoutes := router.Group("/api/v1/profile")
	{
		profileRoutes.Use(middleware.RequireAuth())
		profileRoutes.PUT("", updateProfileHandler(database))
	}
}

func authSessionHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		getCurrentUserHandler(database)(c)
	}
}

// RegisterRequest represents the payload for user registration.
type RegisterRequest struct {
	Username       string `json:"username" binding:"required"`
	Email          string `json:"email" binding:"required,email"`
	Password       string `json:"password" binding:"required,min=8"`
	InvitationCode string `json:"invitation_code"`
}

type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

type TokenResponse struct {
	AccessToken      string `json:"access_token,omitempty"`
	RefreshToken     string `json:"refresh_token,omitempty"`
	TokenType        string `json:"token_type"`
	ExpiresIn        int    `json:"expires_in"`
	SessionExpiresAt string `json:"session_expires_at,omitempty"`
}

type UserResponse struct {
	ID                     int    `json:"id"`
	Username               string `json:"username"`
	Email                  string `json:"email"`
	Role                   string `json:"role"`
	MaxActiveBacktests     int    `json:"max_active_backtests"`
	MaxStrategies          int    `json:"max_strategies"`
	MaxBotInstances        int    `json:"max_bot_instances"`
	FullName               string `json:"full_name"`
	Avatar                 string `json:"avatar"`
	IsActive               bool   `json:"is_active"`
	IsAdmin                bool   `json:"is_admin"`
	MFAEnabled             bool   `json:"mfa_enabled"`
	PrivilegedMFARequired  bool   `json:"privileged_mfa_required"`
	PasswordChangeRequired bool   `json:"password_change_required"`
	CreatedAt              string `json:"created_at"`
	UpdatedAt              string `json:"updated_at"`
}

type RegistrationStatusResponse struct {
	Enabled            bool   `json:"enabled"`
	Reason             string `json:"reason"`
	Mode               string `json:"mode"`
	InvitationRequired bool   `json:"invitation_required"`
}

const maxSessionTTL = 24 * time.Hour

// mfaChallengeTTL bounds the lifetime of a password-only login session that is
// still awaiting its TOTP challenge.
const mfaChallengeTTL = 5 * time.Minute

// sessionTTL returns the configured session lifetime capped at maxSessionTTL (1 day).
// It reads SESSION_TTL_HOURS first, then falls back to REFRESH_TOKEN_EXPIRE_DAYS converted
// to hours, defaulting to 24 hours when neither is set.
func sessionTTL() time.Duration {
	if v := os.Getenv("SESSION_TTL_HOURS"); v != "" {
		if n, err := strconv.Atoi(strings.TrimSpace(v)); err == nil && n > 0 {
			d := time.Duration(n) * time.Hour
			if d > maxSessionTTL {
				return maxSessionTTL
			}
			return d
		}
	}
	if v := os.Getenv("REFRESH_TOKEN_EXPIRE_DAYS"); v != "" {
		if n, err := strconv.Atoi(strings.TrimSpace(v)); err == nil && n > 0 {
			d := time.Duration(n) * 24 * time.Hour
			if d > maxSessionTTL {
				return maxSessionTTL
			}
			return d
		}
	}
	return maxSessionTTL
}

func shouldReturnLegacyAuthTokens() bool {
	value := strings.TrimSpace(strings.ToLower(os.Getenv("AUTH_RETURN_LEGACY_TOKENS")))
	if value == "true" || value == "1" || value == "yes" {
		return true
	}
	return strings.EqualFold(os.Getenv("APP_ENV"), "test")
}

func authCookieSecure() bool {
	// Accept both 'production' and 'prod' (platform.yml uses 'prod').
	appEnv := strings.ToLower(strings.TrimSpace(os.Getenv("APP_ENV")))
	if appEnv == "production" || appEnv == "prod" {
		return true
	}
	// Also accept an explicit opt-in for staging/custom HTTPS environments.
	tlsCert := strings.TrimSpace(os.Getenv("TLS_CERT_FILE"))
	forceHTTPS := strings.ToLower(strings.TrimSpace(os.Getenv("FORCE_HTTPS")))
	return tlsCert != "" || forceHTTPS == "true" || forceHTTPS == "1"
}

func authCookieSameSite() http.SameSite {
	value := strings.ToLower(strings.TrimSpace(os.Getenv("AUTH_COOKIE_SAMESITE")))
	switch value {
	case "none", "no_restriction":
		return http.SameSiteNoneMode
	case "strict":
		return http.SameSiteStrictMode
	case "lax", "":
		return http.SameSiteLaxMode
	default:
		return http.SameSiteLaxMode
	}
}

func authCookieDomain() string {
	return strings.TrimSpace(os.Getenv("AUTH_COOKIE_DOMAIN"))
}

func effectiveAuthCookieSecure() bool {
	if authCookieSameSite() == http.SameSiteNoneMode {
		// Browsers reject SameSite=None cookies unless Secure is set.
		return true
	}
	return authCookieSecure()
}

func refreshTokenMaxAge() int {
	if config.ConfigInstance != nil && config.ConfigInstance.Auth.RefreshTokenExpireDays > 0 {
		return config.ConfigInstance.Auth.RefreshTokenExpireDays * 86400
	}
	return 7 * 86400 // default: 7 days
}

func setSessionCookie(c *gin.Context, token string, maxAge int) {
	secure := effectiveAuthCookieSecure()
	sameSite := authCookieSameSite()
	domain := authCookieDomain()
	http.SetCookie(c.Writer, &http.Cookie{
		Name:     auth.SessionCookieName,
		Value:    token,
		Domain:   domain,
		Path:     "/",
		MaxAge:   maxAge,
		HttpOnly: true,
		Secure:   secure,
		SameSite: sameSite,
	})
}

func setRefreshTokenCookie(c *gin.Context, token string) {
	secure := effectiveAuthCookieSecure()
	sameSite := authCookieSameSite()
	domain := authCookieDomain()
	http.SetCookie(c.Writer, &http.Cookie{
		Name:     "refresh_token",
		Value:    token,
		Domain:   domain,
		Path:     "/api/v1/auth",
		MaxAge:   refreshTokenMaxAge(),
		HttpOnly: true,
		Secure:   secure,
		SameSite: sameSite,
	})
}

func clearAuthCookies(c *gin.Context) {
	secure := effectiveAuthCookieSecure()
	sameSite := authCookieSameSite()
	domain := authCookieDomain()
	for _, name := range []string{auth.SessionCookieName, "access_token", "refresh_token", "token", "jwt"} {
		expirePaths := []string{"/"}
		if name == "refresh_token" {
			expirePaths = append(expirePaths, "/api/v1/auth")
		}

		for _, path := range expirePaths {
			http.SetCookie(c.Writer, &http.Cookie{
				Name:     name,
				Value:    "",
				Domain:   domain,
				Path:     path,
				MaxAge:   -1,
				HttpOnly: true,
				Secure:   secure,
				SameSite: sameSite,
			})
		}
	}
}

func requestSessionToken(c *gin.Context) string {
	if cookieVal, err := c.Cookie(auth.SessionCookieName); err == nil && strings.TrimSpace(cookieVal) != "" {
		return strings.TrimSpace(cookieVal)
	}

	authHeader := strings.TrimSpace(c.GetHeader("Authorization"))
	parts := strings.SplitN(authHeader, " ", 2)
	if len(parts) == 2 && strings.EqualFold(strings.TrimSpace(parts[0]), "Bearer") {
		return strings.TrimSpace(parts[1])
	}
	return ""
}

// generateRefreshTokenForUser mints a refresh JWT bound to the user's current
// session generation, so a password-change bump invalidates it.
func generateRefreshTokenForUser(c *gin.Context, user *models.User, role string) (string, error) {
	gen := int64(0)
	if store := middleware.AuthSessionStore(); store != nil {
		gen = store.CurrentUserGeneration(c.Request.Context(), user.ID)
	}
	return services.GenerateRefreshTokenWithGeneration(user.ID, user.Username, user.IsAdmin, role, gen)
}

func createSessionForUser(c *gin.Context, user *models.User, role string) (string, auth.SessionData, error) {
	store := middleware.AuthSessionStore()
	if store == nil {
		return "", auth.SessionData{}, nil
	}

	sessionToken, sessionData, err := store.Create(c.Request.Context(), auth.SessionData{
		UserID:   user.ID,
		Username: user.Username,
		Email:    user.Email,
		Role:     role,
		IsAdmin:  user.IsAdmin,
	}, sessionTTL())
	if err != nil {
		return "", auth.SessionData{}, err
	}

	return sessionToken, sessionData, nil
}

type registrationMode string

const (
	registrationModeOpen           registrationMode = "open"
	registrationModeDisabled       registrationMode = "disabled"
	registrationModeInvitationOnly registrationMode = "invitation_only"
	maxFailedLoginAttempts                          = 5
)

var loginLockoutDuration = 15 * time.Minute

type registrationPolicy struct {
	Mode               registrationMode
	Enabled            bool
	Reason             string
	InvitationCode     string
	InvitationRequired bool
}

func toUserResponse(user *models.User, privilegedMFARequired bool) UserResponse {
	return UserResponse{
		ID:                     user.ID,
		Username:               user.Username,
		Email:                  user.Email,
		Role:                   models.NormalizeUserRole(user.Role, user.IsAdmin),
		MaxActiveBacktests:     user.MaxActiveBacktests,
		MaxStrategies:          user.MaxStrategies,
		MaxBotInstances:        user.MaxBotInstances,
		FullName:               user.FullName,
		Avatar:                 user.Avatar,
		IsActive:               user.IsActive,
		IsAdmin:                user.IsAdmin,
		MFAEnabled:             user.MFAEnabled,
		PrivilegedMFARequired:  privilegedMFARequired,
		PasswordChangeRequired: user.PasswordChangeRequired,
		CreatedAt:              user.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt:              user.UpdatedAt.UTC().Format(time.RFC3339),
	}
}

func setup2FAHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(userID)
		if err != nil || user == nil {
			c.JSON(http.StatusNotFound, gin.H{"success": false, "message": "User not found"})
			return
		}

		mfaService := services.NewMFAService(repository.NewUserMFARepository(database))
		setup, err := mfaService.Setup(user)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
			return
		}

		writeAuditLog(database, c, "auth.mfa.setup", "user", stringPointer(strconv.Itoa(userID)), gin.H{
			"role":                   user.Role,
			"mfa_mandatory_for_role": models.IsMFAMandatoryRole(user.Role),
		}, "success")

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "2FA setup initialized",
			"data": gin.H{
				"secret":       setup.Secret,
				"qr_code":      setup.QRCode,
				"backup_codes": setup.BackupCodes,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func verify2FAHandler(database *sql.DB) gin.HandlerFunc {
	type verify2FARequest struct {
		Token string `json:"token" binding:"required,len=6"`
	}

	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		var req verify2FARequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Invalid request payload", "error": err.Error()})
			return
		}

		mfaService := services.NewMFAService(repository.NewUserMFARepository(database))
		if err := mfaService.Verify(userID, req.Token); err != nil {
			writeAuditLog(database, c, "auth.mfa.verify", "user", stringPointer(strconv.Itoa(userID)), gin.H{"result": "failed"}, "failure")
			c.JSON(http.StatusUnauthorized, gin.H{"success": false, "message": err.Error()})
			return
		}

		userRepo := repository.NewUserRepository(database)
		if err := userRepo.SetMFAEnabled(userID, true); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
			return
		}

		writeAuditLog(database, c, "auth.mfa.verify", "user", stringPointer(strconv.Itoa(userID)), gin.H{"result": "verified"}, "success")

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "2FA verified successfully",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

// mfaChallengeHandler completes the login-time TOTP challenge. It is the only
// endpoint that accepts a pending (password-only) session: a valid code
// promotes the session to full authentication and issues the refresh cookie
// that the login handler deliberately withheld.
func mfaChallengeHandler(database *sql.DB) gin.HandlerFunc {
	type mfaChallengeRequest struct {
		Token string `json:"token" binding:"required,len=6"`
	}

	return func(c *gin.Context) {
		var req mfaChallengeRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Invalid request payload", "error": err.Error()})
			return
		}

		store := middleware.AuthSessionStore()
		if store == nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "Session store unavailable"})
			return
		}

		sessionToken := requestSessionToken(c)
		if sessionToken == "" {
			c.JSON(http.StatusUnauthorized, gin.H{"success": false, "message": "Authentication required", "error": "missing authentication credentials"})
			return
		}

		sessionData, err := store.Get(c.Request.Context(), sessionToken)
		if err != nil || sessionData == nil {
			c.JSON(http.StatusUnauthorized, gin.H{"success": false, "message": "Session expired, sign in again", "error": "invalid session"})
			return
		}
		if !sessionData.MFAPending() {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "No MFA challenge in progress for this session", "code": "mfa_challenge_not_pending"})
			return
		}

		userID := sessionData.UserID
		requestIP := c.ClientIP()
		userAgent := c.GetHeader("User-Agent")

		mfaService := services.NewMFAService(repository.NewUserMFARepository(database))
		if err := mfaService.Verify(userID, req.Token); err != nil {
			writeAuditLog(database, c, "auth.mfa.challenge", "user", stringPointer(strconv.Itoa(userID)), gin.H{"result": "failed"}, "failure")

			// Bound guessing: burn the pending session after too many bad codes.
			sessionData.ChallengeAttempts++
			if sessionData.ChallengeAttempts >= auth.MaxMFAPreAuthAttempts {
				_ = store.Delete(c.Request.Context(), sessionToken)
				clearAuthCookies(c)
				logSecurityLoginEvent(database, &userID, sessionData.Username, "login", "failure", "mfa_challenge_attempts_exceeded", requestIP, userAgent)
				c.JSON(http.StatusUnauthorized, gin.H{
					"success": false,
					"message": "Too many invalid codes. Please sign in again.",
					"error":   "Too many invalid codes. Please sign in again.",
					"code":    "mfa_challenge_expired",
				})
				return
			}
			if updateErr := store.Update(c.Request.Context(), sessionToken, *sessionData); updateErr != nil {
				log.Printf("mfaChallengeHandler: failed to record challenge attempt: %v", updateErr)
			}
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"message": "Invalid authenticator code",
				"error":   "Invalid authenticator code",
				"code":    "invalid_mfa_code",
			})
			return
		}

		// Reload the user so role/admin flags are current at promotion time.
		userRepo := repository.NewUserRepository(database)
		user, userErr := userRepo.GetByID(userID)
		if userErr != nil || user == nil || !user.IsActive {
			_ = store.Delete(c.Request.Context(), sessionToken)
			clearAuthCookies(c)
			c.JSON(http.StatusUnauthorized, gin.H{"success": false, "message": "User not found or inactive"})
			return
		}

		now := time.Now().UTC()
		sessionData.MFAVerifiedAt = &now
		sessionData.Role = models.NormalizeUserRole(user.Role, user.IsAdmin)
		sessionData.IsAdmin = user.IsAdmin
		// The short challenge TTL applied only to the pending phase; a promoted
		// session gets the full configured lifetime.
		sessionData.ExpiresAt = now.Add(sessionTTL())
		if updateErr := store.Update(c.Request.Context(), sessionToken, *sessionData); updateErr != nil {
			log.Printf("mfaChallengeHandler: failed to promote session: %v", updateErr)
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "Failed to finalize login"})
			return
		}

		_ = userRepo.UpdateLastLogin(user.ID)
		logSecurityLoginEvent(database, &user.ID, user.Username, "login", "success", "authenticated_mfa", requestIP, userAgent)
		writeAuditLog(database, c, "auth.mfa.challenge", "user", stringPointer(strconv.Itoa(userID)), gin.H{"result": "verified"}, "success")

		// Issue the refresh cookie that login withheld until the second factor
		// completed (mirrors the post-password login path).
		jwtRefreshToken, rtErr := generateRefreshTokenForUser(c, user, sessionData.Role)
		if rtErr != nil {
			log.Printf("mfaChallengeHandler: failed to generate refresh token cookie: %v", rtErr)
		}

		setSessionCookie(c, sessionToken, int(sessionTTL().Seconds()))
		if rtErr == nil && jwtRefreshToken != "" {
			setRefreshTokenCookie(c, jwtRefreshToken)
		}

		response := TokenResponse{
			TokenType:        "session",
			ExpiresIn:        int(sessionTTL().Seconds()),
			SessionExpiresAt: sessionData.ExpiresAt.Format(time.RFC3339),
		}
		if shouldReturnLegacyAuthTokens() {
			accessToken, tokenErr := services.GenerateAccessTokenWithRole(user.ID, user.Username, user.IsAdmin, sessionData.Role)
			if tokenErr != nil {
				log.Printf("mfaChallengeHandler: failed to generate access token: %v", tokenErr)
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Failed to generate token"})
				return
			}
			response.AccessToken = accessToken
			response.RefreshToken = jwtRefreshToken
			response.TokenType = "bearer"
			response.ExpiresIn = 1800
		}

		c.JSON(http.StatusOK, response)
	}
}

func stringPointer(value string) *string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return nil
	}
	return &trimmed
}

// registerHandler handles user registration
func registerHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		policy, err := resolveRegistrationPolicy(database)
		if err != nil {
			log.Printf("Failed to resolve registration setting: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "Failed to determine registration availability",
			})
			return
		}
		if !policy.Enabled {
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"error":   policy.Reason,
			})
			return
		}

		var req RegisterRequest

		// Bind JSON with error handling
		if err := c.ShouldBindJSON(&req); err != nil {
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

		if policy.Mode == registrationModeInvitationOnly {
			providedCode := strings.TrimSpace(req.InvitationCode)
			if providedCode == "" {
				c.JSON(http.StatusForbidden, gin.H{
					"success": false,
					"error":   "A valid invitation code is required to register",
				})
				return
			}
		}

		requiresOneTimeTokenRedemption := false
		providedCode := strings.TrimSpace(req.InvitationCode)
		if policy.Mode == registrationModeInvitationOnly {
			sharedCode := strings.TrimSpace(policy.InvitationCode)
			sharedMatch := sharedCode != "" && subtle.ConstantTimeCompare([]byte(providedCode), []byte(sharedCode)) == 1
			requiresOneTimeTokenRedemption = !sharedMatch
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
			Username:               req.Username,
			Email:                  req.Email,
			Role:                   models.NormalizeUserRole("", false),
			Password:               string(hashedPassword),
			IsActive:               true,
			IsAdmin:                false,
			PasswordChangeRequired: false,
		}

		// User creation and one-time invitation redemption must commit
		// atomically: the historical compensation-delete could itself fail and
		// leave an orphan user with a consumed-or-not invite.
		if requiresOneTimeTokenRedemption {
			tx, txErr := database.BeginTx(c.Request.Context(), nil)
			if txErr != nil {
				log.Printf("Failed to open registration transaction: %v", txErr)
				c.JSON(http.StatusInternalServerError, gin.H{
					"success": false,
					"error":   "Failed to register user",
				})
				return
			}
			committed := false
			defer func() {
				if !committed {
					_ = tx.Rollback()
				}
			}()

			if err := userRepo.WithTx(tx).Create(user); err != nil {
				log.Printf("Failed to create user: %v", err)
				c.JSON(http.StatusBadRequest, gin.H{
					"success": false,
					"error":   "User already exists",
				})
				return
			}

			invitationRepo := repository.NewInvitationTokenRepository(database)
			redeemed, redeemErr := invitationRepo.WithTx(tx).Redeem(providedCode, user.ID)
			if redeemErr != nil {
				log.Printf("Failed to redeem invitation token: %v", redeemErr)
				c.JSON(http.StatusInternalServerError, gin.H{
					"success": false,
					"error":   "Failed to validate invitation token",
				})
				return
			}
			if !redeemed {
				c.JSON(http.StatusForbidden, gin.H{
					"success": false,
					"error":   "Invitation code is invalid or already used",
				})
				return
			}
			if commitErr := tx.Commit(); commitErr != nil {
				log.Printf("Failed to commit registration transaction: %v", commitErr)
				c.JSON(http.StatusInternalServerError, gin.H{
					"success": false,
					"error":   "Failed to register user",
				})
				return
			}
			committed = true
		} else {
			err = userRepo.Create(user)
			if err != nil {
				log.Printf("Failed to create user: %v", err)
				c.JSON(http.StatusBadRequest, gin.H{
					"success": false,
					"error":   "User already exists",
				})
				return
			}
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

func registrationStatusHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		policy, err := resolveRegistrationPolicy(database)
		if err != nil {
			log.Printf("Failed to resolve registration status: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "Failed to determine registration availability",
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"data": RegistrationStatusResponse{
				Enabled:            policy.Enabled,
				Reason:             policy.Reason,
				Mode:               string(policy.Mode),
				InvitationRequired: policy.InvitationRequired,
			},
		})
	}
}

func resolveRegistrationPolicy(database *sql.DB) (*registrationPolicy, error) {
	mode, err := resolveRegistrationMode(database)
	if err != nil {
		return nil, err
	}

	invitationCode, err := getPlatformSettingValue(database, "registration_invitation_code")
	if err != nil {
		return nil, err
	}
	invitationCode = strings.TrimSpace(invitationCode)

	policy := &registrationPolicy{
		Mode:               mode,
		Enabled:            true,
		Reason:             "Public registration is enabled",
		InvitationCode:     invitationCode,
		InvitationRequired: mode == registrationModeInvitationOnly,
	}

	switch mode {
	case registrationModeDisabled:
		policy.Enabled = false
		policy.Reason = "Public registration is currently disabled by the administrator"
	case registrationModeInvitationOnly:
		if invitationCode == "" {
			policy.Reason = "Registration requires a valid invitation token"
		} else {
			policy.Reason = "Registration requires a valid invitation code or invitation token"
		}
	default:
		policy.Mode = registrationModeOpen
	}

	return policy, nil
}

func resolveRegistrationMode(database *sql.DB) (registrationMode, error) {
	modeValue, err := getPlatformSettingValue(database, "registration_mode")
	if err != nil {
		return registrationModeOpen, err
	}

	modeCandidate := strings.TrimSpace(strings.ToLower(modeValue))
	switch modeCandidate {
	case "open", "public", "enabled":
		return registrationModeOpen, nil
	case "disabled", "closed", "off":
		return registrationModeDisabled, nil
	case "invitation_only", "invite_only", "invitation":
		return registrationModeInvitationOnly, nil
	}

	if modeCandidate != "" {
		return registrationModeOpen, nil
	}

	enabled, err := isPublicRegistrationEnabled(database)
	if err != nil {
		return registrationModeOpen, err
	}
	if enabled {
		return registrationModeOpen, nil
	}
	return registrationModeDisabled, nil
}

func getPlatformSettingValue(database *sql.DB, key string) (string, error) {
	settingsRepo := repository.NewSettingsRepository(database)
	setting, err := settingsRepo.GetBotSettingBySectionAndKey("platform", key)
	if err != nil {
		if strings.Contains(strings.ToLower(err.Error()), "no such table") || strings.Contains(strings.ToLower(err.Error()), "does not exist") {
			return "", nil
		}
		return "", err
	}
	if setting == nil {
		return "", nil
	}

	return setting.Value, nil
}

func isPublicRegistrationEnabled(database *sql.DB) (bool, error) {
	settingsRepo := repository.NewSettingsRepository(database)
	setting, err := settingsRepo.GetBotSettingBySectionAndKey("platform", "allow_public_registration")
	if err != nil {
		if strings.Contains(strings.ToLower(err.Error()), "no such table") || strings.Contains(strings.ToLower(err.Error()), "does not exist") {
			return true, nil
		}
		return false, err
	}
	if setting == nil {
		return true, nil
	}

	value := strings.TrimSpace(strings.ToLower(setting.Value))
	switch value {
	case "", "true", "1", "yes", "on":
		return true, nil
	case "false", "0", "no", "off":
		return false, nil
	default:
		return true, nil
	}
}

func isSchemaEvolutionError(err error) bool {
	if err == nil {
		return false
	}
	lower := strings.ToLower(err.Error())
	return strings.Contains(lower, "no such table") ||
		strings.Contains(lower, "does not exist") ||
		strings.Contains(lower, "no such column")
}

func readUserLockState(database *sql.DB, userID int) (failedAttempts int, lockedUntil *time.Time, err error) {
	err = database.QueryRow(
		`SELECT COALESCE(failed_login_attempts, 0), locked_until FROM users WHERE id = $1`,
		userID,
	).Scan(&failedAttempts, &lockedUntil)
	if isSchemaEvolutionError(err) {
		return 0, nil, nil
	}
	if err != nil {
		return 0, nil, err
	}
	return failedAttempts, lockedUntil, nil
}

func incrementFailedLogin(database *sql.DB, userID int) {
	_, err := database.Exec(
		`UPDATE users
		 SET failed_login_attempts = COALESCE(failed_login_attempts, 0) + 1,
		     locked_until = CASE
		         WHEN COALESCE(failed_login_attempts, 0) + 1 >= $1 THEN $2
		         ELSE locked_until
		     END
		 WHERE id = $3`,
		maxFailedLoginAttempts,
		time.Now().UTC().Add(loginLockoutDuration),
		userID,
	)
	if err != nil && !isSchemaEvolutionError(err) {
		log.Printf("failed to increment failed login attempts for user_id=%d: %v", userID, err)
	}
}

func resetFailedLogin(database *sql.DB, userID int) {
	_, err := database.Exec(`UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = $1`, userID)
	if err != nil && !isSchemaEvolutionError(err) {
		log.Printf("failed to reset failed login attempts for user_id=%d: %v", userID, err)
	}
}

func logSecurityLoginEvent(database *sql.DB, userID *int, username, eventType, outcome, reason, ipAddress, userAgent string) {
	trimmedUsername := strings.TrimSpace(username)
	if trimmedUsername == "" {
		trimmedUsername = "unknown"
	}

	_, err := database.Exec(
		`INSERT INTO security_login_events (user_id, username, event_type, outcome, reason, ip_address, user_agent, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		userID,
		trimmedUsername,
		eventType,
		outcome,
		reason,
		ipAddress,
		userAgent,
		time.Now().UTC(),
	)
	if err != nil && !isSchemaEvolutionError(err) {
		log.Printf("failed to write security_login_event for username=%s: %v", trimmedUsername, err)
	}
}

// loginHandler handles user login
func loginHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req LoginRequest

		// Bind JSON with error handling
		if err := c.ShouldBindJSON(&req); err != nil {
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
		user, err := userRepo.GetByUsernameContext(c.Request.Context(), req.Username)
		requestIP := c.ClientIP()
		userAgent := c.GetHeader("User-Agent")
		if err != nil {
			log.Printf("login failed: unknown username (error: %v)", err)
			logSecurityLoginEvent(database, nil, req.Username, "login", "failure", "invalid_credentials", requestIP, userAgent)
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "Invalid credentials",
			})
			return
		}

		if user == nil {
			log.Printf("login failed: unknown username")
			logSecurityLoginEvent(database, nil, req.Username, "login", "failure", "invalid_credentials", requestIP, userAgent)
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "Invalid credentials",
			})
			return
		}

		if !user.IsActive {
			logSecurityLoginEvent(database, &user.ID, user.Username, "login", "failure", "account_inactive", requestIP, userAgent)
			c.JSON(http.StatusForbidden, gin.H{
				"success": false,
				"error":   "Account is inactive",
			})
			return
		}

		failedAttempts, lockedUntil, lockErr := readUserLockState(database, user.ID)
		if lockErr != nil {
			log.Printf("Failed to read lock state for user=%s: %v", user.Username, lockErr)
		}
		if lockedUntil != nil && lockedUntil.After(time.Now().UTC()) {
			logSecurityLoginEvent(database, &user.ID, user.Username, "login", "failure", "account_locked", requestIP, userAgent)
			c.JSON(http.StatusTooManyRequests, gin.H{
				"success": false,
				"error":   "Account temporarily locked due to failed login attempts",
				"data": gin.H{
					"locked_until": lockedUntil.UTC().Format(time.RFC3339),
				},
			})
			return
		}

		// Verify password

		err = bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(req.Password))
		if err != nil {
			log.Printf("login failed: password mismatch")
			incrementFailedLogin(database, user.ID)
			logSecurityLoginEvent(database, &user.ID, user.Username, "login", "failure", "invalid_credentials", requestIP, userAgent)
			if failedAttempts+1 >= maxFailedLoginAttempts {
				c.JSON(http.StatusTooManyRequests, gin.H{
					"success": false,
					"error":   "Too many failed login attempts. Account temporarily locked.",
				})
				return
			}
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "Invalid credentials",
			})
			return
		}

		role := models.NormalizeUserRole(user.Role, user.IsAdmin)

		// Users with TOTP enrolled must complete the second factor before any
		// session, refresh token, or bearer token is issued. The pending
		// session created here is only accepted by POST /auth/2fa/challenge.
		if user.MFAEnabled {
			resetFailedLogin(database, user.ID)
			logSecurityLoginEvent(database, &user.ID, user.Username, "login", "pending", "mfa_challenge_required", requestIP, userAgent)

			store := middleware.AuthSessionStore()
			if store == nil {
				log.Printf("loginHandler: cannot issue MFA challenge without a session store for user=%d", user.ID)
				c.JSON(http.StatusInternalServerError, gin.H{
					"success": false,
					"error":   "Authentication temporarily unavailable",
				})
				return
			}
			sessionToken, sessionData, err := store.Create(c.Request.Context(), auth.SessionData{
				UserID:      user.ID,
				Username:    user.Username,
				Email:       user.Email,
				Role:        role,
				IsAdmin:     user.IsAdmin,
				MFARequired: true,
			}, mfaChallengeTTL)
			if err != nil {
				log.Printf("loginHandler: failed to create pending MFA session: %v", err)
				c.JSON(http.StatusInternalServerError, gin.H{
					"success": false,
					"error":   "Failed to create auth session",
				})
				return
			}

			clearAuthCookies(c)
			setSessionCookie(c, sessionToken, int(mfaChallengeTTL.Seconds()))

			c.JSON(http.StatusOK, gin.H{
				"success":            true,
				"message":            "Multi-factor authentication required",
				"mfa_required":       true,
				"code":               "mfa_challenge_required",
				"token_type":         "mfa_challenge",
				"expires_in":         int(mfaChallengeTTL.Seconds()),
				"session_expires_at": sessionData.ExpiresAt.Format(time.RFC3339),
			})
			return
		}

		sessionToken, sessionData, err := createSessionForUser(c, user, role)
		if err != nil {
			log.Printf("Failed to create auth session: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "Failed to create auth session",
			})
			return
		}

		// Update last_login
		_ = userRepo.UpdateLastLogin(user.ID)
		resetFailedLogin(database, user.ID)
		logSecurityLoginEvent(database, &user.ID, user.Username, "login", "success", "authenticated", requestIP, userAgent)

		// Always issue a refresh_token HttpOnly cookie so the JWT refresh path
		// remains available even if the session store is cleared (e.g., restart
		// without Redis). The cookie is never exposed to JS.
		jwtRefreshToken, rtErr := generateRefreshTokenForUser(c, user, role)
		if rtErr != nil {
			log.Printf("loginHandler: failed to generate refresh token cookie: %v", rtErr)
		}

		clearAuthCookies(c)
		if sessionToken != "" {
			setSessionCookie(c, sessionToken, int(sessionTTL().Seconds()))
		}
		if rtErr == nil && jwtRefreshToken != "" {
			setRefreshTokenCookie(c, jwtRefreshToken)
		}

		response := TokenResponse{
			TokenType:        "session",
			ExpiresIn:        int(sessionTTL().Seconds()),
			SessionExpiresAt: sessionData.ExpiresAt.Format(time.RFC3339),
		}

		// If session storage is unavailable (e.g. Redis/session store misconfigured),
		// `sessionToken` is empty and cookie-session auth cannot work for /users/me.
		// Fall back to bearer access tokens so auth remains functional.
		issueBearerFallback := sessionToken == ""
		if issueBearerFallback {
			log.Printf("loginHandler: session store unavailable, issuing bearer fallback token for user=%d", user.ID)
		}

		if shouldReturnLegacyAuthTokens() || issueBearerFallback {
			accessToken, err := services.GenerateAccessTokenWithRole(user.ID, user.Username, user.IsAdmin, role)
			if err != nil {
				log.Printf("Failed to generate access token: %v", err)
				c.JSON(http.StatusInternalServerError, gin.H{
					"success": false,
					"error":   "Failed to generate token",
				})
				return
			}
			response.AccessToken = accessToken
			response.RefreshToken = jwtRefreshToken
			response.TokenType = "bearer"
			response.ExpiresIn = 1800
		}

		c.JSON(http.StatusOK, response)
	}
}

func changePasswordHandler(database *sql.DB) gin.HandlerFunc {
	type changePasswordRequest struct {
		CurrentPassword string `json:"current_password" binding:"required"`
		NewPassword     string `json:"new_password" binding:"required,min=8"`
	}

	return func(c *gin.Context) {
		userIDValue, exists := c.Get("user_id")
		if !exists {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"message": "Not authenticated",
			})
			return
		}

		userID, ok := userIDValue.(int)
		if !ok {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"message": "Invalid user context",
			})
			return
		}

		var req changePasswordRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "Invalid request payload",
				"error":   err.Error(),
			})
			return
		}

		if strings.TrimSpace(req.NewPassword) == "" || len(req.NewPassword) < 8 {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "New password must be at least 8 characters",
			})
			return
		}

		if req.CurrentPassword == req.NewPassword {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "New password must be different from the current password",
			})
			return
		}

		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(userID)
		if err != nil || user == nil {
			c.JSON(http.StatusNotFound, gin.H{
				"success": false,
				"message": "User not found",
			})
			return
		}

		if err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(req.CurrentPassword)); err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"message": "Current password is incorrect",
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
				"error":   err.Error(),
			})
			return
		}

		// A password change revokes every session issued for the account (an
		// attacker holding an active session is logged out with the victim);
		// the client must sign in again. Legacy refresh JWTs are not covered —
		// they need the server-side registry tracked in the improvement plan.
		if store := middleware.AuthSessionStore(); store != nil {
			if err := store.BumpUserGeneration(c.Request.Context(), user.ID); err != nil {
				log.Printf("changePasswordHandler: failed to revoke sessions for user=%d: %v", user.ID, err)
			}
		}
		clearAuthCookies(c)

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Password updated successfully",
			"data": gin.H{
				"user": toUserResponse(user, middleware.IsPrivilegedMFARequired(database)),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

// refreshHandler handles token refresh
func refreshHandler(database *sql.DB) gin.HandlerFunc {
	type RefreshRequest struct {
		RefreshToken string `json:"refresh_token"`
	}

	return func(c *gin.Context) {
		var req RefreshRequest
		if c.Request.ContentLength > 0 {
			_ = c.ShouldBindJSON(&req)
		}

		if req.RefreshToken == "" {
			sessionToken := requestSessionToken(c)
			if sessionToken != "" {
				store := middleware.AuthSessionStore()
				if store != nil {
					sessionData, err := store.Refresh(c.Request.Context(), sessionToken, sessionTTL())
					if err == nil && sessionData != nil {
						setSessionCookie(c, sessionToken, int(sessionTTL().Seconds()))
						sessionRefreshResponse := TokenResponse{
							TokenType:        "session",
							ExpiresIn:        int(sessionTTL().Seconds()),
							SessionExpiresAt: sessionData.ExpiresAt.Format(time.RFC3339),
						}
						if shouldReturnLegacyAuthTokens() {
							newAccessToken, tokenErr := services.GenerateAccessTokenWithRole(
								sessionData.UserID, sessionData.Username, sessionData.IsAdmin, sessionData.Role,
							)
							if tokenErr == nil {
								sessionRefreshResponse.AccessToken = newAccessToken
								sessionRefreshResponse.TokenType = "bearer"
								sessionRefreshResponse.ExpiresIn = 1800
							}
						}
						c.JSON(http.StatusOK, sessionRefreshResponse)
						return
					}
					if err != nil && !errors.Is(err, auth.ErrSessionNotFound) {
						c.JSON(http.StatusUnauthorized, gin.H{
							"success": false,
							"error":   "invalid session",
						})
						return
					}
				}
			}
		}

		refreshToken := req.RefreshToken
		if refreshToken == "" {
			if cookieVal, err := c.Cookie("refresh_token"); err == nil {
				refreshToken = cookieVal
			}
		}
		if refreshToken == "" {
			authHeader := c.GetHeader("Authorization")
			parts := strings.SplitN(authHeader, " ", 2)
			if len(parts) == 2 && strings.EqualFold(parts[0], "Bearer") {
				refreshToken = parts[1]
			}
		}

		if refreshToken == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"error":   "missing refresh token",
			})
			return
		}

		claims, err := services.VerifyTokenClaims(refreshToken)
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "invalid or expired refresh token",
			})
			return
		}

		if claims.Type != "refresh" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "invalid token type for refresh",
			})
			return
		}

		// Generation registry: a refresh token minted before the user's latest
		// generation bump (password change) is revoked.
		if store := middleware.AuthSessionStore(); store != nil && claims.SessionGen >= 0 {
			currentGen := store.CurrentUserGeneration(c.Request.Context(), claims.UserID)
			if currentGen > 0 && claims.SessionGen < currentGen {
				log.Printf("refreshHandler: rejected revoked refresh token for user=%d (gen %d < %d)",
					claims.UserID, claims.SessionGen, currentGen)
				c.JSON(http.StatusUnauthorized, gin.H{
					"success": false,
					"error":   "refresh token revoked",
					"code":    "token_revoked",
				})
				return
			}
		}

		userID := claims.UserID

		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(userID)
		if err != nil || user == nil || !user.IsActive {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"error":   "user not found or inactive",
			})
			return
		}

		role := models.NormalizeUserRole(user.Role, user.IsAdmin)
		sessionToken, sessionData, err := createSessionForUser(c, user, role)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"error":   "failed to create auth session",
			})
			return
		}

		// Rotate the refresh_token cookie so session can survive future store clears.
		newJWTRefreshToken, rtErr := generateRefreshTokenForUser(c, user, role)
		if rtErr != nil {
			log.Printf("refreshHandler: failed to rotate refresh token cookie: %v", rtErr)
		}

		clearAuthCookies(c)
		if sessionToken != "" {
			setSessionCookie(c, sessionToken, int(sessionTTL().Seconds()))
		}
		if rtErr == nil && newJWTRefreshToken != "" {
			setRefreshTokenCookie(c, newJWTRefreshToken)
		}

		response := TokenResponse{
			TokenType:        "session",
			ExpiresIn:        int(sessionTTL().Seconds()),
			SessionExpiresAt: sessionData.ExpiresAt.Format(time.RFC3339),
		}

		// Same fallback as login: if session storage is unavailable, return bearer
		// access token so clients can still authenticate /users/me immediately.
		issueBearerFallback := sessionToken == ""
		if issueBearerFallback {
			log.Printf("refreshHandler: session store unavailable, issuing bearer fallback token for user=%d", user.ID)
		}

		if shouldReturnLegacyAuthTokens() || issueBearerFallback {
			newAccessToken, err := services.GenerateAccessTokenWithRole(user.ID, user.Username, user.IsAdmin, role)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{
					"success": false,
					"error":   "failed to generate access token",
				})
				return
			}
			response.AccessToken = newAccessToken
			response.RefreshToken = newJWTRefreshToken
			response.TokenType = "bearer"
			response.ExpiresIn = 1800
		}

		c.JSON(http.StatusOK, response)
	}
}

func logoutHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		if sessionToken := requestSessionToken(c); sessionToken != "" {
			if store := middleware.AuthSessionStore(); store != nil {
				if err := store.Delete(c.Request.Context(), sessionToken); err != nil {
					log.Printf("Failed to delete auth session: %v", err)
				}
			}
		}

		// Logout is the user's explicit revocation action: bump the session
		// generation so stateless refresh JWTs (7-day cookies) cannot keep
		// minting new sessions after logout, mirroring password-change
		// semantics. Requires the caller to be authenticated; an anonymous
		// logout keeps its current cookie-clearing behavior.
		if userIDValue, exists := c.Get("user_id"); exists {
			if userID, ok := userIDValue.(int); ok && userID > 0 {
				if store := middleware.AuthSessionStore(); store != nil {
					if err := store.BumpUserGeneration(c.Request.Context(), userID); err != nil {
						log.Printf("logoutHandler: failed to revoke sessions for user=%d: %v", userID, err)
					}
				}
			}
		}

		clearAuthCookies(c)
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Logged out",
		})
	}
}

// getCurrentUserHandler gets current user info
func getCurrentUserHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userIDValue, exists := c.Get("user_id")
		if !exists {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Not authenticated"})
			return
		}

		userID, ok := userIDValue.(int)
		if !ok {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid user context"})
			return
		}

		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(userID)
		if err != nil || user == nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found"})
			return
		}

		c.JSON(http.StatusOK, toUserResponse(user, middleware.IsPrivilegedMFARequired(database)))
	}
}

// updateProfileHandler updates user profile
func updateProfileHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userIDValue, exists := c.Get("user_id")
		if !exists {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"message": "Not authenticated",
			})
			return
		}

		userID, ok := userIDValue.(int)
		if !ok {
			c.JSON(http.StatusUnauthorized, gin.H{
				"success": false,
				"message": "Invalid user context",
			})
			return
		}

		var req struct {
			Email    *string `json:"email"`
			FullName *string `json:"full_name"`
			Avatar   *string `json:"avatar"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "Invalid request payload",
				"error":   err.Error(),
			})
			return
		}

		userRepo := repository.NewUserRepository(database)
		user, err := userRepo.GetByID(userID)
		if err != nil || user == nil {
			c.JSON(http.StatusNotFound, gin.H{
				"success": false,
				"message": "User not found",
			})
			return
		}

		if req.Email != nil {
			trimmedEmail := strings.TrimSpace(*req.Email)
			if trimmedEmail == "" {
				c.JSON(http.StatusBadRequest, gin.H{
					"success": false,
					"message": "Email cannot be empty",
				})
				return
			}
			user.Email = trimmedEmail
		}

		if req.FullName != nil {
			user.FullName = strings.TrimSpace(*req.FullName)
		}

		if req.Avatar != nil {
			user.Avatar = strings.TrimSpace(*req.Avatar)
		}

		if err := userRepo.Update(user); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to update profile",
				"error":   err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Profile updated successfully",
			"data": gin.H{
				"user": toUserResponse(user, middleware.IsPrivilegedMFARequired(database)),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}
