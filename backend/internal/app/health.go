package app

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/dydx-trading-bot/backend-go/internal/startup"
	"github.com/gin-gonic/gin"
)

var sensitiveAssignmentPattern = regexp.MustCompile(`(?i)(password|passwd|pwd|token|secret|key)=([^\s,;]+)`)
var urlUserInfoPattern = regexp.MustCompile(`([a-z][a-z0-9+.-]*://)[^\s/@]+@`)

func probeJSONEndpoint(rawURL string, timeout time.Duration) (int, map[string]interface{}, string) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return 0, nil, err.Error()
	}

	httpClient := &http.Client{}
	resp, err := httpClient.Do(req)
	if err != nil {
		return 0, nil, err.Error()
	}
	defer func() { _ = resp.Body.Close() }()

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		payload = nil
	}

	return resp.StatusCode, payload, ""
}

func redactSensitiveText(value string) string {
	value = urlUserInfoPattern.ReplaceAllString(value, "${1}redacted@")
	return sensitiveAssignmentPattern.ReplaceAllString(value, "${1}=redacted")
}

func isSensitiveDependencyKey(key string) bool {
	key = strings.ToLower(strings.TrimSpace(key))
	return strings.Contains(key, "password") ||
		strings.Contains(key, "passwd") ||
		strings.Contains(key, "token") ||
		strings.Contains(key, "secret") ||
		strings.Contains(key, "api_key") ||
		strings.Contains(key, "apikey") ||
		strings.Contains(key, "dsn") ||
		strings.Contains(key, "database_url")
}

func sanitizeDependencyPayload(value interface{}) interface{} {
	switch typed := value.(type) {
	case map[string]interface{}:
		sanitized := make(map[string]interface{}, len(typed))
		for key, nested := range typed {
			if isSensitiveDependencyKey(key) {
				sanitized[key] = "redacted"
				continue
			}
			sanitized[key] = sanitizeDependencyPayload(nested)
		}
		return sanitized
	case []interface{}:
		sanitized := make([]interface{}, 0, len(typed))
		for _, nested := range typed {
			sanitized = append(sanitized, sanitizeDependencyPayload(nested))
		}
		return sanitized
	case string:
		return redactSensitiveText(typed)
	default:
		return value
	}
}

func sanitizeDependencyURL(raw string) string {
	parsed, err := url.Parse(raw)
	if err != nil {
		return redactSensitiveText(raw)
	}
	parsed.User = nil
	query := parsed.Query()
	for key := range query {
		if isSensitiveDependencyKey(key) {
			query.Set(key, "redacted")
		}
	}
	parsed.RawQuery = query.Encode()
	return parsed.String()
}

func buildDependencySnapshot(baseURL, endpoint string, timeout time.Duration) (gin.H, bool) {
	statusCode, payload, probeError := probeJSONEndpoint(endpoint, timeout)
	healthy := probeError == "" && statusCode >= 200 && statusCode < 300

	var sanitizedPayload interface{}
	if payload != nil {
		sanitizedPayload = sanitizeDependencyPayload(payload)
	}

	return gin.H{
		"base_url":       sanitizeDependencyURL(baseURL),
		"probe_url":      sanitizeDependencyURL(endpoint),
		"reachable":      healthy,
		"status_code":    statusCode,
		"error":          redactSensitiveText(probeError),
		"payload":        sanitizedPayload,
		"checked_at_utc": time.Now().UTC().Format(time.RFC3339),
	}, healthy
}

func extractBotRecoveryPayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return nil
	}

	if direct, ok := payload["bot_recovery"].(map[string]interface{}); ok {
		return direct
	}

	data, ok := payload["data"].(map[string]interface{})
	if !ok || data == nil {
		return nil
	}

	if nested, ok := data["bot_recovery"].(map[string]interface{}); ok {
		return nested
	}

	return nil
}

func getPayloadString(payload map[string]interface{}, keys ...string) string {
	for _, key := range keys {
		value, ok := payload[key]
		if !ok || value == nil {
			continue
		}
		switch typed := value.(type) {
		case string:
			if trimmed := strings.TrimSpace(typed); trimmed != "" {
				return redactSensitiveText(trimmed)
			}
		default:
			if trimmed := strings.TrimSpace(fmt.Sprintf("%v", typed)); trimmed != "" && trimmed != "<nil>" {
				return redactSensitiveText(trimmed)
			}
		}
	}
	return ""
}

