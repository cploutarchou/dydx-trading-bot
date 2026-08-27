package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	defaultCodexBaseURL             = "https://graph.codex.io/graphql"
	defaultCodexProvider            = "codex.io"
	defaultCodexRequestsPerSecond   = 5
	defaultCodexMonthlyRequestLimit = 10000
	defaultCodexOverviewTTL         = 45 * time.Second
	defaultCodexSearchTTL           = 45 * time.Second
	defaultCodexDetailTTL           = 60 * time.Second
	defaultCodexChartTTL            = 5 * time.Minute
	defaultCodexHTTPTimeout         = 12 * time.Second
	codexSharedKeyEnvVar            = "CODEX_IO_API_KEY"
)

type CodexCapabilities struct {
	QueryOnly            bool `json:"query_only"`
	SupportsWebSockets   bool `json:"supports_websockets"`
	SupportsWebhooks     bool `json:"supports_webhooks"`
	SupportsWalletPnL    bool `json:"supports_wallet_pnl"`
	SupportsWalletValues bool `json:"supports_wallet_balances"`
	RequestsPerSecond    int  `json:"requests_per_second"`
	MonthlyRequests      int  `json:"monthly_requests"`
}

type CodexStatus struct {
	Provider           string            `json:"provider"`
	Configured         bool              `json:"configured"`
	SharedKeyAvailable bool              `json:"shared_key_available"`
	UserKeyAvailable   bool              `json:"user_key_available"`
	SharedKeyMasked    string            `json:"shared_key_masked"`
	UserKeyMasked      string            `json:"user_key_masked"`
	ActiveKeySource    string            `json:"active_key_source"`
	BaseURL            string            `json:"base_url"`
	Capabilities       CodexCapabilities `json:"capabilities"`
	Message            string            `json:"message"`
}

type CodexTokenSummary struct {
	ID                   string   `json:"id"`
	Address              string   `json:"address"`
	NetworkID            int      `json:"network_id"`
	Name                 string   `json:"name"`
	Symbol               string   `json:"symbol"`
	PriceUSD             float64  `json:"price_usd"`
	PriceChangePct1H     float64  `json:"price_change_pct_1h"`
	PriceChangePct4H     float64  `json:"price_change_pct_4h"`
	PriceChangePct24H    float64  `json:"price_change_pct_24h"`
	LiquidityUSD         float64  `json:"liquidity_usd"`
	VolumeUSD24H         float64  `json:"volume_usd_24h"`
	MarketCapUSD         float64  `json:"market_cap_usd"`
	Transactions24H      int      `json:"transactions_24h"`
	IsScam               bool     `json:"is_scam"`
	Exchanges            []string `json:"exchanges"`
	ConfidenceHint       string   `json:"confidence_hint"`
	ResolutionConfidence string   `json:"resolution_confidence,omitempty"`
}

type CodexMarketOverview struct {
	NetworkID   int                 `json:"network_id"`
	Movers      []CodexTokenSummary `json:"movers"`
	SafeMovers  []CodexTokenSummary `json:"safe_movers"`
	GeneratedAt string              `json:"generated_at"`
}

type CodexPairSummary struct {
	PairID            string  `json:"pair_id"`
	PairAddress       string  `json:"pair_address"`
	ExchangeName      string  `json:"exchange_name"`
	ExchangeID        string  `json:"exchange_id"`
	Protocol          string  `json:"protocol"`
	LiquidityUSD      float64 `json:"liquidity_usd"`
	VolumeUSD24H      float64 `json:"volume_usd_24h"`
	PriceUSD          float64 `json:"price_usd"`
	PriceChangePct24H float64 `json:"price_change_pct_24h"`
	BackingToken      string  `json:"backing_token"`
}

type CodexTokenDetail struct {
	Token             CodexTokenSummary  `json:"token"`
	Description       string             `json:"description"`
	ImageSmallURL     string             `json:"image_small_url"`
	ImageLargeURL     string             `json:"image_large_url"`
	ImageBannerURL    string             `json:"image_banner_url"`
	CirculatingSupply float64            `json:"circulating_supply"`
	TotalSupply       float64            `json:"total_supply"`
	TopPairs          []CodexPairSummary `json:"top_pairs"`
}

type CodexChartPoint struct {
	Timestamp    int64   `json:"timestamp"`
	Open         float64 `json:"open"`
	High         float64 `json:"high"`
	Low          float64 `json:"low"`
	Close        float64 `json:"close"`
	VolumeUSD    float64 `json:"volume_usd"`
	LiquidityUSD float64 `json:"liquidity_usd"`
	Transactions int     `json:"transactions"`
}

type CodexTokenChart struct {
	TokenID     string            `json:"token_id"`
	Interval    string            `json:"interval"`
	Points      []CodexChartPoint `json:"points"`
	GeneratedAt string            `json:"generated_at"`
}

