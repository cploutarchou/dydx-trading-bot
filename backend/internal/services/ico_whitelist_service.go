package services

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/mail"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const (
	ICOPrivacyNoticeVersion     = "ico-privacy-v2026-06-16"
	ICOMarketingConsentVersion  = "ico-marketing-v2026-06-16"
	ICOWhitelistConsentSource   = "ico_public_form"
	ICOWhitelistConfirmationTTL = 72 * time.Hour
)

const icoPrivacyConsentText = "I have read the ExecutionLab ICO Privacy Notice and agree that ExecutionLab may process my email address to review and communicate about my whitelist request."
const icoMarketingConsentText = "I would like to receive optional ExecutionLab ICO updates, document notices, and token-launch communications by email. I understand I can unsubscribe at any time."

type ICOWhitelistService struct {
	repo *repository.ICOWhitelistRepository
	now  func() time.Time
}

type ICOWhitelistSubmitRequest struct {
	Email                   string `json:"email"`
	PrivacyAccepted         bool   `json:"privacy_accepted"`
	PrivacyNoticeVersion    string `json:"privacy_notice_version"`
	MarketingConsent        bool   `json:"marketing_consent"`
	MarketingConsentVersion string `json:"marketing_consent_version"`
	Source                  string `json:"source"`
	Locale                  string `json:"locale"`
	ReferralCode            string `json:"referral_code"`
	Campaign                string `json:"campaign"`
	Honeypot                string `json:"company_website"`
}

type ICOWhitelistSubmitResponse struct {
	Message string `json:"message"`
}

type ICOWhitelistConfirmResponse struct {
	Confirmed bool   `json:"confirmed"`
	Message   string `json:"message"`
}

type ICOTokenActionResponse struct {
	Completed bool   `json:"completed"`
	Message   string `json:"message"`
}

func NewICOWhitelistService(repo *repository.ICOWhitelistRepository) *ICOWhitelistService {
	return &ICOWhitelistService{
		repo: repo,
		now:  func() time.Time { return time.Now().UTC() },
	}
}

