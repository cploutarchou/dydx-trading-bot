package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/mail"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const (
	emailProviderPlunk         = "plunk"
	emailSettingsSection       = "email"
	emailAPIURLSettingKey      = "api_url"
	emailFromEmailSettingKey   = "from_email"
	emailFromNameSettingKey    = "from_name"
	emailReplyToSettingKey     = "reply_to"
	plunkAPIURLEnv             = "PLUNK_API_URL"
	plunkSendPath              = "/v1/send"
	emailErrorBodyLimit        = 2048
	emailResponseBodyLimit     = 8192
	emailDefaultRequestTimeout = 15 * time.Second
	emailNotConfiguredMessage  = "Email delivery is not configured."
)

// EmailStatus is the admin-panel view of outbound email delivery.
type EmailStatus struct {
	Provider                   string `json:"provider"`
	Configured                 bool   `json:"configured"`
	SharedKeyPresent           bool   `json:"shared_key_present"`
	SharedKeyMasked            string `json:"shared_key_masked"`
	SharedKeyLabel             string `json:"shared_key_label"`
	APIURL                     string `json:"api_url"`
	FromEmail                  string `json:"from_email"`
	FromName                   string `json:"from_name"`
	ReplyTo                    string `json:"reply_to"`
	PendingPasswordChangeCount int    `json:"pending_password_change_count"`
}

// EmailConfigPayload is what the admin panel saves. APIKey may be empty when a
// key is already stored, so the sender details can change without re-pasting
// the secret.
type EmailConfigPayload struct {
	APIKey    string `json:"api_key"`
	Label     string `json:"label,omitempty"`
	APIURL    string `json:"api_url"`
	FromEmail string `json:"from_email"`
	FromName  string `json:"from_name"`
	ReplyTo   string `json:"reply_to"`
}

type EmailSendResult struct {
	Delivered bool   `json:"delivered"`
	Message   string `json:"message"`
	MessageID string `json:"message_id,omitempty"`
}

// EmailService sends transactional email through a Plunk-compatible API
// (POST {api_url}/v1/send with a project secret key). Every setting lives in
// the database and is managed from the admin panel; PLUNK_API_URL is only a
// fallback for the API base URL.
type EmailService struct {
	credentials *ExternalAPICredentialService
	settings    *repository.SettingsRepository
	users       *repository.UserRepository
	httpClient  *http.Client
}

func NewEmailService(
	credentials *ExternalAPICredentialService,
	settings *repository.SettingsRepository,
	users *repository.UserRepository,
) *EmailService {
	return &EmailService{
		credentials: credentials,
		settings:    settings,
		users:       users,
		httpClient:  &http.Client{Timeout: emailDefaultRequestTimeout},
	}
}

func (s *EmailService) GetStatus() (*EmailStatus, error) {
	info, err := s.credentials.GetShared(ExternalAPIProviderPlunk)
	if err != nil {
		return nil, fmt.Errorf("failed to load email credential info: %w", err)
	}
	key, keyPresent, err := s.credentials.ResolveSharedKey(ExternalAPIProviderPlunk)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve email API key: %w", err)
	}

	apiURL, _ := s.getSettingValue(emailAPIURLSettingKey, "")
	if apiURL == "" {
		apiURL = strings.TrimSpace(os.Getenv(plunkAPIURLEnv))
	}
	fromEmail, _ := s.getSettingValue(emailFromEmailSettingKey, "")
	fromName, _ := s.getSettingValue(emailFromNameSettingKey, "")
	replyTo, _ := s.getSettingValue(emailReplyToSettingKey, "")

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

	configured := strings.TrimSpace(key) != "" && apiURL != "" && fromEmail != ""

	return &EmailStatus{
		Provider:                   emailProviderPlunk,
		Configured:                 configured,
		SharedKeyPresent:           keyPresent,
		SharedKeyMasked:            valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.MaskedValue }),
		SharedKeyLabel:             valueOrEmpty(info, func(i *ExternalAPICredentialInfo) string { return i.Label }),
		APIURL:                     apiURL,
		FromEmail:                  fromEmail,
		FromName:                   fromName,
		ReplyTo:                    replyTo,
		PendingPasswordChangeCount: pending,
	}, nil
}

