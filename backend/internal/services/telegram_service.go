package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const (
	telegramChatIDGlobalSettingKey     = "telegram_chat_id_global"
	telegramChatIDUserSettingKeyPrefix = "telegram_chat_id_user_"

	legacyTelegramChatIDSettingKey           = "chat_id"
	legacyTelegramChatIDUserSettingKeyPrefix = "chat_id_user_"
)

type TelegramConfigSource string

const (
	TelegramConfigSourceUser   TelegramConfigSource = "user"
	TelegramConfigSourceGlobal TelegramConfigSource = "global"
	TelegramConfigSourceNone   TelegramConfigSource = "none"
)

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

type ResolvedTelegramConfig struct {
	Config *TelegramSharedConfig
	Source TelegramConfigSource
	UserID int
}

// telegramHTTPClient bounds Telegram API calls; http.Post's default client
// has no timeout and can pin handler goroutines indefinitely.
var telegramHTTPClient = &http.Client{Timeout: 10 * time.Second}

func (s *TelegramService) httpClient() *http.Client { return telegramHTTPClient }

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
	return s.GetGlobalStatus()
}

func (s *TelegramService) GetStatusForUser(userID int) (*TelegramStatus, error) {
	return s.GetUserStatusForUser(userID)
}

func (s *TelegramService) GetUserStatusForUser(userID int) (*TelegramStatus, error) {
	if userID < 0 {
		return nil, fmt.Errorf("user id is required")
	}

	if userID == SharedCredentialUserID {
		return s.GetGlobalStatus()
	}

	info, err := s.credentials.Get(userID, ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, fmt.Errorf("failed to load Telegram credential info: %w", err)
	}

	token, tokenPresent, err := s.credentials.ResolveKey(userID, ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve Telegram bot token: %w", err)
	}

	chatID, err := s.getSettingValue(userTelegramChatIDSettingKeys(userID), "")
	if err != nil {
		return nil, fmt.Errorf("failed to load Telegram chat id: %w", err)
	}

	configured := strings.TrimSpace(token) != "" && strings.TrimSpace(chatID) != ""
	message := "Telegram notifications are not configured yet for this user."
	if configured {
		message = "Telegram delivery is configured for this user and will be injected into managed runtime launches."
	} else if tokenPresent {
		message = "Telegram bot token is saved for this user, but chat ID is still required."
	} else if strings.TrimSpace(chatID) != "" {
		message = "Telegram chat ID is saved for this user, but bot token is still required."
	}

	return &TelegramStatus{
		Provider:           "telegram",
		Configured:         configured,
		SharedTokenPresent: tokenPresent,
		SharedTokenMasked:  valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.MaskedValue }),
		SharedTokenLabel:   valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.Label }),
		ChatID:             chatID,
		ChatIDMasked:       maskSecretValue(chatID),
		DeliveryMode:       "user",
		Message:            message,
	}, nil
}

func (s *TelegramService) GetGlobalStatus() (*TelegramStatus, error) {
	info, err := s.credentials.GetShared(ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, fmt.Errorf("failed to load Telegram credential info: %w", err)
	}

	token, tokenPresent, err := s.credentials.ResolveSharedKey(ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve Telegram bot token: %w", err)
	}

	chatID, err := s.getSettingValue(globalTelegramChatIDSettingKeys(), "")
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
		DeliveryMode:       string(TelegramConfigSourceGlobal),
		Message:            message,
	}, nil
}

func (s *TelegramService) SaveSharedConfig(payload TelegramConfigPayload) (*TelegramStatus, error) {
	return s.SaveGlobalConfig(payload)
}

func (s *TelegramService) SaveConfigForUser(userID int, payload TelegramConfigPayload) (*TelegramStatus, error) {
	if userID == SharedCredentialUserID {
		return s.SaveGlobalConfig(payload)
	}
	return s.SaveUserConfigForUser(userID, payload)
}

func (s *TelegramService) SaveUserConfigForUser(userID int, payload TelegramConfigPayload) (*TelegramStatus, error) {
	if userID < 0 {
		return nil, fmt.Errorf("user id is required")
	}
	if userID == SharedCredentialUserID {
		return nil, fmt.Errorf("user id is required")
	}

	return s.saveConfigForScope(userID, payload, TelegramConfigSourceUser)
}

func (s *TelegramService) SaveGlobalConfig(payload TelegramConfigPayload) (*TelegramStatus, error) {
	return s.saveConfigForScope(SharedCredentialUserID, payload, TelegramConfigSourceGlobal)
}

