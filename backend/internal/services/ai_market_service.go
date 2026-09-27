package services

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math/rand/v2"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const (
	defaultAIMarketHTTPTimeout = 75 * time.Second
	defaultAIMarketLimit       = 35
	maxAIMarketLimit           = 150
	defaultAIMarketMaxRetries  = 3
	// aiMarketSelectionMaxTokens is the visible-output budget of a market
	// selection reply on the Chat Completions and Messages APIs: up to 150
	// tickers, a dozen pairs with reasons and a rationale.
	aiMarketSelectionMaxTokens = 2000
)

var SupportedAIProviders = []string{
	ExternalAPIProviderOpenAI,
	ExternalAPIProviderDeepSeek,
	ExternalAPIProviderClaude,
	ExternalAPIProviderGrok,
}

type AICredentialPayload struct {
	Provider string `json:"provider"`
	APIKey   string `json:"api_key"`
	Label    string `json:"label"`
}

type AIProviderStatus struct {
	Provider           string `json:"provider"`
	Label              string `json:"label"`
	Enabled            bool   `json:"enabled"`
	Available          bool   `json:"available"`
	AvailabilityStatus string `json:"availability_status"`
	UnavailableReason  string `json:"unavailable_reason,omitempty"`
	SharedKeyAvailable bool   `json:"shared_key_available"`
	UserKeyAvailable   bool   `json:"user_key_available"`
	UserKeyMasked      string `json:"user_key_masked"`
	ActiveKeySource    string `json:"active_key_source"`
	Model              string `json:"model"`
	// AnalysisModel is the model used for parameter suggestions, backtest
	// explanations and the strategy chat; empty when the provider runs them
	// on its default model.
	AnalysisModel string `json:"analysis_model"`
}

type AIMarketStatus struct {
	Providers []AIProviderStatus `json:"providers"`
}

type AIMarketSelectionRequest struct {
	Provider string           `json:"provider"`
	Mode     string           `json:"mode"`
	Markets  []string         `json:"markets"`
	Limit    int              `json:"limit"`
	Strategy string           `json:"strategy"`
	Criteria AIMarketCriteria `json:"criteria"`

	// StrategyID, when given and owned by the caller, offers the strategy's
	// pair statistics to the model and returns them in the response pairs.
	StrategyID int `json:"strategy_id"`
}

type AIMarketCriteria struct {
	Objective           string  `json:"objective"`
	VolumeWeight        float64 `json:"volume_weight"`
	LiquidityWeight     float64 `json:"liquidity_weight"`
	TradeabilityWeight  float64 `json:"tradeability_weight"`
	MomentumWeight      float64 `json:"momentum_weight"`
	VolatilityWeight    float64 `json:"volatility_weight"`
	CointegrationWeight float64 `json:"cointegration_weight"`
	RiskWeight          float64 `json:"risk_weight"`
	FutureGainers       bool    `json:"future_gainers"`
	Notes               string  `json:"notes"`
}

type AIMarketSelectionResponse struct {
	Provider        string   `json:"provider"`
	Mode            string   `json:"mode"`
	Source          string   `json:"source"`
	SelectedMarkets []string `json:"selected_markets"`
	Rationale       string   `json:"rationale"`
	Confidence      float64  `json:"confidence"`
	UsedAI          bool     `json:"used_ai"`
	FallbackReason  string   `json:"fallback_reason,omitempty"`

	// Basis, Pairs, MarketStats and DroppedCount say what the selection was
	// built from and how much of the model's answer was discarded.
	Basis        AIMarketSelectionBasis `json:"basis"`
	Pairs        []AIMarketPair         `json:"pairs"`
	MarketStats  []AIMarketStatRow      `json:"market_stats"`
	DroppedCount int                    `json:"dropped_count"`
}

type aiResolvedKey struct {
	key             string
	activeSource    string
	userAvailable   bool
	sharedAvailable bool
}

type AIProviderAccessError struct {
	Code    int
	Message string
}

func (e *AIProviderAccessError) Error() string {
	if e == nil {
		return "AI provider access error"
	}
	return e.Message
}

type aiProviderConfig struct {
	provider string
	model    string
	baseURL  string
}

type aiRequestKind string

const (
	aiRequestKindMarketSelection aiRequestKind = "market_selection"
	aiRequestKindBacktestExplain aiRequestKind = "backtest_explain"
	aiRequestKindStrategyParams  aiRequestKind = "strategy_params"
	aiRequestKindRuntimeDigest   aiRequestKind = "runtime_digest"
	aiRequestKindStrategyChat    aiRequestKind = "strategy_chat"
)

type aiUsage struct {
	PromptTokens          int `json:"prompt_tokens"`
	CompletionTokens      int `json:"completion_tokens"`
	TotalTokens           int `json:"total_tokens"`
	PromptCacheHitTokens  int `json:"prompt_cache_hit_tokens"`
	PromptCacheMissTokens int `json:"prompt_cache_miss_tokens"`
	CompletionDetails     struct {
		ReasoningTokens int `json:"reasoning_tokens"`
	} `json:"completion_tokens_details"`
	// Responses API (xAI) and Anthropic Messages API names for the same counts.
	InputTokens        int `json:"input_tokens"`
	OutputTokens       int `json:"output_tokens"`
	InputTokensDetails struct {
		CachedTokens int `json:"cached_tokens"`
	} `json:"input_tokens_details"`
	OutputTokensDetails struct {
		ReasoningTokens int `json:"reasoning_tokens"`
	} `json:"output_tokens_details"`
}

// aiUsageCounts is one provider's usage in the Chat Completions vocabulary.
type aiUsageCounts struct {
	prompt, completion, total, cacheHit, cacheMiss, reasoning int
}

