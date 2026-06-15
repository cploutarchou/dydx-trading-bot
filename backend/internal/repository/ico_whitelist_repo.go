package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type ICOWhitelistRepository struct {
	db *sql.DB
}

func NewICOWhitelistRepository(db *sql.DB) *ICOWhitelistRepository {
	return &ICOWhitelistRepository{db: db}
}

type ICOWhitelistCreateParams struct {
	Email                   string
	NormalizedEmail         string
	Status                  string
	MarketingConsent        bool
	MarketingConsentVersion string
	MarketingConsentText    string
	MarketingConsentedAt    *time.Time
	PrivacyNoticeVersion    string
	PrivacyAcceptedAt       time.Time
	ConfirmationTokenHash   string
	ConfirmationExpiresAt   time.Time
	UnsubscribeTokenHash    string
	WithdrawTokenHash       string
	Source                  string
	Locale                  string
	ReferralCode            string
	Campaign                string
	EmailFingerprint        string
}

type ICOConsentEventParams struct {
	WhitelistApplicationID int64
	EventType              string
	PolicyVersion          string
	ConsentText            string
	Source                 string
	MetadataJSON           string
	OccurredAt             time.Time
}

type ICOEmailOutboxParams struct {
	WhitelistApplicationID *int64
	IdempotencyKey         string
	EmailType              string
	RecipientEmail         string
	RecipientFingerprint   string
	Subject                string
	TemplateKey            string
	PayloadEncrypted       string
	ScheduledAt            time.Time
}

type ICOWhitelistListFilter struct {
	Status string
	Limit  int
	Offset int
}

func (r *ICOWhitelistRepository) CreateOrRefreshPending(
	ctx context.Context,
	params ICOWhitelistCreateParams,
	events []ICOConsentEventParams,
	outbox ICOEmailOutboxParams,
) (*models.ICOWhitelistApplication, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to start whitelist transaction: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback()
		}
	}()

	existing, getErr := r.getByNormalizedEmail(ctx, tx, params.NormalizedEmail)
	if getErr != nil {
		err = getErr
		return nil, err
	}

	var application *models.ICOWhitelistApplication
	if existing == nil {
		application, err = r.createApplication(ctx, tx, params)
		if err != nil {
			return nil, err
		}
	} else {
		application, err = r.refreshPendingApplication(ctx, tx, existing.ID, params)
		if err != nil {
			return nil, err
		}
	}

	for _, event := range events {
		event.WhitelistApplicationID = application.ID
		if event.OccurredAt.IsZero() {
			event.OccurredAt = time.Now().UTC()
		}
		if err = r.createConsentEvent(ctx, tx, event); err != nil {
			return nil, err
		}
	}

	outbox.WhitelistApplicationID = &application.ID
	if err = r.createOutboxEntryIfMissing(ctx, tx, outbox); err != nil {
		return nil, err
	}

	if err = tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit whitelist transaction: %w", err)
	}

	return application, nil
}

func (r *ICOWhitelistRepository) ConfirmByTokenHash(ctx context.Context, tokenHash string, now time.Time) (bool, error) {
	result, err := r.db.ExecContext(ctx, `
		UPDATE ico_whitelist_applications
		SET status = CASE WHEN status = ? THEN ? ELSE status END,
		    email_confirmed_at = ?,
		    marketing_confirmed_at = CASE WHEN marketing_consent = TRUE THEN ? ELSE marketing_confirmed_at END,
		    updated_at = ?
		WHERE confirmation_token_hash = ?
		  AND confirmation_expires_at > ?
		  AND email_confirmed_at IS NULL
		  AND status <> ?
	`,
		models.ICOWhitelistStatusPendingConfirmation,
		models.ICOWhitelistStatusConfirmed,
		now,
		now,
		now,
		tokenHash,
		now,
		models.ICOWhitelistStatusWithdrawn,
	)
	if err != nil {
		return false, fmt.Errorf("failed to confirm whitelist application: %w", err)
	}
	affected, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to inspect confirmation result: %w", err)
	}
	return affected > 0, nil
}