func (s *TelegramService) saveConfigForScope(userID int, payload TelegramConfigPayload, source TelegramConfigSource) (*TelegramStatus, error) {
	status, err := s.GetStatusForUser(userID)
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
		if _, err := s.credentials.Save(userID, ExternalAPIProviderTelegramBot, token, payload.Label); err != nil {
			return nil, err
		}
	}

	chatDescription := telegramChatIDDescription(source)

	if err := s.upsertSetting(userTelegramChatIDSettingKey(userID), chatID, chatDescription); err != nil {
		return nil, err
	}

	return s.GetStatusForUser(userID)
}

func (s *TelegramService) DeleteSharedConfig() error {
	return s.DeleteGlobalConfig()
}

func (s *TelegramService) DeleteConfigForUser(userID int) error {
	if userID == SharedCredentialUserID {
		return s.DeleteGlobalConfig()
	}
	return s.DeleteUserConfigForUser(userID)
}

func (s *TelegramService) DeleteUserConfigForUser(userID int) error {
	if userID < 0 {
		return fmt.Errorf("user id is required")
	}
	if userID == SharedCredentialUserID {
		return fmt.Errorf("user id is required")
	}

	return s.deleteConfigForScope(userID)
}

func (s *TelegramService) DeleteGlobalConfig() error {
	return s.deleteConfigForScope(SharedCredentialUserID)
}

func (s *TelegramService) deleteConfigForScope(userID int) error {
	if err := s.credentials.Delete(userID, ExternalAPIProviderTelegramBot); err != nil && !isCredentialNotFoundError(err) {
		return err
	}

	for _, key := range userTelegramChatIDSettingKeys(userID) {
		existing, err := s.settings.GetBotSettingBySectionAndKey("telegram", key)
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
			if err := s.settings.UpdateBotSetting(existing); err != nil {
				return err
			}
		}
	}
	return nil
}

func (s *TelegramService) ResolveSharedConfig() (*TelegramSharedConfig, bool, error) {
	return s.ResolveGlobalConfig()
}

func (s *TelegramService) ResolveConfigForUser(userID int) (*TelegramSharedConfig, bool, error) {
	if userID == SharedCredentialUserID {
		return s.ResolveGlobalConfig()
	}
	return s.ResolveUserConfigForUser(userID)
}

func (s *TelegramService) ResolveUserConfigForUser(userID int) (*TelegramSharedConfig, bool, error) {
	if userID < 0 {
		return nil, false, fmt.Errorf("user id is required")
	}
	if userID == SharedCredentialUserID {
		return nil, false, fmt.Errorf("user id is required")
	}

	return s.resolveConfigForScope(userID)
}

func (s *TelegramService) ResolveGlobalConfig() (*TelegramSharedConfig, bool, error) {
	return s.resolveConfigForScope(SharedCredentialUserID)
}

func (s *TelegramService) ResolveEffectiveConfig(userID int) (*ResolvedTelegramConfig, error) {
	if userID <= 0 {
		return &ResolvedTelegramConfig{Source: TelegramConfigSourceNone, UserID: userID}, fmt.Errorf("user id is required")
	}

	if config, configured, err := s.ResolveUserConfigForUser(userID); err != nil {
		return nil, err
	} else if configured {
		return &ResolvedTelegramConfig{
			Config: config,
			Source: TelegramConfigSourceUser,
			UserID: userID,
		}, nil
	}

	if config, configured, err := s.ResolveGlobalConfig(); err != nil {
		return nil, err
	} else if configured {
		return &ResolvedTelegramConfig{
			Config: config,
			Source: TelegramConfigSourceGlobal,
			UserID: SharedCredentialUserID,
		}, nil
	}

	return &ResolvedTelegramConfig{
		Config: nil,
		Source: TelegramConfigSourceNone,
		UserID: userID,
	}, nil
}

