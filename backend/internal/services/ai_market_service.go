package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"
)

const (
	defaultAIMarketHTTPTimeout = 20 * time.Second
	defaultAIMarketLimit       = 20
)

var SupportedAIProviders = []string{
	ExternalAPIProviderOpenAI,
	ExternalAPIProviderDeepSeek,
	ExternalAPIProviderClaude,
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
	SharedKeyAvailable bool   `json:"shared_key_available"`
	UserKeyAvailable   bool   `json:"user_key_available"`
	UserKeyMasked      string `json:"user_key_masked"`
	ActiveKeySource    string `json:"active_key_source"`
	Model              string `json:"model"`
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
}

type aiResolvedKey struct {
	key             string
	activeSource    string
	userAvailable   bool
	sharedAvailable bool
}

type aiProviderConfig struct {
	provider string
	model    string
	baseURL  string
}

type AIMarketService struct {
	credentials *ExternalAPICredentialService
	httpClient  *http.Client
}

func NewAIMarketService(credentials *ExternalAPICredentialService) *AIMarketService {
	return &AIMarketService{
		credentials: credentials,
		httpClient:  &http.Client{Timeout: defaultAIMarketHTTPTimeout},
	}
}

func (s *AIMarketService) Status(userID int) (AIMarketStatus, error) {
	providers := make([]AIProviderStatus, 0, len(SupportedAIProviders))
	for _, provider := range SupportedAIProviders {
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
			Enabled:            strings.TrimSpace(resolved.key) != "",
			SharedKeyAvailable: resolved.sharedAvailable,
			UserKeyAvailable:   resolved.userAvailable,
			ActiveKeySource:    resolved.activeSource,
			Model:              s.providerConfig(provider).model,
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

func (s *AIMarketService) DeleteUserKey(userID int, provider string) error {
	normalized, err := normalizeAIProvider(provider)
	if err != nil {
		return err
	}
	return s.credentials.Delete(userID, normalized)
}

func (s *AIMarketService) SelectMarkets(ctx context.Context, userID int, req AIMarketSelectionRequest) (*AIMarketSelectionResponse, error) {
	provider, err := normalizeAIProvider(req.Provider)
	if err != nil {
		return nil, err
	}

	mode := normalizeAIMarketMode(req.Mode)
	limit := req.Limit
	if limit <= 0 || limit > defaultAIMarketLimit {
		limit = defaultAIMarketLimit
	}

	markets := normalizeMarkets(req.Markets)
	if len(markets) < 2 {
		return nil, fmt.Errorf("at least two dYdX markets are required for AI selection")
	}

	resolved, err := s.resolveKey(userID, provider)
	if err != nil {
		return nil, err
	}
	if strings.TrimSpace(resolved.key) == "" {
		return fallbackAIMarketSelection(provider, mode, markets, limit, "No AI key is configured for the selected provider."), nil
	}

	criteria := normalizeAIMarketCriteria(req.Criteria, mode)
	selection, err := s.callProvider(ctx, resolved.key, provider, mode, markets, limit, req.Strategy, criteria)
	if err != nil {
		return fallbackAIMarketSelection(provider, mode, markets, limit, err.Error()), nil
	}

	selected := filterSelectedMarkets(selection.SelectedMarkets, markets, limit)
	if len(selected) < 2 {
		return fallbackAIMarketSelection(provider, mode, markets, limit, "AI response did not include enough valid dYdX markets."), nil
	}

	return &AIMarketSelectionResponse{
		Provider:        provider,
		Mode:            mode,
		Source:          "ai",
		SelectedMarkets: selected,
		Rationale:       strings.TrimSpace(selection.Rationale),
		Confidence:      selection.Confidence,
		UsedAI:          true,
	}, nil
}

func (s *AIMarketService) resolveKey(userID int, provider string) (aiResolvedKey, error) {
	normalized, err := normalizeAIProvider(provider)
	if err != nil {
		return aiResolvedKey{}, err
	}

	resolved := aiResolvedKey{
		sharedAvailable: strings.TrimSpace(os.Getenv(sharedAIKeyEnv(normalized))) != "",
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
	}

	if resolved.sharedAvailable {
		resolved.key = strings.TrimSpace(os.Getenv(sharedAIKeyEnv(normalized)))
		resolved.activeSource = "shared"
	}

	return resolved, nil
}

func (s *AIMarketService) callProvider(ctx context.Context, apiKey string, provider string, mode string, markets []string, limit int, strategy string, criteria AIMarketCriteria) (*AIMarketSelectionResponse, error) {
	config := s.providerConfig(provider)
	prompt := buildAIMarketPrompt(mode, markets, limit, strategy, criteria)

	switch provider {
	case ExternalAPIProviderClaude:
		return s.callClaude(ctx, apiKey, config, prompt)
	default:
		return s.callOpenAICompatible(ctx, apiKey, config, prompt)
	}
}

func (s *AIMarketService) callOpenAICompatible(ctx context.Context, apiKey string, config aiProviderConfig, prompt string) (*AIMarketSelectionResponse, error) {
	body := map[string]any{
		"model": config.model,
		"messages": []map[string]string{
			{"role": "system", "content": "You rank dYdX perpetual markets for a crypto pairs-trading strategy. Return only valid JSON."},
			{"role": "user", "content": prompt},
		},
		"temperature": 0.2,
	}

	var response struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := s.executeJSON(ctx, config.baseURL, apiKey, body, &response, nil); err != nil {
		return nil, err
	}
	if len(response.Choices) == 0 {
		return nil, fmt.Errorf("%s returned no market ranking choices", providerDisplayName(config.provider))
	}
	return parseAIMarketSelection(response.Choices[0].Message.Content)
}

func (s *AIMarketService) callClaude(ctx context.Context, apiKey string, config aiProviderConfig, prompt string) (*AIMarketSelectionResponse, error) {
	body := map[string]any{
		"model":       config.model,
		"max_tokens":  900,
		"temperature": 0.2,
		"system":      "You rank dYdX perpetual markets for a crypto pairs-trading strategy. Return only valid JSON.",
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
	}

	var response struct {
		Content []struct {
			Text string `json:"text"`
			Type string `json:"type"`
		} `json:"content"`
	}

	headers := map[string]string{
		"x-api-key":         apiKey,
		"anthropic-version": "2023-06-01",
	}
	if err := s.executeJSON(ctx, config.baseURL, "", body, &response, headers); err != nil {
		return nil, err
	}
	for _, part := range response.Content {
		if strings.TrimSpace(part.Text) != "" {
			return parseAIMarketSelection(part.Text)
		}
	}
	return nil, fmt.Errorf("Claude returned no market ranking content")
}

func (s *AIMarketService) executeJSON(ctx context.Context, url string, bearer string, payload any, target any, headers map[string]string) error {
	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to encode AI request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("failed to create AI request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if strings.TrimSpace(bearer) != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	for key, value := range headers {
		req.Header.Set(key, value)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to reach AI provider: %w", err)
	}
	defer resp.Body.Close()

	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return fmt.Errorf("failed to read AI response: %w", err)
	}
	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		return fmt.Errorf("AI provider rejected the configured API key")
	}
	if resp.StatusCode == http.StatusTooManyRequests {
		return fmt.Errorf("AI provider rate limit reached")
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("AI provider returned status %d", resp.StatusCode)
	}
	if err := json.Unmarshal(responseBody, target); err != nil {
		return fmt.Errorf("failed to decode AI response: %w", err)
	}
	return nil
}

