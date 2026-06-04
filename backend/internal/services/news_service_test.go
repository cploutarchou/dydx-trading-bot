//go:build integration

package services

import (
	"context"
	"database/sql"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

func setupNewsCredentialService(t *testing.T) *ExternalAPICredentialService {
	t.Helper()
	t.Setenv("ENCRYPTION_KEY", "news-service-test-encryption-key!!")

	dbConn, err := sql.Open("sqlite", "file:news-service-test?mode=memory&cache=shared")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })

	if _, err := dbConn.Exec(`
		CREATE TABLE external_api_credentials (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			provider TEXT NOT NULL,
			label TEXT NOT NULL DEFAULT '',
			encrypted_api_key TEXT NOT NULL,
			api_key_hash TEXT NOT NULL DEFAULT '',
			api_key_masked TEXT NOT NULL DEFAULT '',
			is_active BOOLEAN NOT NULL DEFAULT 1,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			UNIQUE (user_id, provider)
		)
	`); err != nil {
		t.Fatalf("create credentials table: %v", err)
	}

	return NewExternalAPICredentialService(repository.NewExternalAPICredentialRepository(dbConn))
}

func TestNewsServiceParsesCoinDeskRSS(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/xml")
		_, _ = w.Write([]byte(`<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" version="2.0">
  <channel>
    <lastBuildDate>Sun, 05 Apr 2026 14:05:46 +0000</lastBuildDate>
    <item>
      <title><![CDATA[Test headline]]></title>
      <link>https://www.coindesk.com/test-story</link>
      <guid isPermaLink="false">story-1</guid>
      <pubDate>Sun, 05 Apr 2026 14:00:00 +0000</pubDate>
      <description><![CDATA[Test summary]]></description>
      <dc:creator>CoinDesk Reporter</dc:creator>
      <media:content url="https://img.executionlab.io/story.jpg" type="image/*" medium="image"/>
      <category>Markets</category>
      <category>News</category>
    </item>
  </channel>
</rss>`))
	}))
	defer upstream.Close()

	service := &NewsService{
		httpClient:  upstream.Client(),
		credentials: setupNewsCredentialService(t),
		feedURL:     upstream.URL,
	}

	response, err := service.GetLatestCoinDeskNews(context.Background(), 4)
	if err != nil {
		t.Fatalf("GetLatestCoinDeskNews returned error: %v", err)
	}
	if response.Provider != "coindesk" || response.Source != "coindesk_rss" {
		t.Fatalf("unexpected response metadata: %+v", response)
	}
	if len(response.Articles) != 1 {
		t.Fatalf("expected 1 article, got %d", len(response.Articles))
	}
	if response.Articles[0].Title != "Test headline" || response.Articles[0].Author != "CoinDesk Reporter" {
		t.Fatalf("unexpected article payload: %+v", response.Articles[0])
	}
	if !strings.Contains(response.Articles[0].PublishedAt, "2026-04-05T14:00:00Z") {
		t.Fatalf("expected RFC3339 published_at, got %q", response.Articles[0].PublishedAt)
	}
}

func TestNewsServiceCoalescesConcurrentCacheMisses(t *testing.T) {
	var upstreamRequests int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&upstreamRequests, 1)
		time.Sleep(80 * time.Millisecond)
		w.Header().Set("Content-Type", "application/xml")
		_, _ = w.Write([]byte(`<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" version="2.0">
  <channel>
    <lastBuildDate>Sun, 05 Apr 2026 14:05:46 +0000</lastBuildDate>
    <item>
      <title><![CDATA[Coalesced headline]]></title>
      <link>https://www.coindesk.com/coalesced-story</link>
      <guid isPermaLink="false">story-coalesced</guid>
      <pubDate>Sun, 05 Apr 2026 14:00:00 +0000</pubDate>
      <description><![CDATA[Test summary]]></description>
      <dc:creator>CoinDesk Reporter</dc:creator>
      <category>Markets</category>
    </item>
  </channel>
</rss>`))
	}))
	defer upstream.Close()

	service := &NewsService{
		httpClient:  upstream.Client(),
		credentials: setupNewsCredentialService(t),
		feedURL:     upstream.URL,
	}

	const workers = 10
	start := make(chan struct{})
	var wg sync.WaitGroup
	var failures int32

	wg.Add(workers)
	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()
			<-start
			response, err := service.GetLatestCoinDeskNews(context.Background(), 4)
			if err != nil {
				atomic.AddInt32(&failures, 1)
				return
			}
			if len(response.Articles) != 1 {
				atomic.AddInt32(&failures, 1)
			}
		}()
	}

	close(start)
	wg.Wait()

	if failures != 0 {
		t.Fatalf("expected zero failures, got %d", failures)
	}
	if got := atomic.LoadInt32(&upstreamRequests); got != 1 {
		t.Fatalf("expected exactly one upstream request under concurrent miss, got %d", got)
	}
}