func (r *ICOWhitelistRepository) UnsubscribeByTokenHash(ctx context.Context, tokenHash string, now time.Time) (bool, error) {
	result, err := r.db.ExecContext(ctx, `
		UPDATE ico_whitelist_applications
		SET unsubscribed_at = COALESCE(unsubscribed_at, ?),
		    marketing_confirmed_at = NULL,
		    updated_at = ?
		WHERE unsubscribe_token_hash = ?
		  AND unsubscribed_at IS NULL
	`, now, now, tokenHash)
	if err != nil {
		return false, fmt.Errorf("failed to unsubscribe whitelist applicant: %w", err)
	}
	affected, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to inspect unsubscribe result: %w", err)
	}
	return affected > 0, nil
}

func (r *ICOWhitelistRepository) WithdrawByTokenHash(ctx context.Context, tokenHash string, now time.Time) (bool, error) {
	result, err := r.db.ExecContext(ctx, `
		UPDATE ico_whitelist_applications
		SET status = ?,
		    withdrawn_at = COALESCE(withdrawn_at, ?),
		    updated_at = ?
		WHERE withdraw_token_hash = ?
		  AND withdrawn_at IS NULL
		  AND status <> ?
	`, models.ICOWhitelistStatusWithdrawn, now, now, tokenHash, models.ICOWhitelistStatusWithdrawn)
	if err != nil {
		return false, fmt.Errorf("failed to withdraw whitelist application: %w", err)
	}
	affected, err := result.RowsAffected()
	if err != nil {
		return false, fmt.Errorf("failed to inspect withdraw result: %w", err)
	}
	return affected > 0, nil
}

func (r *ICOWhitelistRepository) getByNormalizedEmail(ctx context.Context, exec QueryExecutor, normalizedEmail string) (*models.ICOWhitelistApplication, error) {
	row := exec.QueryRowContext(ctx, `
		SELECT id, email, normalized_email, status, marketing_consent, marketing_consent_version,
		       marketing_consent_text, marketing_consented_at, marketing_confirmed_at,
		       privacy_notice_version, privacy_accepted_at, confirmation_token_hash,
		       confirmation_expires_at, unsubscribe_token_hash, withdraw_token_hash,
		       email_confirmed_at, reviewed_at, reviewed_by,
		       approved_at, rejected_at, rejection_reason, unsubscribed_at, withdrawn_at,
		       source, locale, referral_code, campaign, email_fingerprint, created_at, updated_at
		FROM ico_whitelist_applications
		WHERE normalized_email = ?
		LIMIT 1
	`, normalizedEmail)
	return scanICOWhitelistApplication(row)
}

