package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func createInvitationTokenSchema(t *testing.T, dbConn *sql.DB) {
	t.Helper()
	if _, err := dbConn.Exec(`
	CREATE TABLE invitation_tokens (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		token_code TEXT NOT NULL UNIQUE,
		label TEXT NOT NULL DEFAULT '',
		ib_name TEXT NOT NULL DEFAULT '',
		campaign_name TEXT NOT NULL DEFAULT '',
		max_uses INTEGER NOT NULL DEFAULT 1,
		used_count INTEGER NOT NULL DEFAULT 0,
		created_by_user_id INTEGER,
		last_used_by_user_id INTEGER,
		expires_at DATETIME,
		last_used_at DATETIME,
		revoked_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create invitation_tokens table: %v", err)
	}
}

func TestAdminIBInvitationRoutes_CreateListAndRevoke(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createInvitationTokenSchema(t, dbConn)
	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	bearer := issueAdminBearerToken(t, adminID, "admin", "admin")

	createPayload, _ := json.Marshal(map[string]any{
		"label":            "IB portal smoke",
		"ib_name":          "Atlas IB",
		"campaign_name":    "Q2",
		"max_uses":         1,
		"expires_in_hours": 24,
	})
	createReq := httptest.NewRequest(http.MethodPost, "/api/v1/admin/ib/invitations", bytes.NewReader(createPayload))
	createReq.Header.Set("Content-Type", "application/json")
	createReq.Header.Set("Authorization", bearer)
	createRes := httptest.NewRecorder()
	router.ServeHTTP(createRes, createReq)

	if createRes.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d body=%s", createRes.Code, createRes.Body.String())
	}

	var createBody struct {
		Data struct {
			Token struct {
				TokenCode string `json:"token_code"`
			} `json:"token"`
		} `json:"data"`
	}
	if err := json.Unmarshal(createRes.Body.Bytes(), &createBody); err != nil {
		t.Fatalf("decode create response: %v", err)
	}
	if createBody.Data.Token.TokenCode == "" {
		t.Fatalf("expected created token code")
	}

	listReq := httptest.NewRequest(http.MethodGet, "/api/v1/admin/ib/invitations", nil)
	listReq.Header.Set("Authorization", bearer)
	listRes := httptest.NewRecorder()
	router.ServeHTTP(listRes, listReq)
	if listRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", listRes.Code, listRes.Body.String())
	}

	revokeReq := httptest.NewRequest(
		http.MethodPost,
		"/api/v1/admin/ib/invitations/"+createBody.Data.Token.TokenCode+"/revoke",
		nil,
	)
	revokeReq.Header.Set("Authorization", bearer)
	revokeRes := httptest.NewRecorder()
	router.ServeHTTP(revokeRes, revokeReq)
	if revokeRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", revokeRes.Code, revokeRes.Body.String())
	}
}
