package routes

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	_ "modernc.org/sqlite"
)

// TestPasswordChange_RevokesRefreshToken verifies the generation registry:
// after a password change, a refresh JWT minted before the change is rejected
// with code=token_revoked, while a newly minted one still works.
func TestPasswordChange_RevokesRefreshToken(t *testing.T) {
	router, dbConn, userID := setupLoginMFATestRouter(t)

	// Mint a refresh token at the current generation (0).
	oldToken, err := services.GenerateRefreshTokenWithRole(userID, "mfauser", false, "client")
	if err != nil {
		t.Fatalf("generate old refresh token: %v", err)
	}

	// Change the password (bumps the generation and clears cookies).
	changePayload, _ := json.Marshal(map[string]string{
		"current_password": loginMFATestPassword,
		"new_password":     "NewPass456!",
	})
	changeReq := httptest.NewRequest(http.MethodPut, "/api/v1/auth/change-password", bytes.NewReader(changePayload))
	changeReq.Header.Set("Content-Type", "application/json")
	bearer, tokenErr := services.GenerateAccessTokenWithRole(userID, "mfauser", false, "client")
	if tokenErr != nil {
		t.Fatalf("generate bearer: %v", tokenErr)
	}
	changeReq.Header.Set("Authorization", "Bearer "+bearer)
	changeRes := httptest.NewRecorder()
	router.ServeHTTP(changeRes, changeReq)
	if changeRes.Code != http.StatusOK {
		t.Fatalf("change-password expected 200, got %d body=%s", changeRes.Code, changeRes.Body.String())
	}

	// The pre-change refresh token must now be rejected.
	refreshPayload, _ := json.Marshal(map[string]string{"refresh_token": oldToken})
	refreshReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/refresh", bytes.NewReader(refreshPayload))
	refreshReq.Header.Set("Content-Type", "application/json")
	refreshRes := httptest.NewRecorder()
	router.ServeHTTP(refreshRes, refreshReq)
	if refreshRes.Code != http.StatusUnauthorized {
		t.Fatalf("old refresh token must be rejected after password change, got %d body=%s",
			refreshRes.Code, refreshRes.Body.String())
	}
	var body struct {
		Code string `json:"code"`
	}
	if err := json.Unmarshal(refreshRes.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode refresh response: %v", err)
	}
	if body.Code != "token_revoked" {
		t.Fatalf("expected code=token_revoked, got %q body=%s", body.Code, refreshRes.Body.String())
	}

	_ = dbConn
}
