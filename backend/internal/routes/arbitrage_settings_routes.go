package routes

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

const arbitrageSettingsSection = "arbitrage"

type arbitrageSettingDefinition struct {
	Key          string
	BotKey       string
	ValueType    string
	DefaultValue string
	Description  string
}

var arbitrageSettingDefinitions = []arbitrageSettingDefinition{
	{"arbitrage_improvements_enabled", "ARBITRAGE_IMPROVEMENTS_ENABLED", "boolean", "false", "Enable safe API-call efficiency improvements"},
	{"pair_priority_engine_enabled", "PAIR_PRIORITY_ENGINE_ENABLED", "boolean", "false", "Enable optional pair-priority ranking"},
	{"polymarket_signals_enabled", "POLYMARKET_SIGNALS_ENABLED", "boolean", "false", "Allow Polymarket signals to affect pair priority when implemented"},
	{"defillama_signals_enabled", "DEFILLAMA_SIGNALS_ENABLED", "boolean", "false", "Allow DefiLlama signals to affect pair priority when implemented"},
	{"news_signals_enabled", "NEWS_SIGNALS_ENABLED", "boolean", "false", "Allow news signals to affect pair priority when implemented"},
	{"auto_execution_changes_enabled", "AUTO_EXECUTION_CHANGES_ENABLED", "boolean", "false", "Enable future execution-safety behavior changes"},
	{"pair_priority_max_pairs", "PAIR_PRIORITY_MAX_PAIRS", "integer", "0", "Optional top-N cap for pair-priority scanning; 0 keeps all pairs"},
	{"pair_priority_stale_seconds", "PAIR_PRIORITY_STALE_SECONDS", "float", "86400", "Seconds before pair analysis is treated as stale"},
}

func RegisterArbitrageSettingsRoutes(router *gin.Engine, database *db.Database, apiClient *services.BotAPIClient) {
	settingsService := services.NewSettingsService(repository.NewSettingsRepository(database.DB))

	group := router.Group("/api/v1/settings/arbitrage-runtime")
	group.Use(middleware.RequireAuth())
	group.Use(middleware.RequireMFA(database.DB))
	group.Use(middleware.RequirePermission(database.DB, "crm.admin.manage"))
	group.Use(withArbitrageRequestScopedBotClient(apiClient))
	{
		group.GET("", func(c *gin.Context) {
			settings, err := loadArbitrageRuntimeSettings(settingsService)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			botResponse, syncErr := requestClient.GetArbitrageRuntimeSettings()
			c.JSON(http.StatusOK, gin.H{
				"success":         true,
				"message":         "Arbitrage runtime settings loaded",
				"data":            settings,
				"bot_runtime":     botResponse,
				"bot_sync_status": syncStatus(syncErr),
			})
		})

		group.PUT("", func(c *gin.Context) {
			var body struct {
				Settings map[string]interface{} `json:"settings"`
			}
			if err := c.ShouldBindJSON(&body); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": fmt.Sprintf("Invalid request: %v", err)})
				return
			}

			if err := saveArbitrageRuntimeSettings(settingsService, body.Settings); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
				return
			}

			settings, err := loadArbitrageRuntimeSettings(settingsService)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
				return
			}

			requestClient := getRequestBotAPIClient(c, apiClient)
			botPayload := arbitrageSettingsForBot(settings)
			botResponse, syncErr := requestClient.UpdateArbitrageRuntimeSettings(botPayload)
			status := syncStatus(syncErr)
			writeAuditLog(
				database.DB,
				c,
				"settings.arbitrage_runtime.update",
				"bot_setting",
				nil,
				gin.H{
					"section":         arbitrageSettingsSection,
					"keys":            mapKeys(body.Settings),
					"bot_sync_status": status,
				},
				"success",
			)
			c.JSON(http.StatusOK, gin.H{
				"success":         true,
				"message":         "Arbitrage runtime settings saved",
				"data":            settings,
				"bot_runtime":     botResponse,
				"bot_sync_status": status,
			})
		})
	}
}

func withArbitrageRequestScopedBotClient(apiClient *services.BotAPIClient) gin.HandlerFunc {
	return func(c *gin.Context) {
		requestClient := apiClient.
			WithTraceID(middleware.GetTraceID(c)).
			WithRequestContext(c.Request.Context())

		if services.UseConfiguredBotAPIServiceToken() {
			c.Set("bot_api_client", requestClient)
			c.Next()
			return
		}

		token := extractBotAuthToken(c)
		if token != "" {
			c.Set("bot_api_client", requestClient.WithToken(token))
		} else {
			c.Set("bot_api_client", requestClient)
		}
		c.Next()
	}
}

func syncStatus(err error) string {
	if err != nil {
		return "bot_unreachable"
	}
	return "synced"
}

