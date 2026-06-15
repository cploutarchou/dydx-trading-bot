package services

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const (
	defaultMailgunRegion       = "us"
	defaultMailgunUSBaseURL    = "https://api.mailgun.net"
	defaultMailgunEUBaseURL    = "https://api.eu.mailgun.net"
	mailgunDomainSettingKey    = "domain"
	mailgunFromEmailSettingKey = "from_email"
	mailgunFromNameSettingKey  = "from_name"
	mailgunRegionSettingKey    = "region"
)

type MailgunStatus struct {
	Provider                   string `json:"provider"`
	Configured                 bool   `json:"configured"`
	SharedKeyPresent           bool   `json:"shared_key_present"`
	SharedKeyMasked            string `json:"shared_key_masked"`
	SharedKeyLabel             string `json:"shared_key_label"`
	Domain                     string `json:"domain"`
	FromEmail                  string `json:"from_email"`
	FromName                   string `json:"from_name"`
	Region                     string `json:"region"`
	BaseURL                    string `json:"base_url"`
	PendingPasswordChangeCount int    `json:"pending_password_change_count"`
}

type MailgunConfigPayload struct {
	APIKey    string `json:"api_key"`
	Label     string `json:"label,omitempty"`
	Domain    string `json:"domain"`
	FromEmail string `json:"from_email"`
	FromName  string `json:"from_name"`
	Region    string `json:"region"`
}

type MailgunSendResult struct {
	Delivered bool   `json:"delivered"`
	Message   string `json:"message"`
	MessageID string `json:"message_id,omitempty"`
}

type MailgunService struct {
	credentials *ExternalAPICredentialService
	settings    *repository.SettingsRepository
	users       *repository.UserRepository
	httpClient  *http.Client
}

func NewMailgunService(
	credentials *ExternalAPICredentialService,
	settings *repository.SettingsRepository,
	users *repository.UserRepository,
) *MailgunService {
	return &MailgunService{
		credentials: credentials,
		settings:    settings,
		users:       users,
		httpClient:  &http.Client{Timeout: 15 * time.Second},
	}
}

func (s *MailgunService) GetStatus() (*MailgunStatus, error) {
	info, err := s.credentials.GetShared(ExternalAPIProviderMailgun)
	if err != nil {
		return nil, fmt.Errorf("failed to load Mailgun credential info: %w", err)
	}
	key, keyPresent, err := s.credentials.ResolveSharedKey(ExternalAPIProviderMailgun)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve Mailgun key: %w", err)
	}

	domain, _ := s.getSettingValue(mailgunDomainSettingKey, "")
	fromEmail, _ := s.getSettingValue(mailgunFromEmailSettingKey, "")
	fromName, _ := s.getSettingValue(mailgunFromNameSettingKey, "")
	region, _ := s.getSettingValue(mailgunRegionSettingKey, defaultMailgunRegion)

	users, err := s.users.List(1000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to count password rotation users: %w", err)
	}

	pending := 0
	for _, user := range users {
		if user.PasswordChangeRequired && user.IsActive {
			pending++
		}
	}

	configured := strings.TrimSpace(key) != "" && strings.TrimSpace(domain) != "" && strings.TrimSpace(fromEmail) != ""

	return &MailgunStatus{
		Provider:                   "mailgun",
		Configured:                 configured,
		SharedKeyPresent:           keyPresent,
		SharedKeyMasked:            valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.MaskedValue }),
		SharedKeyLabel:             valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.Label }),
		Domain:                     domain,
		FromEmail:                  fromEmail,
		FromName:                   fromName,
		Region:                     normalizeMailgunRegion(region),
		BaseURL:                    baseURLForMailgunRegion(region),
		PendingPasswordChangeCount: pending,
	}, nil
}

func (s *MailgunService) SaveSharedConfig(payload MailgunConfigPayload) (*MailgunStatus, error) {
	if strings.TrimSpace(payload.APIKey) == "" {
		return nil, fmt.Errorf("api key is required")
	}
	if strings.TrimSpace(payload.Domain) == "" {
		return nil, fmt.Errorf("domain is required")
	}
	if strings.TrimSpace(payload.FromEmail) == "" {
		return nil, fmt.Errorf("from email is required")
	}

	if _, err := s.credentials.SaveShared(ExternalAPIProviderMailgun, payload.APIKey, payload.Label); err != nil {
		return nil, err
	}

	if err := s.upsertSetting(mailgunDomainSettingKey, strings.TrimSpace(payload.Domain), "Mailgun sending domain"); err != nil {
		return nil, err
	}
	if err := s.upsertSetting(mailgunFromEmailSettingKey, strings.TrimSpace(payload.FromEmail), "Mailgun sender email"); err != nil {
		return nil, err
	}
	if err := s.upsertSetting(mailgunFromNameSettingKey, strings.TrimSpace(payload.FromName), "Mailgun sender name"); err != nil {
		return nil, err
	}
	if err := s.upsertSetting(mailgunRegionSettingKey, normalizeMailgunRegion(payload.Region), "Mailgun API region"); err != nil {
		return nil, err
	}

	return s.GetStatus()
}

func (s *MailgunService) DeleteSharedConfig() error {
	if err := s.credentials.DeleteShared(ExternalAPIProviderMailgun); err != nil {
		return err
	}
	return nil
}