func (s *ICOWhitelistService) Submit(ctx context.Context, req ICOWhitelistSubmitRequest) (*ICOWhitelistSubmitResponse, error) {
	if strings.TrimSpace(req.Honeypot) != "" {
		return genericWhitelistResponse(), nil
	}
	normalizedEmail, err := NormalizeICOWhitelistEmail(req.Email)
	if err != nil {
		return nil, err
	}
	if !req.PrivacyAccepted {
		return nil, fmt.Errorf("privacy notice acceptance is required")
	}

	now := s.now()
	token, tokenHash, err := generateWhitelistToken()
	if err != nil {
		return nil, err
	}
	unsubscribeToken, unsubscribeTokenHash, err := generateWhitelistToken()
	if err != nil {
		return nil, err
	}
	withdrawToken, withdrawTokenHash, err := generateWhitelistToken()
	if err != nil {
		return nil, err
	}

	marketingVersion := strings.TrimSpace(req.MarketingConsentVersion)
	if marketingVersion == "" {
		marketingVersion = ICOMarketingConsentVersion
	}
	privacyVersion := strings.TrimSpace(req.PrivacyNoticeVersion)
	if privacyVersion == "" {
		privacyVersion = ICOPrivacyNoticeVersion
	}
	source := strings.TrimSpace(req.Source)
	if source == "" {
		source = ICOWhitelistConsentSource
	}
	fingerprint := emailFingerprint(normalizedEmail)
	var marketingConsentedAt *time.Time
	if req.MarketingConsent {
		marketingConsentedAt = &now
	}

	payload, err := encryptedOutboxPayload(icoEmailPayload{
		ConfirmationURL: publicURL("/ico/whitelist/confirm?token=" + token),
		UnsubscribeURL:  publicURL("/ico/unsubscribe?token=" + unsubscribeToken),
		WithdrawURL:     publicURL("/ico/withdraw?token=" + withdrawToken),
		PrivacyURL:      publicURL("/ico/privacy-notice"),
	})
	if err != nil {
		return nil, err
	}

	events := []repository.ICOConsentEventParams{
		{
			EventType:     "privacy_notice_accepted",
			PolicyVersion: privacyVersion,
			ConsentText:   icoPrivacyConsentText,
			Source:        source,
			MetadataJSON:  consentMetadata(req.Locale, req.Campaign, fingerprint),
			OccurredAt:    now,
		},
	}
	if req.MarketingConsent {
		events = append(events, repository.ICOConsentEventParams{
			EventType:     "marketing_consent_requested",
			PolicyVersion: marketingVersion,
			ConsentText:   icoMarketingConsentText,
			Source:        source,
			MetadataJSON:  consentMetadata(req.Locale, req.Campaign, fingerprint),
			OccurredAt:    now,
		})
	}

	_, err = s.repo.CreateOrRefreshPending(ctx, repository.ICOWhitelistCreateParams{
		Email:                   strings.TrimSpace(req.Email),
		NormalizedEmail:         normalizedEmail,
		Status:                  models.ICOWhitelistStatusPendingConfirmation,
		MarketingConsent:        req.MarketingConsent,
		MarketingConsentVersion: marketingVersion,
		MarketingConsentText:    optionalConsentText(req.MarketingConsent),
		MarketingConsentedAt:    marketingConsentedAt,
		PrivacyNoticeVersion:    privacyVersion,
		PrivacyAcceptedAt:       now,
		ConfirmationTokenHash:   tokenHash,
		ConfirmationExpiresAt:   now.Add(ICOWhitelistConfirmationTTL),
		UnsubscribeTokenHash:    unsubscribeTokenHash,
		WithdrawTokenHash:       withdrawTokenHash,
		Source:                  source,
		Locale:                  strings.TrimSpace(req.Locale),
		ReferralCode:            strings.TrimSpace(req.ReferralCode),
		Campaign:                strings.TrimSpace(req.Campaign),
		EmailFingerprint:        fingerprint,
	}, events, repository.ICOEmailOutboxParams{
		IdempotencyKey:       "ico-whitelist-confirm:" + tokenHash[:24],
		EmailType:            "whitelist_confirmation",
		RecipientEmail:       normalizedEmail,
		RecipientFingerprint: fingerprint,
		Subject:              "Confirm your ExecutionLab whitelist request",
		TemplateKey:          "ico_whitelist_confirmation",
		PayloadEncrypted:     payload,
		ScheduledAt:          now,
	})
	if err != nil {
		return nil, err
	}

	return genericWhitelistResponse(), nil
}

func (s *ICOWhitelistService) Confirm(ctx context.Context, token string) (*ICOWhitelistConfirmResponse, error) {
	token = strings.TrimSpace(token)
	if token == "" {
		return &ICOWhitelistConfirmResponse{
			Confirmed: false,
			Message:   "The confirmation link is invalid or expired.",
		}, nil
	}
	confirmed, err := s.repo.ConfirmByTokenHash(ctx, hashToken(token), s.now())
	if err != nil {
		return nil, err
	}
	if !confirmed {
		return &ICOWhitelistConfirmResponse{
			Confirmed: false,
			Message:   "The confirmation link is invalid, expired, or already used.",
		}, nil
	}
	return &ICOWhitelistConfirmResponse{
		Confirmed: true,
		Message:   "Your whitelist email has been confirmed. This does not guarantee participation, eligibility, or allocation.",
	}, nil
}

func (s *ICOWhitelistService) Unsubscribe(ctx context.Context, token string) (*ICOTokenActionResponse, error) {
	token = strings.TrimSpace(token)
	if token == "" {
		return &ICOTokenActionResponse{Completed: false, Message: "The unsubscribe link is invalid or already used."}, nil
	}
	ok, err := s.repo.UnsubscribeByTokenHash(ctx, hashToken(token), s.now())
	if err != nil {
		return nil, err
	}
	if !ok {
		return &ICOTokenActionResponse{Completed: false, Message: "The unsubscribe link is invalid or already used."}, nil
	}
	return &ICOTokenActionResponse{Completed: true, Message: "Marketing updates have been unsubscribed. Your whitelist application was not deleted."}, nil
}