// counts maps whichever usage names the provider returned onto one set.
func (u aiUsage) counts() aiUsageCounts {
	counts := aiUsageCounts{
		prompt:     u.PromptTokens,
		completion: u.CompletionTokens,
		total:      u.TotalTokens,
		cacheHit:   u.PromptCacheHitTokens,
		cacheMiss:  u.PromptCacheMissTokens,
		reasoning:  u.CompletionDetails.ReasoningTokens,
	}
	if counts.prompt == 0 {
		counts.prompt = u.InputTokens
	}
	if counts.completion == 0 {
		counts.completion = u.OutputTokens
	}
	if counts.cacheHit == 0 {
		counts.cacheHit = u.InputTokensDetails.CachedTokens
	}
	if counts.reasoning == 0 {
		counts.reasoning = u.OutputTokensDetails.ReasoningTokens
	}
	if counts.total == 0 {
		counts.total = counts.prompt + counts.completion
	}
	return counts
}

type aiProviderCallError struct {
	StatusCode int
	Message    string
	Retryable  bool
	// Timeout marks a request the HTTP client gave up on.
	Timeout bool
}

func (e *aiProviderCallError) Error() string {
	if e == nil {
		return "AI provider call error"
	}
	return e.Message
}

type AIMarketService struct {
	credentials *ExternalAPICredentialService
	httpClient  *http.Client
	// chatHTTPClient serves ChatCompletion, whose reasoning replies can take
	// longer than the market-filter calls. Nil falls back to httpClient.
	chatHTTPClient *http.Client
	// Strategy evidence for the analysis endpoints; wired by
	// SetStrategyEvidence, nil in deployments and tests without it.
	evidence   *StrategyEvidenceBuilder
	strategies *StrategyService
	backtests  *repository.BacktestRepository

	// marketEvidence offers a strategy's pair statistics to market selection;
	// nil means selections carry no strategy pairs.
	marketEvidence StrategyEvidenceSource
}

func NewAIMarketService(credentials *ExternalAPICredentialService) *AIMarketService {
	return &AIMarketService{
		credentials:    credentials,
		httpClient:     &http.Client{Timeout: defaultAIMarketHTTPTimeout},
		chatHTTPClient: &http.Client{Timeout: AIChatHTTPTimeout()},
	}
}

func (s *AIMarketService) Status(userID int) (AIMarketStatus, error) {
	providers := make([]AIProviderStatus, 0, len(SupportedAIProviders))
	for _, provider := range SupportedAIProviders {
		enabled := s.providerEnabled(provider)
		resolved, err := s.resolveKey(userID, provider)
		if err != nil {
			return AIMarketStatus{}, err
		}

		info, err := s.credentials.Get(userID, provider)
		if err != nil {
			return AIMarketStatus{}, err
		}

		status := AIProviderStatus{
			Provider:           provider,
			Enabled:            enabled,
			Available:          enabled && strings.TrimSpace(resolved.key) != "",
			SharedKeyAvailable: resolved.sharedAvailable,
			UserKeyAvailable:   resolved.userAvailable,
			Model:              s.providerConfig(provider).model,
			AnalysisModel:      s.analysisModelForProvider(provider),
		}
		switch {
		case !enabled:
			status.AvailabilityStatus = "disabled"
			status.UnavailableReason = "Disabled by administrator"
		case !status.Available:
			status.AvailabilityStatus = "not_configured"
			status.UnavailableReason = "No active API credentials configured"
		default:
			status.AvailabilityStatus = "available"
			status.ActiveKeySource = resolved.activeSource
		}
		if info != nil {
			status.Label = info.Label
			status.UserKeyMasked = info.MaskedValue
		}
		if status.ActiveKeySource == "" {
			status.ActiveKeySource = "none"
		}
		providers = append(providers, status)
	}

	return AIMarketStatus{Providers: providers}, nil
}

func (s *AIMarketService) SaveUserKey(userID int, payload AICredentialPayload) (*ExternalAPICredentialInfo, error) {
	provider, err := normalizeAIProvider(payload.Provider)
	if err != nil {
		return nil, err
	}
	label := strings.TrimSpace(payload.Label)
	if label == "" {
		label = fmt.Sprintf("%s personal key", providerDisplayName(provider))
	}
	return s.credentials.Save(userID, provider, payload.APIKey, label)
}

func (s *AIMarketService) SaveSharedKey(payload AICredentialPayload) (*ExternalAPICredentialInfo, error) {
	provider, err := normalizeAIProvider(payload.Provider)
	if err != nil {
		return nil, err
	}
	label := strings.TrimSpace(payload.Label)
	if label == "" {
		label = fmt.Sprintf("%s shared key", providerDisplayName(provider))
	}
	if s.credentials == nil {
		return nil, fmt.Errorf("credential service is not configured")
	}
	return s.credentials.SaveShared(provider, payload.APIKey, label)
}

func (s *AIMarketService) DeleteUserKey(userID int, provider string) error {
	normalized, err := normalizeAIProvider(provider)
	if err != nil {
		return err
	}
	return s.credentials.Delete(userID, normalized)
}

func (s *AIMarketService) DeleteSharedKey(provider string) error {
	normalized, err := normalizeAIProvider(provider)
	if err != nil {
		return err
	}
	if s.credentials == nil {
		return fmt.Errorf("credential service is not configured")
	}
	return s.credentials.DeleteShared(normalized)
}