func (s *EmailService) SaveSharedConfig(payload EmailConfigPayload) (*EmailStatus, error) {
	apiURL, err := normalizeEmailAPIURL(payload.APIURL)
	if err != nil {
		return nil, err
	}
	fromEmail, err := normalizeEmailAddress(payload.FromEmail, "sender email")
	if err != nil {
		return nil, err
	}
	replyTo := ""
	if strings.TrimSpace(payload.ReplyTo) != "" {
		if replyTo, err = normalizeEmailAddress(payload.ReplyTo, "reply-to email"); err != nil {
			return nil, err
		}
	}

	apiKey := strings.TrimSpace(payload.APIKey)
	if apiKey == "" {
		_, keyPresent, err := s.credentials.ResolveSharedKey(ExternalAPIProviderPlunk)
		if err != nil {
			return nil, fmt.Errorf("failed to resolve email API key: %w", err)
		}
		if !keyPresent {
			return nil, fmt.Errorf("api key is required")
		}
	} else {
		if strings.HasPrefix(apiKey, "pk_") {
			return nil, fmt.Errorf("that is the public key; sending needs the secret key (sk_...)")
		}
		if _, err := s.credentials.SaveShared(ExternalAPIProviderPlunk, apiKey, payload.Label); err != nil {
			return nil, err
		}
	}

	if err := s.upsertSetting(emailAPIURLSettingKey, apiURL, "Email API base URL"); err != nil {
		return nil, err
	}
	if err := s.upsertSetting(emailFromEmailSettingKey, fromEmail, "Email sender address"); err != nil {
		return nil, err
	}
	if err := s.upsertSetting(emailFromNameSettingKey, strings.TrimSpace(payload.FromName), "Email sender name"); err != nil {
		return nil, err
	}
	if err := s.upsertSetting(emailReplyToSettingKey, replyTo, "Email reply-to address"); err != nil {
		return nil, err
	}

	return s.GetStatus()
}

func (s *EmailService) DeleteSharedConfig() error {
	return s.credentials.DeleteShared(ExternalAPIProviderPlunk)
}

func (s *EmailService) SendPasswordRotationNotice(ctx context.Context, user *models.User) (*EmailSendResult, error) {
	textBody := fmt.Sprintf(
		"Hello %s,\n\nYour ExecutionLab account has been provisioned.\n\nUsername: %s\nRole: %s\n\nUse the temporary password provided by your administrator and change it immediately after your first sign in.\n",
		displayNameForUser(user),
		user.Username,
		models.NormalizeUserRole(user.Role, user.IsAdmin),
	)
	result, err := s.SendEmail(ctx, user.Email, "Your ExecutionLab account is ready", textBody, "", "onboarding")
	if err != nil {
		return nil, err
	}
	switch {
	case result.Delivered:
		result.Message = "Onboarding email sent."
	case result.Message == emailNotConfiguredMessage:
		result.Message = "Email delivery is not configured, so the onboarding email was skipped."
	}
	return result, nil
}

// SendTest delivers a fixed message so an admin can verify the saved
// configuration end to end.
func (s *EmailService) SendTest(ctx context.Context, to string) (*EmailSendResult, error) {
	recipient, err := normalizeEmailAddress(to, "recipient")
	if err != nil {
		return nil, err
	}
	sentAt := time.Now().UTC().Format(time.RFC3339)
	textBody := fmt.Sprintf("This is a test message from the ExecutionLab admin panel.\n\nSent at %s.\nIf you received it, outbound email delivery works.\n", sentAt)
	return s.SendEmail(ctx, recipient, "ExecutionLab email delivery test", textBody, "", "test")
}

// SendEmail delivers one transactional message. tags are accepted for call-site
// compatibility and forwarded as template data; the send API has no tag field.
func (s *EmailService) SendEmail(ctx context.Context, to string, subject string, textBody string, htmlBody string, tags ...string) (*EmailSendResult, error) {
	status, err := s.GetStatus()
	if err != nil {
		return nil, err
	}
	if !status.Configured {
		return &EmailSendResult{Delivered: false, Message: emailNotConfiguredMessage}, nil
	}
	key, _, err := s.credentials.ResolveSharedKey(ExternalAPIProviderPlunk)
	if err != nil {
		return nil, err
	}
	endpoint, err := normalizeEmailAPIURL(status.APIURL)
	if err != nil {
		return &EmailSendResult{Delivered: false, Message: "Email API URL is invalid."}, nil
	}

	body := htmlBody
	if strings.TrimSpace(body) == "" {
		body = plainTextToHTML(textBody)
	}
	payload := map[string]any{
		"to":         strings.TrimSpace(to),
		"subject":    strings.TrimSpace(subject),
		"body":       body,
		"from":       status.FromEmail,
		"subscribed": false,
	}
	if status.FromName != "" {
		payload["name"] = status.FromName
	}
	if status.ReplyTo != "" {
		payload["reply"] = status.ReplyTo
	}
	if cleaned := cleanEmailTags(tags); len(cleaned) > 0 {
		payload["data"] = map[string]any{"tags": strings.Join(cleaned, ",")}
	}

	encoded, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to encode email request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint+plunkSendPath, bytes.NewReader(encoded))
	if err != nil {
		return nil, fmt.Errorf("failed to create email request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+key)

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send email: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		detail, _ := io.ReadAll(io.LimitReader(resp.Body, emailErrorBodyLimit))
		return &EmailSendResult{
			Delivered: false,
			Message:   fmt.Sprintf("Email API returned %d: %s", resp.StatusCode, extractEmailAPIError(detail)),
		}, nil
	}

	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, emailResponseBodyLimit))
	return &EmailSendResult{
		Delivered: true,
		Message:   "Email accepted for delivery.",
		MessageID: extractPlunkMessageID(respBody),
	}, nil
}

