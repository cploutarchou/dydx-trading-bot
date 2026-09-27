package handlers

import (
	"context"
	"errors"
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
	// The analysis endpoints (parameter suggestions, backtest explanations,
	// market selection) share the chat's per-user budget: 6 requests a
	// minute, at most 3 back to back, one in flight.
	aiAnalysisRequestsPerSecond = 6.0 / 60.0
	aiAnalysisRequestBurst      = 3
	// Handler deadlines fit one analysis-model call on the chat HTTP client
	// (150 s per attempt) plus the evidence reads.
	aiBacktestExplainDeadline = 150 * time.Second
	aiSuggestParamsDeadline   = 170 * time.Second
)

type AIMarketHandler struct {
	service *services.AIMarketService

	analysisLimiter *middleware.RateLimiter
	inflightMu      sync.Mutex
	inflight        map[int]struct{}
}

func NewAIMarketHandler(service *services.AIMarketService) *AIMarketHandler {
	return &AIMarketHandler{
		service:         service,
		analysisLimiter: middleware.NewRateLimiter(aiAnalysisRequestsPerSecond, aiAnalysisRequestBurst),
		inflight:        make(map[int]struct{}),
	}
}

// analysisActor is the caller of an analysis endpoint with the bot token of
// the request (forwarded only on deployments without a service token).
func analysisActor(c *gin.Context) services.AIAnalysisActor {
	return services.AIAnalysisActor{
		UserID:   getUserID(c),
		IsAdmin:  c.GetBool("is_admin"),
		BotToken: middleware.ExtractRequestAccessToken(c),
	}
}

// acquireAnalysis takes the caller's in-flight slot and a token of the
// per-minute budget; it answers 429 with the chat's codes in the error text
// when either is exhausted. The release is a no-op when acquisition failed.
func (h *AIMarketHandler) acquireAnalysis(c *gin.Context) (func(), bool) {
	userID := getUserID(c)
	h.inflightMu.Lock()
	if _, busy := h.inflight[userID]; busy {
		h.inflightMu.Unlock()
		h.respondError(c, http.StatusTooManyRequests, errors.New(services.StrategyChatCodeBusy+": The assistant is still answering your previous request"), "")
		return func() {}, false
	}
	h.inflight[userID] = struct{}{}
	h.inflightMu.Unlock()
	release := func() {
		h.inflightMu.Lock()
		delete(h.inflight, userID)
		h.inflightMu.Unlock()
	}

	h.analysisLimiter.MaybeCleanup(time.Hour, 10*time.Minute)
	if !h.analysisLimiter.Allow(strconv.Itoa(userID)) {
		release()
		h.respondError(c, http.StatusTooManyRequests, errors.New(services.StrategyChatCodeRateLimited+": Too many requests. Wait a moment and try again."), "")
		return func() {}, false
	}
	return release, true
}

