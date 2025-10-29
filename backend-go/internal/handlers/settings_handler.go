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