func (s *EmailService) getSettingValue(key string, fallback string) (string, error) {
	setting, err := s.settings.GetBotSettingBySectionAndKey(emailSettingsSection, key)
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

func (s *EmailService) upsertSetting(key string, value string, description string) error {
	existing, err := s.settings.GetBotSettingBySectionAndKey(emailSettingsSection, key)
	if err != nil && !isMissingTableError(err) {
		return fmt.Errorf("failed to load email setting %s: %w", key, err)
	}
	if existing != nil {
		existing.Value = value
		existing.Description = description
		existing.IsActive = true
		existing.Version++
		return s.settings.UpdateBotSetting(existing)
	}

	return s.settings.CreateBotSetting(&models.BotSetting{
		Section:      emailSettingsSection,
		Key:          key,
		Value:        value,
		ValueType:    "string",
		Description:  description,
		DefaultValue: "",
		IsActive:     true,
		Version:      1,
	})
}

// normalizeEmailAPIURL accepts only an absolute http(s) base URL without
// credentials, query or fragment. Plain http is allowed for loopback hosts so
// a local mail stack works in development.
func normalizeEmailAPIURL(raw string) (string, error) {
	trimmed := strings.TrimRight(strings.TrimSpace(raw), "/")
	if trimmed == "" {
		return "", fmt.Errorf("api url is required")
	}
	parsed, err := url.Parse(trimmed)
	if err != nil || parsed.Host == "" {
		return "", fmt.Errorf("api url must be an absolute URL such as https://api.example.com")
	}
	if parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
		return "", fmt.Errorf("api url must not contain credentials, a query or a fragment")
	}
	switch parsed.Scheme {
	case "https":
	case "http":
		host := parsed.Hostname()
		if host != "localhost" && host != "127.0.0.1" && host != "::1" {
			return "", fmt.Errorf("api url must use https")
		}
	default:
		return "", fmt.Errorf("api url must use https")
	}
	return strings.TrimSuffix(trimmed, plunkSendPath), nil
}

func normalizeEmailAddress(raw string, field string) (string, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return "", fmt.Errorf("%s is required", field)
	}
	parsed, err := mail.ParseAddress(trimmed)
	if err != nil || parsed.Address != trimmed {
		return "", fmt.Errorf("%s must be a plain email address", field)
	}
	return parsed.Address, nil
}

func plainTextToHTML(text string) string {
	escaped := html.EscapeString(strings.TrimSpace(text))
	paragraphs := strings.Split(escaped, "\n\n")
	for i, paragraph := range paragraphs {
		paragraphs[i] = "<p>" + strings.ReplaceAll(paragraph, "\n", "<br>") + "</p>"
	}
	return strings.Join(paragraphs, "")
}

func cleanEmailTags(tags []string) []string {
	cleaned := make([]string, 0, len(tags))
	for _, tag := range tags {
		if trimmed := strings.TrimSpace(tag); trimmed != "" {
			cleaned = append(cleaned, trimmed)
		}
	}
	return cleaned
}

func extractEmailAPIError(body []byte) string {
	var parsed struct {
		Message string `json:"message"`
		Error   string `json:"error"`
	}
	if err := json.Unmarshal(body, &parsed); err == nil {
		if msg := strings.TrimSpace(parsed.Message); msg != "" {
			return msg
		}
		if msg := strings.TrimSpace(parsed.Error); msg != "" {
			return msg
		}
	}
	return strings.TrimSpace(string(body))
}

func extractPlunkMessageID(body []byte) string {
	var parsed struct {
		Emails []struct {
			Email string `json:"email"`
		} `json:"emails"`
	}
	if err := json.Unmarshal(body, &parsed); err == nil && len(parsed.Emails) > 0 {
		return strings.TrimSpace(parsed.Emails[0].Email)
	}
	return ""
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
