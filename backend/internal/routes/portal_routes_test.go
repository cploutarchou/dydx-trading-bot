package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"

	"github.com/gin-gonic/gin"
)

func setupPortalRouter(t *testing.T) (*gin.Engine, *sql.DB) {
	t.Helper()
	router, dbConn := setupAdminUserRouter(t)
	RegisterPortalRoutes(router, dbConn)
	return router, dbConn
}

func createPartnerApplicationsSchema(t *testing.T, dbConn *sql.DB) {
	t.Helper()
	if _, err := dbConn.Exec(`
	CREATE TABLE partner_applications (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		applicant_user_id INTEGER NOT NULL,
		sponsor_user_id INTEGER,
		requested_role TEXT NOT NULL,
		status TEXT NOT NULL DEFAULT 'pending',
		business_name TEXT NOT NULL DEFAULT '',
		notes TEXT NOT NULL DEFAULT '',
		review_notes TEXT NOT NULL DEFAULT '',
		reviewed_by_user_id INTEGER,
		reviewed_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create partner_applications table: %v", err)
	}
}

func createPartnerRelationshipsSchema(t *testing.T, dbConn *sql.DB) {
	t.Helper()
	if _, err := dbConn.Exec(`
	CREATE TABLE partner_relationships (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		sponsor_user_id INTEGER NOT NULL,
		partner_user_id INTEGER NOT NULL UNIQUE,
		relationship_type TEXT NOT NULL,
		source_application_id INTEGER,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create partner_relationships table: %v", err)
	}
}

func createPartnerCommissionMetricsSchema(t *testing.T, dbConn *sql.DB) {
	t.Helper()
	if _, err := dbConn.Exec(`
	CREATE TABLE partner_commission_metrics (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		period_start DATETIME NOT NULL,
		period_end DATETIME NOT NULL,
		direct_clients INTEGER NOT NULL DEFAULT 0,
		sub_ib_count INTEGER NOT NULL DEFAULT 0,
		notional_volume_usd REAL NOT NULL DEFAULT 0,
		gross_commission_usd REAL NOT NULL DEFAULT 0,
		rebate_usd REAL NOT NULL DEFAULT 0,
		net_commission_usd REAL NOT NULL DEFAULT 0,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL,
		UNIQUE(user_id, period_start, period_end)
	);`); err != nil {
		t.Fatalf("create partner_commission_metrics table: %v", err)
	}
}

func TestPortalRoutes_CreateListAndReviewApplication(t *testing.T) {
	router, dbConn := setupPortalRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createPartnerApplicationsSchema(t, dbConn)
	createPartnerRelationshipsSchema(t, dbConn)
	createPartnerCommissionMetricsSchema(t, dbConn)

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	clientID := seedAdminUser(t, dbConn, "client1", "client1@example.local", "client", true)
	clientBearer := issueAdminBearerToken(t, clientID, "client1", "client")
	adminBearer := issueAdminBearerToken(t, adminID, "admin", "admin")

	createPayload, _ := json.Marshal(map[string]any{
		"requested_role": "ib",
		"business_name":  "Atlas Desk",
		"notes":          "We operate a regional partner book.",
	})
	createReq := httptest.NewRequest(http.MethodPost, "/api/v1/portal/applications", bytes.NewReader(createPayload))
	createReq.Header.Set("Content-Type", "application/json")
	createReq.Header.Set("Authorization", clientBearer)
	createRes := httptest.NewRecorder()
	router.ServeHTTP(createRes, createReq)

	if createRes.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d body=%s", createRes.Code, createRes.Body.String())
	}

	listReq := httptest.NewRequest(http.MethodGet, "/api/v1/portal/applications", nil)
	listReq.Header.Set("Authorization", clientBearer)
	listRes := httptest.NewRecorder()
	router.ServeHTTP(listRes, listReq)

	if listRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", listRes.Code, listRes.Body.String())
	}

	reviewPayload, _ := json.Marshal(map[string]any{
		"status":       "approved",
		"review_notes": "Approved after manual KYC and partner review.",
	})
	reviewReq := httptest.NewRequest(http.MethodPost, "/api/v1/admin/crm/applications/1/review", bytes.NewReader(reviewPayload))
	reviewReq.Header.Set("Content-Type", "application/json")
	reviewReq.Header.Set("Authorization", adminBearer)
	reviewRes := httptest.NewRecorder()
	router.ServeHTTP(reviewRes, reviewReq)

	if reviewRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", reviewRes.Code, reviewRes.Body.String())
	}

	var updatedRole string
	if err := dbConn.QueryRow(`SELECT role FROM users WHERE id = ?`, clientID).Scan(&updatedRole); err != nil {
		t.Fatalf("query updated role: %v", err)
	}
	if updatedRole != "ib" {
		t.Fatalf("expected applicant role to be ib, got %s", updatedRole)
	}

	hierarchyReq := httptest.NewRequest(http.MethodGet, "/api/v1/portal/hierarchy", nil)
	hierarchyReq.Header.Set("Authorization", adminBearer)
	hierarchyRes := httptest.NewRecorder()
	router.ServeHTTP(hierarchyRes, hierarchyReq)
	if hierarchyRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", hierarchyRes.Code, hierarchyRes.Body.String())
	}
}

