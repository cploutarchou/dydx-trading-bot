package routes

import (
	"database/sql"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

type portalOverviewModule struct {
	Key         string   `json:"key"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Routes      []string `json:"routes"`
}

type partnerApplicationRequest struct {
	RequestedRole string `json:"requested_role" binding:"required"`
	SponsorUserID *int   `json:"sponsor_user_id"`
	BusinessName  string `json:"business_name"`
	Notes         string `json:"notes"`
}

type reviewPartnerApplicationRequest struct {
	Status      string `json:"status" binding:"required"`
	ReviewNotes string `json:"review_notes"`
}

type upsertCommissionMetricRequest struct {
	PeriodStart        string  `json:"period_start"`
	PeriodEnd          string  `json:"period_end"`
	DirectClients      int     `json:"direct_clients"`
	SubIBCount         int     `json:"sub_ib_count"`
	NotionalVolumeUSD  float64 `json:"notional_volume_usd"`
	GrossCommissionUSD float64 `json:"gross_commission_usd"`
	RebateUSD          float64 `json:"rebate_usd"`
	NetCommissionUSD   float64 `json:"net_commission_usd"`
}

func RegisterPortalRoutes(router *gin.Engine, database *sql.DB) {
	portal := router.Group("/api/v1/portal")
	portal.Use(middleware.RequireAuth())
	{
		portal.GET("/overview", portalOverviewHandler(database))
		portal.GET("/applications", listPartnerApplicationsHandler(database))
		portal.POST("/applications", createPartnerApplicationHandler(database))
		portal.GET("/hierarchy", portalHierarchyHandler(database))
		portal.GET("/hierarchy/tree", portalHierarchyTreeHandler(database))
		portal.GET("/commission-metrics", portalCommissionMetricsHandler(database))
	}

	crm := router.Group("/api/v1/admin/crm")
	crm.Use(middleware.RequireAuth())
	crm.Use(middleware.RequireMFA(database))
	{
		crm.GET("/summary", middleware.RequirePermission(database, "crm.read"), crmSummaryHandler(database))
		crm.GET("/users", middleware.RequirePermission(database, "users.read"), crmUsersTableHandler(database))
		crm.GET("/hierarchy", middleware.RequirePermission(database, "crm.read"), crmHierarchyTableHandler(database))
		crm.GET("/security-events", middleware.RequirePermission(database, "security.events.read"), crmSecurityEventsHandler(database))
		crm.POST("/applications/:id/review", middleware.RequirePermission(database, "kyc.review"), reviewPartnerApplicationHandler(database))
		crm.PUT("/commission-metrics/:user_id", middleware.RequirePermission(database, "finance.manage"), upsertCommissionMetricsHandler(database))
	}
}

func portalOverviewHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		userRepo := repository.NewUserRepository(database)
		appRepo := repository.NewPartnerApplicationRepository(database)
		relationshipRepo := repository.NewPartnerRelationshipRepository(database)

		users, err := userRepo.List(1000, 0)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load users: %v", err)})
			return
		}

		pending, err := appRepo.CountPending()
		if err != nil {
			pending = 0
		}

		relationships, _ := relationshipRepo.List(5000, 0)

		counts := map[string]int{}
		for _, user := range users {
			counts[models.NormalizeUserRole(user.Role, user.IsAdmin)]++
		}

		hierarchyEdges := len(relationships)

		modules := portalModulesForRole(role)
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Portal overview loaded",
			"data": gin.H{
				"role":    role,
				"modules": modules,
				"counts": gin.H{
					"clients":                      counts["client"],
					"ibs":                          counts["ib"],
					"sub_ibs":                      counts["sub_ib"],
					"backoffice":                   counts["backoffice"],
					"admins":                       counts["admin"],
					"hierarchy_edges":              hierarchyEdges,
					"pending_partner_applications": pending,
				},
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func listPartnerApplicationsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		appRepo := repository.NewPartnerApplicationRepository(database)

		limit := 100
		offset := 0
		if parsedLimit, err := strconv.Atoi(c.DefaultQuery("limit", "100")); err == nil && parsedLimit > 0 && parsedLimit <= 500 {
			limit = parsedLimit
		}
		if parsedOffset, err := strconv.Atoi(c.DefaultQuery("offset", "0")); err == nil && parsedOffset >= 0 {
			offset = parsedOffset
		}

		var (
			applications []*models.PartnerApplication
			err          error
		)

		switch {
		case canManageCRM(role):
			applications, err = appRepo.List(limit, offset)
		case role == "ib" || role == "sub_ib":
			applications, err = appRepo.ListBySponsor(userID, limit, offset)
			if err == nil {
				own, ownErr := appRepo.ListByApplicant(userID, limit, offset)
				if ownErr == nil {
					applications = append(applications, own...)
				}
			}
		default:
			applications, err = appRepo.ListByApplicant(userID, limit, offset)
		}

		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load partner applications: %v", err)})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Partner applications loaded",
			"data":      gin.H{"applications": applications},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func createPartnerApplicationHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		userRole := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		var req partnerApplicationRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}

		requestedRole := strings.TrimSpace(strings.ToLower(req.RequestedRole))
		if requestedRole != "ib" && requestedRole != "sub_ib" {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "requested_role must be ib or sub_ib"})
			return
		}

		if userRole == "client" && requestedRole == "sub_ib" {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Clients can request IB status first before becoming sub-IB managers"})
			return
		}

		if userRole == "sub_ib" && requestedRole != "ib" {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Sub-IB users can only request promotion to IB"})
			return
		}

		appRepo := repository.NewPartnerApplicationRepository(database)
		application := &models.PartnerApplication{
			ApplicantUserID: userID,
			SponsorUserID:   req.SponsorUserID,
			RequestedRole:   requestedRole,
			Status:          "pending",
			BusinessName:    strings.TrimSpace(req.BusinessName),
			Notes:           strings.TrimSpace(req.Notes),
			ReviewNotes:     "",
		}
		if err := appRepo.Create(application); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to create partner application: %v", err)})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"success":   true,
			"message":   "Partner application submitted successfully",
			"data":      gin.H{"application": application},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func crmSummaryHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userRepo := repository.NewUserRepository(database)
		appRepo := repository.NewPartnerApplicationRepository(database)
		relationshipRepo := repository.NewPartnerRelationshipRepository(database)
		commissionRepo := repository.NewPartnerCommissionMetricRepository(database)
		users, err := userRepo.List(1000, 0)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load CRM summary: %v", err)})
			return
		}
		pending, _ := appRepo.CountPending()
		relationships, _ := relationshipRepo.List(5000, 0)

		counts := map[string]int{}
		activeUsers := 0
		for _, user := range users {
			roleKey := models.NormalizeUserRole(user.Role, user.IsAdmin)
			counts[roleKey]++
			if user.IsActive {
				activeUsers++
			}
		}

		relationshipByPartner := map[int]*models.PartnerRelationship{}
		for _, relationship := range relationships {
			relationshipByPartner[relationship.PartnerUserID] = relationship
		}

		totalCommission := 0.0
		for _, user := range users {
			if models.NormalizeUserRole(user.Role, user.IsAdmin) != "ib" && models.NormalizeUserRole(user.Role, user.IsAdmin) != "sub_ib" {
				continue
			}
			metric, metricErr := commissionRepo.GetLatestByUser(user.ID)
			if metricErr == nil && metric != nil {
				totalCommission += metric.NetCommissionUSD
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "CRM summary loaded",
			"data": gin.H{
				"active_users":                 activeUsers,
				"clients":                      counts["client"],
				"ibs":                          counts["ib"],
				"sub_ibs":                      counts["sub_ib"],
				"backoffice":                   counts["backoffice"],
				"hierarchy_edges":              len(relationships),
				"sponsored_partners":           len(relationshipByPartner),
				"net_commission_usd":           totalCommission,
				"pending_partner_applications": pending,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func reviewPartnerApplicationHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		applicationID, err := strconv.Atoi(c.Param("id"))
		if err != nil || applicationID <= 0 {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Invalid application id"})
			return
		}

		var req reviewPartnerApplicationRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}

		status := strings.TrimSpace(strings.ToLower(req.Status))
		if status != "approved" && status != "rejected" && status != "reviewing" {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "status must be approved, rejected, or reviewing"})
			return
		}

		appRepo := repository.NewPartnerApplicationRepository(database)
		relationshipRepo := repository.NewPartnerRelationshipRepository(database)
		application, err := appRepo.GetByID(applicationID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load application: %v", err)})
			return
		}
		if application == nil {
			c.JSON(http.StatusNotFound, gin.H{"success": false, "message": "Application not found"})
			return
		}

		reviewerID := c.GetInt("user_id")
		previousStatus := application.Status
		reviewedAt := time.Now().UTC()
		application.Status = status
		application.ReviewNotes = strings.TrimSpace(req.ReviewNotes)
		application.ReviewedByUserID = &reviewerID
		application.ReviewedAt = &reviewedAt

		if status == "approved" {
			userRepo := repository.NewUserRepository(database)
			user, userErr := userRepo.GetByID(application.ApplicantUserID)
			if userErr != nil || user == nil {
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "Failed to load applicant user"})
				return
			}
			user.Role = application.RequestedRole
			user.IsAdmin = application.RequestedRole == "admin"
			if err := userRepo.Update(user); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to promote applicant: %v", err)})
				return
			}

			if application.SponsorUserID != nil {
				relationship := &models.PartnerRelationship{
					SponsorUserID:       *application.SponsorUserID,
					PartnerUserID:       application.ApplicantUserID,
					RelationshipType:    application.RequestedRole,
					SourceApplicationID: &application.ID,
					IsActive:            true,
				}
				if err := relationshipRepo.Upsert(relationship); err != nil {
					c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to persist partner hierarchy: %v", err)})
					return
				}
			}
		}

		if err := appRepo.UpdateReview(application); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to review application: %v", err)})
			return
		}

		writeAuditLog(database, c, "crm.application.review", "partner_application", stringPointer(strconv.Itoa(application.ID)), gin.H{
			"previous_status": previousStatus,
			"new_status":      application.Status,
			"requested_role":  application.RequestedRole,
			"review_notes":    application.ReviewNotes,
		}, "success")

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Partner application reviewed successfully",
			"data":      gin.H{"application": application},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func portalHierarchyHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		relationshipRepo := repository.NewPartnerRelationshipRepository(database)

		limit := 200
		offset := 0
		if parsedLimit, err := strconv.Atoi(c.DefaultQuery("limit", "200")); err == nil && parsedLimit > 0 && parsedLimit <= 2000 {
			limit = parsedLimit
		}

		var (
			relationships []*models.PartnerRelationship
			err           error
		)
		if canManageCRM(role) {
			relationships, err = relationshipRepo.List(limit, offset)
		} else {
			relationships, err = relationshipRepo.ListBySponsor(userID, limit, offset)
		}
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load hierarchy: %v", err)})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Hierarchy loaded",
			"data":      gin.H{"relationships": relationships},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func portalCommissionMetricsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		requestedUserID := c.GetInt("user_id")
		if queryUserID := strings.TrimSpace(c.Query("user_id")); queryUserID != "" && canManageCRM(role) {
			if parsedID, err := strconv.Atoi(queryUserID); err == nil && parsedID > 0 {
				requestedUserID = parsedID
			}
		}

		relationshipRepo := repository.NewPartnerRelationshipRepository(database)
		commissionRepo := repository.NewPartnerCommissionMetricRepository(database)

		directRelationships, _ := relationshipRepo.ListBySponsor(requestedUserID, 2000, 0)
		directPartnerIDs := make([]int, 0, len(directRelationships))
		subIBCount := 0
		for _, relationship := range directRelationships {
			directPartnerIDs = append(directPartnerIDs, relationship.PartnerUserID)
			if relationship.RelationshipType == "sub_ib" {
				subIBCount++
			}
		}

		ownMetric, err := commissionRepo.GetLatestByUser(requestedUserID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load commission metrics: %v", err)})
			return
		}

		if ownMetric == nil {
			now := time.Now().UTC()
			ownMetric = &models.PartnerCommissionMetric{
				UserID:             requestedUserID,
				PeriodStart:        now.AddDate(0, 0, -30),
				PeriodEnd:          now,
				DirectClients:      len(directPartnerIDs),
				SubIBCount:         subIBCount,
				NotionalVolumeUSD:  0,
				GrossCommissionUSD: 0,
				RebateUSD:          0,
				NetCommissionUSD:   0,
			}
		} else {
			if ownMetric.DirectClients == 0 {
				ownMetric.DirectClients = len(directPartnerIDs)
			}
			if ownMetric.SubIBCount == 0 {
				ownMetric.SubIBCount = subIBCount
			}
		}

		downlineMetric, downlineErr := commissionRepo.AggregateByUsers(directPartnerIDs)
		if downlineErr != nil {
			downlineMetric = &models.PartnerCommissionMetric{}
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Commission metrics loaded",
			"data": gin.H{
				"owner":              ownMetric,
				"downline":           downlineMetric,
				"direct_partner_ids": directPartnerIDs,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func crmUsersTableHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userRepo := repository.NewUserRepository(database)
		relationshipRepo := repository.NewPartnerRelationshipRepository(database)
		users, err := userRepo.List(2000, 0)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load users: %v", err)})
			return
		}

		relationships, _ := relationshipRepo.List(5000, 0)
		relationshipByPartner := map[int]*models.PartnerRelationship{}
		directCountBySponsor := map[int]int{}
		for _, relationship := range relationships {
			relationshipByPartner[relationship.PartnerUserID] = relationship
			directCountBySponsor[relationship.SponsorUserID]++
		}

		rows := make([]gin.H, 0, len(users))
		for _, user := range users {
			normalizedRole := models.NormalizeUserRole(user.Role, user.IsAdmin)
			sponsorUserID := 0
			relationshipType := ""
			if relationship, ok := relationshipByPartner[user.ID]; ok {
				sponsorUserID = relationship.SponsorUserID
				relationshipType = relationship.RelationshipType
			}

			rows = append(rows, gin.H{
				"id":                   user.ID,
				"username":             user.Username,
				"email":                user.Email,
				"role":                 normalizedRole,
				"is_active":            user.IsActive,
				"sponsor_user_id":      sponsorUserID,
				"relationship_type":    relationshipType,
				"direct_partner_count": directCountBySponsor[user.ID],
				"created_at":           user.CreatedAt,
				"updated_at":           user.UpdatedAt,
			})
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "CRM users loaded",
			"data": gin.H{
				"users": rows,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func crmHierarchyTableHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		relationshipRepo := repository.NewPartnerRelationshipRepository(database)
		relationships, err := relationshipRepo.List(5000, 0)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load hierarchy table: %v", err)})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "CRM hierarchy loaded",
			"data": gin.H{
				"relationships": relationships,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func crmSecurityEventsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := 100
		offset := 0
		if parsedLimit, err := strconv.Atoi(c.DefaultQuery("limit", "100")); err == nil && parsedLimit > 0 && parsedLimit <= 1000 {
			limit = parsedLimit
		}
		if parsedOffset, err := strconv.Atoi(c.DefaultQuery("offset", "0")); err == nil && parsedOffset >= 0 {
			offset = parsedOffset
		}

		rows, err := database.Query(
			`SELECT id, user_id, username, event_type, outcome, reason, ip_address, user_agent, created_at
			 FROM security_login_events
			 ORDER BY created_at DESC
			 LIMIT $1 OFFSET $2`,
			limit,
			offset,
		)
		if err != nil {
			errLower := strings.ToLower(err.Error())
			if strings.Contains(errLower, "no such table") || strings.Contains(errLower, "does not exist") {
				c.JSON(http.StatusOK, gin.H{
					"success":   true,
					"message":   "Security events not available yet",
					"data":      gin.H{"events": []gin.H{}},
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load security events: %v", err)})
			return
		}
		defer func() { _ = rows.Close() }()

		events := make([]gin.H, 0)
		for rows.Next() {
			var (
				id        int
				userID    sql.NullInt64
				username  string
				eventType string
				outcome   string
				reason    string
				ipAddress sql.NullString
				userAgent sql.NullString
				createdAt time.Time
			)

			if scanErr := rows.Scan(&id, &userID, &username, &eventType, &outcome, &reason, &ipAddress, &userAgent, &createdAt); scanErr != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to parse security event: %v", scanErr)})
				return
			}

			event := gin.H{
				"id":         id,
				"username":   username,
				"event_type": eventType,
				"outcome":    outcome,
				"reason":     reason,
				"created_at": createdAt.UTC().Format(time.RFC3339),
			}
			if userID.Valid {
				event["user_id"] = userID.Int64
			}
			if ipAddress.Valid {
				event["ip_address"] = ipAddress.String
			}
			if userAgent.Valid {
				event["user_agent"] = userAgent.String
			}

			events = append(events, event)
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Security events loaded",
			"data": gin.H{
				"events": events,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func upsertCommissionMetricsHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID, err := strconv.Atoi(c.Param("user_id"))
		if err != nil || userID <= 0 {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "Invalid user id"})
			return
		}

		var req upsertCommissionMetricRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
			return
		}

		periodStart := time.Now().UTC().AddDate(0, 0, -30)
		periodEnd := time.Now().UTC()
		if strings.TrimSpace(req.PeriodStart) != "" {
			if parsed, parseErr := time.Parse(time.RFC3339, req.PeriodStart); parseErr == nil {
				periodStart = parsed.UTC()
			}
		}
		if strings.TrimSpace(req.PeriodEnd) != "" {
			if parsed, parseErr := time.Parse(time.RFC3339, req.PeriodEnd); parseErr == nil {
				periodEnd = parsed.UTC()
			}
		}

		metric := &models.PartnerCommissionMetric{
			UserID:             userID,
			PeriodStart:        periodStart,
			PeriodEnd:          periodEnd,
			DirectClients:      req.DirectClients,
			SubIBCount:         req.SubIBCount,
			NotionalVolumeUSD:  req.NotionalVolumeUSD,
			GrossCommissionUSD: req.GrossCommissionUSD,
			RebateUSD:          req.RebateUSD,
			NetCommissionUSD:   req.NetCommissionUSD,
		}

		commissionRepo := repository.NewPartnerCommissionMetricRepository(database)
		if err := commissionRepo.Upsert(metric); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to save commission metric: %v", err)})
			return
		}

		writeAuditLog(database, c, "crm.commission.upsert", "partner_commission_metric", stringPointer(strconv.Itoa(userID)), gin.H{
			"period_start":         periodStart.UTC().Format(time.RFC3339),
			"period_end":           periodEnd.UTC().Format(time.RFC3339),
			"direct_clients":       req.DirectClients,
			"sub_ib_count":         req.SubIBCount,
			"notional_volume_usd":  req.NotionalVolumeUSD,
			"gross_commission_usd": req.GrossCommissionUSD,
			"rebate_usd":           req.RebateUSD,
			"net_commission_usd":   req.NetCommissionUSD,
		}, "success")

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Commission metric saved",
			"data":      gin.H{"metric": metric},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

// portalHierarchyTreeHandler builds an unlimited-depth pyramid tree starting from the
// requesting user (or all roots for admin/backoffice). It uses a recursive walk over
// the flat edge list to avoid N+1 DB calls.
func portalHierarchyTreeHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := models.NormalizeUserRole(c.GetString("role"), c.GetBool("is_admin"))
		relationshipRepo := repository.NewPartnerRelationshipRepository(database)

		var (
			allEdges []*models.PartnerRelationship
			err      error
		)
		if canManageCRM(role) {
			allEdges, err = relationshipRepo.List(10000, 0)
		} else {
			// For IBs, load all edges in the entire subtree (up to 10k) so we can
			// recurse below their own direct partners as well.
			allEdges, err = relationshipRepo.List(10000, 0)
		}
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": fmt.Sprintf("Failed to load hierarchy: %v", err)})
			return
		}

		// Build adjacency: sponsorID → []PartnerRelationship
		children := make(map[int][]*models.PartnerRelationship)
		partnerIDs := make(map[int]bool)
		for _, e := range allEdges {
			children[e.SponsorUserID] = append(children[e.SponsorUserID], e)
			partnerIDs[e.PartnerUserID] = true
		}

		// Determine root IDs: sponsors that are nobody's partner
		var rootIDs []int
		if canManageCRM(role) {
			seen := make(map[int]bool)
			for _, e := range allEdges {
				if !partnerIDs[e.SponsorUserID] && !seen[e.SponsorUserID] {
					rootIDs = append(rootIDs, e.SponsorUserID)
					seen[e.SponsorUserID] = true
				}
			}
		} else {
			rootIDs = []int{userID}
		}

		var buildTree func(sponsorID, depth int) []*models.IBPyramidNode
		buildTree = func(sponsorID, depth int) []*models.IBPyramidNode {
			edges := children[sponsorID]
			nodes := make([]*models.IBPyramidNode, 0, len(edges))
			for _, e := range edges {
				node := &models.IBPyramidNode{
					UserID:           e.PartnerUserID,
					SponsorUserID:    &e.SponsorUserID,
					RelationshipType: e.RelationshipType,
					TierLevel:        depth,
					IsActive:         e.IsActive,
					Children:         buildTree(e.PartnerUserID, depth+1),
				}
				nodes = append(nodes, node)
			}
			return nodes
		}

		maxDepth := 0
		totalNodes := 0

		var countTree func(nodes []*models.IBPyramidNode, depth int)
		countTree = func(nodes []*models.IBPyramidNode, depth int) {
			for _, n := range nodes {
				totalNodes++
				if depth > maxDepth {
					maxDepth = depth
				}
				countTree(n.Children, depth+1)
			}
		}

		roots := make([]*models.IBPyramidNode, 0, len(rootIDs))
		for _, rootID := range rootIDs {
			node := &models.IBPyramidNode{
				UserID:           rootID,
				SponsorUserID:    nil,
				RelationshipType: "root",
				TierLevel:        0,
				IsActive:         true,
				Children:         buildTree(rootID, 1),
			}
			roots = append(roots, node)
		}
		countTree(roots, 0)

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Pyramid tree loaded",
			"data": gin.H{
				"roots":       roots,
				"total_nodes": totalNodes,
				"max_depth":   maxDepth,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func canManageCRM(role string) bool {
	return role == "admin" ||
		role == "super_admin" ||
		role == "backoffice" ||
		role == "operations_admin" ||
		role == "compliance_admin" ||
		role == "support_agent" ||
		role == "finance_admin" ||
		role == "read_only_auditor" ||
		role == "security_analyst"
}

func portalModulesForRole(role string) []portalOverviewModule {
	baseClient := portalOverviewModule{
		Key:         "client_area",
		Title:       "Client Area",
		Description: "Funding, support, onboarding, and status tracking for end clients.",
		Routes:      []string{"/client-area"},
	}
	ibPortal := portalOverviewModule{
		Key:         "ib_portal",
		Title:       "IB Portal",
		Description: "Partner onboarding, invitation tokens, revenue operations, and sub-IB visibility.",
		Routes:      []string{"/ib-portal"},
	}
	crm := portalOverviewModule{
		Key:         "crm_backoffice",
		Title:       "CRM Backoffice",
		Description: "Manage clients, IBs, applications, and account progression across the partner tree.",
		Routes:      []string{"/crm"},
	}
	adminHub := portalOverviewModule{
		Key:         "admin_hub",
		Title:       "Admin Hub",
		Description: "Global operating control center with access to CRM, security, access control, and platform configuration.",
		Routes:      []string{"/admin"},
	}

	switch role {
	case "admin", "super_admin":
		return []portalOverviewModule{adminHub, crm, ibPortal, baseClient}
	case "backoffice", "operations_admin", "compliance_admin", "support_agent", "finance_admin", "read_only_auditor", "security_analyst":
		return []portalOverviewModule{crm, baseClient}
	case "ib", "sub_ib":
		return []portalOverviewModule{ibPortal, baseClient}
	default:
		return []portalOverviewModule{baseClient}
	}
}
