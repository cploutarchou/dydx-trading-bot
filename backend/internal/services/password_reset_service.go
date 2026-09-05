package services

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"os"
	"strings"
	"time"
)

// PasswordResetService issues and mails single-use password reset tokens.
// The raw token exists only in the email; the repository stores its SHA-256.
type PasswordResetService struct {
	tokens PasswordResetTokenStore
	mail   *MailgunService
}

// PasswordResetTokenStore is the persistence seam (implemented by the
// repository package; kept as an interface so tests can stub it).
type PasswordResetTokenStore interface {
	Create(ctx context.Context, userID int, tokenHash string, expiresAt time.Time, createdIP string) error
	RecentCreatedWithin(ctx context.Context, userID int, window time.Duration) (bool, error)
}

const (
	passwordResetTokenTTL    = 30 * time.Minute
	passwordResetCooldown    = time.Minute
)

func NewPasswordResetService(tokens PasswordResetTokenStore, mail *MailgunService) *PasswordResetService {
	return &PasswordResetService{tokens: tokens, mail: mail}
}

// hashResetToken maps a raw reset token to its stored representation.
// (Separate from ico_whitelist_service.hashToken: different token domains.)
func hashResetToken(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

// IssueResetToken generates a token for the user and emails the reset link.
// Returned errors are for server-side logging only: the HTTP layer must
// respond identically whether or not the account exists (no enumeration).
func (s *PasswordResetService) IssueResetToken(ctx context.Context, userID int, email, username, clientIP string) error {
	recent, err := s.tokens.RecentCreatedWithin(ctx, userID, passwordResetCooldown)
	if err != nil {
		return fmt.Errorf("reset cooldown check: %w", err)
	}
	if recent {
		// A reset mail already went out seconds ago; stay silent rather than
		// letting the endpoint be used to flood the mailbox.
		return nil
	}

	rawBytes := make([]byte, 32)
	if _, err := rand.Read(rawBytes); err != nil {
		return fmt.Errorf("reset token entropy: %w", err)
	}
	rawToken := base64.RawURLEncoding.EncodeToString(rawBytes)

	if err := s.tokens.Create(ctx, userID, hashResetToken(rawToken), time.Now().UTC().Add(passwordResetTokenTTL), clientIP); err != nil {
		return fmt.Errorf("persist reset token: %w", err)
	}

	link := passwordResetPublicURL("/reset-password?token=" + rawToken)
	subject := "Reset your ExecutionLab password"
	textBody := fmt.Sprintf(
		"Hello %s,\n\nWe received a request to reset your ExecutionLab password.\n\nOpen this link within %d minutes to choose a new one:\n%s\n\nIf you did not request this, ignore this email — your current password keeps working and the link expires.\n",
		username, int(passwordResetTokenTTL.Minutes()), link,
	)
	htmlBody := fmt.Sprintf(
		"<p>Hello %s,</p><p>We received a request to reset your ExecutionLab password.</p><p><a href=\"%s\">Choose a new password</a> — this link works for the next %d minutes and can be used once.</p><p>If you did not request this, ignore this email; your current password keeps working.</p>",
		username, link, int(passwordResetTokenTTL.Minutes()),
	)

	if _, err := s.mail.SendEmail(ctx, email, subject, textBody, htmlBody, "password-reset"); err != nil {
		return fmt.Errorf("send reset email: %w", err)
	}
	return nil
}

// HashForValidation exposes hashing to the HTTP layer for the consume step.
func HashForValidation(rawToken string) string { return hashResetToken(rawToken) }

// passwordResetPublicURL mirrors the whitelist service's link building:
// PUBLIC_APP_URL -> FRONTEND_URL -> local dev default.
func passwordResetPublicURL(path string) string {
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