func (s *AIMarketService) providerConfig(provider string) aiProviderConfig {
	switch provider {
	case ExternalAPIProviderDeepSeek:
		return aiProviderConfig{
			provider: provider,
			model:    envWithDefault("DEEPSEEK_MODEL", "deepseek-chat"),
			baseURL:  envWithDefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions"),
		}
	case ExternalAPIProviderClaude:
		return aiProviderConfig{
			provider: provider,
			model:    envWithDefault("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
			baseURL:  envWithDefault("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1/messages"),
		}
	default:
		return aiProviderConfig{
			provider: ExternalAPIProviderOpenAI,
			model:    envWithDefault("OPENAI_MODEL", "gpt-4o-mini"),
			baseURL:  envWithDefault("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
		}
	}
}

func parseAIMarketSelection(content string) (*AIMarketSelectionResponse, error) {
	trimmed := strings.TrimSpace(content)
	trimmed = strings.TrimPrefix(trimmed, "```json")
	trimmed = strings.TrimPrefix(trimmed, "```")
	trimmed = strings.TrimSuffix(trimmed, "```")
	trimmed = strings.TrimSpace(trimmed)

	var parsed struct {
		SelectedMarkets []string `json:"selected_markets"`
		Rationale       string   `json:"rationale"`
		Confidence      float64  `json:"confidence"`
	}
	if err := json.Unmarshal([]byte(trimmed), &parsed); err != nil {
		return nil, fmt.Errorf("AI provider returned non-JSON market ranking")
	}
	return &AIMarketSelectionResponse{
		SelectedMarkets: parsed.SelectedMarkets,
		Rationale:       parsed.Rationale,
		Confidence:      parsed.Confidence,
	}, nil
}

func fallbackAIMarketSelection(provider string, mode string, markets []string, limit int, reason string) *AIMarketSelectionResponse {
	selected := normalizeMarkets(markets)
	if len(selected) > limit {
		selected = selected[:limit]
	}
	return &AIMarketSelectionResponse{
		Provider:        provider,
		Mode:            mode,
		Source:          "deterministic_fallback",
		SelectedMarkets: selected,
		Rationale:       "Selected the first active dYdX markets because AI ranking was unavailable.",
		Confidence:      0,
		UsedAI:          false,
		FallbackReason:  reason,
	}
}

func buildAIMarketPrompt(mode string, markets []string, limit int, strategy string, criteria AIMarketCriteria) string {
	strategy = strings.TrimSpace(strategy)
	if strategy == "" {
		strategy = "cointegration pairs trading with controlled liquidity, volatility, and backtest coverage"
	}
	return fmt.Sprintf(`Rank this dYdX perpetual market universe for %s.

Mode: %s
Objective: %s
Select exactly %d markets when possible, never more than %d.
Only choose symbols from the provided list.
Apply these strategy-aware ranking weights on a 0-1 scale:
- volume_weight: %.2f
- liquidity_weight: %.2f
- tradeability_weight: %.2f
- momentum_weight: %.2f
- volatility_weight: %.2f
- cointegration_weight: %.2f
- risk_weight: %.2f
- future_gainers: %t

Interpretation:
- volume/liquidity/tradeability: favor markets with deeper participation, tighter execution assumptions, and lower slippage risk.
- momentum/future_gainers: include assets with plausible upside catalysts, but do not sacrifice minimum liquidity.
- volatility: useful for spread movement, but penalize unstable micro-cap style markets when risk_weight is high.
- cointegration: favor assets likely to have stable statistical relationships for pairs trading.
- risk: penalize thin, meme-only, illiquid, or structurally fragile markets.
Additional strategy notes: %s

Markets:
%s

Return only JSON in this shape:
{"selected_markets":["BTC-USD","ETH-USD"],"rationale":"short reason","confidence":0.74}`,
		strategy,
		mode,
		criteria.Objective,
		limit,
		limit,
		criteria.VolumeWeight,
		criteria.LiquidityWeight,
		criteria.TradeabilityWeight,
		criteria.MomentumWeight,
		criteria.VolatilityWeight,
		criteria.CointegrationWeight,
		criteria.RiskWeight,
		criteria.FutureGainers,
		criteria.Notes,
		strings.Join(markets, ", "),
	)
}

func normalizeAIMarketCriteria(criteria AIMarketCriteria, mode string) AIMarketCriteria {
	objective := strings.TrimSpace(strings.ToLower(criteria.Objective))
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

func normalizeMarkets(markets []string) []string {
	seen := map[string]bool{}
	normalized := make([]string, 0, len(markets))
	for _, market := range markets {
		item := strings.ToUpper(strings.TrimSpace(market))
		if item == "" || seen[item] {
			continue
		}
		seen[item] = true
		normalized = append(normalized, item)
	}
	sort.Strings(normalized)
	return normalized
}

func filterSelectedMarkets(selected []string, available []string, limit int) []string {
	availableSet := map[string]bool{}
	for _, market := range normalizeMarkets(available) {
		availableSet[market] = true
	}

	result := make([]string, 0, limit)
	seen := map[string]bool{}
	for _, market := range selected {
		item := strings.ToUpper(strings.TrimSpace(market))
		if item == "" || seen[item] || !availableSet[item] {
			continue
		}
		seen[item] = true
		result = append(result, item)
		if len(result) >= limit {
			break
		}
	}
	return result
}

func sharedAIKeyEnv(provider string) string {
	switch provider {
	case ExternalAPIProviderDeepSeek:
		return "DEEPSEEK_API_KEY"
	case ExternalAPIProviderClaude:
		return "ANTHROPIC_API_KEY"
	default:
		return "OPENAI_API_KEY"
	}
}

func providerDisplayName(provider string) string {
	switch provider {
	case ExternalAPIProviderDeepSeek:
		return "DeepSeek"
	case ExternalAPIProviderClaude:
		return "Claude"
	default:
		return "OpenAI"
	}
}

func envWithDefault(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}
