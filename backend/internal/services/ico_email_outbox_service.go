package services

import (
	"context"
	"fmt"
	"html"
	"log"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type ICOEmailOutboxService struct {
	repo *repository.ICOWhitelistRepository
	mail *EmailService
	now  func() time.Time
}

func NewICOEmailOutboxService(repo *repository.ICOWhitelistRepository, mail *EmailService) *ICOEmailOutboxService {
	return &ICOEmailOutboxService{
		repo: repo,
		mail: mail,
		now:  func() time.Time { return time.Now().UTC() },
	}
}

func (s *ICOEmailOutboxService) ProcessPending(ctx context.Context, limit int) (int, error) {
	entries, err := s.repo.ListPendingOutbox(ctx, limit, s.now())
	if err != nil {
		return 0, err
	}
	processed := 0
	for _, entry := range entries {
		if err := s.processOne(ctx, entry); err != nil {
			log.Printf("ICO email outbox: failed entry id=%d type=%s: %v", entry.ID, entry.EmailType, err)
		}
		processed++
	}
	return processed, nil
}

func (s *ICOEmailOutboxService) processOne(ctx context.Context, entry models.ICOEmailOutboxEntry) error {
	payload, err := decryptOutboxPayload(entry.PayloadEncrypted)
	if err != nil {
		_ = s.repo.MarkOutboxFailed(ctx, entry.ID, false, "invalid encrypted payload", s.now())
		return err
	}

	textBody, htmlBody := renderICOEmail(entry, payload)
	result, err := s.mail.SendEmail(ctx, entry.RecipientEmail, entry.Subject, textBody, htmlBody, "ico", entry.EmailType)
	if err != nil {
		_ = s.repo.MarkOutboxFailed(ctx, entry.ID, true, "email send failed", s.now())
		return err
	}
	// Delivery semantics are at-least-once: a crash between the provider call
	// and MarkOutboxSent causes one duplicate resend on the next tick. The
	// repository's status guard ensures the bookkeeping itself is
	// single-writer across replicas.
	if result == nil || !result.Delivered {
		_ = s.repo.MarkOutboxFailed(ctx, entry.ID, true, "email not configured or delivery rejected", s.now())
		return nil
	}

	return s.repo.MarkOutboxSent(ctx, entry.ID, result.MessageID, s.now())
}

func renderICOEmail(entry models.ICOEmailOutboxEntry, payload *icoEmailPayload) (string, string) {
	switch entry.TemplateKey {
	case "ico_whitelist_confirmation":
		return renderWhitelistConfirmationEmail(payload)
	default:
		text := fmt.Sprintf("ExecutionLab notification\n\nOpen: %s\n", payload.ConfirmationURL)
		htmlBody := "<p>ExecutionLab notification</p><p><a href=\"" + html.EscapeString(payload.ConfirmationURL) + "\">Open notification</a></p>"
		return text, htmlBody
	}
}

func renderWhitelistConfirmationEmail(payload *icoEmailPayload) (string, string) {
	text := strings.Join([]string{
		"Confirm your ExecutionLab whitelist email",
		"",
		"Use the link below to confirm the email address for your ICO whitelist request.",
		payload.ConfirmationURL,
		"",
		"This confirmation does not guarantee participation, eligibility, or allocation.",
		"",
		"Optional marketing updates can be unsubscribed from here:",
		payload.UnsubscribeURL,
		"",
		"To withdraw the whitelist request:",
		payload.WithdrawURL,
		"",
		"Privacy notice:",
		payload.PrivacyURL,
	}, "\n")

	htmlBody := fmt.Sprintf(`
<!doctype html>
<html>
  <body style="margin:0;background:#050816;color:#e2e8f0;font-family:Inter,Arial,sans-serif;">
    <table role="presentation" width="100%%" cellspacing="0" cellpadding="0" style="background:#050816;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#0b1220;border:1px solid #1e293b;border-radius:16px;padding:28px;">
            <tr><td>
              <p style="margin:0 0 12px;color:#67e8f9;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">ExecutionLab ICO whitelist</p>
              <h1 style="margin:0 0 16px;color:#fff;font-size:28px;line-height:1.15;">Confirm your whitelist email</h1>
              <p style="margin:0 0 22px;color:#cbd5e1;line-height:1.6;">Use this link to confirm the email address for your ICO whitelist request. Confirmation does not guarantee participation, eligibility, or allocation.</p>
              <p style="margin:0 0 24px;"><a href="%s" style="display:inline-block;background:#0891b2;color:#fff;text-decoration:none;font-weight:700;padding:13px 18px;border-radius:10px;">Confirm email</a></p>
              <p style="margin:0 0 8px;color:#94a3b8;font-size:14px;line-height:1.6;">Optional marketing updates can be <a href="%s" style="color:#a5f3fc;">unsubscribed</a>. You can also <a href="%s" style="color:#a5f3fc;">withdraw the whitelist request</a>.</p>
              <p style="margin:0;color:#94a3b8;font-size:14px;line-height:1.6;"><a href="%s" style="color:#a5f3fc;">Privacy notice</a></p>
            </td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`,
		html.EscapeString(payload.ConfirmationURL),
		html.EscapeString(payload.UnsubscribeURL),
		html.EscapeString(payload.WithdrawURL),
		html.EscapeString(payload.PrivacyURL),
	)
	return text, htmlBody
}
