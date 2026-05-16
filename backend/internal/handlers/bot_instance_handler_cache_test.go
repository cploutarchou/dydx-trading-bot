package handlers

import (
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestReadBotStatsCacheTTLSeconds_Default(t *testing.T) {
	t.Setenv("BOT_STATS_CACHE_TTL_SECONDS", "")
	if got := readBotStatsCacheTTLSeconds(); got != defaultBotStatsCacheTTLSeconds {
		t.Fatalf("expected default ttl %d, got %d", defaultBotStatsCacheTTLSeconds, got)
	}
}

func TestReadBotStatsCacheTTLSeconds_ValidValue(t *testing.T) {
	t.Setenv("BOT_STATS_CACHE_TTL_SECONDS", "45")
	if got := readBotStatsCacheTTLSeconds(); got != 45 {
		t.Fatalf("expected ttl 45, got %d", got)
	}
}

func TestReadBotStatsCacheTTLSeconds_InvalidFallsBackToDefault(t *testing.T) {
	t.Setenv("BOT_STATS_CACHE_TTL_SECONDS", "not-a-number")
	if got := readBotStatsCacheTTLSeconds(); got != defaultBotStatsCacheTTLSeconds {
		t.Fatalf("expected fallback ttl %d, got %d", defaultBotStatsCacheTTLSeconds, got)
	}
}

func TestReadBotStatsCacheTTLSeconds_NegativeDisablesCache(t *testing.T) {
	t.Setenv("BOT_STATS_CACHE_TTL_SECONDS", "-1")
	if got := readBotStatsCacheTTLSeconds(); got != 0 {
		t.Fatalf("expected ttl 0 for negative value, got %d", got)
	}
}

func TestBotStatsCacheKey(t *testing.T) {
	if got := botStatsCacheKey("abc-123"); got != "bot:stats:abc-123" {
		t.Fatalf("unexpected cache key: %s", got)
	}
}

func TestParseLimitOffsetQuery_Defaults(t *testing.T) {
	gin.SetMode(gin.TestMode)
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	req := httptest.NewRequest("GET", "/api/v1/bots/bot-1/positions", nil)
	c.Request = req

	limit, offset := parseLimitOffsetQuery(c, 100, 500)

	if limit != 100 {
		t.Fatalf("expected default limit 100, got %d", limit)
	}
	if offset != 0 {
		t.Fatalf("expected default offset 0, got %d", offset)
	}
}

func TestParseLimitOffsetQuery_PageAndPageSize(t *testing.T) {
	gin.SetMode(gin.TestMode)
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	req := httptest.NewRequest("GET", "/api/v1/bots/bot-1/positions?page=3&page_size=25", nil)
	c.Request = req

	limit, offset := parseLimitOffsetQuery(c, 100, 500)

	if limit != 25 {
		t.Fatalf("expected limit 25, got %d", limit)
	}
	if offset != 50 {
		t.Fatalf("expected offset 50 for page=3,page_size=25, got %d", offset)
	}
}

func TestParseLimitOffsetQuery_OffsetOverridesPage(t *testing.T) {
	gin.SetMode(gin.TestMode)
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	req := httptest.NewRequest("GET", "/api/v1/bots/bot-1/positions?page=4&page_size=20&offset=7", nil)
	c.Request = req

	limit, offset := parseLimitOffsetQuery(c, 100, 500)

	if limit != 20 {
		t.Fatalf("expected limit 20, got %d", limit)
	}
	if offset != 7 {
		t.Fatalf("expected explicit offset override 7, got %d", offset)
	}
}
