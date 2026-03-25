package services

import "github.com/dydx-trading-bot/backend-go/internal/models"

// SettingsServiceIface defines the operations required by the settings handler.
// This allows handlers to be tested against lightweight in-memory mocks.
type SettingsServiceIface interface {
	CreateBotSetting(section, key, value, valueType, description, defaultValue string, isActive bool) (*models.BotSetting, error)
	GetBotSetting(section, key string) (*models.BotSetting, error)
	GetBotSettingsBySection(section string) ([]models.BotSetting, error)
	GetAllBotSettings() ([]models.BotSetting, error)
	UpdateBotSetting(id int, value, description string, isActive bool) (*models.BotSetting, error)
	DeleteBotSetting(id int) error
	GetRedisSetting() (*models.RedisSetting, error)
	UpdateRedisSetting(enabled bool, host string, port, db int, password string, ssl bool) (*models.RedisSetting, error)
	ClearCache()
	GetCacheStats() map[string]interface{}
}