type CodexAssetRef struct {
	Label     string `json:"label,omitempty"`
	Symbol    string `json:"symbol,omitempty"`
	Address   string `json:"address,omitempty"`
	NetworkID *int   `json:"network_id,omitempty"`
}

type CodexAssetContextRequest struct {
	NetworkID *int            `json:"network_id,omitempty"`
	Assets    []CodexAssetRef `json:"assets"`
}

type CodexAssetIntel struct {
	Label            string             `json:"label"`
	Resolved         bool               `json:"resolved"`
	ResolutionReason string             `json:"resolution_reason,omitempty"`
	Token            *CodexTokenSummary `json:"token,omitempty"`
}

type CodexAssetContextResponse struct {
	Items []CodexAssetIntel `json:"items"`
}

type CodexKeyPayload struct {
	APIKey string `json:"api_key"`
	Label  string `json:"label,omitempty"`
}

type codexResolvedKey struct {
	key                string
	activeSource       string
	sharedKeyAvailable bool
	userKeyAvailable   bool
}

type cacheEntry struct {
	expiresAt time.Time
	value     any
}

type codexInFlightCall struct {
	done  chan struct{}
	value any
	err   error
}

type serialRateLimiter struct {
	mu       sync.Mutex
	interval time.Duration
	next     time.Time
}

func newSerialRateLimiter(perSecond int) *serialRateLimiter {
	if perSecond <= 0 {
		perSecond = defaultCodexRequestsPerSecond
	}
	return &serialRateLimiter{
		interval: time.Second / time.Duration(perSecond),
	}
}

