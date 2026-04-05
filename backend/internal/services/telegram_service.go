package services

import (
	"fmt"
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const telegramChatIDSettingKey = "chat_id"

type TelegramStatus struct {
	Provider           string `json:"provider"`
	Configured         bool   `json:"configured"`
	SharedTokenPresent bool   `json:"shared_token_present"`
	SharedTokenMasked  string `json:"shared_token_masked"`
	SharedTokenLabel   string `json:"shared_token_label"`
	ChatID             string `json:"chat_id"`
	ChatIDMasked       string `json:"chat_id_masked"`
	DeliveryMode       string `json:"delivery_mode"`
	Message            string `json:"message"`
}

type TelegramConfigPayload struct {
	BotToken string `json:"bot_token"`
	ChatID   string `json:"chat_id"`
	Label    string `json:"label,omitempty"`
}

type TelegramSharedConfig struct {
	BotToken string
	ChatID   string
}

type TelegramService struct {
	credentials *ExternalAPICredentialService
	settings    *repository.SettingsRepository
}

func NewTelegramService(
	credentials *ExternalAPICredentialService,
	settings *repository.SettingsRepository,
) *TelegramService {
	return &TelegramService{
		credentials: credentials,
		settings:    settings,
	}
}

func (s *TelegramService) GetStatus() (*TelegramStatus, error) {
	info, err := s.credentials.GetShared(ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, fmt.Errorf("failed to load Telegram credential info: %w", err)
	}

	token, tokenPresent, err := s.credentials.ResolveSharedKey(ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve Telegram bot token: %w", err)
	}

	chatID, err := s.getSettingValue(telegramChatIDSettingKey, "")
	if err != nil {
		return nil, fmt.Errorf("failed to load Telegram chat id: %w", err)
	}

	configured := strings.TrimSpace(token) != "" && strings.TrimSpace(chatID) != ""
	message := "Telegram notifications are not configured yet."
	if configured {
		message = "Shared Telegram delivery is configured for runtime-managed bot notifications."
	} else if tokenPresent {
		message = "Telegram bot token is saved, but chat ID is still required."
	} else if strings.TrimSpace(chatID) != "" {
		message = "Telegram chat ID is saved, but bot token is still required."
	}

	return &TelegramStatus{
		Provider:           "telegram",
		Configured:         configured,
		SharedTokenPresent: tokenPresent,
		SharedTokenMasked:  valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.MaskedValue }),
		SharedTokenLabel:   valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.Label }),
		ChatID:             chatID,
		ChatIDMasked:       maskSecretValue(chatID),
		DeliveryMode:       "shared",
		Message:            message,
	}, nil
}

func (s *TelegramService) SaveSharedConfig(payload TelegramConfigPayload) (*TelegramStatus, error) {
	status, err := s.GetStatus()
	if err != nil {
		return nil, err
	}

	chatID := strings.TrimSpace(payload.ChatID)
	if chatID == "" {
		return nil, fmt.Errorf("chat id is required")
	}

	token := strings.TrimSpace(payload.BotToken)
	if token == "" && !status.SharedTokenPresent {
		return nil, fmt.Errorf("bot token is required")
	}
	if token != "" {
		if _, err := s.credentials.SaveShared(ExternalAPIProviderTelegramBot, token, payload.Label); err != nil {
			return nil, err
		}
	}

	if err := s.upsertSetting(telegramChatIDSettingKey, chatID, "Telegram chat id for shared platform notifications"); err != nil {
		return nil, err
	}

	return s.GetStatus()
}

func (s *TelegramService) DeleteSharedConfig() error {
	if err := s.credentials.DeleteShared(ExternalAPIProviderTelegramBot); err != nil {
		return err
	}
	existing, err := s.settings.GetBotSettingBySectionAndKey("telegram", telegramChatIDSettingKey)
	if err != nil {
		if isMissingTableError(err) {
			return nil
		}
		return fmt.Errorf("failed to load Telegram chat id: %w", err)
	}
	if existing != nil {
		existing.Value = ""
		existing.IsActive = false
		existing.Version++
		return s.settings.UpdateBotSetting(existing)
	}
	return nil
}

func (s *TelegramService) ResolveSharedConfig() (*TelegramSharedConfig, bool, error) {
	token, tokenPresent, err := s.credentials.ResolveSharedKey(ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, false, err
	}
	chatID, err := s.getSettingValue(telegramChatIDSettingKey, "")
	if err != nil {
		return nil, false, err
	}
	if !tokenPresent || strings.TrimSpace(token) == "" || strings.TrimSpace(chatID) == "" {
		return &TelegramSharedConfig{
			BotToken: "",
			ChatID:   "",
		}, false, nil
	}
	return &TelegramSharedConfig{
		BotToken: strings.TrimSpace(token),
		ChatID:   strings.TrimSpace(chatID),
	}, true, nil
}

func (s *TelegramService) getSettingValue(key string, fallback string) (string, error) {
	setting, err := s.settings.GetBotSettingBySectionAndKey("telegram", key)
	if err != nil {
		if isMissingTableError(err) {
			return fallback, nil
		}
		return "", err
	}
	if setting == nil || !setting.IsActive {
		return fallback, nil
	}
	return strings.TrimSpace(setting.Value), nil
}

func (s *TelegramService) upsertSetting(key string, value string, description string) error {
	existing, err := s.settings.GetBotSettingBySectionAndKey("telegram", key)
	if err != nil && !isMissingTableError(err) {
		return fmt.Errorf("failed to load telegram setting %s: %w", key, err)
	}
	if existing != nil {
		existing.Value = value
		existing.Description = description
		existing.IsActive = true
		existing.Version++
		return s.settings.UpdateBotSetting(existing)
	}

	return s.settings.CreateBotSetting(&models.BotSetting{
		Section:      "telegram",
		Key:          key,
		Value:        value,
		ValueType:    "string",
		Description:  description,
		DefaultValue: "",
		IsActive:     true,
		Version:      1,
	})
}
