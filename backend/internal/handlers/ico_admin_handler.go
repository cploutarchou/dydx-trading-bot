package handlers

import (
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type ICOAdminHandler struct {
	repo      *repository.ICOWhitelistRepository
	outbox    *services.ICOEmailOutboxService
	readiness *services.ICOReadinessService
}

func NewICOAdminHandler(repo *repository.ICOWhitelistRepository, outbox *services.ICOEmailOutboxService, readiness *services.ICOReadinessService) *ICOAdminHandler {
	return &ICOAdminHandler{repo: repo, outbox: outbox, readiness: readiness}
}

type icoReadinessUpdateRequest struct {
	TokenomicsAllocationFinalized bool   `json:"tokenomics_allocation_finalized"`
	TokenomicsAllocationNotes     string `json:"tokenomics_allocation_notes"`
	VestingScheduleFinalized      bool   `json:"vesting_schedule_finalized"`
	VestingScheduleNotes          string `json:"vesting_schedule_notes"`
	TokenPrice                    string `json:"token_price"`
	AcceptedCurrencies            string `json:"accepted_currencies"`
	SmartContractAddress          string `json:"smart_contract_address"`
	SmartContractAuditStatus      string `json:"smart_contract_audit_status"`
	SmartContractAuditURL         string `json:"smart_contract_audit_url"`
	KYCProvider                   string `json:"kyc_provider"`
	KYCPolicyURL                  string `json:"kyc_policy_url"`
	RestrictedJurisdictions       string `json:"restricted_jurisdictions"`
	LegalEntityName               string `json:"legal_entity_name"`
	ControllerContact             string `json:"controller_contact"`
	ParticipationTermsURL         string `json:"participation_terms_url"`
	PrivacyNoticeURL              string `json:"privacy_notice_url"`
	RiskDisclosureURL             string `json:"risk_disclosure_url"`
	MailgunDNSVerified            bool   `json:"mailgun_dns_verified"`
	SPFVerified                   bool   `json:"spf_verified"`
	DKIMVerified                  bool   `json:"dkim_verified"`
	DMARCVerified                 bool   `json:"dmarc_verified"`
	ProductionSmokeTestPassed     bool   `json:"production_smoke_test_passed"`
	MonitoringConfigured          bool   `json:"monitoring_configured"`
	AlertingConfigured            bool   `json:"alerting_configured"`
	BackupsConfigured             bool   `json:"backups_configured"`
	BusinessApproved              bool   `json:"business_approved"`
	LegalApproved                 bool   `json:"legal_approved"`
	TechnicalApproved             bool   `json:"technical_approved"`
	Published                     bool   `json:"published"`
}

func (h *ICOAdminHandler) ListWhitelistApplications(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Admin access required"})
		return
	}
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))
	applications, err := h.repo.ListApplications(c.Request.Context(), repository.ICOWhitelistListFilter{
		Status: c.Query("status"),
		Limit:  limit,
		Offset: offset,
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Failed to list whitelist applications"})
		return
	}
	rows := make([]gin.H, 0, len(applications))
	for _, app := range applications {
		rows = append(rows, maskWhitelistApplication(app))
	}
	c.JSON(http.StatusOK, APIResponse{Success: true, Data: gin.H{"applications": rows}, Timestamp: time.Now().UTC().Format(time.RFC3339)})
}

func (h *ICOAdminHandler) ProcessEmailOutbox(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Admin access required"})
		return
	}
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "25"))
	processed, err := h.outbox.ProcessPending(c.Request.Context(), limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Failed to process outbox"})
		return
	}
	c.JSON(http.StatusOK, APIResponse{Success: true, Data: gin.H{"processed": processed}, Timestamp: time.Now().UTC().Format(time.RFC3339)})
}

func (h *ICOAdminHandler) GetProductionReadiness(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Admin access required"})
		return
	}
	snapshot, err := h.readiness.Get(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Failed to load ICO production readiness"})
		return
	}
	c.JSON(http.StatusOK, APIResponse{Success: true, Data: snapshot, Timestamp: time.Now().UTC().Format(time.RFC3339)})
}

