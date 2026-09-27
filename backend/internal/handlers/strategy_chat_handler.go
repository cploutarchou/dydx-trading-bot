package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

const (
	// A user may start 6 chat turns a minute, at most 3 back to back.
	strategyChatTurnsPerSecond = 6.0 / 60.0
	strategyChatTurnBurst      = 3
)

// StrategyChatHandler serves /api/v1/strategies/:id/chat.
type StrategyChatHandler struct {
	service     *services.StrategyChatService
	limiter     *middleware.RateLimiter
	turnTimeout time.Duration
	auditLogger StrategyAuditLogger

	inflightMu sync.Mutex
	inflight   map[int]struct{}
}

// NewStrategyChatHandler creates the chat handler with its per-user limits.
func NewStrategyChatHandler(service *services.StrategyChatService) *StrategyChatHandler {
	return &StrategyChatHandler{
		service:     service,
		limiter:     middleware.NewRateLimiter(strategyChatTurnsPerSecond, strategyChatTurnBurst),
		turnTimeout: services.AIChatMaxDuration(),
		inflight:    make(map[int]struct{}),
	}
}

// SetAuditLogger wires audit logging for applied and created proposals.
func (h *StrategyChatHandler) SetAuditLogger(logger StrategyAuditLogger) {
	h.auditLogger = logger
}

type strategyChatMessageRequest struct {
	SessionID *int64 `json:"session_id"`
	Content   string `json:"content"`
	Provider  string `json:"provider"`
}

type strategyChatApplyRequest struct {
	Fields             *[]string `json:"fields"`
	AcknowledgeRunning bool      `json:"acknowledge_running"`
}

type strategyChatCreateRequest struct {
	Name   string    `json:"name"`
	Fields *[]string `json:"fields"`
}

// GetChat returns the current session, its messages and runtime_active.
func (h *StrategyChatHandler) GetChat(c *gin.Context) {
	actor, strategyID, ok := h.actorAndStrategy(c)
	if !ok {
		return
	}
	state, err := h.service.GetChat(actor, strategyID)
	if err != nil {
		respondStrategyChatError(c, err)
		return
	}
	respondStrategyChat(c, http.StatusOK, state)
}

// StartSession archives the current session and starts a new one.
func (h *StrategyChatHandler) StartSession(c *gin.Context) {
	actor, strategyID, ok := h.actorAndStrategy(c)
	if !ok {
		return
	}
	turn, err := h.service.StartSession(actor, strategyID)
	if err != nil {
		respondStrategyChatError(c, err)
		return
	}
	respondStrategyChat(c, http.StatusOK, turn)
}