func (h *AIMarketHandler) GetStatus(c *gin.Context) {
	status, err := h.service.Status(getUserID(c))
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to load AI provider status")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      status,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) SaveKey(c *gin.Context) {
	var req services.AICredentialPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid AI key request")
		return
	}

	credential, err := h.service.SaveUserKey(getUserID(c), req)
	if err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to save AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      credential,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) SaveSharedKey(c *gin.Context) {
	if !c.GetBool("is_admin") {
		h.respondError(c, http.StatusForbidden, errors.New("admin access required"), "Admin access required")
		return
	}

	var req services.AICredentialPayload
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid AI key request")
		return
	}

	credential, err := h.service.SaveSharedKey(req)
	if err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to save shared AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      credential,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) DeleteKey(c *gin.Context) {
	provider := c.Param("provider")
	if err := h.service.DeleteUserKey(getUserID(c), provider); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to delete AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true, "provider": provider},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) DeleteSharedKey(c *gin.Context) {
	if !c.GetBool("is_admin") {
		h.respondError(c, http.StatusForbidden, errors.New("admin access required"), "Admin access required")
		return
	}

	provider := strings.TrimSpace(c.Param("provider"))
	if provider == "" {
		h.respondError(c, http.StatusBadRequest, errors.New("provider is required"), "Provider is required")
		return
	}

	if err := h.service.DeleteSharedKey(provider); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to delete shared AI key")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      gin.H{"deleted": true, "provider": provider},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// aiMarketSelectDeadline bounds one market selection: the provider client
// allows 75 s per attempt, so one quick failure and a retry fit.
const aiMarketSelectDeadline = 90 * time.Second

// SelectMarkets ranks the universe the route loaded from the bot; the
// request's markets, when given, restrict that universe.
func (h *AIMarketHandler) SelectMarkets(c *gin.Context, universe *services.MarketUniverse) {
	var req services.AIMarketSelectionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid AI market selection request")
		return
	}
	release, acquired := h.acquireAnalysis(c)
	if !acquired {
		return
	}
	defer release()

	ctx, cancel := context.WithTimeout(c.Request.Context(), aiMarketSelectDeadline)
	defer cancel()

	result, err := h.service.SelectMarkets(ctx, analysisActor(c), req, universe)
	if err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Failed to select dYdX markets with AI")
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) ExplainBacktest(c *gin.Context) {
	var req services.AIBacktestExplainRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid backtest explain request")
		return
	}
	if strings.TrimSpace(req.RunID) == "" {
		h.respondError(c, http.StatusBadRequest, errors.New("run_id is required"), "")
		return
	}
	// Ownership first, so a run that is not the caller's costs no budget.
	actor := analysisActor(c)
	if err := h.service.AuthorizeAIBacktestRun(c.Request.Context(), actor, req.RunID); err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to explain backtest with AI")
		return
	}
	release, acquired := h.acquireAnalysis(c)
	if !acquired {
		return
	}
	defer release()

	ctx, cancel := context.WithTimeout(c.Request.Context(), aiBacktestExplainDeadline)
	defer cancel()
	result, err := h.service.ExplainBacktest(ctx, actor, req)
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to explain backtest with AI")
		return
	}
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) SuggestStrategyParams(c *gin.Context) {
	var req services.AISuggestParamsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid parameter suggestion request")
		return
	}
	if req.StrategyID <= 0 {
		h.respondError(c, http.StatusBadRequest, errors.New("strategy_id is required"), "")
		return
	}
	// Ownership first, so a strategy that is not the caller's costs no budget.
	actor := analysisActor(c)
	if err := h.service.AuthorizeAIStrategy(actor, req.StrategyID); err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to suggest strategy parameters with AI")
		return
	}
	release, acquired := h.acquireAnalysis(c)
	if !acquired {
		return
	}
	defer release()

	ctx, cancel := context.WithTimeout(c.Request.Context(), aiSuggestParamsDeadline)
	defer cancel()
	result, err := h.service.SuggestStrategyParams(ctx, actor, req)
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to suggest strategy parameters with AI")
		return
	}
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) RuntimeDigest(c *gin.Context) {
	var req services.AIRuntimeDigestRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.respondError(c, http.StatusBadRequest, err, "Invalid runtime digest request")
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), 45*time.Second)
	defer cancel()
	result, err := h.service.RuntimeDigest(ctx, analysisActor(c), req)
	if err != nil {
		h.respondError(c, http.StatusBadGateway, err, "Failed to generate runtime digest with AI")
		return
	}
	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      result,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *AIMarketHandler) respondError(c *gin.Context, status int, err error, fallback string) {
	message := fallback
	if err != nil {
		message = err.Error()
	}
	var providerErr *services.AIProviderAccessError
	if errors.As(err, &providerErr) {
		status = providerErr.Code
		message = providerErr.Message
	}
	var requestErr *services.AIRequestError
	if errors.As(err, &requestErr) {
		status = requestErr.Status
		message = requestErr.Message
	}
	if errors.Is(err, context.DeadlineExceeded) {
		status = http.StatusGatewayTimeout
		message = "AI market selection timed out"
	}
	c.JSON(status, APIResponse{
		Success:   false,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Error:     message,
	})
}
