package handlers

import "testing"

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