func appendPayloadBlockers(blockers []string, value interface{}) []string {
	switch typed := value.(type) {
	case []interface{}:
		for _, item := range typed {
			if text := redactSensitiveText(strings.TrimSpace(fmt.Sprintf("%v", item))); text != "" && text != "<nil>" {
				blockers = append(blockers, text)
			}
		}
	case []string:
		for _, item := range typed {
			if text := redactSensitiveText(strings.TrimSpace(item)); text != "" {
				blockers = append(blockers, text)
			}
		}
	case string:
		if text := redactSensitiveText(strings.TrimSpace(typed)); text != "" {
			blockers = append(blockers, text)
		}
	}
	return blockers
}

func buildBotReadinessSummary(snapshot gin.H) gin.H {
	statusCode, _ := snapshot["status_code"].(int)
	probeError, _ := snapshot["error"].(string)
	payload, _ := snapshot["payload"].(map[string]interface{})
	data := map[string]interface{}{}
	if payload != nil {
		if nested, ok := payload["data"].(map[string]interface{}); ok {
			data = nested
		}
	}

	message := getPayloadString(payload, "message", "error", "detail")
	if message == "" {
		message = getPayloadString(data, "message", "error", "detail")
	}
	if message == "" {
		message = strings.TrimSpace(probeError)
	}
	if message == "" && statusCode > 0 {
		message = fmt.Sprintf("upstream bot API readiness check returned HTTP %d", statusCode)
	}
	if message == "" {
		message = "upstream bot API readiness check failed"
	}

	blockers := []string{}
	if payload != nil {
		blockers = appendPayloadBlockers(blockers, payload["blockers"])
		blockers = appendPayloadBlockers(blockers, payload["errors"])
	}
	if data != nil {
		blockers = appendPayloadBlockers(blockers, data["blockers"])
		blockers = appendPayloadBlockers(blockers, data["errors"])
	}
	if len(blockers) == 0 {
		blockers = append(blockers, message)
	}

	reasonText := strings.ToLower(strings.Join(append(blockers, message), " "))
	reason := "bot_api_not_ready"
	action := "check the upstream bot API /ready endpoint and bot service logs"
	if strings.Contains(reasonText, "migration") || strings.Contains(reasonText, "schema") {
		reason = "bot_migrations_unhealthy"
		action = "run or repair the bot service database migrations before marking the backend ready"
	} else if strings.Contains(reasonText, "database") ||
		strings.Contains(reasonText, "db") ||
		strings.Contains(reasonText, "connection refused") ||
		strings.Contains(reasonText, "connect") {
		reason = "bot_database_unavailable"
		action = "verify the dedicated bot database is reachable and the bot service has valid DB configuration"
	} else if strings.TrimSpace(probeError) != "" {
		reason = "bot_api_unreachable"
		action = "ensure the bot service is running and reachable from the backend"
	}

	return gin.H{
		"ready":       false,
		"status_code": statusCode,
		"reason":      reason,
		"message":     message,
		"blockers":    blockers,
		"action":      action,
	}
}

func firstNonEmptyEnv(keys ...string) string {
	for _, key := range keys {
		if value := strings.TrimSpace(os.Getenv(key)); value != "" {
			return value
		}
	}
	return ""
}

func buildServiceMetadata(startTime time.Time) gin.H {
	buildTag := firstNonEmptyEnv("APP_BUILD_TAG", "IMAGE_TAG")
	if buildTag == "" {
		buildTag = "unknown"
	}

	buildCommit := firstNonEmptyEnv("APP_BUILD_COMMIT", "GIT_COMMIT", "SOURCE_COMMIT")
	if buildCommit == "" {
		buildCommit = "unknown"
	}

	buildTime := firstNonEmptyEnv("APP_BUILD_TIME", "BUILD_TIME")
	if buildTime == "" {
		buildTime = "unknown"
	}

	return gin.H{
		"name":           "backend",
		"version":        "1.0.0",
		"environment":    config.ResolveAppConfigEnvironment(),
		"uptime_seconds": time.Since(startTime).Seconds(),
		"started_at_utc": startTime.UTC().Format(time.RFC3339),
		"build": gin.H{
			"tag":      buildTag,
			"commit":   buildCommit,
			"built_at": buildTime,
		},
	}
}