func (s *ICOWhitelistService) Withdraw(ctx context.Context, token string) (*ICOTokenActionResponse, error) {
	token = strings.TrimSpace(token)
	if token == "" {
		return &ICOTokenActionResponse{Completed: false, Message: "The withdrawal link is invalid or already used."}, nil
	}
	ok, err := s.repo.WithdrawByTokenHash(ctx, hashToken(token), s.now())
	if err != nil {
		return nil, err
	}
	if !ok {
		return &ICOTokenActionResponse{Completed: false, Message: "The withdrawal link is invalid or already used."}, nil
	}
	return &ICOTokenActionResponse{Completed: true, Message: "Your whitelist request has been withdrawn."}, nil
}

func NormalizeICOWhitelistEmail(value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if len(trimmed) > 320 {
		return "", fmt.Errorf("email address is too long")
	}
	parsed, err := mail.ParseAddress(trimmed)
	if err != nil || parsed == nil {
		return "", fmt.Errorf("enter a valid email address")
	}
	normalized := strings.ToLower(strings.TrimSpace(parsed.Address))
	if normalized == "" || len(normalized) > 320 {
		return "", fmt.Errorf("enter a valid email address")
	}
	return normalized, nil
}

func genericWhitelistResponse() *ICOWhitelistSubmitResponse {
	return &ICOWhitelistSubmitResponse{
		Message: "If the address is eligible to receive whitelist communications, a confirmation email will be sent.",
	}
}

func optionalConsentText(consented bool) string {
	if !consented {
		return ""
	}
	return icoMarketingConsentText
}

func consentMetadata(locale, campaign, emailHash string) string {
	payload := map[string]string{
		"locale":            strings.TrimSpace(locale),
		"campaign":          strings.TrimSpace(campaign),
		"email_fingerprint": emailHash,
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		return "{}"
	}
	return string(encoded)
}

func generateWhitelistToken() (string, string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", "", fmt.Errorf("failed to generate confirmation token")
	}
	token := base64.RawURLEncoding.EncodeToString(bytes)
	return token, hashToken(token), nil
}

func hashToken(token string) string {
	sum := sha256.Sum256([]byte(strings.TrimSpace(token)))
	return hex.EncodeToString(sum[:])
}

func emailFingerprint(normalizedEmail string) string {
	sum := sha256.Sum256([]byte(strings.ToLower(strings.TrimSpace(normalizedEmail))))
	return hex.EncodeToString(sum[:])
}

func EmailFingerprintForWebhook(normalizedEmail string) string {
	return emailFingerprint(normalizedEmail)
}

type icoEmailPayload struct {
	ConfirmationURL string `json:"confirmation_url"`
	UnsubscribeURL  string `json:"unsubscribe_url"`
	WithdrawURL     string `json:"withdraw_url"`
	PrivacyURL      string `json:"privacy_url"`
}

func encryptedOutboxPayload(payload icoEmailPayload) (string, error) {
	encoded, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to encode email payload")
	}
	encrypted, err := encryptString(loadEncryptionSecret(), string(encoded))
	if err != nil {
		return "", fmt.Errorf("failed to encrypt email payload: %w", err)
	}
	return encrypted, nil
}

func decryptOutboxPayload(encrypted string) (*icoEmailPayload, error) {
	decrypted, err := decryptString(loadEncryptionSecret(), encrypted)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt email payload: %w", err)
	}
	var payload icoEmailPayload
	if err := json.Unmarshal([]byte(decrypted), &payload); err != nil {
		return nil, fmt.Errorf("failed to decode email payload: %w", err)
	}
	return &payload, nil
}

func publicURL(path string) string {
	base := strings.TrimRight(strings.TrimSpace(os.Getenv("PUBLIC_APP_URL")), "/")
	if base == "" {
		base = strings.TrimRight(strings.TrimSpace(os.Getenv("FRONTEND_URL")), "/")
	}
	if base == "" {
		base = "http://localhost:5173"
	}
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}
	return base + path
}
