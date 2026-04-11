package handlers

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

// SettingsHandler handles settings API endpoints
type SettingsHandler struct {
	service services.SettingsServiceIface
}

func (h *SettingsHandler) resolveEffectiveRedisSetting() (*models.RedisSetting, error) {
	redisSetting, err := h.service.GetRedisSetting()
	if err != nil {
		return nil, err
	}
	if redisSetting != nil {
		return redisSetting, nil
	}

	if config.ConfigInstance == nil || !config.ConfigInstance.Redis.Enabled {
		return nil, nil
	}

	return &models.RedisSetting{
		Enabled:  config.ConfigInstance.Redis.Enabled,
		Host:     config.ConfigInstance.Redis.Host,
		Port:     config.ConfigInstance.Redis.Port,
		Db:       config.ConfigInstance.Redis.Db,
		Password: config.ConfigInstance.Redis.Password,
		SSL:      config.ConfigInstance.Redis.SSL,
	}, nil
}

func inferValueType(value interface{}) string {
	switch value.(type) {
	case bool:
		return "boolean"
	case float64, float32:
		return "float"
	case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64:
		return "integer"
	default:
		return "string"
	}
}

func normalizeSettingValue(value interface{}) string {
	switch v := value.(type) {
	case string:
		return v
	case bool, float64, float32, int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64:
		return fmt.Sprintf("%v", v)
	default:
		payload, err := json.Marshal(v)
		if err != nil {
			return fmt.Sprintf("%v", v)
		}
		return string(payload)
	}
}

func toInt(value interface{}, fallback int) int {
	switch v := value.(type) {
	case float64:
		return int(v)
	case float32:
		return int(v)
	case int:
		return v
	case int64:
		return int(v)
	case int32:
		return int(v)
	case string:
		parsed, err := strconv.Atoi(v)
		if err != nil {
			return fallback
		}
		return parsed
	default:
		return fallback
	}
}

func toBool(value interface{}, fallback bool) bool {
	switch v := value.(type) {
	case bool:
		return v
	case string:
		lower := strings.ToLower(strings.TrimSpace(v))
		if lower == "true" || lower == "1" || lower == "yes" || lower == "on" {
			return true
		}
		if lower == "false" || lower == "0" || lower == "no" || lower == "off" {
			return false
		}
		return fallback
	default:
		return fallback
	}
}

// NewSettingsHandler creates a new settings handler
func NewSettingsHandler(service services.SettingsServiceIface) *SettingsHandler {
	return &SettingsHandler{
		service: service,
	}
}

// ============ BotSetting Endpoints ============

// CreateBotSetting creates a new bot setting
func (h *SettingsHandler) CreateBotSetting(c *gin.Context) {
	var req struct {
		Section      string `json:"section" binding:"required"`
		Key          string `json:"key" binding:"required"`
		Value        string `json:"value"`
		ValueType    string `json:"value_type"`
		Description  string `json:"description"`
		DefaultValue string `json:"default_value"`
		IsActive     bool   `json:"is_active"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	setting, err := h.service.CreateBotSetting(
		req.Section,
		req.Key,
		req.Value,
		req.ValueType,
		req.Description,
		req.DefaultValue,
		req.IsActive,
	)

	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to create setting: %v", err),
		})
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotSetting retrieves a bot setting
func (h *SettingsHandler) GetBotSetting(c *gin.Context) {
	section := c.Query("section")
	key := c.Query("key")

	if section == "" || key == "" {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "section and key are required",
		})
		return
	}

	setting, err := h.service.GetBotSetting(section, key)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get setting: %v", err),
		})
		return
	}

	if setting == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Setting not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetBotSettingsBySection retrieves all settings in a section
func (h *SettingsHandler) GetBotSettingsBySection(c *gin.Context) {
	section := c.Query("section")

	if section == "" {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "section is required",
		})
		return
	}

	settings, err := h.service.GetBotSettingsBySection(section)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get settings: %v", err),
		})
		return
	}

	var result []map[string]interface{}
	for _, s := range settings {
		result = append(result, s.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"settings": result,
			"count":    len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ListAllBotSettings retrieves all bot settings
func (h *SettingsHandler) ListAllBotSettings(c *gin.Context) {
	settings, err := h.service.GetAllBotSettings()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to list settings: %v", err),
		})
		return
	}

	var result []map[string]interface{}
	for _, s := range settings {
		result = append(result, s.ToDict())
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"settings": result,
			"count":    len(result),
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// UpdateBotSetting updates a bot setting
func (h *SettingsHandler) UpdateBotSetting(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid setting ID",
		})
		return
	}

	var req struct {
		Value       string `json:"value"`
		Description string `json:"description"`
		IsActive    bool   `json:"is_active"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	setting, err := h.service.UpdateBotSetting(id, req.Value, req.Description, req.IsActive)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to update setting: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// DeleteBotSetting deletes a bot setting
func (h *SettingsHandler) DeleteBotSetting(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Invalid setting ID",
		})
		return
	}

	if err := h.service.DeleteBotSetting(id); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to delete setting: %v", err),
		})
		return
	}

	c.Status(http.StatusNoContent)
}

