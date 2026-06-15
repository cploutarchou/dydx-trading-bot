package handlers

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type ICOMailgunWebhookHandler struct {
	repo *repository.ICOWhitelistRepository
	now  func() time.Time
}

func NewICOMailgunWebhookHandler(repo *repository.ICOWhitelistRepository) *ICOMailgunWebhookHandler {
	return &ICOMailgunWebhookHandler{repo: repo, now: func() time.Time { return time.Now().UTC() }}
}

type mailgunWebhookPayload struct {
	Signature struct {
		Timestamp string `json:"timestamp"`
		Token     string `json:"token"`
		Signature string `json:"signature"`
	} `json:"signature"`
	EventData struct {
		Event     string `json:"event"`
		Timestamp any    `json:"timestamp"`
		Message   struct {
			Headers struct {
				MessageID string `json:"message-id"`
			} `json:"headers"`
		} `json:"message"`
		Recipient string         `json:"recipient"`
		Reason    string         `json:"reason"`
		Delivery  map[string]any `json:"delivery-status"`
	} `json:"event-data"`
}

func (h *ICOMailgunWebhookHandler) Handle(c *gin.Context) {
	var payload mailgunWebhookPayload
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "invalid webhook payload"})
		return
	}
	if !h.verify(payload.Signature.Timestamp, payload.Signature.Token, payload.Signature.Signature) {
		c.JSON(http.StatusUnauthorized, gin.H{"success": false, "message": "invalid webhook signature"})
		return
	}

	normalizedEmail, _ := services.NormalizeICOWhitelistEmail(payload.EventData.Recipient)
	fingerprint := ""
	if normalizedEmail != "" {
		fingerprint = services.EmailFingerprintForWebhook(normalizedEmail)
	}
	eventHash := webhookEventHash(payload.Signature.Timestamp, payload.Signature.Token, payload.EventData.Event, payload.EventData.Message.Headers.MessageID)
	metadataBytes, _ := json.Marshal(map[string]string{
		"reason": strings.TrimSpace(payload.EventData.Reason),
	})
	var providerTimestamp *time.Time
	if ts := parseWebhookTimestamp(payload.EventData.Timestamp); ts != nil {
		providerTimestamp = ts
	}
	if err := h.repo.RecordEmailEvent(
		c.Request.Context(),
		payload.EventData.Message.Headers.MessageID,
		payload.EventData.Event,
		fingerprint,
		providerTimestamp,
		eventHash,
		string(metadataBytes),
	); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "webhook could not be recorded"})
		return
	}

	switch strings.ToLower(strings.TrimSpace(payload.EventData.Event)) {
	case "complained", "unsubscribed", "failed":
		reason := payload.EventData.Event
		if strings.TrimSpace(payload.EventData.Reason) != "" {
			reason = payload.EventData.Reason
		}
		if normalizedEmail != "" {
			_ = h.repo.UpsertSuppression(c.Request.Context(), normalizedEmail, fingerprint, reason, "mailgun_webhook")
		}
	}

	c.JSON(http.StatusOK, gin.H{"success": true})
}

func (h *ICOMailgunWebhookHandler) verify(timestamp, token, signature string) bool {
	key := strings.TrimSpace(os.Getenv("MAILGUN_WEBHOOK_SIGNING_KEY"))
	if key == "" {
		return false
	}
	parsedTimestamp, err := strconv.ParseInt(strings.TrimSpace(timestamp), 10, 64)
	if err != nil {
		return false
	}
	if h.now().Sub(time.Unix(parsedTimestamp, 0)) > 15*time.Minute {
		return false
	}
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(timestamp + token))
	expected := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(strings.TrimSpace(signature)))
}

func webhookEventHash(parts ...string) string {
	sum := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return hex.EncodeToString(sum[:])
}

func parseWebhookTimestamp(value any) *time.Time {
	switch typed := value.(type) {
	case float64:
		t := time.Unix(int64(typed), 0).UTC()
		return &t
	case string:
		if seconds, err := strconv.ParseInt(typed, 10, 64); err == nil {
			t := time.Unix(seconds, 0).UTC()
			return &t
		}
		if parsed, err := time.Parse(time.RFC3339, typed); err == nil {
			t := parsed.UTC()
			return &t
		}
	default:
		_ = fmt.Sprintf("%v", value)
	}
	return nil
}