func loadArbitrageRuntimeSettings(service *services.SettingsService) (map[string]interface{}, error) {
	result := map[string]interface{}{}
	for _, definition := range arbitrageSettingDefinitions {
		setting, err := service.GetBotSetting(arbitrageSettingsSection, definition.Key)
		if err != nil {
			return nil, fmt.Errorf("failed to load %s.%s: %w", arbitrageSettingsSection, definition.Key, err)
		}
		if setting == nil {
			setting, err = service.CreateBotSetting(
				arbitrageSettingsSection,
				definition.Key,
				definition.DefaultValue,
				definition.ValueType,
				definition.Description,
				definition.DefaultValue,
				true,
			)
			if err != nil {
				return nil, fmt.Errorf("failed to initialize %s.%s: %w", arbitrageSettingsSection, definition.Key, err)
			}
		}
		result[definition.Key] = parseArbitrageSettingValue(setting.Value, definition)
	}
	return result, nil
}

func saveArbitrageRuntimeSettings(service *services.SettingsService, updates map[string]interface{}) error {
	if updates == nil {
		return fmt.Errorf("settings payload is required")
	}

	allowed := map[string]arbitrageSettingDefinition{}
	for _, definition := range arbitrageSettingDefinitions {
		allowed[definition.Key] = definition
	}

	for key, value := range updates {
		definition, ok := allowed[key]
		if !ok {
			return fmt.Errorf("unsupported arbitrage setting: %s", key)
		}
		normalized, err := normalizeArbitrageSettingValue(value, definition)
		if err != nil {
			return fmt.Errorf("invalid %s.%s: %w", arbitrageSettingsSection, key, err)
		}

		existing, err := service.GetBotSetting(arbitrageSettingsSection, key)
		if err != nil {
			return fmt.Errorf("failed to load %s.%s: %w", arbitrageSettingsSection, key, err)
		}
		if existing == nil {
			if _, err := service.CreateBotSetting(arbitrageSettingsSection, key, normalized, definition.ValueType, definition.Description, definition.DefaultValue, true); err != nil {
				return fmt.Errorf("failed to create %s.%s: %w", arbitrageSettingsSection, key, err)
			}
			continue
		}
		if _, err := service.UpdateBotSetting(existing.ID, normalized, definition.Description, existing.IsActive); err != nil {
			return fmt.Errorf("failed to update %s.%s: %w", arbitrageSettingsSection, key, err)
		}
	}
	return nil
}

func parseArbitrageSettingValue(value string, definition arbitrageSettingDefinition) interface{} {
	switch definition.ValueType {
	case "boolean":
		return strings.EqualFold(strings.TrimSpace(value), "true") || strings.TrimSpace(value) == "1"
	case "integer":
		parsed, err := strconv.Atoi(strings.TrimSpace(value))
		if err != nil || parsed < 0 {
			return 0
		}
		return parsed
	case "float":
		parsed, err := strconv.ParseFloat(strings.TrimSpace(value), 64)
		if err != nil || parsed < 0 {
			fallback, _ := strconv.ParseFloat(definition.DefaultValue, 64)
			return fallback
		}
		return parsed
	default:
		return value
	}
}

func normalizeArbitrageSettingValue(value interface{}, definition arbitrageSettingDefinition) (string, error) {
	switch definition.ValueType {
	case "boolean":
		return fmt.Sprintf("%t", toBoolSetting(value)), nil
	case "integer":
		parsed, err := toNonNegativeInt(value)
		if err != nil {
			return "", err
		}
		return strconv.Itoa(parsed), nil
	case "float":
		parsed, err := toNonNegativeFloat(value)
		if err != nil {
			return "", err
		}
		return strconv.FormatFloat(parsed, 'f', -1, 64), nil
	default:
		return fmt.Sprint(value), nil
	}
}

func toBoolSetting(value interface{}) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		text := strings.ToLower(strings.TrimSpace(typed))
		return text == "true" || text == "1" || text == "yes" || text == "on"
	default:
		return false
	}
}

func toNonNegativeInt(value interface{}) (int, error) {
	switch typed := value.(type) {
	case float64:
		if typed < 0 {
			return 0, fmt.Errorf("must be non-negative")
		}
		return int(typed), nil
	case int:
		if typed < 0 {
			return 0, fmt.Errorf("must be non-negative")
		}
		return typed, nil
	case string:
		parsed, err := strconv.Atoi(strings.TrimSpace(typed))
		if err != nil || parsed < 0 {
			return 0, fmt.Errorf("must be a non-negative integer")
		}
		return parsed, nil
	default:
		return 0, fmt.Errorf("must be a non-negative integer")
	}
}

func toNonNegativeFloat(value interface{}) (float64, error) {
	switch typed := value.(type) {
	case float64:
		if typed < 0 {
			return 0, fmt.Errorf("must be non-negative")
		}
		return typed, nil
	case int:
		if typed < 0 {
			return 0, fmt.Errorf("must be non-negative")
		}
		return float64(typed), nil
	case string:
		parsed, err := strconv.ParseFloat(strings.TrimSpace(typed), 64)
		if err != nil || parsed < 0 {
			return 0, fmt.Errorf("must be a non-negative number")
		}
		return parsed, nil
	default:
		return 0, fmt.Errorf("must be a non-negative number")
	}
}

func arbitrageSettingsForBot(settings map[string]interface{}) map[string]interface{} {
	payload := map[string]interface{}{}
	for _, definition := range arbitrageSettingDefinitions {
		payload[definition.BotKey] = settings[definition.Key]
	}
	return payload
}