// SelectMarkets ranks the tradable universe the route loaded: a deterministic
// score orders the markets, the model sees the numbers as a table, and its
// answer is validated against the same universe. A provider failure falls
// back to the score order, never to an alphabetical list.
func (s *AIMarketService) SelectMarkets(ctx context.Context, actor AIAnalysisActor, req AIMarketSelectionRequest, universe *MarketUniverse) (*AIMarketSelectionResponse, error) {
	provider, resolved, err := s.resolveUsableKey(actor.UserID, req.Provider)
	if err != nil {
		return nil, err
	}
	if universe == nil {
		return nil, fmt.Errorf("dYdX market universe is required for AI selection")
	}

	mode := normalizeAIMarketMode(req.Mode)
	limit := req.Limit
	if limit <= 0 {
		limit = defaultAIMarketLimit
	}
	if limit > maxAIMarketLimit {
		limit = maxAIMarketLimit
	}

	stats := restrictMarketUniverse(universe, req.Markets)
	if len(stats) < 2 {
		return nil, fmt.Errorf("at least two tradable dYdX markets with market data are required for AI selection")
	}

	criteria := normalizeAIMarketCriteria(req.Criteria, mode)
	ranked := scoreMarkets(stats, criteria)
	rows := aiMarketPromptRowCount(len(ranked), limit)
	evidence, evidenceErr := s.marketPairEvidence(ctx, actor, req.StrategyID, ranked)
	if evidenceErr != nil {
		log.Printf("ai_market_selection strategy pair evidence unavailable strategy_id=%d: %v", req.StrategyID, evidenceErr)
	}
	selection := marketSelection{
		provider:   provider,
		mode:       mode,
		limit:      limit,
		ranked:     ranked,
		hasDetails: universe.HasDetails,
		basis:      marketSelectionBasis(universe, ranked, rows, evidence),
		evidence:   evidence,
	}

	prompt := buildAIMarketPromptWithTable(aiMarketPromptInput{
		Mode:       mode,
		Limit:      limit,
		Strategy:   req.Strategy,
		Criteria:   criteria,
		Ranked:     ranked,
		Rows:       rows,
		Network:    universe.Network,
		Source:     universe.Source,
		HasDetails: universe.HasDetails,
		Evidence:   evidence,
	})
	reply, err := s.callMarketSelectionProvider(ctx, resolved.key, provider, prompt, limit)
	if err != nil {
		return fallbackAIMarketSelection(selection, aiMarketFallbackReason(provider, err, actor.IsAdmin)), nil
	}

	selected, modelPairs, dropped := validateMarketSelection(reply, ranked, limit)
	if len(selected) < 2 {
		return fallbackAIMarketSelection(selection, "AI response did not include enough valid dYdX markets."), nil
	}
	pairs := mergeMarketPairs(evidencePairsWithin(selected, evidence), modelPairs)
	return selection.response(aiMarketSourceAI, selected, pairs, truncateAIText(reply.Rationale, 1200), reply.Confidence, true, "", dropped), nil
}

func (s *AIMarketService) resolveUsableKey(userID int, provider string) (string, aiResolvedKey, error) {
	normalized, err := normalizeAIProvider(provider)
	if err != nil {
		return "", aiResolvedKey{}, err
	}

	if !s.providerEnabled(normalized) {
		return normalized, aiResolvedKey{}, &AIProviderAccessError{
			Code:    http.StatusForbidden,
			Message: fmt.Sprintf("%s is disabled by administrator", providerDisplayName(normalized)),
		}
	}

	resolved, err := s.resolveKey(userID, normalized)
	if err != nil {
		return normalized, aiResolvedKey{}, err
	}

	if strings.TrimSpace(resolved.key) == "" {
		return normalized, aiResolvedKey{}, &AIProviderAccessError{
			Code:    http.StatusConflict,
			Message: fmt.Sprintf("%s is not configured with active credentials", providerDisplayName(normalized)),
		}
	}

	return normalized, resolved, nil
}

func (s *AIMarketService) resolveKey(userID int, provider string) (aiResolvedKey, error) {
	normalized, err := normalizeAIProvider(provider)
	if err != nil {
		return aiResolvedKey{}, err
	}

	sharedEnvKey := strings.TrimSpace(os.Getenv(sharedAIKeyEnv(normalized)))
	resolved := aiResolvedKey{
		sharedAvailable: sharedEnvKey != "",
		activeSource:    "none",
	}

	if s.credentials != nil {
		key, ok, err := s.credentials.ResolveKey(userID, normalized)
		if err != nil {
			return resolved, fmt.Errorf("failed to resolve %s API key: %w", providerDisplayName(normalized), err)
		}
		if ok && strings.TrimSpace(key) != "" {
			resolved.key = strings.TrimSpace(key)
			resolved.userAvailable = true
			resolved.activeSource = "user"
			return resolved, nil
		}

		sharedKey, sharedOk, sharedErr := s.credentials.ResolveSharedKey(normalized)
		if sharedErr != nil {
			return resolved, fmt.Errorf("failed to resolve shared %s API key: %w", providerDisplayName(normalized), sharedErr)
		}
		if sharedOk && strings.TrimSpace(sharedKey) != "" {
			resolved.sharedAvailable = true
			resolved.key = strings.TrimSpace(sharedKey)
			resolved.activeSource = "shared"
			return resolved, nil
		}
	}

	if sharedEnvKey != "" {
		resolved.key = sharedEnvKey
		resolved.activeSource = "shared"
	}

	return resolved, nil
}

func (s *AIMarketService) providerEnabled(provider string) bool {
	var key string
	switch provider {
	case ExternalAPIProviderOpenAI:
		key = "AI_PROVIDER_OPENAI_ENABLED"
	case ExternalAPIProviderDeepSeek:
		key = "AI_PROVIDER_DEEPSEEK_ENABLED"
	case ExternalAPIProviderClaude:
		key = "AI_PROVIDER_CLAUDE_ENABLED"
	case ExternalAPIProviderGrok:
		key = "AI_PROVIDER_GROK_ENABLED"
	default:
		// An unknown provider is never enabled, so it cannot borrow another
		// provider's key or endpoint.
		return false
	}

	raw := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if raw == "" {
		return true
	}

	switch raw {
	case "1", "true", "yes", "on", "enabled":
		return true
	case "0", "false", "no", "off", "disabled":
		return false
	default:
		return true
	}
}