func (r *ICOWhitelistRepository) createApplication(ctx context.Context, exec QueryExecutor, params ICOWhitelistCreateParams) (*models.ICOWhitelistApplication, error) {
	result, err := exec.ExecContext(ctx, `
		INSERT INTO ico_whitelist_applications (
			email, normalized_email, status, marketing_consent, marketing_consent_version,
			marketing_consent_text, marketing_consented_at, privacy_notice_version,
			privacy_accepted_at, confirmation_token_hash, confirmation_expires_at,
			unsubscribe_token_hash, withdraw_token_hash,
			source, locale, referral_code, campaign, email_fingerprint, created_at, updated_at
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`,
		params.Email,
		params.NormalizedEmail,
		params.Status,
		params.MarketingConsent,
		params.MarketingConsentVersion,
		params.MarketingConsentText,
		params.MarketingConsentedAt,
		params.PrivacyNoticeVersion,
		params.PrivacyAcceptedAt,
		params.ConfirmationTokenHash,
		params.ConfirmationExpiresAt,
		params.UnsubscribeTokenHash,
		params.WithdrawTokenHash,
		params.Source,
		params.Locale,
		params.ReferralCode,
		params.Campaign,
		params.EmailFingerprint,
		time.Now().UTC(),
		time.Now().UTC(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create whitelist application: %w", err)
	}
	id, err := result.LastInsertId()
	if err != nil {
		return nil, fmt.Errorf("failed to get whitelist application id: %w", err)
	}
	return r.getByID(ctx, exec, id)
}

func (r *ICOWhitelistRepository) refreshPendingApplication(ctx context.Context, exec QueryExecutor, id int64, params ICOWhitelistCreateParams) (*models.ICOWhitelistApplication, error) {
	_, err := exec.ExecContext(ctx, `
		UPDATE ico_whitelist_applications
		SET email = ?,
		    marketing_consent = ?,
		    marketing_consent_version = ?,
		    marketing_consent_text = ?,
		    marketing_consented_at = ?,
		    privacy_notice_version = ?,
		    privacy_accepted_at = ?,
		    confirmation_token_hash = ?,
		    confirmation_expires_at = ?,
		    unsubscribe_token_hash = ?,
		    withdraw_token_hash = ?,
		    source = ?,
		    locale = ?,
		    referral_code = ?,
		    campaign = ?,
		    email_fingerprint = ?,
		    updated_at = ?
		WHERE id = ?
		  AND status IN (?, ?)
	`,
		params.Email,
		params.MarketingConsent,
		params.MarketingConsentVersion,
		params.MarketingConsentText,
		params.MarketingConsentedAt,
		params.PrivacyNoticeVersion,
		params.PrivacyAcceptedAt,
		params.ConfirmationTokenHash,
		params.ConfirmationExpiresAt,
		params.UnsubscribeTokenHash,
		params.WithdrawTokenHash,
		params.Source,
		params.Locale,
		params.ReferralCode,
		params.Campaign,
		params.EmailFingerprint,
		time.Now().UTC(),
		id,
		models.ICOWhitelistStatusPendingConfirmation,
		models.ICOWhitelistStatusConfirmed,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to refresh whitelist application: %w", err)
	}
	return r.getByID(ctx, exec, id)
}

func (r *ICOWhitelistRepository) getByID(ctx context.Context, exec QueryExecutor, id int64) (*models.ICOWhitelistApplication, error) {
	row := exec.QueryRowContext(ctx, `
		SELECT id, email, normalized_email, status, marketing_consent, marketing_consent_version,
		       marketing_consent_text, marketing_consented_at, marketing_confirmed_at,
		       privacy_notice_version, privacy_accepted_at, confirmation_token_hash,
		       confirmation_expires_at, unsubscribe_token_hash, withdraw_token_hash,
		       email_confirmed_at, reviewed_at, reviewed_by,
		       approved_at, rejected_at, rejection_reason, unsubscribed_at, withdrawn_at,
		       source, locale, referral_code, campaign, email_fingerprint, created_at, updated_at
		FROM ico_whitelist_applications
		WHERE id = ?
		LIMIT 1
	`, id)
	return scanICOWhitelistApplication(row)
}

func (r *ICOWhitelistRepository) createConsentEvent(ctx context.Context, exec QueryExecutor, params ICOConsentEventParams) error {
	_, err := exec.ExecContext(ctx, `
		INSERT INTO ico_consent_events (
			whitelist_application_id, event_type, policy_version, consent_text, source, metadata_json, occurred_at
		)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`,
		params.WhitelistApplicationID,
		params.EventType,
		params.PolicyVersion,
		params.ConsentText,
		params.Source,
		params.MetadataJSON,
		params.OccurredAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create whitelist consent event: %w", err)
	}
	return nil
}

func (r *ICOWhitelistRepository) createOutboxEntryIfMissing(ctx context.Context, exec QueryExecutor, params ICOEmailOutboxParams) error {
	if params.WhitelistApplicationID == nil {
		return fmt.Errorf("whitelist application id is required for outbox entry")
	}
	_, err := exec.ExecContext(ctx, `
		INSERT IGNORE INTO ico_email_outbox (
			whitelist_application_id, idempotency_key, email_type, recipient_email,
			recipient_fingerprint, subject, template_key, payload_encrypted, scheduled_at
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
	`,
		*params.WhitelistApplicationID,
		params.IdempotencyKey,
		params.EmailType,
		params.RecipientEmail,
		params.RecipientFingerprint,
		params.Subject,
		params.TemplateKey,
		params.PayloadEncrypted,
		params.ScheduledAt,
	)
	if err != nil {
		return fmt.Errorf("failed to enqueue whitelist email: %w", err)
	}
	return nil
}

func (r *ICOWhitelistRepository) ListPendingOutbox(ctx context.Context, limit int, now time.Time) ([]models.ICOEmailOutboxEntry, error) {
	if limit <= 0 || limit > 100 {
		limit = 25
	}
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, whitelist_application_id, idempotency_key, email_type, recipient_email,
		       recipient_fingerprint, subject, template_key, payload_encrypted, status,
		       attempts, max_attempts, last_error, provider_message_id, scheduled_at,
		       sent_at, created_at, updated_at
		FROM ico_email_outbox
		WHERE status IN ('pending', 'retry')
		  AND scheduled_at <= ?
		  AND attempts < max_attempts
		ORDER BY scheduled_at ASC, id ASC
		LIMIT ?
	`, now, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to list pending ICO email outbox: %w", err)
	}
	defer func() { _ = rows.Close() }()

	var entries []models.ICOEmailOutboxEntry
	for rows.Next() {
		entry, scanErr := scanICOEmailOutboxEntry(rows)
		if scanErr != nil {
			return nil, scanErr
		}
		entries = append(entries, *entry)
	}
	return entries, rows.Err()
}

func (r *ICOWhitelistRepository) MarkOutboxSent(ctx context.Context, id int64, providerMessageID string, now time.Time) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE ico_email_outbox
		SET status = 'sent',
		    attempts = attempts + 1,
		    provider_message_id = ?,
		    sent_at = ?,
		    updated_at = ?
		WHERE id = ?
	`, providerMessageID, now, now, id)
	if err != nil {
		return fmt.Errorf("failed to mark ICO email outbox sent: %w", err)
	}
	return nil
}

