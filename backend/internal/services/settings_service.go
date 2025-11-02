package services

import (
	"fmt"
	"log"
	"sync"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// SettingsService manages bot and redis settings
type SettingsService struct {
	mu    sync.RWMutex
	repo  *repository.SettingsRepository
	cache map[string]*models.BotSetting
}

// NewSettingsService creates a new settings service
func NewSettingsService(repo *repository.SettingsRepository) *SettingsService {
	return &SettingsService{
		repo:  repo,
		cache: make(map[string]*models.BotSetting),
	}
}

// ============ BotSetting Operations ============

// CreateBotSetting creates a new bot setting
func (s *SettingsService) CreateBotSetting(section, key, value, valueType, description, defaultValue string, isActive bool) (*models.BotSetting, error) {
	if section == "" || key == "" {
		return nil, fmt.Errorf("section and key are required")
	}

	setting := &models.BotSetting{
		Section:      section,
		Key:          key,
		Value:        value,
		ValueType:    valueType,
		Description:  description,
		DefaultValue: defaultValue,
		IsActive:     isActive,
		Version:      1,
	}

	if err := s.repo.CreateBotSetting(setting); err != nil {
		return nil, fmt.Errorf("failed to create bot setting: %w", err)
	}

	// Update cache
	s.mu.Lock()
	cacheKey := fmt.Sprintf("%s:%s", section, key)
	s.cache[cacheKey] = setting
	s.mu.Unlock()

	log.Printf("✅ Created bot setting: %s:%s", section, key)
	return setting, nil
}

// GetBotSetting retrieves a bot setting by section and key
func (s *SettingsService) GetBotSetting(section, key string) (*models.BotSetting, error) {
	if section == "" || key == "" {
		return nil, fmt.Errorf("section and key are required")
	}

	// Check cache first
	s.mu.RLock()
	cacheKey := fmt.Sprintf("%s:%s", section, key)
	if cached, ok := s.cache[cacheKey]; ok {
		s.mu.RUnlock()
		return cached, nil
	}
	s.mu.RUnlock()

	// Query database
	setting, err := s.repo.GetBotSettingBySectionAndKey(section, key)
	if err != nil {
		return nil, fmt.Errorf("failed to get bot setting: %w", err)
	}

	// Update cache
	if setting != nil {
		s.mu.Lock()
		s.cache[cacheKey] = setting
		s.mu.Unlock()
	}

	return setting, nil
}

// GetBotSettingsBySection retrieves all settings in a section
func (s *SettingsService) GetBotSettingsBySection(section string) ([]models.BotSetting, error) {
	if section == "" {
		return nil, fmt.Errorf("section is required")
	}

	settings, err := s.repo.GetBotSettingsBySection(section)
	if err != nil {
		return nil, fmt.Errorf("failed to get bot settings by section: %w", err)
	}

	return settings, nil
}

// UpdateBotSetting updates an existing bot setting
func (s *SettingsService) UpdateBotSetting(id int, value, description string, isActive bool) (*models.BotSetting, error) {
	if id <= 0 {
		return nil, fmt.Errorf("invalid setting id")
	}

	setting, err := s.repo.GetBotSettingByID(id)
	if err != nil {
		return nil, fmt.Errorf("failed to get setting: %w", err)
	}

	if setting == nil {
		return nil, fmt.Errorf("setting not found")
	}

	// Update fields
	setting.Value = value
	setting.Description = description
	setting.IsActive = isActive
	setting.Version++

	if err := s.repo.UpdateBotSetting(setting); err != nil {
		return nil, fmt.Errorf("failed to update bot setting: %w", err)
	}

	// Clear cache for this setting
	s.mu.Lock()
	cacheKey := fmt.Sprintf("%s:%s", setting.Section, setting.Key)
	delete(s.cache, cacheKey)
	s.mu.Unlock()

	log.Printf("✅ Updated bot setting: %s:%s", setting.Section, setting.Key)
	return setting, nil
}

// DeleteBotSetting deletes a bot setting
func (s *SettingsService) DeleteBotSetting(id int) error {
	if id <= 0 {
		return fmt.Errorf("invalid setting id")
	}

	setting, err := s.repo.GetBotSettingByID(id)
	if err != nil {
		return fmt.Errorf("failed to get setting: %w", err)
	}

	if setting == nil {
		return fmt.Errorf("setting not found")
	}

	if err := s.repo.DeleteBotSetting(id); err != nil {
		return fmt.Errorf("failed to delete bot setting: %w", err)
	}

	// Clear cache
	s.mu.Lock()
	cacheKey := fmt.Sprintf("%s:%s", setting.Section, setting.Key)
	delete(s.cache, cacheKey)
	s.mu.Unlock()

	log.Printf("✅ Deleted bot setting: %s:%s", setting.Section, setting.Key)
	return nil
}

// GetAllBotSettings retrieves all bot settings
func (s *SettingsService) GetAllBotSettings() ([]models.BotSetting, error) {
	settings, err := s.repo.GetAllBotSettings()
	if err != nil {
		return nil, fmt.Errorf("failed to get all bot settings: %w", err)
	}

	return settings, nil
}

// ============ RedisSetting Operations ============

// GetRedisSetting retrieves redis settings (usually only one)
func (s *SettingsService) GetRedisSetting() (*models.RedisSetting, error) {
	setting, err := s.repo.GetRedisSetting()
	if err != nil {
		return nil, fmt.Errorf("failed to get redis setting: %w", err)
	}

	return setting, nil
}

// CreateRedisSetting creates or updates redis settings
func (s *SettingsService) CreateRedisSetting(enabled bool, host string, port int, db int, password string, ssl bool) (*models.RedisSetting, error) {
	if host == "" {
		return nil, fmt.Errorf("host is required")
	}

	if port <= 0 || port > 65535 {
		return nil, fmt.Errorf("invalid port: %d", port)
	}

	// Check if setting exists
	existing, err := s.repo.GetRedisSetting()
	if err != nil {
		return nil, fmt.Errorf("failed to check existing redis setting: %w", err)
	}

	var setting *models.RedisSetting

	if existing != nil {
		// Update existing
		existing.Enabled = enabled
		existing.Host = host
		existing.Port = port
		existing.Db = db
		existing.Password = password
		existing.SSL = ssl

		if err := s.repo.UpdateRedisSetting(existing); err != nil {
			return nil, fmt.Errorf("failed to update redis setting: %w", err)
		}

		setting = existing
		log.Printf("✅ Updated redis setting: %s:%d", host, port)
	} else {
		// Create new
		setting = &models.RedisSetting{
			Enabled:  enabled,
			Host:     host,
			Port:     port,
			Db:       db,
			Password: password,
			SSL:      ssl,
		}

		if err := s.repo.CreateRedisSetting(setting); err != nil {
			return nil, fmt.Errorf("failed to create redis setting: %w", err)
		}

		log.Printf("✅ Created redis setting: %s:%d", host, port)
	}

	return setting, nil
}

// UpdateRedisSetting updates redis settings
func (s *SettingsService) UpdateRedisSetting(enabled bool, host string, port int, db int, password string, ssl bool) (*models.RedisSetting, error) {
	if host == "" {
		return nil, fmt.Errorf("host is required")
	}

	if port <= 0 || port > 65535 {
		return nil, fmt.Errorf("invalid port: %d", port)
	}

	setting, err := s.repo.GetRedisSetting()
	if err != nil {
		return nil, fmt.Errorf("failed to get redis setting: %w", err)
	}

	if setting == nil {
		return s.CreateRedisSetting(enabled, host, port, db, password, ssl)
	}

	// Update fields
	setting.Enabled = enabled
	setting.Host = host
	setting.Port = port
	setting.Db = db
	setting.Password = password
	setting.SSL = ssl

	if err := s.repo.UpdateRedisSetting(setting); err != nil {
		return nil, fmt.Errorf("failed to update redis setting: %w", err)
	}

	log.Printf("✅ Updated redis setting: %s:%d", host, port)
	return setting, nil
}

// ClearCache clears the bot settings cache
func (s *SettingsService) ClearCache() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.cache = make(map[string]*models.BotSetting)
	log.Printf("✅ Cleared settings cache")
}

// GetCacheStats returns cache statistics
func (s *SettingsService) GetCacheStats() map[string]interface{} {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return map[string]interface{}{
		"cached_settings": len(s.cache),
	}
}