func TestPortalRoutes_CRMRequiresOperationalRole(t *testing.T) {
	router, dbConn := setupPortalRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createPartnerApplicationsSchema(t, dbConn)
	createPartnerRelationshipsSchema(t, dbConn)
	createPartnerCommissionMetricsSchema(t, dbConn)

	clientID := seedAdminUser(t, dbConn, "client2", "client2@example.local", "client", true)
	clientBearer := issueAdminBearerToken(t, clientID, "client2", "client")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/admin/crm/summary", nil)
	req.Header.Set("Authorization", clientBearer)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusForbidden {
		t.Fatalf("expected 403, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestPortalRoutes_SubIBCanOnlyRequestIB(t *testing.T) {
	router, dbConn := setupPortalRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createPartnerApplicationsSchema(t, dbConn)
	createPartnerRelationshipsSchema(t, dbConn)
	createPartnerCommissionMetricsSchema(t, dbConn)

	subIBID := seedAdminUser(t, dbConn, "subib", "subib@example.local", "sub_ib", true)
	subIBBearer := issueAdminBearerToken(t, subIBID, "subib", "sub_ib")

	payload, _ := json.Marshal(map[string]any{
		"requested_role": "sub_ib",
		"business_name":  "Nested Desk",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/portal/applications", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", subIBBearer)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestPortalRoutes_CommissionMetricsLifecycle(t *testing.T) {
	router, dbConn := setupPortalRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createPartnerApplicationsSchema(t, dbConn)
	createPartnerRelationshipsSchema(t, dbConn)
	createPartnerCommissionMetricsSchema(t, dbConn)

	adminID := seedAdminUser(t, dbConn, "admin2", "admin2@example.local", "admin", true)
	ibID := seedAdminUser(t, dbConn, "ib1", "ib1@example.local", "ib", true)
	adminBearer := issueAdminBearerToken(t, adminID, "admin2", "admin")
	ibBearer := issueAdminBearerToken(t, ibID, "ib1", "ib")

	upsertPayload, _ := json.Marshal(map[string]any{
		"direct_clients":       12,
		"sub_ib_count":         3,
		"notional_volume_usd":  125000.5,
		"gross_commission_usd": 5400.25,
		"rebate_usd":           700.25,
		"net_commission_usd":   4700,
	})
	upsertReq := httptest.NewRequest(
		http.MethodPut,
		"/api/v1/admin/crm/commission-metrics/"+strconv.Itoa(ibID),
		bytes.NewReader(upsertPayload),
	)
	upsertReq.Header.Set("Content-Type", "application/json")
	upsertReq.Header.Set("Authorization", adminBearer)
	upsertRes := httptest.NewRecorder()
	router.ServeHTTP(upsertRes, upsertReq)
	if upsertRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", upsertRes.Code, upsertRes.Body.String())
	}

	portalReq := httptest.NewRequest(http.MethodGet, "/api/v1/portal/commission-metrics", nil)
	portalReq.Header.Set("Authorization", ibBearer)
	portalRes := httptest.NewRecorder()
	router.ServeHTTP(portalRes, portalReq)
	if portalRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", portalRes.Code, portalRes.Body.String())
	}
}