func (s *MailgunService) SendPasswordRotationNotice(ctx context.Context, user *models.User) (*MailgunSendResult, error) {
	status, err := s.GetStatus()
	if err != nil {
		return nil, err
	}
	if !status.Configured {
		return &MailgunSendResult{
			Delivered: false,
			Message:   "Mailgun is not configured, so onboarding email was skipped.",
		}, nil
	}

	key, _, err := s.credentials.ResolveSharedKey(ExternalAPIProviderMailgun)
	if err != nil {
		return nil, err
	}

	from := status.FromEmail
	if strings.TrimSpace(status.FromName) != "" {
		from = fmt.Sprintf("%s <%s>", strings.TrimSpace(status.FromName), status.FromEmail)
	}

	form := url.Values{}
	form.Set("from", from)
	form.Set("to", user.Email)
	form.Set("subject", "Your dYdX Bot account is ready")
	form.Set("text", fmt.Sprintf(
		"Hello %s,\n\nYour dYdX Bot account has been provisioned.\n\nUsername: %s\nRole: %s\n\nUse the temporary password provided by your administrator and change it immediately after your first sign in.\n",
		displayNameForUser(user),
		user.Username,
		models.NormalizeUserRole(user.Role, user.IsAdmin),
	))

	endpoint := fmt.Sprintf("%s/v3/%s/messages", baseURLForMailgunRegion(status.Region), status.Domain)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, fmt.Errorf("failed to create Mailgun request: %w", err)
	}
	req.SetBasicAuth("api", key)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send Mailgun email: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return &MailgunSendResult{
			Delivered: false,
			Message:   fmt.Sprintf("Mailgun returned %d: %s", resp.StatusCode, strings.TrimSpace(string(body))),
		}, nil
	}

	return &MailgunSendResult{
		Delivered: true,
		Message:   "Onboarding email delivered through Mailgun.",
	}, nil
}

func (s *MailgunService) SendEmail(ctx context.Context, to string, subject string, textBody string, htmlBody string, tags ...string) (*MailgunSendResult, error) {
	status, err := s.GetStatus()
	if err != nil {
		return nil, err
	}
	if !status.Configured {
		return &MailgunSendResult{
			Delivered: false,
			Message:   "Mailgun is not configured.",
		}, nil
	}
	key, _, err := s.credentials.ResolveSharedKey(ExternalAPIProviderMailgun)
	if err != nil {
		return nil, err
	}

	from := status.FromEmail
	if strings.TrimSpace(status.FromName) != "" {
		from = fmt.Sprintf("%s <%s>", strings.TrimSpace(status.FromName), status.FromEmail)
	}

	form := url.Values{}
	form.Set("from", from)
	form.Set("to", strings.TrimSpace(to))
	form.Set("subject", strings.TrimSpace(subject))
	form.Set("text", textBody)
	if strings.TrimSpace(htmlBody) != "" {
		form.Set("html", htmlBody)
	}
	for _, tag := range tags {
		if strings.TrimSpace(tag) != "" {
			form.Add("o:tag", strings.TrimSpace(tag))
		}
	}

	endpoint := fmt.Sprintf("%s/v3/%s/messages", baseURLForMailgunRegion(status.Region), status.Domain)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, fmt.Errorf("failed to create Mailgun request: %w", err)
	}
	req.SetBasicAuth("api", key)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send Mailgun email: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return &MailgunSendResult{
			Delivered: false,
			Message:   fmt.Sprintf("Mailgun returned %d", resp.StatusCode),
		}, nil
	}

	return &MailgunSendResult{
		Delivered: true,
		Message:   "Email delivered through Mailgun.",
		MessageID: extractMailgunMessageID(string(body)),
	}, nil
}

func (s *MailgunService) getSettingValue(key string, fallback string) (string, error) {
	setting, err := s.settings.GetBotSettingBySectionAndKey("mailgun", key)
	if err != nil {
		if isMissingTableError(err) {
			return fallback, nil
		}
		return "", err
	}
	if setting == nil {
		return fallback, nil
	}
	return strings.TrimSpace(setting.Value), nil
}

func (s *MailgunService) upsertSetting(key string, value string, description string) error {
	existing, err := s.settings.GetBotSettingBySectionAndKey("mailgun", key)
	if err != nil && !isMissingTableError(err) {
		return fmt.Errorf("failed to load mailgun setting %s: %w", key, err)
	}
	if existing != nil {
		existing.Value = value
		existing.Description = description
		existing.IsActive = true
		existing.Version++
		return s.settings.UpdateBotSetting(existing)
	}

	return s.settings.CreateBotSetting(&models.BotSetting{
		Section:      "mailgun",
		Key:          key,
		Value:        value,
		ValueType:    "string",
		Description:  description,
		DefaultValue: "",
		IsActive:     true,
		Version:      1,
	})
}

func normalizeMailgunRegion(region string) string {
	switch strings.ToLower(strings.TrimSpace(region)) {
	case "eu":
		return "eu"
	default:
		return defaultMailgunRegion
	}
}

func baseURLForMailgunRegion(region string) string {
	if normalizeMailgunRegion(region) == "eu" {
		if envURL := strings.TrimSpace(os.Getenv("MAILGUN_API_BASE_URL_EU")); envURL != "" {
			return envURL
		}
		return defaultMailgunEUBaseURL
	}
	if envURL := strings.TrimSpace(os.Getenv("MAILGUN_API_BASE_URL")); envURL != "" {
		return envURL
	}
	return defaultMailgunUSBaseURL
}

func displayNameForUser(user *models.User) string {
	if strings.TrimSpace(user.FullName) != "" {
		return strings.TrimSpace(user.FullName)
	}
	return user.Username
}

func valueOrEmpty[T any](value *T, getter func(*T) string) string {
	if value == nil {
		return ""
	}
	return getter(value)
}

func isMissingTableError(err error) bool {
	lower := strings.ToLower(err.Error())
	return strings.Contains(lower, "no such table") || strings.Contains(lower, "does not exist")
}

func extractMailgunMessageID(body string) string {
	var parsed struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal([]byte(body), &parsed); err == nil {
		return strings.TrimSpace(parsed.ID)
	}
	return ""
}