// callProvider ranks a names-only universe: the tickers in the given order
// with no statistics. SelectMarkets builds its prompt from the bot's market
// data instead; this entry point remains for callers that only have names.
func (s *AIMarketService) callProvider(ctx context.Context, apiKey string, provider string, mode string, markets []string, limit int, strategy string, criteria AIMarketCriteria) (*AIMarketSelectionResponse, error) {
	mode = normalizeAIMarketMode(mode)
	criteria = normalizeAIMarketCriteria(criteria, mode)
	ranked := scoreMarkets(marketStatsFromTickers(markets), criteria)
	prompt := buildAIMarketPromptWithTable(aiMarketPromptInput{
		Mode:     mode,
		Limit:    limit,
		Strategy: strategy,
		Criteria: criteria,
		Ranked:   ranked,
		Rows:     aiMarketPromptRowCount(len(ranked), limit),
	})
	return s.callMarketSelectionProvider(ctx, apiKey, provider, prompt, limit)
}

// callMarketSelectionProvider sends the prompt to the provider and parses the
// reply; validation against the universe happens in SelectMarkets.
func (s *AIMarketService) callMarketSelectionProvider(ctx context.Context, apiKey string, provider string, prompt string, limit int) (*AIMarketSelectionResponse, error) {
	config := s.providerConfig(provider)
	switch provider {
	case ExternalAPIProviderClaude:
		return s.callClaude(ctx, apiKey, config, prompt)
	case ExternalAPIProviderGrok:
		return s.callXAIMarketSelection(ctx, apiKey, config, prompt, limit)
	case ExternalAPIProviderOpenAI, ExternalAPIProviderDeepSeek:
		return s.callOpenAICompatible(ctx, apiKey, config, prompt)
	default:
		return nil, fmt.Errorf("unsupported AI provider: %s", provider)
	}
}

func (s *AIMarketService) callOpenAICompatible(ctx context.Context, apiKey string, config aiProviderConfig, prompt string) (*AIMarketSelectionResponse, error) {
	body := map[string]any{
		"model": config.model,
		"messages": []map[string]string{
			{"role": "system", "content": "You rank dYdX perpetual markets for a crypto pairs-trading strategy. Return only valid JSON. The response must be a JSON object matching the provided schema example."},
			{"role": "user", "content": prompt},
		},
		"temperature": 0.2,
		"max_tokens":  aiMarketSelectionMaxTokens,
		"response_format": map[string]string{
			"type": "json_object",
		},
	}
	applyDeepSeekOptions(body, config, aiRequestKindMarketSelection)

	var response struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
			FinishReason string `json:"finish_reason"`
		} `json:"choices"`
		Usage aiUsage `json:"usage"`
	}

	if err := s.executeJSON(ctx, config, aiRequestKindMarketSelection, apiKey, body, &response, nil); err != nil {
		return nil, err
	}
	if len(response.Choices) == 0 {
		return nil, fmt.Errorf("%s returned no market ranking choices", providerDisplayName(config.provider))
	}
	if response.Choices[0].FinishReason == "length" {
		// A reply cut at the token limit is partial JSON: never parsed, the
		// caller falls back to the deterministic ranking.
		return nil, &aiReplyCutOffError{Provider: config.provider}
	}
	return parseAIMarketSelection(response.Choices[0].Message.Content)
}

// Messages API requests carry no temperature: the provider's newer models
// reject a non-default value, and the default is fine for these tasks.
func (s *AIMarketService) callClaude(ctx context.Context, apiKey string, config aiProviderConfig, prompt string) (*AIMarketSelectionResponse, error) {
	body := map[string]any{
		"model":      config.model,
		"max_tokens": aiMarketSelectionMaxTokens,
		"system":     "You rank dYdX perpetual markets for a crypto pairs-trading strategy. Return only valid JSON.",
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
	}

	var response struct {
		Content []struct {
			Text string `json:"text"`
			Type string `json:"type"`
		} `json:"content"`
		StopReason string  `json:"stop_reason"`
		Usage      aiUsage `json:"usage"`
	}

	headers := map[string]string{
		"x-api-key":         apiKey,
		"anthropic-version": "2023-06-01",
	}
	if err := s.executeJSON(ctx, config, aiRequestKindMarketSelection, "", body, &response, headers); err != nil {
		return nil, err
	}
	if response.StopReason == "max_tokens" {
		return nil, &aiReplyCutOffError{Provider: config.provider}
	}
	for _, part := range response.Content {
		if strings.TrimSpace(part.Text) != "" {
			return parseAIMarketSelection(part.Text)
		}
	}
	return nil, fmt.Errorf("claude returned no market ranking content")
}

// aiCallPolicy is how many times, over which client, a provider call is tried.
type aiCallPolicy struct {
	client      *http.Client
	maxAttempts int
	// retryServerErrors also retries 502 and 504, and retryTimeouts decides
	// whether a client timeout counts as a retryable network failure.
	retryServerErrors bool
	retryTimeouts     bool
	// describeErrors appends the provider's own error message to a rejected
	// request, read from either {"code","error"} or {"error":{"message"}}.
	describeErrors bool
}

func (s *AIMarketService) executeJSON(ctx context.Context, config aiProviderConfig, kind aiRequestKind, bearer string, payload any, target any, headers map[string]string) error {
	return s.executeJSONWithPolicy(ctx, aiCallPolicy{
		client:         s.httpClient,
		maxAttempts:    defaultAIMarketMaxRetries,
		retryTimeouts:  true,
		describeErrors: config.provider == ExternalAPIProviderGrok,
	}, config, kind, bearer, payload, target, headers)
}

