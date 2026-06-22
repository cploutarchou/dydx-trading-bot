package app

import (
	"testing"

	"github.com/gin-gonic/gin"
)

func TestBuildBotReadinessSummary_ClassifiesBotDatabaseUnavailable(t *testing.T) {
	snapshot := gin.H{
		"status_code": 503,
		"error":       "",
		"payload": map[string]interface{}{
			"ready":   false,
			"message": "bot database unavailable: dial tcp 10.0.0.5:5432: connect: connection refused",
		},
	}

	summary := buildBotReadinessSummary(snapshot)
	if summary["reason"] != "bot_database_unavailable" {
		t.Fatalf("expected bot_database_unavailable, got %+v", summary)
	}
	if summary["action"] == "" {
		t.Fatalf("expected actionable recovery guidance, got %+v", summary)
	}
}

func TestBuildBotReadinessSummary_ClassifiesMissingBotMigrations(t *testing.T) {
	snapshot := gin.H{
		"status_code": 503,
		"payload": map[string]interface{}{
			"data": map[string]interface{}{
				"blockers": []interface{}{
					"bot database migrations missing: expected schema version 12",
				},
			},
		},
	}

	summary := buildBotReadinessSummary(snapshot)
	if summary["reason"] != "bot_migrations_unhealthy" {
		t.Fatalf("expected bot_migrations_unhealthy, got %+v", summary)
	}
}

func TestBuildDependencySnapshot_RedactsSecretsFromURLAndPayload(t *testing.T) {
	payload := map[string]interface{}{
		"database_url": "postgres://bot_user:super-secret@db.local:5432/bot",
		"message":      "password=super-secret token=abc123",
		"data": map[string]interface{}{
			"api_key": "abc123",
		},
	}

	sanitized := sanitizeDependencyPayload(payload).(map[string]interface{})
	if sanitized["database_url"] != "redacted" {
		t.Fatalf("expected database_url to be redacted, got %+v", sanitized)
	}
	if sanitized["message"] == payload["message"] {
		t.Fatalf("expected sensitive message assignments to be redacted, got %+v", sanitized)
	}
	data := sanitized["data"].(map[string]interface{})
	if data["api_key"] != "redacted" {
		t.Fatalf("expected nested api_key redaction, got %+v", sanitized)
	}

	gotURL := sanitizeDependencyURL("http://user:secret@bot.local:8889/ready?token=abc&debug=true")
	if gotURL != "http://bot.local:8889/ready?debug=true&token=redacted" {
		t.Fatalf("unexpected sanitized URL: %q", gotURL)
	}
}

func TestBuildDependencySnapshot_RedactsDatabaseURLSecrets(t *testing.T) {
	payload := map[string]interface{}{
		"database_url": "postgres://bot_user:super-secret@db.local:5432/bot",
	}

	sanitized := sanitizeDependencyPayload(payload).(map[string]interface{})
	if sanitized["database_url"] != "redacted" {
		t.Fatalf("expected database_url to be redacted, got %+v", sanitized)
	}
}
