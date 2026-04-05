package services

import (
	"context"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	ExternalAPIProviderCoinDesk = "coindesk_news"
	defaultCoinDeskRSSURL       = "https://www.coindesk.com/arc/outboundfeeds/rss/"
	defaultCoinDeskNewsTTL      = 5 * time.Minute
	defaultCoinDeskNewsLimit    = 8
)

type CoinDeskNewsConfigStatus struct {
	Provider          string `json:"provider"`
	SharedKeyPresent  bool   `json:"shared_key_present"`
	SharedKeyMasked   string `json:"shared_key_masked"`
	SharedKeyLabel    string `json:"shared_key_label"`
	FeedURL           string `json:"feed_url"`
	Source            string `json:"source"`
	ConfiguredByAdmin bool   `json:"configured_by_admin"`
}

type CoinDeskNewsConfigPayload struct {
	APIKey string `json:"api_key"`
	Label  string `json:"label,omitempty"`
}

type CoinDeskArticle struct {
	ID          string   `json:"id"`
	Title       string   `json:"title"`
	URL         string   `json:"url"`
	Summary     string   `json:"summary"`
	Author      string   `json:"author"`
	Category    string   `json:"category"`
	PublishedAt string   `json:"published_at"`
	ImageURL    string   `json:"image_url"`
	Tags        []string `json:"tags"`
}

type CoinDeskNewsResponse struct {
	Provider    string            `json:"provider"`
	Source      string            `json:"source"`
	FeedURL     string            `json:"feed_url"`
	LastBuildAt string            `json:"last_build_at"`
	GeneratedAt string            `json:"generated_at"`
	Articles    []CoinDeskArticle `json:"articles"`
}

type NewsService struct {
	httpClient  *http.Client
	credentials *ExternalAPICredentialService
	feedURL     string

	cacheMu sync.RWMutex
	cache   *newsCacheEntry
}

type newsCacheEntry struct {
	expiresAt time.Time
	value     *CoinDeskNewsResponse
}

type coinDeskRSS struct {
	Channel struct {
		LastBuildDate string            `xml:"lastBuildDate"`
		Items         []coinDeskRSSItem `xml:"item"`
	} `xml:"channel"`
}

type coinDeskRSSItem struct {
	GUID        string              `xml:"guid"`
	Title       string              `xml:"title"`
	Link        string              `xml:"link"`
	Description string              `xml:"description"`
	PubDate     string              `xml:"pubDate"`
	Creator     string              `xml:"http://purl.org/dc/elements/1.1/ creator"`
	Categories  []string            `xml:"category"`
	Media       []coinDeskMediaItem `xml:"http://search.yahoo.com/mrss/ content"`
}

type coinDeskMediaItem struct {
	URL string `xml:"url,attr"`
}

func NewNewsServiceFromEnv(credentials *ExternalAPICredentialService) *NewsService {
	feedURL := strings.TrimSpace(os.Getenv("COINDESK_RSS_URL"))
	if feedURL == "" {
		feedURL = defaultCoinDeskRSSURL
	}

	return &NewsService{
		httpClient:  &http.Client{Timeout: 12 * time.Second},
		credentials: credentials,
		feedURL:     feedURL,
	}
}

func (s *NewsService) GetCoinDeskConfigStatus() (*CoinDeskNewsConfigStatus, error) {
	_, sharedPresent, err := s.credentials.ResolveSharedKey(ExternalAPIProviderCoinDesk)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve CoinDesk shared key: %w", err)
	}

	info, err := s.credentials.GetShared(ExternalAPIProviderCoinDesk)
	if err != nil {
		return nil, fmt.Errorf("failed to load CoinDesk shared key status: %w", err)
	}

	return &CoinDeskNewsConfigStatus{
		Provider:         "coindesk",
		SharedKeyPresent: sharedPresent,
		SharedKeyMasked: func() string {
			if info != nil {
				return info.MaskedValue
			}
			return ""
		}(),
		SharedKeyLabel: func() string {
			if info != nil {
				return info.Label
			}
			return ""
		}(),
		FeedURL:           s.feedURL,
		Source:            "coindesk_rss",
		ConfiguredByAdmin: info != nil && info.IsActive,
	}, nil
}

func (s *NewsService) SaveCoinDeskSharedKey(payload CoinDeskNewsConfigPayload) (*ExternalAPICredentialInfo, error) {
	return s.credentials.SaveShared(ExternalAPIProviderCoinDesk, payload.APIKey, payload.Label)
}