// SendMessage runs one chat turn. Each user has at most one turn in flight
// and a small per-minute budget; the in-flight slot is released on every
// path. The strategy and the session are checked first, so a refused request
// (such as a stale session_id) never uses up the budget.
func (h *StrategyChatHandler) SendMessage(c *gin.Context) {
	actor, strategyID, ok := h.actorAndStrategy(c)
	if !ok {
		return
	}
	var req strategyChatMessageRequest
	if err := bindOptionalStrategyChatJSON(c, &req); err != nil {
		respondStrategyChatError(c, invalidStrategyChatRequest("Invalid request body"))
		return
	}
	input := services.StrategyChatSendInput{
		SessionID: req.SessionID,
		Content:   req.Content,
		Provider:  req.Provider,
		BotToken:  middleware.ExtractRequestAccessToken(c),
	}
	if _, _, err := h.service.ValidateMessageInput(input); err != nil {
		respondStrategyChatError(c, err)
		return
	}
	if err := h.service.ValidateSendTarget(actor, strategyID, req.SessionID); err != nil {
		respondStrategyChatError(c, err)
		return
	}

	release, acquired := h.acquireTurn(actor.UserID)
	if !acquired {
		respondStrategyChatError(c, &services.StrategyChatError{
			Status:  http.StatusTooManyRequests,
			Code:    services.StrategyChatCodeBusy,
			Message: "The assistant is still answering your previous message",
		})
		return
	}
	defer release()

	h.limiter.MaybeCleanup(time.Hour, 10*time.Minute)
	if !h.limiter.Allow(strconv.Itoa(actor.UserID)) {
		respondStrategyChatError(c, &services.StrategyChatError{
			Status:  http.StatusTooManyRequests,
			Code:    services.StrategyChatCodeRateLimited,
			Message: "Too many messages. Wait a moment and try again.",
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), h.turnTimeout)
	defer cancel()
	turn, err := h.service.SendMessage(ctx, actor, strategyID, input)
	if err != nil {
		respondStrategyChatError(c, err)
		return
	}
	respondStrategyChat(c, http.StatusOK, turn)
}

// ApplyProposal applies a pending proposal to the strategy.
func (h *StrategyChatHandler) ApplyProposal(c *gin.Context) {
	actor, strategyID, ok := h.actorAndStrategy(c)
	if !ok {
		return
	}
	messageID, ok := strategyChatMessageID(c)
	if !ok {
		return
	}
	var req strategyChatApplyRequest
	if err := bindOptionalStrategyChatJSON(c, &req); err != nil {
		respondStrategyChatError(c, invalidStrategyChatRequest("Invalid request body"))
		return
	}
	result, err := h.service.ApplyProposal(actor, strategyID, messageID, services.StrategyChatApplyInput{
		Fields:             req.Fields,
		AcknowledgeRunning: req.AcknowledgeRunning,
	})
	if err != nil {
		respondStrategyChatError(c, err)
		return
	}
	if h.auditLogger != nil {
		h.auditLogger(c, "strategy.assistant.apply", result.Strategy.ID, result.AuditDetails)
	}
	respondStrategyChat(c, http.StatusOK, gin.H{"strategy": result.Strategy.ToDict(), "message": result.Message})
}

// CreateStrategy creates a new strategy from a pending proposal.
func (h *StrategyChatHandler) CreateStrategy(c *gin.Context) {
	actor, strategyID, ok := h.actorAndStrategy(c)
	if !ok {
		return
	}
	messageID, ok := strategyChatMessageID(c)
	if !ok {
		return
	}
	var req strategyChatCreateRequest
	if err := bindOptionalStrategyChatJSON(c, &req); err != nil {
		respondStrategyChatError(c, invalidStrategyChatRequest("Invalid request body"))
		return
	}
	result, err := h.service.CreateStrategyFromProposal(actor, strategyID, messageID, services.StrategyChatCreateInput{
		Name:   req.Name,
		Fields: req.Fields,
	})
	if err != nil {
		respondStrategyChatError(c, err)
		return
	}
	if h.auditLogger != nil {
		h.auditLogger(c, "strategy.assistant.create", result.Strategy.ID, result.AuditDetails)
	}
	respondStrategyChat(c, http.StatusCreated, gin.H{"strategy": result.Strategy.ToDict(), "message": result.Message})
}

// DismissProposal closes a pending proposal.
func (h *StrategyChatHandler) DismissProposal(c *gin.Context) {
	actor, strategyID, ok := h.actorAndStrategy(c)
	if !ok {
		return
	}
	messageID, ok := strategyChatMessageID(c)
	if !ok {
		return
	}
	message, err := h.service.DismissProposal(actor, strategyID, messageID)
	if err != nil {
		respondStrategyChatError(c, err)
		return
	}
	respondStrategyChat(c, http.StatusOK, gin.H{"message": message})
}

func (h *StrategyChatHandler) acquireTurn(userID int) (func(), bool) {
	h.inflightMu.Lock()
	defer h.inflightMu.Unlock()
	if _, busy := h.inflight[userID]; busy {
		return nil, false
	}
	h.inflight[userID] = struct{}{}
	return func() {
		h.inflightMu.Lock()
		delete(h.inflight, userID)
		h.inflightMu.Unlock()
	}, true
}

func (h *StrategyChatHandler) actorAndStrategy(c *gin.Context) (services.StrategyChatActor, int, bool) {
	userID := getUserID(c)
	if userID <= 0 {
		respondStrategyChatError(c, &services.StrategyChatError{Status: http.StatusUnauthorized, Code: "UNAUTHORIZED", Message: "Unauthorized"})
		return services.StrategyChatActor{}, 0, false
	}
	strategyID, err := strconv.Atoi(strings.TrimSpace(c.Param("id")))
	if err != nil || strategyID <= 0 {
		respondStrategyChatError(c, invalidStrategyChatRequest("Invalid strategy ID"))
		return services.StrategyChatActor{}, 0, false
	}
	return services.StrategyChatActor{UserID: userID, IsAdmin: c.GetBool("is_admin")}, strategyID, true
}

func strategyChatMessageID(c *gin.Context) (int64, bool) {
	messageID, err := strconv.ParseInt(strings.TrimSpace(c.Param("message_id")), 10, 64)
	if err != nil || messageID <= 0 {
		respondStrategyChatError(c, invalidStrategyChatRequest("Invalid message ID"))
		return 0, false
	}
	return messageID, true
}

// bindOptionalStrategyChatJSON decodes a JSON body; an empty body is an empty
// request.
func bindOptionalStrategyChatJSON(c *gin.Context, target any) error {
	if c.Request.Body == nil {
		return nil
	}
	if err := json.NewDecoder(c.Request.Body).Decode(target); err != nil && !errors.Is(err, io.EOF) {
		return err
	}
	return nil
}

func invalidStrategyChatRequest(message string) *services.StrategyChatError {
	return &services.StrategyChatError{Status: http.StatusBadRequest, Code: services.StrategyChatCodeInvalidRequest, Message: message}
}

func respondStrategyChat(c *gin.Context, status int, data any) {
	c.JSON(status, APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func respondStrategyChatError(c *gin.Context, err error) {
	var chatErr *services.StrategyChatError
	if !errors.As(err, &chatErr) {
		log.Printf("strategy_chat unexpected error: %v", err)
		chatErr = &services.StrategyChatError{
			Status:  http.StatusInternalServerError,
			Code:    services.StrategyChatCodeInternal,
			Message: "Something went wrong. Try again.",
		}
	}
	c.JSON(chatErr.Status, gin.H{
		"success":   false,
		"error":     chatErr.Message,
		"code":      chatErr.Code,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}
