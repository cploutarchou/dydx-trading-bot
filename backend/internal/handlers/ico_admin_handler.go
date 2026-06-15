package handlers

import (
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type ICOAdminHandler struct {
	repo   *repository.ICOWhitelistRepository
	outbox *services.ICOEmailOutboxService
}

func NewICOAdminHandler(repo *repository.ICOWhitelistRepository, outbox *services.ICOEmailOutboxService) *ICOAdminHandler {
	return &ICOAdminHandler{repo: repo, outbox: outbox}
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