func (r *ICOWhitelistRepository) MarkOutboxFailed(ctx context.Context, id int64, retry bool, message string, now time.Time) error {
	status := "failed"
	if retry {
		status = "retry"
	}
	_, err := r.db.ExecContext(ctx, `
		UPDATE ico_email_outbox
		SET status = ?,
		    attempts = attempts + 1,
		    last_error = ?,
		    scheduled_at = CASE WHEN ? THEN DATE_ADD(?, INTERVAL 15 MINUTE) ELSE scheduled_at END,
		    updated_at = ?
		WHERE id = ?
	`, status, message, retry, now, now, id)
	if err != nil {
		return fmt.Errorf("failed to mark ICO email outbox failed: %w", err)
	}
	return nil
}

func (r *ICOWhitelistRepository) ListApplications(ctx context.Context, filter ICOWhitelistListFilter) ([]models.ICOWhitelistApplication, error) {
	limit := filter.Limit
	if limit <= 0 || limit > 200 {
		limit = 50
	}
	query := `
		SELECT id, email, normalized_email, status, marketing_consent, marketing_consent_version,
		       marketing_consent_text, marketing_consented_at, marketing_confirmed_at,
		       privacy_notice_version, privacy_accepted_at, confirmation_token_hash,
		       confirmation_expires_at, unsubscribe_token_hash, withdraw_token_hash,
		       email_confirmed_at, reviewed_at, reviewed_by, approved_at, rejected_at,
		       rejection_reason, unsubscribed_at, withdrawn_at, source, locale, referral_code,
		       campaign, email_fingerprint, created_at, updated_at
		FROM ico_whitelist_applications`
	args := []interface{}{}
	if filter.Status != "" {
		query += ` WHERE status = ?`
		args = append(args, filter.Status)
	}
	query += ` ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?`
	args = append(args, limit, maxInt(filter.Offset, 0))

	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list whitelist applications: %w", err)
	}
	defer func() { _ = rows.Close() }()
	var applications []models.ICOWhitelistApplication
	for rows.Next() {
		app, scanErr := scanICOWhitelistApplication(rows)
		if scanErr != nil {
			return nil, scanErr
		}
		applications = append(applications, *app)
	}
	return applications, rows.Err()
}