func (l *serialRateLimiter) Wait(ctx context.Context) error {
	l.mu.Lock()
	now := time.Now()
	waitUntil := l.next
	if waitUntil.Before(now) {
		waitUntil = now
	}
	l.next = waitUntil.Add(l.interval)
	l.mu.Unlock()

	delay := time.Until(waitUntil)
	if delay <= 0 {
		return nil
	}

	timer := time.NewTimer(delay)
	defer timer.Stop()

	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

type CodexService struct {
	baseURL      string
	httpClient   *http.Client
	credentials  *ExternalAPICredentialService
	sharedAPIKey string
	limiter      *serialRateLimiter
	cacheMu      sync.RWMutex
	cache        map[string]cacheEntry
	inFlightMu   sync.Mutex
	inFlight     map[string]*codexInFlightCall
}

type CodexServiceError struct {
	Code    int
	Message string
}

func (e *CodexServiceError) Error() string {
	return e.Message
}

func (e *CodexServiceError) StatusCode() int {
	return e.Code
}

func NewCodexServiceFromEnv(credentials *ExternalAPICredentialService) *CodexService {
	baseURL := strings.TrimRight(strings.TrimSpace(os.Getenv("CODEX_IO_BASE_URL")), "/")
	if baseURL == "" {
		baseURL = defaultCodexBaseURL
	}

	return &CodexService{
		baseURL:      baseURL,
		httpClient:   &http.Client{Timeout: defaultCodexHTTPTimeout},
		credentials:  credentials,
		sharedAPIKey: strings.TrimSpace(os.Getenv(codexSharedKeyEnvVar)),
		limiter:      newSerialRateLimiter(defaultCodexRequestsPerSecond),
		cache:        make(map[string]cacheEntry),
		inFlight:     make(map[string]*codexInFlightCall),
	}
}

func (s *CodexService) Status(userID int) (CodexStatus, error) {
	resolved, err := s.resolveAPIKey(userID)
	if err != nil {
		return CodexStatus{}, err
	}

	status := CodexStatus{
		Provider:           defaultCodexProvider,
		Configured:         strings.TrimSpace(resolved.key) != "",
		SharedKeyAvailable: resolved.sharedKeyAvailable,
		UserKeyAvailable:   resolved.userKeyAvailable,
		SharedKeyMasked:    maskSecretValue(s.sharedAPIKey),
		ActiveKeySource:    resolved.activeSource,
		BaseURL:            s.baseURL,
		Capabilities:       defaultCapabilities(),
	}
	if s.credentials != nil {
		if info, infoErr := s.credentials.Get(userID, ExternalAPIProviderCodexIO); infoErr == nil && info != nil {
			status.UserKeyMasked = info.MaskedValue
		}
	}
	if status.Configured {
		if status.ActiveKeySource == "user" {
			status.Message = "Codex.io market intelligence is live with your personal API key."
		} else {
			status.Message = "Codex.io market intelligence is live with the shared backend API key."
		}
	} else {
		status.Message = "Codex.io market intelligence is unavailable. Add a personal key in Settings or configure CODEX_IO_API_KEY on the backend."
	}

	return status, nil
}

func (s *CodexService) SaveUserKey(userID int, payload CodexKeyPayload) (*ExternalAPICredentialInfo, error) {
	if s.credentials == nil {
		return nil, fmt.Errorf("credential service is not configured")
	}
	return s.credentials.Save(userID, ExternalAPIProviderCodexIO, payload.APIKey, payload.Label)
}

func (s *CodexService) DeleteUserKey(userID int) error {
	if s.credentials == nil {
		return fmt.Errorf("credential service is not configured")
	}
	return s.credentials.Delete(userID, ExternalAPIProviderCodexIO)
}

func (s *CodexService) GetMarketOverview(ctx context.Context, userID int, networkID int, limit int, traceID string) (*CodexMarketOverview, error) {
	if limit <= 0 {
		limit = 6
	}
	cacheKey := fmt.Sprintf("overview:%d:%d", networkID, limit)
	if cached, ok := s.getCached(cacheKey); ok {
		if overview, ok := cached.(*CodexMarketOverview); ok {
			return overview, nil
		}
	}

	value, err := s.doSingleFlight(cacheKey, func() (any, error) {
		if cached, ok := s.getCached(cacheKey); ok {
			return cached, nil
		}

		resolved, err := s.resolveAPIKey(userID)
		if err != nil {
			return nil, err
		}
		if strings.TrimSpace(resolved.key) == "" {
			return nil, &CodexServiceError{Code: http.StatusServiceUnavailable, Message: "Codex.io is not configured"}
		}

		query := `
		query CodexMarketOverview($network: [Int!], $limit: Int!, $moversRankings: [TokenRanking], $safeRankings: [TokenRanking]) {
			movers: filterTokens(
				filters: {
					network: $network,
					liquidity: { gte: 25000 },
					volume24: { gte: 5000 },
					txnCount24: { gte: 20 }
				},
				rankings: $moversRankings,
				limit: $limit
			) {
				results {
					...TokenResultFields
				}
			}
			safe: filterTokens(
				filters: {
					network: $network,
					liquidity: { gte: 100000 },
					volume24: { gte: 25000 },
					txnCount24: { gte: 40 },
					change24: { gte: -0.35, lte: 0.35 }
				},
				rankings: $safeRankings,
				limit: $limit
			) {
				results {
					...TokenResultFields
				}
			}
		}

		fragment TokenResultFields on TokenFilterResult {
			token {
				id
				address
				networkId
				name
				symbol
				isScam
			}
			priceUSD
			change1
			change4
			change24
			liquidity
			volume24
			marketCap
			txnCount24
			exchanges {
				name
			}
		}
	`

		var response struct {
			Movers struct {
				Results []codexTokenFilterResult `json:"results"`
			} `json:"movers"`
			Safe struct {
				Results []codexTokenFilterResult `json:"results"`
			} `json:"safe"`
		}

		err = s.executeQuery(ctx, resolved.key, traceID, query, map[string]any{
			"network": []int{networkID},
			"limit":   limit,
			"moversRankings": []map[string]string{
				{"attribute": "change24", "direction": "DESC"},
				{"attribute": "volume24", "direction": "DESC"},
			},
			"safeRankings": []map[string]string{
				{"attribute": "liquidity", "direction": "DESC"},
				{"attribute": "volume24", "direction": "DESC"},
			},
		}, &response)
		if err != nil {
			return nil, err
		}

		overview := &CodexMarketOverview{
			NetworkID:   networkID,
			Movers:      mapTokenResults(response.Movers.Results),
			SafeMovers:  mapTokenResults(response.Safe.Results),
			GeneratedAt: time.Now().UTC().Format(time.RFC3339),
		}
		s.setCached(cacheKey, overview, defaultCodexOverviewTTL)
		return overview, nil
	})
	if err != nil {
		return nil, err
	}

	overview, ok := value.(*CodexMarketOverview)
	if !ok || overview == nil {
		return nil, fmt.Errorf("unexpected market overview cache type")
	}
	return overview, nil
}

func (s *CodexService) SearchTokens(ctx context.Context, userID int, queryText string, networkID *int, limit int, traceID string) ([]CodexTokenSummary, error) {
	queryText = strings.TrimSpace(queryText)
	if queryText == "" {
		return []CodexTokenSummary{}, nil
	}
	if limit <= 0 {
		limit = 8
	}
	cacheKey := fmt.Sprintf("search:%s:%v:%d", strings.ToLower(queryText), networkIDValue(networkID), limit)
	if cached, ok := s.getCached(cacheKey); ok {
		if results, ok := cached.([]CodexTokenSummary); ok {
			return results, nil
		}
	}

	value, err := s.doSingleFlight(cacheKey, func() (any, error) {
		if cached, ok := s.getCached(cacheKey); ok {
			return cached, nil
		}

		resolved, err := s.resolveAPIKey(userID)
		if err != nil {
			return nil, err
		}
		if strings.TrimSpace(resolved.key) == "" {
			return nil, &CodexServiceError{Code: http.StatusServiceUnavailable, Message: "Codex.io is not configured"}
		}

		var filters map[string]any
		if networkID != nil && *networkID > 0 {
			filters = map[string]any{"network": []int{*networkID}}
		}

		query := `
		query CodexTokenSearch($phrase: String!, $filters: TokenFilters, $limit: Int!) {
			filterTokens(
				phrase: $phrase,
				filters: $filters,
				rankings: [
					{ attribute: liquidity, direction: DESC },
					{ attribute: volume24, direction: DESC }
				],
				limit: $limit
			) {
				results {
					token {
						id
						address
						networkId
						name
						symbol
						isScam
					}
					priceUSD
					change1
					change4
					change24
					liquidity
					volume24
					marketCap
					txnCount24
					exchanges {
						name
					}
				}
			}
		}
	`
		var response struct {
			FilterTokens struct {
				Results []codexTokenFilterResult `json:"results"`
			} `json:"filterTokens"`
		}

		err = s.executeQuery(ctx, resolved.key, traceID, query, map[string]any{
			"phrase":  queryText,
			"filters": filters,
			"limit":   limit,
		}, &response)
		if err != nil {
			return nil, err
		}

		results := mapTokenResults(response.FilterTokens.Results)
		s.setCached(cacheKey, results, defaultCodexSearchTTL)
		return results, nil
	})
	if err != nil {
		return nil, err
	}

	results, ok := value.([]CodexTokenSummary)
	if !ok {
		return nil, fmt.Errorf("unexpected token search cache type")
	}
	return results, nil
}

func (s *CodexService) GetTokenDetail(ctx context.Context, userID int, networkID int, address string, traceID string) (*CodexTokenDetail, error) {
	address = strings.TrimSpace(strings.ToLower(address))
	if address == "" || networkID <= 0 {
		return nil, &CodexServiceError{Code: http.StatusBadRequest, Message: "network id and address are required"}
	}
	cacheKey := fmt.Sprintf("detail:%d:%s", networkID, address)
	if cached, ok := s.getCached(cacheKey); ok {
		if detail, ok := cached.(*CodexTokenDetail); ok {
			return detail, nil
		}
	}

	value, err := s.doSingleFlight(cacheKey, func() (any, error) {
		if cached, ok := s.getCached(cacheKey); ok {
			return cached, nil
		}

		resolved, err := s.resolveAPIKey(userID)
		if err != nil {
			return nil, err
		}
		if strings.TrimSpace(resolved.key) == "" {
			return nil, &CodexServiceError{Code: http.StatusServiceUnavailable, Message: "Codex.io is not configured"}
		}

		tokenID := fmt.Sprintf("%s:%d", address, networkID)
		query := `
		query CodexTokenDetail($tokenAddress: String!, $networkId: Int!, $tokenIds: [String]) {
			token(input: { address: $tokenAddress, networkId: $networkId }) {
				id
				address
				networkId
				name
				symbol
				isScam
				description
				imageSmallUrl
				imageLargeUrl
				imageBannerUrl
				circulatingSupply
				totalSupply
			}
			filterTokens(tokens: $tokenIds, limit: 1) {
				results {
					token {
						id
						address
						networkId
						name
						symbol
						isScam
					}
					priceUSD
					change1
					change4
					change24
					liquidity
					volume24
					marketCap
					txnCount24
					exchanges {
						name
					}
				}
			}
			listPairsWithMetadataForToken(limit: 5, networkId: $networkId, tokenAddress: $tokenAddress) {
				results {
					volume
					liquidity
					token {
						symbol
					}
					backingToken {
						symbol
					}
					pair {
						id
						address
						protocol
					}
					exchange {
						id
						name
					}
				}
			}
		}
	`

		var response struct {
			Token        codexEnhancedToken `json:"token"`
			FilterTokens struct {
				Results []codexTokenFilterResult `json:"results"`
			} `json:"filterTokens"`
			ListPairsWithMetadataForToken struct {
				Results []codexPairMetadataResult `json:"results"`
			} `json:"listPairsWithMetadataForToken"`
		}

		err = s.executeQuery(ctx, resolved.key, traceID, query, map[string]any{
			"tokenAddress": address,
			"networkId":    networkID,
			"tokenIds":     []string{tokenID},
		}, &response)
		if err != nil {
			return nil, err
		}

		summary := CodexTokenSummary{
			ID:        tokenID,
			Address:   address,
			NetworkID: networkID,
			Name:      response.Token.Name,
			Symbol:    response.Token.Symbol,
			IsScam:    response.Token.IsScam,
		}
		if len(response.FilterTokens.Results) > 0 {
			summary = mapTokenResults(response.FilterTokens.Results)[0]
		}

		detail := &CodexTokenDetail{
			Token:             summary,
			Description:       strings.TrimSpace(response.Token.Description),
			ImageSmallURL:     response.Token.ImageSmallURL,
			ImageLargeURL:     response.Token.ImageLargeURL,
			ImageBannerURL:    response.Token.ImageBannerURL,
			CirculatingSupply: parseFloatString(response.Token.CirculatingSupply),
			TotalSupply:       parseFloatString(response.Token.TotalSupply),
			TopPairs:          mapPairResults(response.ListPairsWithMetadataForToken.Results),
		}
		s.setCached(cacheKey, detail, defaultCodexDetailTTL)
		return detail, nil
	})
	if err != nil {
		return nil, err
	}

	detail, ok := value.(*CodexTokenDetail)
	if !ok || detail == nil {
		return nil, fmt.Errorf("unexpected token detail cache type")
	}
	return detail, nil
}

func (s *CodexService) GetTokenChart(ctx context.Context, userID int, networkID int, address string, interval string, points int, traceID string) (*CodexTokenChart, error) {
	address = strings.TrimSpace(strings.ToLower(address))
	if address == "" || networkID <= 0 {
		return nil, &CodexServiceError{Code: http.StatusBadRequest, Message: "network id and address are required"}
	}
	resolution, fromUnix, toUnix, countback := normalizeChartInterval(interval, points)
	cacheKey := fmt.Sprintf("chart:%d:%s:%s:%d", networkID, address, resolution, countback)
	if cached, ok := s.getCached(cacheKey); ok {
		if chart, ok := cached.(*CodexTokenChart); ok {
			return chart, nil
		}
	}

	value, err := s.doSingleFlight(cacheKey, func() (any, error) {
		if cached, ok := s.getCached(cacheKey); ok {
			return cached, nil
		}

		resolved, err := s.resolveAPIKey(userID)
		if err != nil {
			return nil, err
		}
		if strings.TrimSpace(resolved.key) == "" {
			return nil, &CodexServiceError{Code: http.StatusServiceUnavailable, Message: "Codex.io is not configured"}
		}

		tokenID := fmt.Sprintf("%s:%d", address, networkID)
		query := `
		query CodexTokenChart($symbol: String!, $from: Int!, $to: Int!, $resolution: String!, $countback: Int!) {
			getTokenBars(
				symbol: $symbol,
				from: $from,
				to: $to,
				resolution: $resolution,
				currencyCode: USD,
				removeLeadingNullValues: true,
				removeEmptyBars: true,
				countback: $countback
			) {
				s
				t
				o
				h
				l
				c
				volume
				liquidity
				transactions
			}
		}
	`

		var response struct {
			GetTokenBars codexBarsResponse `json:"getTokenBars"`
		}

		err = s.executeQuery(ctx, resolved.key, traceID, query, map[string]any{
			"symbol":     tokenID,
			"from":       fromUnix,
			"to":         toUnix,
			"resolution": resolution,
			"countback":  countback,
		}, &response)
		if err != nil {
			return nil, err
		}

		chart := &CodexTokenChart{
			TokenID:     tokenID,
			Interval:    strings.ToLower(interval),
			Points:      mapBars(response.GetTokenBars),
			GeneratedAt: time.Now().UTC().Format(time.RFC3339),
		}
		s.setCached(cacheKey, chart, defaultCodexChartTTL)
		return chart, nil
	})
	if err != nil {
		return nil, err
	}

	chart, ok := value.(*CodexTokenChart)
	if !ok || chart == nil {
		return nil, fmt.Errorf("unexpected token chart cache type")
	}
	return chart, nil
}

func (s *CodexService) ResolveAssetsContext(ctx context.Context, userID int, request CodexAssetContextRequest, traceID string) (*CodexAssetContextResponse, error) {
	items := make([]CodexAssetIntel, 0, len(request.Assets))
	for _, asset := range request.Assets {
		items = append(items, s.resolveSingleAsset(ctx, userID, request.NetworkID, asset, traceID))
	}
	return &CodexAssetContextResponse{Items: items}, nil
}

func (s *CodexService) resolveSingleAsset(ctx context.Context, userID int, defaultNetworkID *int, asset CodexAssetRef, traceID string) CodexAssetIntel {
	label := strings.TrimSpace(asset.Label)
	if label == "" {
		label = strings.TrimSpace(asset.Symbol)
		if label == "" {
			label = strings.TrimSpace(asset.Address)
		}
	}

	networkID := asset.NetworkID
	if networkID == nil {
		networkID = defaultNetworkID
	}

	if networkID != nil && *networkID > 0 && strings.TrimSpace(asset.Address) != "" {
		detail, err := s.GetTokenDetail(ctx, userID, *networkID, asset.Address, traceID)
		if err == nil && detail != nil {
			token := detail.Token
			token.ResolutionConfidence = "high"
			return CodexAssetIntel{Label: label, Resolved: true, Token: &token}
		}
	}

	symbol := normalizeAssetSymbol(asset.Symbol)
	if symbol == "" {
		return CodexAssetIntel{Label: label, Resolved: false, ResolutionReason: "missing symbol or address"}
	}

	searchResults, err := s.SearchTokens(ctx, userID, symbol, networkID, 6, traceID)
	if err != nil {
		return CodexAssetIntel{Label: label, Resolved: false, ResolutionReason: "market lookup unavailable"}
	}

	var exact []CodexTokenSummary
	for _, result := range searchResults {
		if strings.EqualFold(strings.TrimSpace(result.Symbol), symbol) {
			exact = append(exact, result)
		}
	}

	if len(exact) != 1 {
		return CodexAssetIntel{Label: label, Resolved: false, ResolutionReason: "symbol is ambiguous or unresolved"}
	}

	token := exact[0]
	token.ResolutionConfidence = "medium"
	return CodexAssetIntel{Label: label, Resolved: true, Token: &token}
}

func (s *CodexService) resolveAPIKey(userID int) (codexResolvedKey, error) {
	resolved := codexResolvedKey{
		sharedKeyAvailable: strings.TrimSpace(s.sharedAPIKey) != "",
		activeSource:       "none",
	}

	if userID > 0 && s.credentials != nil {
		userKey, ok, err := s.credentials.ResolveKey(userID, ExternalAPIProviderCodexIO)
		if err != nil {
			return resolved, fmt.Errorf("failed to resolve user Codex.io key: %w", err)
		}
		if ok && strings.TrimSpace(userKey) != "" {
			resolved.key = strings.TrimSpace(userKey)
			resolved.userKeyAvailable = true
			resolved.activeSource = "user"
			return resolved, nil
		}
	}

	if resolved.sharedKeyAvailable {
		resolved.key = strings.TrimSpace(s.sharedAPIKey)
		resolved.activeSource = "shared"
	}

	return resolved, nil
}

func (s *CodexService) executeQuery(ctx context.Context, apiKey string, traceID string, query string, variables map[string]any, target any) error {
	if err := s.limiter.Wait(ctx); err != nil {
		return &CodexServiceError{Code: http.StatusRequestTimeout, Message: "Codex.io request timed out before dispatch"}
	}

	payload, err := json.Marshal(map[string]any{
		"query":     query,
		"variables": variables,
	})
	if err != nil {
		return fmt.Errorf("failed to marshal codex graphql request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.baseURL, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("failed to create codex graphql request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", apiKey)
	if strings.TrimSpace(traceID) != "" {
		req.Header.Set("X-Trace-Id", traceID)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return &CodexServiceError{Code: http.StatusBadGateway, Message: fmt.Sprintf("failed to reach Codex.io upstream: %v", err)}
	}
	defer func() { _ = resp.Body.Close() }()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return &CodexServiceError{Code: http.StatusBadGateway, Message: "failed to read Codex.io response"}
	}

	var envelope struct {
		Data   json.RawMessage `json:"data"`
		Errors []struct {
			Message string `json:"message"`
		} `json:"errors"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		return &CodexServiceError{Code: http.StatusBadGateway, Message: "failed to decode Codex.io response"}
	}

	if resp.StatusCode == http.StatusUnauthorized {
		return &CodexServiceError{Code: http.StatusUnauthorized, Message: "Codex.io rejected the configured API key"}
	}
	if resp.StatusCode == http.StatusTooManyRequests {
		return &CodexServiceError{Code: http.StatusTooManyRequests, Message: "Codex.io rate limit reached"}
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		message := strings.TrimSpace(firstGraphQLErrorMessage(envelope.Errors))
		if message == "" {
			message = fmt.Sprintf("Codex.io upstream returned status %d", resp.StatusCode)
		}
		log.Printf("❌ Codex.io upstream error trace_id=%s status=%d body=%s", traceID, resp.StatusCode, strings.TrimSpace(string(body)))
		return &CodexServiceError{Code: http.StatusBadGateway, Message: message}
	}
	if len(envelope.Errors) > 0 {
		message := firstGraphQLErrorMessage(envelope.Errors)
		if message == "" {
			message = "Codex.io returned an unknown GraphQL error"
		}
		return &CodexServiceError{Code: http.StatusBadGateway, Message: message}
	}
	if len(envelope.Data) == 0 {
		return &CodexServiceError{Code: http.StatusBadGateway, Message: "Codex.io returned an empty response"}
	}
	if err := json.Unmarshal(envelope.Data, target); err != nil {
		return &CodexServiceError{Code: http.StatusBadGateway, Message: "failed to decode normalized Codex.io payload"}
	}

	return nil
}

func (s *CodexService) getCached(key string) (any, bool) {
	s.cacheMu.RLock()
	defer s.cacheMu.RUnlock()
	entry, ok := s.cache[key]
	if !ok || time.Now().After(entry.expiresAt) {
		return nil, false
	}
	return entry.value, true
}

func (s *CodexService) setCached(key string, value any, ttl time.Duration) {
	s.cacheMu.Lock()
	defer s.cacheMu.Unlock()
	s.cache[key] = cacheEntry{
		expiresAt: time.Now().Add(ttl),
		value:     value,
	}
}

func (s *CodexService) doSingleFlight(key string, fn func() (any, error)) (any, error) {
	s.inFlightMu.Lock()
	if s.inFlight == nil {
		s.inFlight = make(map[string]*codexInFlightCall)
	}
	if call, ok := s.inFlight[key]; ok {
		s.inFlightMu.Unlock()
		<-call.done
		return call.value, call.err
	}

	call := &codexInFlightCall{done: make(chan struct{})}
	s.inFlight[key] = call
	s.inFlightMu.Unlock()

	// Deferred cleanup keeps the call completable even if fn panics; without it
	// every waiter (and every future request for this key) would block forever.
	defer func() {
		s.inFlightMu.Lock()
		delete(s.inFlight, key)
		close(call.done)
		s.inFlightMu.Unlock()
	}()

	func() {
		defer func() {
			if r := recover(); r != nil {
				call.err = fmt.Errorf("codex singleflight panic: %v", r)
			}
		}()
		call.value, call.err = fn()
	}()

	return call.value, call.err
}

func defaultCapabilities() CodexCapabilities {
	return CodexCapabilities{
		QueryOnly:            true,
		SupportsWebSockets:   false,
		SupportsWebhooks:     false,
		SupportsWalletPnL:    false,
		SupportsWalletValues: false,
		RequestsPerSecond:    defaultCodexRequestsPerSecond,
		MonthlyRequests:      defaultCodexMonthlyRequestLimit,
	}
}

func firstGraphQLErrorMessage(errors []struct {
	Message string `json:"message"`
}) string {
	for _, item := range errors {
		if strings.TrimSpace(item.Message) != "" {
			return item.Message
		}
	}
	return ""
}

func normalizeChartInterval(interval string, points int) (resolution string, fromUnix int, toUnix int, countback int) {
	switch strings.ToLower(strings.TrimSpace(interval)) {
	case "1h":
		resolution = "60"
		if points <= 0 {
			points = 48
		}
	case "4h":
		resolution = "240"
		if points <= 0 {
			points = 45
		}
	default:
		resolution = "1D"
		if points <= 0 {
			points = 60
		}
	}

	to := time.Now().UTC()
	from := to.Add(-time.Duration(points+2) * resolutionDuration(resolution))
	return resolution, int(from.Unix()), int(to.Unix()), points
}

func resolutionDuration(resolution string) time.Duration {
	switch resolution {
	case "60":
		return time.Hour
	case "240":
		return 4 * time.Hour
	default:
		return 24 * time.Hour
	}
}

func networkIDValue(networkID *int) int {
	if networkID == nil {
		return 0
	}
	return *networkID
}

func normalizeAssetSymbol(symbol string) string {
	symbol = strings.TrimSpace(strings.ToUpper(symbol))
	if symbol == "" {
		return ""
	}
	if strings.Contains(symbol, "-") {
		parts := strings.Split(symbol, "-")
		if len(parts) > 0 {
			symbol = strings.TrimSpace(parts[0])
		}
	}
	if strings.Contains(symbol, "/") {
		parts := strings.Split(symbol, "/")
		if len(parts) > 0 {
			symbol = strings.TrimSpace(parts[0])
		}
	}
	return symbol
}

func mapTokenResults(results []codexTokenFilterResult) []CodexTokenSummary {
	summaries := make([]CodexTokenSummary, 0, len(results))
	seen := map[string]struct{}{}
	for _, result := range results {
		if strings.TrimSpace(result.Token.ID) == "" {
			continue
		}
		if _, exists := seen[result.Token.ID]; exists {
			continue
		}
		seen[result.Token.ID] = struct{}{}
		summaries = append(summaries, CodexTokenSummary{
			ID:                result.Token.ID,
			Address:           result.Token.Address,
			NetworkID:         result.Token.NetworkID,
			Name:              result.Token.Name,
			Symbol:            result.Token.Symbol,
			PriceUSD:          parseFloatString(result.PriceUSD),
			PriceChangePct1H:  parseDecimalPercentString(result.Change1),
			PriceChangePct4H:  parseDecimalPercentString(result.Change4),
			PriceChangePct24H: parseDecimalPercentString(result.Change24),
			LiquidityUSD:      parseFloatString(result.Liquidity),
			VolumeUSD24H:      parseFloatString(result.Volume24),
			MarketCapUSD:      parseFloatString(result.MarketCap),
			Transactions24H:   result.TxnCount24,
			IsScam:            result.Token.IsScam,
			Exchanges:         compactExchangeNames(result.Exchanges),
			ConfidenceHint:    confidenceHint(parseFloatString(result.Liquidity), parseFloatString(result.Volume24), result.Token.IsScam),
		})
	}
	return summaries
}

func mapPairResults(results []codexPairMetadataResult) []CodexPairSummary {
	pairs := make([]CodexPairSummary, 0, len(results))
	for _, result := range results {
		pairs = append(pairs, CodexPairSummary{
			PairID:            result.Pair.ID,
			PairAddress:       result.Pair.Address,
			ExchangeName:      result.Exchange.Name,
			ExchangeID:        result.Exchange.ID,
			Protocol:          result.Pair.Protocol,
			LiquidityUSD:      parseFloatString(result.Liquidity),
			VolumeUSD24H:      parseFloatString(result.Volume),
			PriceUSD:          0,
			PriceChangePct24H: 0,
			BackingToken:      result.BackingToken.Symbol,
		})
	}
	sort.Slice(pairs, func(i, j int) bool {
		return pairs[i].LiquidityUSD > pairs[j].LiquidityUSD
	})
	return pairs
}

func mapBars(response codexBarsResponse) []CodexChartPoint {
	points := make([]CodexChartPoint, 0, len(response.T))
	for index, timestamp := range response.T {
		points = append(points, CodexChartPoint{
			Timestamp:    int64(timestamp),
			Open:         safeIndexFloat(response.O, index),
			High:         safeIndexFloat(response.H, index),
			Low:          safeIndexFloat(response.L, index),
			Close:        safeIndexFloat(response.C, index),
			VolumeUSD:    safeIndexStringFloat(response.Volume, index),
			LiquidityUSD: safeIndexStringFloat(response.Liquidity, index),
			Transactions: safeIndexInt(response.Transactions, index),
		})
	}
	return points
}

func safeIndexFloat(values []float64, index int) float64 {
	if index < 0 || index >= len(values) {
		return 0
	}
	return values[index]
}

func safeIndexStringFloat(values []string, index int) float64 {
	if index < 0 || index >= len(values) {
		return 0
	}
	return parseFloatString(values[index])
}

func safeIndexInt(values []int, index int) int {
	if index < 0 || index >= len(values) {
		return 0
	}
	return values[index]
}

func parseFloatString(raw string) float64 {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return 0
	}
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return 0
	}
	return value
}

func parseDecimalPercentString(raw string) float64 {
	return parseFloatString(raw) * 100
}

func compactExchangeNames(exchanges []codexExchange) []string {
	names := make([]string, 0, len(exchanges))
	seen := map[string]struct{}{}
	for _, exchange := range exchanges {
		name := strings.TrimSpace(exchange.Name)
		if name == "" {
			continue
		}
		if _, exists := seen[name]; exists {
			continue
		}
		seen[name] = struct{}{}
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func confidenceHint(liquidityUSD float64, volumeUSD24H float64, isScam bool) string {
	if isScam {
		return "flagged"
	}
	switch {
	case liquidityUSD >= 500000 && volumeUSD24H >= 200000:
		return "high"
	case liquidityUSD >= 100000 && volumeUSD24H >= 50000:
		return "medium"
	default:
		return "low"
	}
}

type codexEnhancedToken struct {
	ID                string `json:"id"`
	Address           string `json:"address"`
	NetworkID         int    `json:"networkId"`
	Name              string `json:"name"`
	Symbol            string `json:"symbol"`
	IsScam            bool   `json:"isScam"`
	Description       string `json:"description"`
	ImageSmallURL     string `json:"imageSmallUrl"`
	ImageLargeURL     string `json:"imageLargeUrl"`
	ImageBannerURL    string `json:"imageBannerUrl"`
	CirculatingSupply string `json:"circulatingSupply"`
	TotalSupply       string `json:"totalSupply"`
}

type codexTokenFilterResult struct {
	Token      codexEnhancedToken `json:"token"`
	PriceUSD   string             `json:"priceUSD"`
	Change1    string             `json:"change1"`
	Change4    string             `json:"change4"`
	Change24   string             `json:"change24"`
	Liquidity  string             `json:"liquidity"`
	Volume24   string             `json:"volume24"`
	MarketCap  string             `json:"marketCap"`
	TxnCount24 int                `json:"txnCount24"`
	Exchanges  []codexExchange    `json:"exchanges"`
}

type codexExchange struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

type codexPairMetadataResult struct {
	Volume    string `json:"volume"`
	Liquidity string `json:"liquidity"`
	Token     struct {
		Symbol string `json:"symbol"`
	} `json:"token"`
	BackingToken struct {
		Symbol string `json:"symbol"`
	} `json:"backingToken"`
	Pair struct {
		ID       string `json:"id"`
		Address  string `json:"address"`
		Protocol string `json:"protocol"`
	} `json:"pair"`
	Exchange codexExchange `json:"exchange"`
}

type codexBarsResponse struct {
	S            string    `json:"s"`
	T            []int     `json:"t"`
	O            []float64 `json:"o"`
	H            []float64 `json:"h"`
	L            []float64 `json:"l"`
	C            []float64 `json:"c"`
	Volume       []string  `json:"volume"`
	Liquidity    []string  `json:"liquidity"`
	Transactions []int     `json:"transactions"`
}