func (s *NewsService) DeleteCoinDeskSharedKey() error {
	return s.credentials.DeleteShared(ExternalAPIProviderCoinDesk)
}

func (s *NewsService) GetLatestCoinDeskNews(ctx context.Context, limit int) (*CoinDeskNewsResponse, error) {
	if limit <= 0 {
		limit = defaultCoinDeskNewsLimit
	}

	if cached := s.getCached(limit); cached != nil {
		return cached, nil
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.feedURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create CoinDesk news request: %w", err)
	}

	if key, ok, err := s.credentials.ResolveSharedKey(ExternalAPIProviderCoinDesk); err == nil && ok && strings.TrimSpace(key) != "" {
		req.Header.Set("Authorization", "Bearer "+key)
		req.Header.Set("X-API-Key", key)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to reach CoinDesk feed: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return nil, fmt.Errorf("CoinDesk feed returned status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read CoinDesk feed: %w", err)
	}

	var feed coinDeskRSS
	if err := xml.Unmarshal(body, &feed); err != nil {
		return nil, fmt.Errorf("failed to parse CoinDesk RSS feed: %w", err)
	}

	articles := make([]CoinDeskArticle, 0, min(limit, len(feed.Channel.Items)))
	for _, item := range feed.Channel.Items {
		if len(articles) >= limit {
			break
		}
		articles = append(articles, CoinDeskArticle{
			ID:          fallbackArticleID(item),
			Title:       strings.TrimSpace(item.Title),
			URL:         strings.TrimSpace(item.Link),
			Summary:     strings.TrimSpace(item.Description),
			Author:      strings.TrimSpace(item.Creator),
			Category:    firstCategory(item.Categories),
			PublishedAt: parseRSSDate(item.PubDate),
			ImageURL:    firstMediaURL(item.Media),
			Tags:        collectTags(item.Categories),
		})
	}

	response := &CoinDeskNewsResponse{
		Provider:    "coindesk",
		Source:      "coindesk_rss",
		FeedURL:     s.feedURL,
		LastBuildAt: parseRSSDate(feed.Channel.LastBuildDate),
		GeneratedAt: time.Now().UTC().Format(time.RFC3339),
		Articles:    articles,
	}
	s.setCached(response)
	return response, nil
}

func (s *NewsService) getCached(limit int) *CoinDeskNewsResponse {
	s.cacheMu.RLock()
	defer s.cacheMu.RUnlock()
	if s.cache == nil || time.Now().After(s.cache.expiresAt) || s.cache.value == nil {
		return nil
	}
	if len(s.cache.value.Articles) < limit {
		return nil
	}

	cloned := *s.cache.value
	cloned.Articles = append([]CoinDeskArticle(nil), s.cache.value.Articles[:limit]...)
	return &cloned
}

func (s *NewsService) setCached(value *CoinDeskNewsResponse) {
	s.cacheMu.Lock()
	defer s.cacheMu.Unlock()
	s.cache = &newsCacheEntry{
		expiresAt: time.Now().Add(defaultCoinDeskNewsTTL),
		value:     value,
	}
}

func fallbackArticleID(item coinDeskRSSItem) string {
	if strings.TrimSpace(item.GUID) != "" {
		return strings.TrimSpace(item.GUID)
	}
	return strings.TrimSpace(item.Link)
}

func parseRSSDate(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	parsed, err := time.Parse(time.RFC1123Z, raw)
	if err != nil {
		return raw
	}
	return parsed.UTC().Format(time.RFC3339)
}

func firstCategory(categories []string) string {
	for _, category := range categories {
		category = strings.TrimSpace(category)
		if category != "" && strings.ToLower(category) != "news" {
			return category
		}
	}
	return "News"
}

func collectTags(categories []string) []string {
	tags := make([]string, 0, len(categories))
	seen := map[string]struct{}{}
	for _, category := range categories {
		category = strings.TrimSpace(category)
		if category == "" {
			continue
		}
		if _, exists := seen[category]; exists {
			continue
		}
		seen[category] = struct{}{}
		tags = append(tags, category)
	}
	return tags
}

func firstMediaURL(media []coinDeskMediaItem) string {
	for _, item := range media {
		if strings.TrimSpace(item.URL) != "" {
			return strings.TrimSpace(item.URL)
		}
	}
	return ""
}

func min(a int, b int) int {
	if a < b {
		return a
	}
	return b
}