func (s *TelegramService) resolveConfigForScope(userID int) (*TelegramSharedConfig, bool, error) {
	token, tokenPresent, err := s.credentials.ResolveKey(userID, ExternalAPIProviderTelegramBot)
	if err != nil {
		return nil, false, err
	}
	chatID, err := s.getSettingValue(userTelegramChatIDSettingKeys(userID), "")
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

func userTelegramChatIDSettingKey(userID int) string {
	if userID <= 0 {
		return telegramChatIDGlobalSettingKey
	}
	return fmt.Sprintf("%s%d", telegramChatIDUserSettingKeyPrefix, userID)
}

func userTelegramChatIDSettingKeys(userID int) []string {
	if userID <= 0 {
		return globalTelegramChatIDSettingKeys()
	}
	return []string{
		userTelegramChatIDSettingKey(userID),
		fmt.Sprintf("%s%d", legacyTelegramChatIDUserSettingKeyPrefix, userID),
	}
}

func globalTelegramChatIDSettingKeys() []string {
	return []string{telegramChatIDGlobalSettingKey, legacyTelegramChatIDSettingKey}
}

func telegramChatIDDescription(source TelegramConfigSource) string {
	if source == TelegramConfigSourceGlobal {
		return "Telegram chat id for global platform notifications"
	}
	return "Telegram chat id for user notifications"
}

func isCredentialNotFoundError(err error) bool {
	if err == nil {
		return false
	}
	return strings.Contains(strings.ToLower(strings.TrimSpace(err.Error())), "credential not found")
}

func (s *TelegramService) getSettingValue(keys []string, fallback string) (string, error) {
	for _, key := range keys {
		setting, err := s.settings.GetBotSettingBySectionAndKey("telegram", key)
		if err != nil {
			if isMissingTableError(err) {
				return fallback, nil
			}
			return "", err
		}
		if setting != nil && setting.IsActive {
			return strings.TrimSpace(setting.Value), nil
		}
	}
	return fallback, nil
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

type PreflightValidationResult struct {
	Valid            bool   `json:"valid"`
	ChatName         string `json:"chat_name,omitempty"`
	ChatID           string `json:"chat_id,omitempty"`
	Error            string `json:"error,omitempty"`
	ValidationReason string `json:"validation_reason,omitempty"`
}

func (s *TelegramService) PreflightValidateTelegramDelivery(token, chatID string) (*PreflightValidationResult, error) {
	token = strings.TrimSpace(token)
	chatID = strings.TrimSpace(chatID)

	if token == "" || chatID == "" {
		return &PreflightValidationResult{
			Valid: false,
			Error: "token and chat_id are required",
		}, nil
	}

	// Step 1: Validate token by calling getMe
	getMeURL := fmt.Sprintf("https://api.telegram.org/bot%s/getMe", token)
	resp, err := s.httpClient().Post(getMeURL, "application/json", nil)
	if err != nil {
		return &PreflightValidationResult{
			Valid:            false,
			Error:            fmt.Sprintf("failed to validate token: %v", err),
			ValidationReason: "network error",
		}, nil
	}
	defer func() { _ = resp.Body.Close() }()

	var getMeResp map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&getMeResp); err != nil {
		return &PreflightValidationResult{
			Valid:            false,
			Error:            fmt.Sprintf("invalid token response: %v", err),
			ValidationReason: "token validation failed",
		}, nil
	}

	ok, _ := getMeResp["ok"].(bool)
	if !ok {
		desc, _ := getMeResp["description"].(string)
		return &PreflightValidationResult{
			Valid:            false,
			Error:            fmt.Sprintf("invalid token: %s", desc),
			ValidationReason: "invalid bot token",
		}, nil
	}

	// Step 2: Validate chat by calling getChat
	getChatURL := fmt.Sprintf("https://api.telegram.org/bot%s/getChat", token)
	getChatPayload := map[string]string{"chat_id": chatID}
	payloadBytes, _ := json.Marshal(getChatPayload)
	chatResp, err := s.httpClient().Post(getChatURL, "application/json", bytes.NewReader(payloadBytes))
	if err != nil {
		return &PreflightValidationResult{
			Valid:            false,
			Error:            fmt.Sprintf("failed to validate chat: %v", err),
			ValidationReason: "network error",
		}, nil
	}
	defer func() { _ = chatResp.Body.Close() }()

	var getChatRespBody map[string]interface{}
	if err := json.NewDecoder(chatResp.Body).Decode(&getChatRespBody); err != nil {
		return &PreflightValidationResult{
			Valid:            false,
			Error:            fmt.Sprintf("invalid chat response: %v", err),
			ValidationReason: "chat validation failed",
		}, nil
	}

	ok, _ = getChatRespBody["ok"].(bool)
	if !ok {
		desc, _ := getChatRespBody["description"].(string)
		if strings.Contains(strings.ToLower(desc), "bot account") || strings.Contains(strings.ToLower(desc), "bots can't") {
			return &PreflightValidationResult{
				Valid:            false,
				Error:            "Chat appears to be a bot account. Use a user/group/channel ID instead.",
				ValidationReason: "invalid chat target (bot account)",
			}, nil
		}
		return &PreflightValidationResult{
			Valid:            false,
			Error:            fmt.Sprintf("invalid chat: %s", desc),
			ValidationReason: "invalid chat id or no access",
		}, nil
	}

	// Extract chat name/title for confirmation
	chatData, _ := getChatRespBody["result"].(map[string]interface{})
	chatName := ""
	if chatData != nil {
		if title, ok := chatData["title"].(string); ok {
			chatName = title
		} else if username, ok := chatData["username"].(string); ok {
			chatName = "@" + username
		}
	}

	return &PreflightValidationResult{
		Valid:            true,
		ChatID:           chatID,
		ChatName:         chatName,
		ValidationReason: "token and chat validated successfully",
	}, nil
}