func (s *AIMarketService) executeJSONWithPolicy(ctx context.Context, policy aiCallPolicy, config aiProviderConfig, kind aiRequestKind, bearer string, payload any, target any, headers map[string]string) error {
	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to encode AI request: %w", err)
	}
	if policy.client == nil {
		policy.client = s.httpClient
	}
	if policy.maxAttempts <= 0 {
		policy.maxAttempts = 1
	}

	var lastErr error
	for attempt := 1; attempt <= policy.maxAttempts; attempt++ {
		started := time.Now()
		responseBody, statusCode, err := s.executeJSONAttempt(ctx, policy.client, config.baseURL, bearer, bodyBytes, headers)
		latency := time.Since(started)
		if err == nil {
			if err := json.Unmarshal(responseBody, target); err != nil {
				return fmt.Errorf("failed to decode AI response: %w", err)
			}
			logAIProviderUsage(config, kind, attempt, statusCode, latency, responseBody, nil)
			return nil
		}

		if policy.describeErrors {
			describeAIProviderError(err, responseBody)
		}
		logAIProviderUsage(config, kind, attempt, statusCode, latency, responseBody, err)
		lastErr = err
		if !policy.shouldRetry(err) || attempt == policy.maxAttempts {
			break
		}
		if sleepErr := sleepAIBackoff(ctx, attempt); sleepErr != nil {
			return sleepErr
		}
	}
	return lastErr
}

func (p aiCallPolicy) shouldRetry(err error) bool {
	if !p.retryTimeouts && isAIClientTimeout(err) {
		return false
	}
	if shouldRetryAIProviderError(err) {
		return true
	}
	var callErr *aiProviderCallError
	return p.retryServerErrors && errors.As(err, &callErr) && callErr.StatusCode >= 500
}

func (s *AIMarketService) executeJSONAttempt(ctx context.Context, client *http.Client, url string, bearer string, bodyBytes []byte, headers map[string]string) ([]byte, int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, 0, fmt.Errorf("failed to create AI request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if strings.TrimSpace(bearer) != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	for key, value := range headers {
		req.Header.Set(key, value)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, &aiProviderCallError{
			Message:   fmt.Sprintf("failed to reach AI provider: %v", err),
			Retryable: true,
			Timeout:   isNetTimeout(err),
		}
	}
	defer func() { _ = resp.Body.Close() }()

	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return responseBody, resp.StatusCode, &aiProviderCallError{
			StatusCode: resp.StatusCode,
			Message:    fmt.Sprintf("failed to read AI response: %v", err),
			Retryable:  true,
		}
	}
	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		return responseBody, resp.StatusCode, &aiProviderCallError{
			StatusCode: resp.StatusCode,
			Message:    "AI provider rejected the configured API key",
			Retryable:  false,
		}
	}
	if resp.StatusCode == http.StatusTooManyRequests {
		return responseBody, resp.StatusCode, &aiProviderCallError{
			StatusCode: resp.StatusCode,
			Message:    "AI provider rate limit reached",
			Retryable:  true,
		}
	}
	if resp.StatusCode == http.StatusPaymentRequired {
		return responseBody, resp.StatusCode, &aiProviderCallError{
			StatusCode: resp.StatusCode,
			Message:    "AI provider account has insufficient balance",
			Retryable:  false,
		}
	}
	if resp.StatusCode == http.StatusRequestTimeout || resp.StatusCode == http.StatusInternalServerError || resp.StatusCode == http.StatusServiceUnavailable {
		return responseBody, resp.StatusCode, &aiProviderCallError{
			StatusCode: resp.StatusCode,
			Message:    fmt.Sprintf("AI provider returned status %d", resp.StatusCode),
			Retryable:  true,
		}
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return responseBody, resp.StatusCode, &aiProviderCallError{
			StatusCode: resp.StatusCode,
			Message:    fmt.Sprintf("AI provider returned status %d", resp.StatusCode),
			Retryable:  false,
		}
	}
	return responseBody, resp.StatusCode, nil
}

