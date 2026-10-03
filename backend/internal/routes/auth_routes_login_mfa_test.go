package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/pquerna/otp/totp"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

const loginMFATestJWTSecret = "login-mfa-test-secret-32-characters!!"

const loginMFATestPassword = "Pass123!"

func setupLoginMFATestRouter(t *testing.T) (*gin.Engine, *sql.DB, int) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("JWT_SECRET_KEY", loginMFATestJWTSecret)
	t.Setenv("APP_ENV", "development")
	t.Setenv("AUTH_RETURN_LEGACY_TOKENS", "false")
	t.Setenv("ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")
	if err := config.LoadConfig(); err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	middleware.InitAuthMiddleware(config.ConfigInstance)

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}

	for _, ddl := range []string{`
	CREATE TABLE users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT NOT NULL UNIQUE,
		email TEXT NOT NULL UNIQUE,
		role TEXT NOT NULL DEFAULT 'client',
		full_name TEXT,
		avatar TEXT,
		hashed_password TEXT NOT NULL,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		mfa_enabled BOOLEAN NOT NULL DEFAULT 0,
		password_change_required BOOLEAN NOT NULL DEFAULT 0,
		failed_login_attempts INTEGER NOT NULL DEFAULT 0,
		locked_until DATETIME,
		last_login DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`, `
	CREATE TABLE user_mfa_credentials (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL UNIQUE,
		encrypted_secret TEXT NOT NULL,
		encrypted_backup_codes TEXT NOT NULL,
		enabled BOOLEAN NOT NULL DEFAULT 0,
		verified_at DATETIME,
		last_used_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL,
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
	);`, `
	CREATE TABLE audit_logs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		action TEXT NOT NULL,
		resource_type TEXT,
		resource_id TEXT,
		details TEXT,
		status TEXT,
		ip_address TEXT,
		created_at DATETIME NOT NULL
	);`, `
	CREATE TABLE security_login_events (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		username TEXT NOT NULL,
		event_type TEXT NOT NULL,
		outcome TEXT NOT NULL,
		reason TEXT,
		ip_address TEXT,
		user_agent TEXT,
		created_at DATETIME NOT NULL
	);`,
	} {
		if _, err := dbConn.Exec(ddl); err != nil {
			t.Fatalf("create schema: %v", err)
		}
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(loginMFATestPassword), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate hash: %v", err)
	}
	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, mfa_enabled, created_at, updated_at) VALUES (?, ?, ?, '', '', ?, 1, 0, 0, ?, ?)`,
		"mfauser", "mfauser@example.local", "client", string(hash), now, now,
	); err != nil {
		t.Fatalf("insert mfa user: %v", err)
	}
	var userID int
	if err := dbConn.QueryRow(`SELECT id FROM users WHERE username = ?`, "mfauser").Scan(&userID); err != nil {
		t.Fatalf("lookup mfa user id: %v", err)
	}

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	return router, dbConn, userID
}

// enrollMFA enables TOTP for the user through the public endpoints and
// returns the plaintext secret so tests can generate valid codes.
func enrollMFA(t *testing.T, router *gin.Engine, userID int) string {
	t.Helper()
	bearer := "Bearer " + issueLoginMFATestToken(t, userID, "mfauser", "client")

	setupReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/2fa/setup", bytes.NewReader([]byte(`{}`)))
	setupReq.Header.Set("Content-Type", "application/json")
	setupReq.Header.Set("Authorization", bearer)
	setupRes := httptest.NewRecorder()
	router.ServeHTTP(setupRes, setupReq)
	if setupRes.Code != http.StatusOK {
		t.Fatalf("2fa/setup expected 200, got %d body=%s", setupRes.Code, setupRes.Body.String())
	}
	var setupBody struct {
		Data struct {
			Secret string `json:"secret"`
		} `json:"data"`
	}
	if err := json.Unmarshal(setupRes.Body.Bytes(), &setupBody); err != nil {
		t.Fatalf("decode setup response: %v", err)
	}

	// Enroll with the PREVIOUS window's code (valid under the ±2 skew):
	// verification is one-code-per-window now, so burning the current
	// window here would force the login challenge below to wait ~30s for
	// the next one.
	code, err := totp.GenerateCode(
		setupBody.Data.Secret, time.Now().UTC().Add(-30*time.Second),
	)
	if err != nil {
		t.Fatalf("generate totp code: %v", err)
	}
	verifyPayload, _ := json.Marshal(map[string]string{"token": code})
	verifyReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/2fa/verify", bytes.NewReader(verifyPayload))
	verifyReq.Header.Set("Content-Type", "application/json")
	verifyReq.Header.Set("Authorization", bearer)
	verifyRes := httptest.NewRecorder()
	router.ServeHTTP(verifyRes, verifyReq)
	if verifyRes.Code != http.StatusOK {
		t.Fatalf("2fa/verify expected 200, got %d body=%s", verifyRes.Code, verifyRes.Body.String())
	}
	return setupBody.Data.Secret
}

func issueLoginMFATestToken(t *testing.T, userID int, username, role string) string {
	t.Helper()
	token, err := services.GenerateAccessTokenWithRole(userID, username, false, role)
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	return token
}

func doLogin(t *testing.T, router *gin.Engine) *httptest.ResponseRecorder {
	t.Helper()
	payload, _ := json.Marshal(map[string]string{"username": "mfauser", "password": loginMFATestPassword})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/auth/login", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	return res
}

// sessionCookieFrom returns the effective session cookie. Handlers clear
// stale cookies before setting fresh ones, so the last matching cookie wins.
func sessionCookieFrom(t *testing.T, res *httptest.ResponseRecorder) *http.Cookie {
	t.Helper()
	var match *http.Cookie
	for _, cookie := range res.Result().Cookies() {
		if cookie.Name == "dydx_session" {
			match = cookie
		}
	}
	if match == nil || match.Value == "" {
		t.Fatalf("expected dydx_session cookie with a value in response, cookies=%v", res.Result().Cookies())
	}
	return match
}

// hasSetCookie reports a cookie actively set to a value (clearing cookies with
// MaxAge < 0 do not count).
func hasSetCookie(res *httptest.ResponseRecorder, name string) bool {
	for _, cookie := range res.Result().Cookies() {
		if cookie.Name == name && cookie.Value != "" && cookie.MaxAge > 0 {
			return true
		}
	}
	return false
}

func requestWithSessionCookie(method, path string, sessionCookie *http.Cookie, body []byte) *http.Request {
	var req *http.Request
	if body != nil {
		req = httptest.NewRequest(method, path, bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	req.AddCookie(sessionCookie)
	return req
}

func doChallenge(router *gin.Engine, sessionCookie *http.Cookie, code string) *httptest.ResponseRecorder {
	payload, _ := json.Marshal(map[string]string{"token": code})
	req := requestWithSessionCookie(http.MethodPost, "/api/v1/auth/2fa/challenge", sessionCookie, payload)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	return res
}

// Regression test for the audit finding "MFA is never enforced at login":
// a correct password for a TOTP-enrolled account must no longer produce a
// usable session, refresh cookie, or bearer token.
func TestLogin_MFARequired_IssuesPendingSessionOnly(t *testing.T) {
	router, dbConn, userID := setupLoginMFATestRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })
	enrollMFA(t, router, userID)

	res := doLogin(t, router)
	if res.Code != http.StatusOK {
		t.Fatalf("login expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Success      bool   `json:"success"`
		MFARequired  bool   `json:"mfa_required"`
		Code         string `json:"code"`
		TokenType    string `json:"token_type"`
		AccessToken  string `json:"access_token"`
		RefreshToken string `json:"refresh_token"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	if !body.Success || !body.MFARequired || body.Code != "mfa_challenge_required" {
		t.Fatalf("expected mfa_challenge_required response, got %s", res.Body.String())
	}
	if body.TokenType != "mfa_challenge" {
		t.Fatalf("expected token_type=mfa_challenge, got %q", body.TokenType)
	}
	if body.AccessToken != "" || body.RefreshToken != "" {
		t.Fatalf("pending login must not issue bearer tokens: %s", res.Body.String())
	}
	if !hasSetCookie(res, "dydx_session") {
		t.Fatal("expected pending session cookie")
	}
	if hasSetCookie(res, "refresh_token") {
		t.Fatal("pending login must not issue a refresh cookie")
	}

	// The pending session must be rejected by ordinary authenticated routes.
	meReq := requestWithSessionCookie(http.MethodGet, "/api/v1/users/me", sessionCookieFrom(t, res), nil)
	meRes := httptest.NewRecorder()
	router.ServeHTTP(meRes, meReq)
	if meRes.Code != http.StatusUnauthorized {
		t.Fatalf("pending session must be rejected, got %d body=%s", meRes.Code, meRes.Body.String())
	}
	var meBody struct {
		Error string `json:"error"`
		Code  string `json:"code"`
	}
	if err := json.Unmarshal(meRes.Body.Bytes(), &meBody); err != nil {
		t.Fatalf("decode me response: %v", err)
	}
	if meBody.Code != "mfa_challenge_required" {
		t.Fatalf("expected code=mfa_challenge_required, got %s", meRes.Body.String())
	}
}