// ============ RedisSetting Endpoints ============

// GetRedisSetting retrieves redis settings
func (h *SettingsHandler) GetRedisSetting(c *gin.Context) {
	setting, err := h.resolveEffectiveRedisSetting()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to get redis setting: %v", err),
		})
		return
	}

	if setting == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     "Redis setting not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// UpdateRedisSetting updates redis settings
func (h *SettingsHandler) UpdateRedisSetting(c *gin.Context) {
	var req struct {
		Enabled  bool   `json:"enabled"`
		Host     string `json:"host" binding:"required"`
		Port     int    `json:"port" binding:"required"`
		Db       int    `json:"db"`
		Password string `json:"password"`
		SSL      bool   `json:"ssl"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	setting, err := h.service.UpdateRedisSetting(req.Enabled, req.Host, req.Port, req.Db, req.Password, req.SSL)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to update redis setting: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ClearSettingsCache clears the settings cache
func (h *SettingsHandler) ClearSettingsCache(c *gin.Context) {
	h.service.ClearCache()

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"message": "Settings cache cleared",
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetCacheStats returns cache statistics
func (h *SettingsHandler) GetCacheStats(c *gin.Context) {
	stats := h.service.GetCacheStats()

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      stats,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ============ Additional Endpoints ============

// Initialize initializes default settings (idempotent)
func (h *SettingsHandler) Initialize(c *gin.Context) {
	// Define default settings to initialize
	defaultSettings := []struct {
		section      string
		key          string
		value        string
		valueType    string
		description  string
		defaultValue string
		isActive     bool
	}{
		{
			section:      "trading",
			key:          "max_position_size",
			value:        "1000",
			valueType:    "integer",
			description:  "Maximum position size per trade",
			defaultValue: "1000",
			isActive:     true,
		},
		{
			section:      "trading",
			key:          "stop_loss_percentage",
			value:        "5",
			valueType:    "float",
			description:  "Stop loss percentage for trades",
			defaultValue: "5",
			isActive:     true,
		},
		{
			section:      "trading",
			key:          "take_profit_percentage",
			value:        "10",
			valueType:    "float",
			description:  "Take profit percentage for trades",
			defaultValue: "10",
			isActive:     true,
		},
		{
			section:      "api",
			key:          "request_timeout",
			value:        "30",
			valueType:    "integer",
			description:  "API request timeout in seconds",
			defaultValue: "30",
			isActive:     true,
		},
		{
			section:      "api",
			key:          "retry_attempts",
			value:        "3",
			valueType:    "integer",
			description:  "Number of retry attempts for failed requests",
			defaultValue: "3",
			isActive:     true,
		},
		{
			section:      "platform",
			key:          "allow_public_registration",
			value:        "true",
			valueType:    "boolean",
			description:  "Allow new users to register without administrator approval",
			defaultValue: "true",
			isActive:     true,
		},
		{
			section:      "platform",
			key:          "registration_mode",
			value:        "open",
			valueType:    "string",
			description:  "Registration mode: open, disabled, or invitation_only",
			defaultValue: "open",
			isActive:     true,
		},
		{
			section:      "platform",
			key:          "registration_invitation_code",
			value:        "",
			valueType:    "string",
			description:  "Invitation code required when registration_mode is invitation_only",
			defaultValue: "",
			isActive:     true,
		},
		{
			section:      "platform",
			key:          "require_privileged_mfa",
			value:        "false",
			valueType:    "boolean",
			description:  "Require MFA enrollment before privileged admin and CRM actions",
			defaultValue: "false",
			isActive:     true,
		},
		{
			section:      "bot",
			key:          "enabled",
			value:        "false",
			valueType:    "boolean",
			description:  "Enable or disable the trading bot",
			defaultValue: "false",
			isActive:     true,
		},
		{
			section:      "bot",
			key:          "log_level",
			value:        "info",
			valueType:    "string",
			description:  "Logging level (debug, info, warn, error)",
			defaultValue: "info",
			isActive:     true,
		},
	}

	// Try to create default settings
	for _, setting := range defaultSettings {
		// Check if setting already exists
		existing, _ := h.service.GetBotSetting(setting.section, setting.key)
		if existing != nil {
			// Setting already exists, skip
			continue
		}

		// Try to create the setting
		_, _ = h.service.CreateBotSetting(
			setting.section,
			setting.key,
			setting.value,
			setting.valueType,
			setting.description,
			setting.defaultValue,
			setting.isActive,
		)
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"message": "Settings initialized successfully",
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetSchema returns the settings schema
func (h *SettingsHandler) GetSchema(c *gin.Context) {
	// Return the schema for settings with sections array matching frontend structure
	schema := map[string]interface{}{
		"sections": []map[string]interface{}{
			{
				"section":     "trading",
				"title":       "Trading",
				"description": "Trading configuration settings",
				"fields": []map[string]interface{}{
					{
						"key":           "max_position_size",
						"label":         "Max Position Size",
						"value_type":    "integer",
						"description":   "Maximum position size per trade",
						"default_value": "1000",
						"required":      false,
					},
					{
						"key":           "stop_loss_percentage",
						"label":         "Stop Loss Percentage",
						"value_type":    "float",
						"description":   "Stop loss percentage for trades",
						"default_value": "5",
						"required":      false,
					},
					{
						"key":           "take_profit_percentage",
						"label":         "Take Profit Percentage",
						"value_type":    "float",
						"description":   "Take profit percentage for trades",
						"default_value": "10",
						"required":      false,
					},
				},
			},
			{
				"section":     "api",
				"title":       "API",
				"description": "API configuration settings",
				"fields": []map[string]interface{}{
					{
						"key":           "request_timeout",
						"label":         "Request Timeout",
						"value_type":    "integer",
						"description":   "API request timeout in seconds",
						"default_value": "30",
						"required":      false,
					},
					{
						"key":           "retry_attempts",
						"label":         "Retry Attempts",
						"value_type":    "integer",
						"description":   "Number of retry attempts for failed requests",
						"default_value": "3",
						"required":      false,
					},
				},
			},
			{
				"section":     "platform",
				"title":       "Platform Access",
				"description": "Platform-wide user access controls",
				"fields": []map[string]interface{}{
					{
						"key":           "allow_public_registration",
						"label":         "Allow Public Registration",
						"value_type":    "boolean",
						"description":   "Enable or disable self-service account registration",
						"default_value": true,
						"required":      false,
					},
					{
						"key":           "registration_mode",
						"label":         "Registration Mode",
						"value_type":    "string",
						"description":   "open, disabled, or invitation_only",
						"default_value": "open",
						"required":      false,
					},
					{
						"key":           "registration_invitation_code",
						"label":         "Registration Invitation Code",
						"value_type":    "string",
						"description":   "Required when Registration Mode is invitation_only",
						"default_value": "",
						"required":      false,
					},
					{
						"key":           "require_privileged_mfa",
						"label":         "Require Privileged MFA",
						"value_type":    "boolean",
						"description":   "Require MFA for admin and CRM operators before privileged actions",
						"default_value": false,
						"required":      false,
					},
				},
			},
			{
				"section":     "redis",
				"title":       "Redis",
				"description": "Redis connection settings",
				"fields": []map[string]interface{}{
					{
						"key":           "enabled",
						"label":         "Enabled",
						"value_type":    "boolean",
						"description":   "Enable or disable Redis",
						"default_value": false,
						"required":      false,
					},
					{
						"key":           "host",
						"label":         "Host",
						"value_type":    "string",
						"description":   "Redis server host",
						"default_value": "redis",
						"required":      false,
					},
					{
						"key":           "port",
						"label":         "Port",
						"value_type":    "integer",
						"description":   "Redis server port",
						"default_value": 6379,
						"required":      false,
					},
					{
						"key":           "password",
						"label":         "Password",
						"value_type":    "string",
						"description":   "Redis server password (optional)",
						"default_value": "",
						"required":      false,
					},
					{
						"key":           "db",
						"label":         "Database",
						"value_type":    "integer",
						"description":   "Redis database number",
						"default_value": 0,
						"required":      false,
					},
					{
						"key":           "ssl",
						"label":         "Use SSL",
						"value_type":    "boolean",
						"description":   "Enable TLS/SSL when connecting to Redis",
						"default_value": false,
						"required":      false,
					},
				},
			},
		},
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      schema,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// GetSettings retrieves all settings
func (h *SettingsHandler) GetSettings(c *gin.Context) {
	// Retrieve all bot and redis settings
	allSettings, err := h.service.GetAllBotSettings()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to retrieve settings: %v", err),
		})
		return
	}

	// If no settings exist, initialize defaults
	if len(allSettings) == 0 {
		// Create default settings
		defaultSettings := []struct {
			section      string
			key          string
			value        string
			valueType    string
			description  string
			defaultValue string
			isActive     bool
		}{
			{
				section:      "trading",
				key:          "max_position_size",
				value:        "1000",
				valueType:    "integer",
				description:  "Maximum position size per trade",
				defaultValue: "1000",
				isActive:     true,
			},
			{
				section:      "trading",
				key:          "stop_loss_percentage",
				value:        "5",
				valueType:    "float",
				description:  "Stop loss percentage for trades",
				defaultValue: "5",
				isActive:     true,
			},
			{
				section:      "trading",
				key:          "take_profit_percentage",
				value:        "10",
				valueType:    "float",
				description:  "Take profit percentage for trades",
				defaultValue: "10",
				isActive:     true,
			},
			{
				section:      "api",
				key:          "request_timeout",
				value:        "30",
				valueType:    "integer",
				description:  "API request timeout in seconds",
				defaultValue: "30",
				isActive:     true,
			},
			{
				section:      "api",
				key:          "retry_attempts",
				value:        "3",
				valueType:    "integer",
				description:  "Number of retry attempts for failed requests",
				defaultValue: "3",
				isActive:     true,
			},
			{
				section:      "platform",
				key:          "allow_public_registration",
				value:        "true",
				valueType:    "boolean",
				description:  "Allow new users to register without administrator approval",
				defaultValue: "true",
				isActive:     true,
			},
			{
				section:      "platform",
				key:          "registration_mode",
				value:        "open",
				valueType:    "string",
				description:  "Registration mode: open, disabled, or invitation_only",
				defaultValue: "open",
				isActive:     true,
			},
			{
				section:      "platform",
				key:          "registration_invitation_code",
				value:        "",
				valueType:    "string",
				description:  "Invitation code required when registration_mode is invitation_only",
				defaultValue: "",
				isActive:     true,
			},
			{
				section:      "platform",
				key:          "require_privileged_mfa",
				value:        "false",
				valueType:    "boolean",
				description:  "Require MFA enrollment before privileged admin and CRM actions",
				defaultValue: "false",
				isActive:     true,
			},
			{
				section:      "bot",
				key:          "enabled",
				value:        "false",
				valueType:    "boolean",
				description:  "Enable or disable the trading bot",
				defaultValue: "false",
				isActive:     true,
			},
			{
				section:      "bot",
				key:          "log_level",
				value:        "info",
				valueType:    "string",
				description:  "Logging level (debug, info, warn, error)",
				defaultValue: "info",
				isActive:     true,
			},
		}

		// Create all defaults
		for _, setting := range defaultSettings {
			if _, err := h.service.CreateBotSetting(
				setting.section,
				setting.key,
				setting.value,
				setting.valueType,
				setting.description,
				setting.defaultValue,
				setting.isActive,
			); err != nil {
				c.JSON(http.StatusInternalServerError, APIResponse{
					Success:   false,
					Timestamp: time.Now().UTC().Format(time.RFC3339),
					Error:     fmt.Sprintf("Failed to create default setting %s.%s: %v", setting.section, setting.key, err),
				})
				return
			}
		}

		// Fetch again after creation
		allSettings, _ = h.service.GetAllBotSettings()
	}

	// Convert to sections structure matching the schema
	settingsBySection := make(map[string][]map[string]interface{})

	for _, setting := range allSettings {
		dict := setting.ToDict()

		// Ensure all fields have non-null values
		if dict["section"] == nil || dict["section"] == "" {
			dict["section"] = "general"
		}
		if dict["key"] == nil {
			dict["key"] = ""
		}
		if dict["value"] == nil {
			dict["value"] = ""
		}
		if dict["value_type"] == nil {
			dict["value_type"] = "string"
		}
		if dict["description"] == nil {
			dict["description"] = ""
		}
		if dict["default_value"] == nil {
			dict["default_value"] = ""
		}
		if dict["is_active"] == nil {
			dict["is_active"] = true
		}

		// Get section name, ensuring it's a string
		section := "general"
		if sectionVal, ok := dict["section"].(string); ok && sectionVal != "" {
			section = sectionVal
		}

		settingsBySection[section] = append(settingsBySection[section], dict)
	}

	// Convert to section array format matching frontend structure
	var sections []map[string]interface{}
	for sectionName, settings := range settingsBySection {
		sections = append(sections, map[string]interface{}{
			"section":  sectionName,
			"settings": settings,
		})
	}

	redisSetting, err := h.resolveEffectiveRedisSetting()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to retrieve redis settings: %v", err),
		})
		return
	}

	if redisSetting != nil {
		redisSettings := []map[string]interface{}{
			{
				"id":            0,
				"section":       "redis",
				"key":           "enabled",
				"value":         redisSetting.Enabled,
				"value_type":    "boolean",
				"description":   "Enable or disable Redis",
				"default_value": false,
				"is_active":     true,
			},
			{
				"id":            0,
				"section":       "redis",
				"key":           "host",
				"value":         redisSetting.Host,
				"value_type":    "string",
				"description":   "Redis server host",
				"default_value": "redis",
				"is_active":     true,
			},
			{
				"id":            0,
				"section":       "redis",
				"key":           "port",
				"value":         redisSetting.Port,
				"value_type":    "integer",
				"description":   "Redis server port",
				"default_value": 6379,
				"is_active":     true,
			},
			{
				"id":            0,
				"section":       "redis",
				"key":           "db",
				"value":         redisSetting.Db,
				"value_type":    "integer",
				"description":   "Redis database number",
				"default_value": 0,
				"is_active":     true,
			},
			{
				"id":            0,
				"section":       "redis",
				"key":           "password",
				"value":         redisSetting.Password,
				"value_type":    "string",
				"description":   "Redis server password (optional)",
				"default_value": "",
				"is_active":     true,
			},
			{
				"id":            0,
				"section":       "redis",
				"key":           "ssl",
				"value":         redisSetting.SSL,
				"value_type":    "boolean",
				"description":   "Enable TLS/SSL when connecting to Redis",
				"default_value": false,
				"is_active":     true,
			},
		}

		sections = append(sections, map[string]interface{}{
			"section":  "redis",
			"settings": redisSettings,
		})
	}

	response := map[string]interface{}{
		"sections": sections,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      response,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// TestRedisConnection tests the connectivity to the configured Redis server.
func (h *SettingsHandler) TestRedisConnection(c *gin.Context) {
	redisSetting, err := h.resolveEffectiveRedisSetting()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Failed to load Redis settings: %v", err),
		})
		return
	}

	if redisSetting == nil {
		c.JSON(http.StatusOK, APIResponse{
			Success: true,
			Data: map[string]interface{}{
				"connected": false,
				"message":   "Redis is not configured",
			},
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	opts := &redis.Options{
		Addr:     fmt.Sprintf("%s:%d", redisSetting.Host, redisSetting.Port),
		Password: redisSetting.Password,
		DB:       redisSetting.Db,
	}
	if redisSetting.SSL {
		opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
	}

	client := redis.NewClient(opts)
	defer func() {
		if closeErr := client.Close(); closeErr != nil {
			log.Printf("Failed to close Redis test client: %v", closeErr)
		}
	}()

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	start := time.Now()
	_, pingErr := client.Ping(ctx).Result()
	latencyMs := time.Since(start).Milliseconds()

	if pingErr != nil {
		c.JSON(http.StatusOK, APIResponse{
			Success: true,
			Data: map[string]interface{}{
				"connected":  false,
				"message":    pingErr.Error(),
				"host":       redisSetting.Host,
				"port":       redisSetting.Port,
				"latency_ms": latencyMs,
			},
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"connected":  true,
			"message":    "Connection successful",
			"host":       redisSetting.Host,
			"port":       redisSetting.Port,
			"latency_ms": latencyMs,
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// UpdateSettings applies updates for both bot and redis settings.
// Input is expected as a map where keys use the format "section.key".
func (h *SettingsHandler) UpdateSettings(c *gin.Context) {
	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	redisUpdates := map[string]interface{}{}
	updated := 0

	for compoundKey, rawValue := range updates {
		parts := strings.SplitN(compoundKey, ".", 2)
		if len(parts) != 2 {
			continue
		}

		section := strings.TrimSpace(parts[0])
		key := strings.TrimSpace(parts[1])
		if section == "" || key == "" {
			continue
		}

		if strings.EqualFold(section, "redis") {
			redisUpdates[key] = rawValue
			continue
		}

		existing, err := h.service.GetBotSetting(section, key)
		if err != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Failed to load existing setting %s: %v", compoundKey, err),
			})
			return
		}

		normalizedValue := normalizeSettingValue(rawValue)
		if existing == nil {
			_, err = h.service.CreateBotSetting(
				section,
				key,
				normalizedValue,
				inferValueType(rawValue),
				compoundKey,
				normalizedValue,
				true,
			)
		} else {
			_, err = h.service.UpdateBotSetting(existing.ID, normalizedValue, existing.Description, existing.IsActive)
		}

		if err != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Failed to persist setting %s: %v", compoundKey, err),
			})
			return
		}

		updated++
	}

	if len(redisUpdates) > 0 {
		existingRedis, err := h.resolveEffectiveRedisSetting()
		if err != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Failed to load redis settings: %v", err),
			})
			return
		}

		enabled := false
		host := "redis"
		port := 6379
		db := 0
		password := ""
		ssl := false

		if existingRedis != nil {
			enabled = existingRedis.Enabled
			host = existingRedis.Host
			port = existingRedis.Port
			db = existingRedis.Db
			password = existingRedis.Password
			ssl = existingRedis.SSL
		}

		if value, ok := redisUpdates["enabled"]; ok {
			enabled = toBool(value, enabled)
		}
		if value, ok := redisUpdates["host"]; ok {
			host = normalizeSettingValue(value)
		}
		if value, ok := redisUpdates["port"]; ok {
			port = toInt(value, port)
		}
		if value, ok := redisUpdates["db"]; ok {
			db = toInt(value, db)
		}
		if value, ok := redisUpdates["password"]; ok {
			password = normalizeSettingValue(value)
		}
		if value, ok := redisUpdates["ssl"]; ok {
			ssl = toBool(value, ssl)
		}

		_, err = h.service.UpdateRedisSetting(enabled, host, port, db, password, ssl)
		if err != nil {
			c.JSON(http.StatusInternalServerError, APIResponse{
				Success:   false,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
				Error:     fmt.Sprintf("Failed to persist redis settings: %v", err),
			})
			return
		}

		updated += len(redisUpdates)
	}

	c.JSON(http.StatusOK, APIResponse{
		Success: true,
		Data: map[string]interface{}{
			"updated": updated,
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
