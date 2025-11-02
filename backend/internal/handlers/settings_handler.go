package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// SettingsHandler handles settings API endpoints
type SettingsHandler struct {
	service *services.SettingsService
}

// NewSettingsHandler creates a new settings handler
func NewSettingsHandler(service *services.SettingsService) *SettingsHandler {
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
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to create setting: %v", err),
		})
		return
	}

	c.JSON(http.StatusCreated, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetBotSetting retrieves a bot setting
func (h *SettingsHandler) GetBotSetting(c *gin.Context) {
	section := c.Query("section")
	key := c.Query("key")

	if section == "" || key == "" {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "section and key are required",
		})
		return
	}

	setting, err := h.service.GetBotSetting(section, key)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get setting: %v", err),
		})
		return
	}

	if setting == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Setting not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetBotSettingsBySection retrieves all settings in a section
func (h *SettingsHandler) GetBotSettingsBySection(c *gin.Context) {
	section := c.Query("section")

	if section == "" {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "section is required",
		})
		return
	}

	settings, err := h.service.GetBotSettingsBySection(section)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// ListAllBotSettings retrieves all bot settings
func (h *SettingsHandler) ListAllBotSettings(c *gin.Context) {
	settings, err := h.service.GetAllBotSettings()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// UpdateBotSetting updates a bot setting
func (h *SettingsHandler) UpdateBotSetting(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	setting, err := h.service.UpdateBotSetting(id, req.Value, req.Description, req.IsActive)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to update setting: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// DeleteBotSetting deletes a bot setting
func (h *SettingsHandler) DeleteBotSetting(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Invalid setting ID",
		})
		return
	}

	if err := h.service.DeleteBotSetting(id); err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to delete setting: %v", err),
		})
		return
	}

	c.Status(http.StatusNoContent)
}

// ============ RedisSetting Endpoints ============

// GetRedisSetting retrieves redis settings
func (h *SettingsHandler) GetRedisSetting(c *gin.Context) {
	setting, err := h.service.GetRedisSetting()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to get redis setting: %v", err),
		})
		return
	}

	if setting == nil {
		c.JSON(http.StatusNotFound, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     "Redis setting not found",
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Invalid request: %v", err),
		})
		return
	}

	setting, err := h.service.UpdateRedisSetting(req.Enabled, req.Host, req.Port, req.Db, req.Password, req.SSL)
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
			Error:     fmt.Sprintf("Failed to update redis setting: %v", err),
		})
		return
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      setting.ToDict(),
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetCacheStats returns cache statistics
func (h *SettingsHandler) GetCacheStats(c *gin.Context) {
	stats := h.service.GetCacheStats()

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      stats,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
				"section":     "redis",
				"title":       "Redis",
				"description": "Redis connection settings",
				"fields": []map[string]interface{}{
					{
						"key":           "host",
						"label":         "Host",
						"value_type":    "string",
						"description":   "Redis server host",
						"default_value": "localhost",
						"required":      false,
					},
					{
						"key":           "port",
						"label":         "Port",
						"value_type":    "integer",
						"description":   "Redis server port",
						"default_value": "6379",
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
						"default_value": "0",
						"required":      false,
					},
				},
			},
		},
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      schema,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}

// GetSettings retrieves all settings
func (h *SettingsHandler) GetSettings(c *gin.Context) {
	// Retrieve all bot and redis settings
	allSettings, err := h.service.GetAllBotSettings()
	if err != nil {
		c.JSON(http.StatusInternalServerError, APIResponse{
			Success:   false,
			Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
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
			h.service.CreateBotSetting(
				setting.section,
				setting.key,
				setting.value,
				setting.valueType,
				setting.description,
				setting.defaultValue,
				setting.isActive,
			)
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

	response := map[string]interface{}{
		"sections": sections,
	}

	c.JSON(http.StatusOK, APIResponse{
		Success:   true,
		Data:      response,
		Timestamp: time.Now().UTC().Format(time.RFC3339) + "Z",
	})
}