// A pending (password-only) session must not be reported as an established
// session by /auth/refresh: clients use refresh to decide whether they are
// logged in, so it answers with the challenge-required contract instead of a
// session payload, and neither promotes the session nor issues tokens.
func TestAuthRefresh_PendingMFASession_ReportsChallengeRequired(t *testing.T) {
	router, dbConn, userID := setupLoginMFATestRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })
	enrollMFA(t, router, userID)

	loginRes := doLogin(t, router)
	if loginRes.Code != http.StatusOK {
		t.Fatalf("login expected 200, got %d body=%s", loginRes.Code, loginRes.Body.String())
	}
	sessionCookie := sessionCookieFrom(t, loginRes)

	refreshRes := httptest.NewRecorder()
	router.ServeHTTP(
		refreshRes,
		requestWithSessionCookie(http.MethodPost, "/api/v1/auth/refresh", sessionCookie, []byte(`{}`)),
	)
	if refreshRes.Code != http.StatusOK {
		t.Fatalf("refresh expected 200, got %d body=%s", refreshRes.Code, refreshRes.Body.String())
	}

	var body struct {
		Success      bool   `json:"success"`
		MFARequired  bool   `json:"mfa_required"`
		Code         string `json:"code"`
		TokenType    string `json:"token_type"`
		AccessToken  string `json:"access_token"`
		RefreshToken string `json:"refresh_token"`
	}
	if err := json.Unmarshal(refreshRes.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode refresh response: %v", err)
	}
	if !body.Success || !body.MFARequired || body.Code != "mfa_challenge_required" {
		t.Fatalf("expected mfa_challenge_required contract, got %s", refreshRes.Body.String())
	}
	if body.TokenType != "mfa_challenge" {
		t.Fatalf("expected token_type=mfa_challenge, got %q", body.TokenType)
	}
	if body.AccessToken != "" || body.RefreshToken != "" {
		t.Fatalf("pending refresh must not issue tokens: %s", refreshRes.Body.String())
	}
	if hasSetCookie(refreshRes, "refresh_token") {
		t.Fatal("pending refresh must not issue a refresh cookie")
	}

	// The refresh must not have promoted the session: ordinary routes still
	// reject it with the challenge-required contract.
	meRes := httptest.NewRecorder()
	router.ServeHTTP(meRes, requestWithSessionCookie(http.MethodGet, "/api/v1/users/me", sessionCookie, nil))
	if meRes.Code != http.StatusUnauthorized {
		t.Fatalf("pending session must still be rejected after refresh, got %d body=%s", meRes.Code, meRes.Body.String())
	}
}