func (h *ICOAdminHandler) UpdateProductionReadiness(c *gin.Context) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Admin access required"})
		return
	}
	var request icoReadinessUpdateRequest
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Invalid readiness request"})
		return
	}
	actorID := c.GetInt("user_id")
	var updatedBy *int
	if actorID > 0 {
		updatedBy = &actorID
	}
	snapshot, err := h.readiness.Update(c.Request.Context(), repository.ICOReadinessUpdateParams{
		TokenomicsAllocationFinalized: request.TokenomicsAllocationFinalized,
		TokenomicsAllocationNotes:     request.TokenomicsAllocationNotes,
		VestingScheduleFinalized:      request.VestingScheduleFinalized,
		VestingScheduleNotes:          request.VestingScheduleNotes,
		TokenPrice:                    request.TokenPrice,
		AcceptedCurrencies:            request.AcceptedCurrencies,
		SmartContractAddress:          request.SmartContractAddress,
		SmartContractAuditStatus:      request.SmartContractAuditStatus,
		SmartContractAuditURL:         request.SmartContractAuditURL,
		KYCProvider:                   request.KYCProvider,
		KYCPolicyURL:                  request.KYCPolicyURL,
		RestrictedJurisdictions:       request.RestrictedJurisdictions,
		LegalEntityName:               request.LegalEntityName,
		ControllerContact:             request.ControllerContact,
		ParticipationTermsURL:         request.ParticipationTermsURL,
		PrivacyNoticeURL:              request.PrivacyNoticeURL,
		RiskDisclosureURL:             request.RiskDisclosureURL,
		MailgunDNSVerified:            request.MailgunDNSVerified,
		SPFVerified:                   request.SPFVerified,
		DKIMVerified:                  request.DKIMVerified,
		DMARCVerified:                 request.DMARCVerified,
		ProductionSmokeTestPassed:     request.ProductionSmokeTestPassed,
		MonitoringConfigured:          request.MonitoringConfigured,
		AlertingConfigured:            request.AlertingConfigured,
		BackupsConfigured:             request.BackupsConfigured,
		BusinessApproved:              request.BusinessApproved,
		LegalApproved:                 request.LegalApproved,
		TechnicalApproved:             request.TechnicalApproved,
		Published:                     request.Published,
	}, updatedBy)
	if errors.Is(err, services.ErrICOReadinessPublishBlocked) {
		c.JSON(http.StatusConflict, APIResponse{Success: false, Data: snapshot, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "ICO cannot be published until production readiness blockers are resolved"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{Success: false, Timestamp: time.Now().UTC().Format(time.RFC3339), Error: "Failed to update ICO production readiness"})
		return
	}
	c.JSON(http.StatusOK, APIResponse{Success: true, Data: snapshot, Timestamp: time.Now().UTC().Format(time.RFC3339)})
}

func maskWhitelistApplication(app models.ICOWhitelistApplication) gin.H {
	return gin.H{
		"id":                     app.ID,
		"email_masked":           maskEmail(app.NormalizedEmail),
		"status":                 app.Status,
		"marketing_consent":      app.MarketingConsent,
		"marketing_confirmed":    app.MarketingConfirmedAt != nil,
		"privacy_notice_version": app.PrivacyNoticeVersion,
		"email_confirmed":        app.EmailConfirmedAt != nil,
		"unsubscribed":           app.UnsubscribedAt != nil,
		"withdrawn":              app.WithdrawnAt != nil,
		"source":                 app.Source,
		"created_at":             app.CreatedAt,
		"updated_at":             app.UpdatedAt,
	}
}

func maskEmail(email string) string {
	for idx, ch := range email {
		if ch == '@' {
			if idx <= 1 {
				return "*" + email[idx:]
			}
			return email[:1] + "***" + email[idx:]
		}
	}
	if len(email) <= 2 {
		return "**"
	}
	return email[:1] + "***"
}