func (s *AIMarketService) providerConfig(provider string) aiProviderConfig {
	switch provider {
	case ExternalAPIProviderOpenAI:
		return aiProviderConfig{
			provider: ExternalAPIProviderOpenAI,
			model:    envWithDefault("OPENAI_MODEL", "gpt-4o-mini"),
			baseURL:  envWithDefault("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
		}
	case ExternalAPIProviderDeepSeek:
		return aiProviderConfig{
			provider: provider,
			model:    envWithDefault("DEEPSEEK_MODEL", "deepseek-v4-flash"),
			baseURL:  envWithDefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions"),
		}
	case ExternalAPIProviderClaude:
		return aiProviderConfig{
			provider: provider,
			model:    envWithDefault("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
			baseURL:  envWithDefault("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1/messages"),
		}
	case ExternalAPIProviderGrok:
		return aiProviderConfig{
			provider: provider,
			model:    envWithDefault("XAI_MODEL", "grok-4.3"),
			baseURL:  envWithDefault("XAI_BASE_URL", "https://api.x.ai/v1/responses"),
		}
	default:
		// No endpoint and no model: a call for an unknown provider fails
		// instead of reaching another provider's API.
		return aiProviderConfig{provider: provider}
	}
}

func parseAIMarketSelection(content string) (*AIMarketSelectionResponse, error) {
	trimmed := strings.TrimSpace(content)
	trimmed = strings.TrimPrefix(trimmed, "```json")
	trimmed = strings.TrimPrefix(trimmed, "```")
	trimmed = strings.TrimSuffix(trimmed, "```")
	trimmed = strings.TrimSpace(trimmed)

	// The pairs are optional in JSON-mode replies; the strict Grok schema
	// always carries them. Nothing here is trusted: SelectMarkets validates
	// every ticker and pair against the universe.
	var parsed struct {
		SelectedMarkets []string `json:"selected_markets"`
		Pairs           []struct {
			Market1 string `json:"market_1"`
			Market2 string `json:"market_2"`
			Reason  string `json:"reason"`
		} `json:"pairs"`
		Rationale  string  `json:"rationale"`
		Confidence float64 `json:"confidence"`
	}
	if err := json.Unmarshal([]byte(trimmed), &parsed); err != nil {
		return nil, fmt.Errorf("AI provider returned non-JSON market ranking")
	}
	if len(parsed.SelectedMarkets) < 2 {
		return nil, fmt.Errorf("AI provider returned fewer than two selected markets")
	}
	if parsed.Confidence < 0 {
		parsed.Confidence = 0
	}
	if parsed.Confidence > 1 {
		parsed.Confidence = 1
	}
	pairs := make([]AIMarketPair, 0, len(parsed.Pairs))
	for _, pair := range parsed.Pairs {
		pairs = append(pairs, AIMarketPair{Market1: pair.Market1, Market2: pair.Market2, Reason: pair.Reason, Source: aiMarketPairSourceModel})
	}
	return &AIMarketSelectionResponse{
		SelectedMarkets: parsed.SelectedMarkets,
		Pairs:           pairs,
		Rationale:       parsed.Rationale,
		Confidence:      parsed.Confidence,
	}, nil
}

// fallbackAIMarketSelection answers from the deterministic score order when
// the model could not: the top markets by score, the strategy's own pairs
// among them, and a rationale that says what ordered them.
func fallbackAIMarketSelection(sel marketSelection, reason string) *AIMarketSelectionResponse {
	limit := sel.limit
	if limit > len(sel.ranked) {
		limit = len(sel.ranked)
	}
	selected := make([]string, 0, limit)
	for _, market := range sel.ranked[:limit] {
		selected = append(selected, market.Ticker)
	}
	rationale := "AI ranking was unavailable; markets are ranked by the deterministic score from dYdX market data: 24 h volume, open interest and trade count, thin markets penalised."
	switch {
	case !sel.hasDetails:
		rationale = "AI ranking was unavailable and the bot sent no market statistics; markets are listed in the bot's 24 h volume order."
	case marketsHavePriceChange(marketStatsOf(sel.ranked)):
		rationale = "AI ranking was unavailable; markets are ranked by the deterministic score from dYdX market data: 24 h volume, open interest, trade count and 24 h price change, thin markets penalised."
	}
	return sel.response(aiMarketSourceDeterministic, selected, evidencePairsWithin(selected, sel.evidence), rationale, 0, false, reason, 0)
}

func normalizeAIMarketCriteria(criteria AIMarketCriteria, mode string) AIMarketCriteria {
	// The objective is free text from the browser that reaches the prompt:
	// sanitized and bounded like every other caller string.
	objective := strings.ToLower(sanitizeStrategyChatText(criteria.Objective, 64))
	if objective == "" {
		objective = mode
	}

	normalized := AIMarketCriteria{
		Objective:           objective,
		VolumeWeight:        clampCriteriaWeight(criteria.VolumeWeight, 0.65),
		LiquidityWeight:     clampCriteriaWeight(criteria.LiquidityWeight, 0.75),
		TradeabilityWeight:  clampCriteriaWeight(criteria.TradeabilityWeight, 0.75),
		MomentumWeight:      clampCriteriaWeight(criteria.MomentumWeight, 0.35),
		VolatilityWeight:    clampCriteriaWeight(criteria.VolatilityWeight, 0.45),
		CointegrationWeight: clampCriteriaWeight(criteria.CointegrationWeight, 0.65),
		RiskWeight:          clampCriteriaWeight(criteria.RiskWeight, 0.55),
		FutureGainers:       criteria.FutureGainers,
		Notes:               strings.TrimSpace(criteria.Notes),
	}

	switch objective {
	case "volume", "highest_volume":
		normalized.VolumeWeight = maxAICriteriaWeight(normalized.VolumeWeight, 0.9)
		normalized.LiquidityWeight = maxAICriteriaWeight(normalized.LiquidityWeight, 0.85)
		normalized.TradeabilityWeight = maxAICriteriaWeight(normalized.TradeabilityWeight, 0.8)
	case "tradeable", "most_tradeable":
		normalized.TradeabilityWeight = maxAICriteriaWeight(normalized.TradeabilityWeight, 0.95)
		normalized.LiquidityWeight = maxAICriteriaWeight(normalized.LiquidityWeight, 0.9)
		normalized.RiskWeight = maxAICriteriaWeight(normalized.RiskWeight, 0.75)
	case "future_gainers", "gainers":
		normalized.FutureGainers = true
		normalized.MomentumWeight = maxAICriteriaWeight(normalized.MomentumWeight, 0.85)
		normalized.VolumeWeight = maxAICriteriaWeight(normalized.VolumeWeight, 0.65)
	case "volatility":
		normalized.VolatilityWeight = maxAICriteriaWeight(normalized.VolatilityWeight, 0.85)
		normalized.RiskWeight = maxAICriteriaWeight(normalized.RiskWeight, 0.65)
	case "cointegration", "pairs_trading":
		normalized.CointegrationWeight = maxAICriteriaWeight(normalized.CointegrationWeight, 0.9)
		normalized.TradeabilityWeight = maxAICriteriaWeight(normalized.TradeabilityWeight, 0.8)
	}

	return normalized
}

func clampCriteriaWeight(value float64, fallback float64) float64 {
	if value <= 0 {
		return fallback
	}
	if value > 1 {
		return 1
	}
	return value
}

func maxAICriteriaWeight(left float64, right float64) float64 {
	if left > right {
		return left
	}
	return right
}

func normalizeAIProvider(provider string) (string, error) {
	normalized := strings.TrimSpace(strings.ToLower(provider))
	switch normalized {
	case "", ExternalAPIProviderOpenAI:
		return ExternalAPIProviderOpenAI, nil
	case ExternalAPIProviderDeepSeek:
		return ExternalAPIProviderDeepSeek, nil
	case ExternalAPIProviderClaude, "anthropic":
		return ExternalAPIProviderClaude, nil
	case ExternalAPIProviderGrok, "xai", "x.ai":
		return ExternalAPIProviderGrok, nil
	default:
		return "", fmt.Errorf("unsupported AI provider: %s", provider)
	}
}

func normalizeAIMarketMode(mode string) string {
	normalized := strings.TrimSpace(strings.ToLower(mode))
	switch normalized {
	case "popular", "most_popular":
		return "most_popular"
	case "profitable", "most_profitable":
		return "most_profitable"
	case "top20", "top_20":
		return "top_20"
	default:
		return "ai_recommended"
	}
}

func sharedAIKeyEnv(provider string) string {
	switch provider {
	case ExternalAPIProviderOpenAI:
		return "OPENAI_API_KEY"
	case ExternalAPIProviderDeepSeek:
		return "DEEPSEEK_API_KEY"
	case ExternalAPIProviderClaude:
		return "ANTHROPIC_API_KEY"
	case ExternalAPIProviderGrok:
		return "XAI_API_KEY"
	default:
		return ""
	}
}

func providerDisplayName(provider string) string {
	switch provider {
	case ExternalAPIProviderOpenAI:
		return "OpenAI"
	case ExternalAPIProviderDeepSeek:
		return "DeepSeek"
	case ExternalAPIProviderClaude:
		return "Claude"
	case ExternalAPIProviderGrok:
		return "Grok"
	default:
		return ""
	}
}

func envWithDefault(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

// ==================== AI TEXT GENERATION ====================

// AITextResponse is the shared response shape for free-text AI endpoints.
type AITextResponse struct {
	Provider string `json:"provider"`
	Content  string `json:"content"`
	UsedAI   bool   `json:"used_ai"`
}

// AIRuntimeDigestRequest carries a live runtime snapshot.
type AIRuntimeDigestRequest struct {
	Provider      string  `json:"provider"`
	RunningBots   int     `json:"running_bots"`
	TotalBots     int     `json:"total_bots"`
	OpenPositions int     `json:"open_positions"`
	TotalPnlUSD   float64 `json:"total_pnl_usd"`
	ActivePairs   int     `json:"active_pairs"`
	ErrorCount    int     `json:"error_count"`
	Network       string  `json:"network"`
}

// RuntimeDigest generates a 2-sentence live operational health verdict. A
// provider failure yields the fixed message of its class; the provider's own
// text is shown to admins only.
func (s *AIMarketService) RuntimeDigest(ctx context.Context, actor AIAnalysisActor, req AIRuntimeDigestRequest) (*AITextResponse, error) {
	provider, err := normalizeAIProvider(req.Provider)
	if err != nil {
		provider = ExternalAPIProviderDeepSeek
	}
	provider, resolved, err := s.resolveUsableKey(actor.UserID, provider)
	if err != nil {
		return nil, err
	}

	network := req.Network
	if network == "" {
		network = "unknown"
	}

	systemPrompt := "You are a trading operations assistant monitoring a live DeFi pairs trading system. Be very concise. No markdown. Respond in exactly 2 sentences: first a health verdict, second a recommended action."
	userPrompt := fmt.Sprintf(
		`Live runtime snapshot (network: %s):
- Running bots: %d of %d total
- Open positions: %d
- Active pairs: %d
- Unrealised PnL: $%.2f
- Bots in error state: %d

Give a 2-sentence operational health verdict and recommended action.`,
		network, req.RunningBots, req.TotalBots,
		req.OpenPositions, req.ActivePairs,
		req.TotalPnlUSD, req.ErrorCount,
	)
	content, err := s.callAIForTextTask(ctx, resolved.key, provider, aiRequestKindRuntimeDigest, systemPrompt, userPrompt)
	if err != nil {
		return &AITextResponse{Provider: provider, Content: analysisUnavailableMessage(ctx, actor, provider, err), UsedAI: false}, nil
	}
	return &AITextResponse{Provider: provider, Content: content, UsedAI: true}, nil
}

func (s *AIMarketService) callAIForTextTask(ctx context.Context, apiKey string, provider string, kind aiRequestKind, systemPrompt string, userPrompt string) (string, error) {
	config := s.providerConfigForKind(provider, kind)
	switch provider {
	case ExternalAPIProviderClaude:
		return s.callClaudeForText(ctx, apiKey, config, kind, systemPrompt, userPrompt)
	case ExternalAPIProviderGrok:
		return s.callXAIForText(ctx, apiKey, config, kind, systemPrompt, userPrompt)
	case ExternalAPIProviderOpenAI, ExternalAPIProviderDeepSeek:
		return s.callOpenAICompatibleForText(ctx, apiKey, config, kind, systemPrompt, userPrompt)
	default:
		return "", fmt.Errorf("unsupported AI provider: %s", provider)
	}
}

func (s *AIMarketService) callOpenAICompatibleForText(ctx context.Context, apiKey string, config aiProviderConfig, kind aiRequestKind, systemPrompt string, userPrompt string) (string, error) {
	body := map[string]any{
		"model": config.model,
		"messages": []map[string]string{
			{"role": "system", "content": systemPrompt},
			{"role": "user", "content": userPrompt},
		},
		"temperature": 0.3,
		"max_tokens":  maxTokensForAIRequest(kind),
	}
	applyDeepSeekOptions(body, config, kind)

	content, err := s.executeOpenAICompatibleText(ctx, apiKey, config, kind, body)
	if err == nil {
		return content, nil
	}

	if config.provider == ExternalAPIProviderDeepSeek && kind == aiRequestKindStrategyParams && isEmptyAIContentError(err) {
		fallbackBody := cloneAIRequestBody(body)
		fallbackBody["thinking"] = map[string]string{"type": "disabled"}
		delete(fallbackBody, "reasoning_effort")
		return s.executeOpenAICompatibleText(ctx, apiKey, config, kind, fallbackBody)
	}

	return "", err
}

func (s *AIMarketService) executeOpenAICompatibleText(ctx context.Context, apiKey string, config aiProviderConfig, kind aiRequestKind, body map[string]any) (string, error) {
	var response struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage aiUsage `json:"usage"`
	}
	if err := s.aiExecutorForKind(kind)(ctx, config, kind, apiKey, body, &response, nil); err != nil {
		return "", err
	}
	if len(response.Choices) == 0 {
		return "", fmt.Errorf("%s returned no response", providerDisplayName(config.provider))
	}
	content := strings.TrimSpace(response.Choices[0].Message.Content)
	if content == "" {
		return "", &aiProviderCallError{
			Message:   fmt.Sprintf("%s returned empty content", providerDisplayName(config.provider)),
			Retryable: true,
		}
	}
	return content, nil
}

func (s *AIMarketService) callClaudeForText(ctx context.Context, apiKey string, config aiProviderConfig, kind aiRequestKind, systemPrompt string, userPrompt string) (string, error) {
	body := map[string]any{
		"model":      config.model,
		"max_tokens": maxTokensForAIRequest(kind),
		"system":     systemPrompt,
		"messages": []map[string]string{
			{"role": "user", "content": userPrompt},
		},
	}
	var response struct {
		Content []struct {
			Text string `json:"text"`
		} `json:"content"`
		Usage aiUsage `json:"usage"`
	}
	headers := map[string]string{
		"x-api-key":         apiKey,
		"anthropic-version": "2023-06-01",
	}
	if err := s.aiExecutorForKind(kind)(ctx, config, kind, "", body, &response, headers); err != nil {
		return "", err
	}
	for _, part := range response.Content {
		if t := strings.TrimSpace(part.Text); t != "" {
			return t, nil
		}
	}
	return "", fmt.Errorf("claude returned no content")
}

func applyDeepSeekOptions(body map[string]any, config aiProviderConfig, kind aiRequestKind) {
	if config.provider != ExternalAPIProviderDeepSeek {
		return
	}

	// JSON mode (response_format json_object) is only relied on without
	// thinking, whatever the kind: market selection, the strategy chat and
	// the parameter suggestions all read one JSON object back.
	if _, jsonMode := body["response_format"]; jsonMode {
		body["thinking"] = map[string]string{"type": "disabled"}
		return
	}
	switch kind {
	case aiRequestKindStrategyParams:
		body["thinking"] = map[string]string{"type": "enabled"}
		body["reasoning_effort"] = envWithDefault("DEEPSEEK_REASONING_EFFORT", "high")
		delete(body, "temperature")
	default:
		body["thinking"] = map[string]string{"type": "disabled"}
	}
}

func maxTokensForAIRequest(kind aiRequestKind) int {
	switch kind {
	case aiRequestKindStrategyParams:
		return 4096
	case aiRequestKindMarketSelection:
		return aiMarketSelectionMaxTokens
	case aiRequestKindRuntimeDigest:
		return 320
	default:
		return 700
	}
}

func shouldRetryAIProviderError(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return false
	}
	var callErr *aiProviderCallError
	return errors.As(err, &callErr) && callErr.Retryable
}

func isEmptyAIContentError(err error) bool {
	var callErr *aiProviderCallError
	return errors.As(err, &callErr) && strings.Contains(strings.ToLower(callErr.Message), "empty content")
}

func cloneAIRequestBody(body map[string]any) map[string]any {
	clone := make(map[string]any, len(body))
	for key, value := range body {
		clone[key] = value
	}
	return clone
}

func sleepAIBackoff(ctx context.Context, attempt int) error {
	base := 200 * time.Millisecond
	delay := base << max(attempt-1, 0)
	if delay > 2*time.Second {
		delay = 2 * time.Second
	}
	jitter := time.Duration(rand.Int64N(int64(delay / 2)))
	timer := time.NewTimer(delay + jitter)
	defer timer.Stop()

	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func logAIProviderUsage(config aiProviderConfig, kind aiRequestKind, attempt int, statusCode int, latency time.Duration, responseBody []byte, err error) {
	var envelope struct {
		Usage aiUsage `json:"usage"`
	}
	if len(responseBody) > 0 {
		_ = json.Unmarshal(responseBody, &envelope)
	}
	usage := envelope.Usage.counts()

	errorClass := ""
	if err != nil {
		errorClass = classifyAIProviderError(err)
	}
	log.Printf(
		"ai_provider_call provider=%s model=%s kind=%s attempt=%d status=%d latency_ms=%d prompt_tokens=%d completion_tokens=%d total_tokens=%d prompt_cache_hit_tokens=%d prompt_cache_miss_tokens=%d reasoning_tokens=%d error_class=%s",
		config.provider,
		config.model,
		kind,
		attempt,
		statusCode,
		latency.Milliseconds(),
		usage.prompt,
		usage.completion,
		usage.total,
		usage.cacheHit,
		usage.cacheMiss,
		usage.reasoning,
		errorClass,
	)
}

func classifyAIProviderError(err error) string {
	var callErr *aiProviderCallError
	if errors.As(err, &callErr) {
		switch callErr.StatusCode {
		case http.StatusUnauthorized, http.StatusForbidden:
			return "auth"
		case http.StatusPaymentRequired:
			return "quota"
		case http.StatusTooManyRequests:
			return "rate_limit"
		case http.StatusInternalServerError, http.StatusServiceUnavailable:
			return "provider_unavailable"
		default:
			if callErr.StatusCode > 0 {
				return "provider_status"
			}
			if callErr.Timeout {
				return "timeout"
			}
			return "network"
		}
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return "timeout"
	}
	return "unknown"
}
