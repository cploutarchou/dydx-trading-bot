//go:build integration

package routes

import (
	"database/sql"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

func setupSeparatedPortalRouter(t *testing.T) (*gin.Engine, *sql.DB) {
	t.Helper()
	router, dbConn := setupPortalRouter(t)
	RegisterBackofficeRoutes(router, dbConn)
	RegisterIBPortalRoutes(router, dbConn)
	return router, dbConn
}

func TestSeparatedPortalRoutes_ClientCannotAccessBackofficeOrIB(t *testing.T) {
	router, dbConn := setupSeparatedPortalRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	clientID := seedAdminUser(t, dbConn, "client1", "client1@example.local", "client", true)
	clientBearer := issueAdminBearerToken(t, clientID, "client1", "client")

	backofficeReq := httptest.NewRequest(http.MethodGet, "/api/v1/backoffice/users", nil)
	backofficeReq.Header.Set("Authorization", clientBearer)
	backofficeRes := httptest.NewRecorder()
	router.ServeHTTP(backofficeRes, backofficeReq)
	if backofficeRes.Code != http.StatusForbidden {
		t.Fatalf("expected client backoffice access to be 403, got %d body=%s", backofficeRes.Code, backofficeRes.Body.String())
	}

	ibReq := httptest.NewRequest(http.MethodGet, "/api/v1/ib/profile", nil)
	ibReq.Header.Set("Authorization", clientBearer)
	ibRes := httptest.NewRecorder()
	router.ServeHTTP(ibRes, ibReq)
	if ibRes.Code != http.StatusForbidden {
		t.Fatalf("expected client IB access to be 403, got %d body=%s", ibRes.Code, ibRes.Body.String())
	}
}

func TestIBInvitationScopeBlocksOtherIBTokens(t *testing.T) {
	router, dbConn := setupSeparatedPortalRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createInvitationTokenSchema(t, dbConn)
	ibOneID := seedAdminUser(t, dbConn, "ib1", "ib1@example.local", "ib", true)
	ibTwoID := seedAdminUser(t, dbConn, "ib2", "ib2@example.local", "ib", true)

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO invitation_tokens (token_code, label, ib_name, campaign_name, max_uses, used_count, created_by_user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"IB-SCOPE-TEST",
		"Owned by IB one",
		"IB One",
		"Scope",
		5,
		0,
		ibOneID,
		now,
		now,
	); err != nil {
		t.Fatalf("seed invitation token: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v1/ib/invitations/IB-SCOPE-TEST", nil)
	req.Header.Set("Authorization", issueAdminBearerToken(t, ibTwoID, "ib2", "ib"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusForbidden {
		t.Fatalf("expected cross-IB invitation access to be 403, got %d body=%s", res.Code, res.Body.String())
	}
}