func (r *ICOWhitelistRepository) UpsertSuppression(ctx context.Context, normalizedEmail, fingerprint, reason, source string) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO ico_marketing_suppressions (normalized_email, email_fingerprint, reason, source, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?)
		ON DUPLICATE KEY UPDATE
			reason = VALUES(reason),
			source = VALUES(source),
			updated_at = VALUES(updated_at)
	`, normalizedEmail, fingerprint, reason, source, time.Now().UTC(), time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to upsert ICO suppression: %w", err)
	}
	return nil
}

func (r *ICOWhitelistRepository) RecordEmailEvent(ctx context.Context, providerMessageID, eventType, recipientFingerprint string, providerTimestamp *time.Time, eventHash, metadataJSON string) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT IGNORE INTO ico_email_events (
			provider_message_id, event_type, recipient_fingerprint, provider_timestamp, event_hash, metadata_json, created_at
		)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, providerMessageID, eventType, recipientFingerprint, providerTimestamp, eventHash, metadataJSON, time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to record ICO email event: %w", err)
	}
	return nil
}

func scanICOWhitelistApplication(scanner interface {
	Scan(dest ...interface{}) error
}) (*models.ICOWhitelistApplication, error) {
	var (
		app                models.ICOWhitelistApplication
		marketingConsented sql.NullTime
		marketingConfirmed sql.NullTime
		emailConfirmed     sql.NullTime
		reviewedAt         sql.NullTime
		reviewedBy         sql.NullInt64
		approvedAt         sql.NullTime
		rejectedAt         sql.NullTime
		unsubscribedAt     sql.NullTime
		withdrawnAt        sql.NullTime
	)
	err := scanner.Scan(
		&app.ID,
		&app.Email,
		&app.NormalizedEmail,
		&app.Status,
		&app.MarketingConsent,
		&app.MarketingConsentVersion,
		&app.MarketingConsentText,
		&marketingConsented,
		&marketingConfirmed,
		&app.PrivacyNoticeVersion,
		&app.PrivacyAcceptedAt,
		&app.ConfirmationTokenHash,
		&app.ConfirmationExpiresAt,
		&app.UnsubscribeTokenHash,
		&app.WithdrawTokenHash,
		&emailConfirmed,
		&reviewedAt,
		&reviewedBy,
		&approvedAt,
		&rejectedAt,
		&app.RejectionReason,
		&unsubscribedAt,
		&withdrawnAt,
		&app.Source,
		&app.Locale,
		&app.ReferralCode,
		&app.Campaign,
		&app.EmailFingerprint,
		&app.CreatedAt,
		&app.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to scan whitelist application: %w", err)
	}
	if marketingConsented.Valid {
		app.MarketingConsentedAt = &marketingConsented.Time
	}
	if marketingConfirmed.Valid {
		app.MarketingConfirmedAt = &marketingConfirmed.Time
	}
	if emailConfirmed.Valid {
		app.EmailConfirmedAt = &emailConfirmed.Time
	}
	if reviewedAt.Valid {
		app.ReviewedAt = &reviewedAt.Time
	}
	if reviewedBy.Valid {
		app.ReviewedBy = &reviewedBy.Int64
	}
	if approvedAt.Valid {
		app.ApprovedAt = &approvedAt.Time
	}
	if rejectedAt.Valid {
		app.RejectedAt = &rejectedAt.Time
	}
	if unsubscribedAt.Valid {
		app.UnsubscribedAt = &unsubscribedAt.Time
	}
	if withdrawnAt.Valid {
		app.WithdrawnAt = &withdrawnAt.Time
	}
	return &app, nil
}

func scanICOEmailOutboxEntry(scanner interface {
	Scan(dest ...interface{}) error
}) (*models.ICOEmailOutboxEntry, error) {
	var (
		entry                models.ICOEmailOutboxEntry
		whitelistApplication sql.NullInt64
		sentAt               sql.NullTime
	)
	err := scanner.Scan(
		&entry.ID,
		&whitelistApplication,
		&entry.IdempotencyKey,
		&entry.EmailType,
		&entry.RecipientEmail,
		&entry.RecipientFingerprint,
		&entry.Subject,
		&entry.TemplateKey,
		&entry.PayloadEncrypted,
		&entry.Status,
		&entry.Attempts,
		&entry.MaxAttempts,
		&entry.LastError,
		&entry.ProviderMessageID,
		&entry.ScheduledAt,
		&sentAt,
		&entry.CreatedAt,
		&entry.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to scan ICO email outbox entry: %w", err)
	}
	if whitelistApplication.Valid {
		entry.WhitelistApplicationID = &whitelistApplication.Int64
	}
	if sentAt.Valid {
		entry.SentAt = &sentAt.Time
	}
	return &entry, nil
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