func TestLogin_MFAChallenge_CompletesLogin(t *testing.T) {
	router, dbConn, userID := setupLoginMFATestRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })
	secret := enrollMFA(t, router, userID)

	loginRes := doLogin(t, router)
	if loginRes.Code != http.StatusOK {
		t.Fatalf("login expected 200, got %d", loginRes.Code)
	}
	sessionCookie := sessionCookieFrom(t, loginRes)

	code, err := totp.GenerateCode(secret, time.Now().UTC())
	if err != nil {
		t.Fatalf("generate totp code: %v", err)
	}
	challengeRes := doChallenge(router, sessionCookie, code)
	if challengeRes.Code != http.StatusOK {
		t.Fatalf("challenge expected 200, got %d body=%s", challengeRes.Code, challengeRes.Body.String())
	}

	var body struct {
		TokenType        string `json:"token_type"`
		SessionExpiresAt string `json:"session_expires_at"`
	}
	if err := json.Unmarshal(challengeRes.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode challenge response: %v", err)
	}
	if body.TokenType != "session" || body.SessionExpiresAt == "" {
		t.Fatalf("expected promoted session response, got %s", challengeRes.Body.String())
	}
	if !hasSetCookie(challengeRes, "refresh_token") {
		t.Fatal("expected refresh cookie after successful challenge")
	}

	// The promoted session must now pass ordinary authenticated routes.
	meReq := requestWithSessionCookie(http.MethodGet, "/api/v1/users/me", sessionCookie, nil)
	meRes := httptest.NewRecorder()
	router.ServeHTTP(meRes, meReq)
	if meRes.Code != http.StatusOK {
		t.Fatalf("promoted session expected 200 on /users/me, got %d body=%s", meRes.Code, meRes.Body.String())
	}

	var lastLogin sql.NullString
	if err := dbConn.QueryRow(`SELECT last_login FROM users WHERE id = ?`, userID).Scan(&lastLogin); err != nil {
		t.Fatalf("query last_login: %v", err)
	}
	if !lastLogin.Valid {
		t.Fatal("expected last_login recorded after completed MFA login")
	}
}