func registerHealthRoutes(router *gin.Engine, cfg *config.Config, database *db.Database, botAPIURL string, startTime time.Time) {
	router.GET("/version", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": buildServiceMetadata(startTime),
		})
	})

	router.GET("/api/v1/version", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": buildServiceMetadata(startTime),
		})
	})

	router.GET("/health", func(c *gin.Context) {
		dbOwnership := startup.BuildDatabaseOwnershipDiagnostics(cfg)
		dbHealthy := true
		dbError := ""
		if err := database.Health(); err != nil {
			dbHealthy = false
			dbError = err.Error()
		}

		botSnapshot, botHealthy := buildDependencySnapshot(botAPIURL, botAPIURL+"/health", 3*time.Second)
		var botPayload map[string]interface{}
		if payload, ok := botSnapshot["payload"].(map[string]interface{}); ok {
			botPayload = payload
		}
		botRecovery := extractBotRecoveryPayload(botPayload)
		stats := database.GetStats()

		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"live":      true,
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"dependencies": gin.H{
				"database_healthy": dbHealthy,
				"bot_api_healthy":  botHealthy,
			},
			"database_ownership": dbOwnership,
			"bot_api":            botSnapshot,
			"bot_recovery":       botRecovery,
			"database": gin.H{
				"healthy":             dbHealthy,
				"error":               dbError,
				"open_connections":    stats.OpenConnections,
				"in_use":              stats.InUse,
				"idle":                stats.Idle,
				"wait_count":          stats.WaitCount,
				"wait_duration":       stats.WaitDuration.String(),
				"max_idle_closed":     stats.MaxIdleClosed,
				"max_lifetime_closed": stats.MaxLifetimeClosed,
			},
			"service": buildServiceMetadata(startTime),
		})
	})

	router.GET("/ready", func(c *gin.Context) {
		dbOwnership := startup.BuildDatabaseOwnershipDiagnostics(cfg)
		if dbOwnership.BlockingViolation {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":             "not_ready",
				"ready":              false,
				"component":          "database_ownership",
				"database_ownership": dbOwnership,
			})
			return
		}

		if err := database.Health(); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":    "not_ready",
				"ready":     false,
				"component": "database",
				"error":     err.Error(),
			})
			return
		}

		botSnapshot, botReady := buildDependencySnapshot(botAPIURL, botAPIURL+"/ready", 3*time.Second)
		var botPayload map[string]interface{}
		if payload, ok := botSnapshot["payload"].(map[string]interface{}); ok {
			botPayload = payload
		}
		botRecovery := extractBotRecoveryPayload(botPayload)
		if !botReady {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":        "not_ready",
				"ready":         false,
				"component":     "bot_api",
				"bot_api":       botSnapshot,
				"bot_recovery":  botRecovery,
				"bot_readiness": buildBotReadinessSummary(botSnapshot),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":             "ready",
			"ready":              true,
			"database_ownership": dbOwnership,
			"bot_api":            botSnapshot,
			"bot_recovery":       botRecovery,
			"checked_at_utc":     time.Now().UTC().Format(time.RFC3339),
		})
	})

	router.GET("/metrics", func(c *gin.Context) {
		stats := database.GetStats()
		botSnapshot, _ := buildDependencySnapshot(botAPIURL, botAPIURL+"/metrics", 3*time.Second)

		c.JSON(http.StatusOK, gin.H{
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"uptime_seconds": time.Since(startTime).Seconds(),
			"database": gin.H{
				"connections": gin.H{
					"open":                stats.OpenConnections,
					"in_use":              stats.InUse,
					"idle":                stats.Idle,
					"max_idle_closed":     stats.MaxIdleClosed,
					"max_lifetime_closed": stats.MaxLifetimeClosed,
				},
				"wait_stats": gin.H{
					"count":    stats.WaitCount,
					"duration": stats.WaitDuration.String(),
				},
			},
			"bot_api":        botSnapshot,
			"bot_api_client": services.BotAPIStats(),
			"backtest_sync": gin.H{
				"run_upsert_outcomes": repository.BacktestRunSyncOutcomeCounters(),
			},
			"service":        buildServiceMetadata(startTime),
		})
	})
}