func TestLogin_MFAChallenge_RejectsInvalidCode(t *testing.T) {
	router, dbConn, userID := setupLoginMFATestRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })
	enrollMFA(t, router, userID)

	loginRes := doLogin(t, router)
	sessionCookie := sessionCookieFrom(t, loginRes)

	challengeRes := doChallenge(router, sessionCookie, "000000")
	if challengeRes.Code != http.StatusUnauthorized {
		t.Fatalf("challenge expected 401, got %d body=%s", challengeRes.Code, challengeRes.Body.String())
	}
	var body struct {
		Code string `json:"code"`
	}
	if err := json.Unmarshal(challengeRes.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode challenge response: %v", err)
	}
	if body.Code != "invalid_mfa_code" {
		t.Fatalf("expected code=invalid_mfa_code, got %s", challengeRes.Body.String())
	}
}

func TestLogin_MFAChallenge_LocksOutAfterMaxAttempts(t *testing.T) {
	router, dbConn, userID := setupLoginMFATestRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })
	secret := enrollMFA(t, router, userID)

	loginRes := doLogin(t, router)
	sessionCookie := sessionCookieFrom(t, loginRes)

	var lastRes *httptest.ResponseRecorder
	for i := 0; i < auth.MaxMFAPreAuthAttempts; i++ {
		lastRes = doChallenge(router, sessionCookie, "000000")
	}
	if lastRes.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 after exhausting attempts, got %d", lastRes.Code)
	}
	var body struct {
		Code string `json:"code"`
	}
	if err := json.Unmarshal(lastRes.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.Code != "mfa_challenge_expired" {
		t.Fatalf("expected code=mfa_challenge_expired, got %s", lastRes.Body.String())
	}

	// The pending session is gone: even a valid code no longer works.
	validCode, err := totp.GenerateCode(secret, time.Now().UTC())
	if err != nil {
		t.Fatalf("generate totp code: %v", err)
	}
	afterLockRes := doChallenge(router, sessionCookie, validCode)
	if afterLockRes.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 after session burn, got %d body=%s", afterLockRes.Code, afterLockRes.Body.String())
	}
}

func TestLogin_WithoutMFA_RemainsDirect(t *testing.T) {
	router, dbConn, _ := setupLoginMFATestRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	res := doLogin(t, router)
	if res.Code != http.StatusOK {
		t.Fatalf("login expected 200, got %d body=%s", res.Code, res.Body.String())
	}
	var body struct {
		MFARequired bool   `json:"mfa_required"`
		TokenType   string `json:"token_type"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	if body.MFARequired {
		t.Fatalf("non-MFA user must log in directly: %s", res.Body.String())
	}
	if body.TokenType != "session" {
		t.Fatalf("expected token_type=session, got %q", body.TokenType)
	}
	if !hasSetCookie(res, "refresh_token") {
		t.Fatal("expected refresh cookie for non-MFA login")
	}

	meReq := requestWithSessionCookie(http.MethodGet, "/api/v1/users/me", sessionCookieFrom(t, res), nil)
	meRes := httptest.NewRecorder()
	router.ServeHTTP(meRes, meReq)
	if meRes.Code != http.StatusOK {
		t.Fatalf("expected 200 on /users/me, got %d body=%s", meRes.Code, meRes.Body.String())
	}
}

// Regression test (review P1): the 2FA endpoints bound token with len=6,
// which rejected the 11-character backup-code format at binding time and
// made the implemented backup-code recovery path unreachable over HTTP.
func TestMFAHandlers_AcceptBackupCodeShape(t *testing.T) {
	router, dbConn, userID := setupLoginMFATestRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	// validMFACodeShape contract
	for _, ok := range []string{"123456", "ABCDE-FGHIJ"} {
		if !validMFACodeShape(ok) {
			t.Fatalf("expected %q to be a valid MFA code shape", ok)
		}
	}
	for _, bad := range []string{"", "12345", "1234567", "abcdef", "ABC-DEFGHIJ", "ABCDEFGHIJ-", "ABCDEFGHIJK"} {
		if validMFACodeShape(bad) {
			t.Fatalf("expected %q to be rejected", bad)
		}
	}

	// HTTP layer: a backup-code-shaped token must pass binding (it will fail
	// verification only after enrollment exists, not with a 400 shape error).
	bearer := "Bearer " + issueLoginMFATestToken(t, userID, "mfauser", "client")
	payload, _ := json.Marshal(map[string]string{"token": "ABCDE-FGHIJ"})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/auth/2fa/verify", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", bearer)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code == http.StatusBadRequest {
		t.Fatalf("backup-code shape must not be rejected at binding, got 400 body=%s", res.Body.String())
	}
}
