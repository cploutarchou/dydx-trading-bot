package models

import "time"

const (
	ICOWhitelistStatusPendingConfirmation = "pending_confirmation"
	ICOWhitelistStatusConfirmed           = "confirmed"
	ICOWhitelistStatusUnderReview         = "under_review"
	ICOWhitelistStatusApproved            = "approved"
	ICOWhitelistStatusRejected            = "rejected"
	ICOWhitelistStatusWaitlisted          = "waitlisted"
	ICOWhitelistStatusWithdrawn           = "withdrawn"
)

type ICOWhitelistApplication struct {
	ID                      int64      `db:"id" json:"id"`
	Email                   string     `db:"email" json:"email"`
	NormalizedEmail         string     `db:"normalized_email" json:"normalized_email"`
	Status                  string     `db:"status" json:"status"`
	MarketingConsent        bool       `db:"marketing_consent" json:"marketing_consent"`
	MarketingConsentVersion string     `db:"marketing_consent_version" json:"marketing_consent_version"`
	MarketingConsentText    string     `db:"marketing_consent_text" json:"-"`
	MarketingConsentedAt    *time.Time `db:"marketing_consented_at" json:"marketing_consented_at,omitempty"`
	MarketingConfirmedAt    *time.Time `db:"marketing_confirmed_at" json:"marketing_confirmed_at,omitempty"`
	PrivacyNoticeVersion    string     `db:"privacy_notice_version" json:"privacy_notice_version"`
	PrivacyAcceptedAt       time.Time  `db:"privacy_accepted_at" json:"privacy_accepted_at"`
	ConfirmationTokenHash   string     `db:"confirmation_token_hash" json:"-"`
	ConfirmationExpiresAt   time.Time  `db:"confirmation_expires_at" json:"confirmation_expires_at"`
	UnsubscribeTokenHash    string     `db:"unsubscribe_token_hash" json:"-"`
	WithdrawTokenHash       string     `db:"withdraw_token_hash" json:"-"`
	EmailConfirmedAt        *time.Time `db:"email_confirmed_at" json:"email_confirmed_at,omitempty"`
	ReviewedAt              *time.Time `db:"reviewed_at" json:"reviewed_at,omitempty"`
	ReviewedBy              *int64     `db:"reviewed_by" json:"reviewed_by,omitempty"`
	ApprovedAt              *time.Time `db:"approved_at" json:"approved_at,omitempty"`
	RejectedAt              *time.Time `db:"rejected_at" json:"rejected_at,omitempty"`
	RejectionReason         string     `db:"rejection_reason" json:"rejection_reason,omitempty"`
	UnsubscribedAt          *time.Time `db:"unsubscribed_at" json:"unsubscribed_at,omitempty"`
	WithdrawnAt             *time.Time `db:"withdrawn_at" json:"withdrawn_at,omitempty"`
	Source                  string     `db:"source" json:"source"`
	Locale                  string     `db:"locale" json:"locale,omitempty"`
	ReferralCode            string     `db:"referral_code" json:"referral_code,omitempty"`
	Campaign                string     `db:"campaign" json:"campaign,omitempty"`
	EmailFingerprint        string     `db:"email_fingerprint" json:"-"`
	CreatedAt               time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt               time.Time  `db:"updated_at" json:"updated_at"`
}

type ICOConsentEvent struct {
	ID                     int64     `db:"id" json:"id"`
	WhitelistApplicationID int64     `db:"whitelist_application_id" json:"whitelist_application_id"`
	EventType              string    `db:"event_type" json:"event_type"`
	PolicyVersion          string    `db:"policy_version" json:"policy_version"`
	ConsentText            string    `db:"consent_text" json:"-"`
	Source                 string    `db:"source" json:"source"`
	MetadataJSON           string    `db:"metadata_json" json:"metadata_json"`
	OccurredAt             time.Time `db:"occurred_at" json:"occurred_at"`
}

type ICOEmailOutboxEntry struct {
	ID                     int64      `db:"id" json:"id"`
	WhitelistApplicationID *int64     `db:"whitelist_application_id" json:"whitelist_application_id,omitempty"`
	IdempotencyKey         string     `db:"idempotency_key" json:"idempotency_key"`
	EmailType              string     `db:"email_type" json:"email_type"`
	RecipientEmail         string     `db:"recipient_email" json:"recipient_email"`
	RecipientFingerprint   string     `db:"recipient_fingerprint" json:"-"`
	Subject                string     `db:"subject" json:"subject"`
	TemplateKey            string     `db:"template_key" json:"template_key"`
	PayloadEncrypted       string     `db:"payload_encrypted" json:"-"`
	Status                 string     `db:"status" json:"status"`
	Attempts               int        `db:"attempts" json:"attempts"`
	MaxAttempts            int        `db:"max_attempts" json:"max_attempts"`
	LastError              string     `db:"last_error" json:"last_error,omitempty"`
	ProviderMessageID      string     `db:"provider_message_id" json:"provider_message_id,omitempty"`
	ScheduledAt            time.Time  `db:"scheduled_at" json:"scheduled_at"`
	SentAt                 *time.Time `db:"sent_at" json:"sent_at,omitempty"`
	CreatedAt              time.Time  `db:"created_at" json:"created_at"`
	UpdatedAt              time.Time  `db:"updated_at" json:"updated_at"`
}

type ICOEmailEvent struct {
	ID                   int64      `db:"id" json:"id"`
	OutboxID             *int64     `db:"outbox_id" json:"outbox_id,omitempty"`
	ProviderMessageID    string     `db:"provider_message_id" json:"provider_message_id"`
	EventType            string     `db:"event_type" json:"event_type"`
	RecipientFingerprint string     `db:"recipient_fingerprint" json:"-"`
	ProviderTimestamp    *time.Time `db:"provider_timestamp" json:"provider_timestamp,omitempty"`
	EventHash            string     `db:"event_hash" json:"event_hash"`
	MetadataJSON         string     `db:"metadata_json" json:"metadata_json"`
	CreatedAt            time.Time  `db:"created_at" json:"created_at"`
}

type ICOMarketingSuppression struct {
	ID               int64     `db:"id" json:"id"`
	NormalizedEmail  string    `db:"normalized_email" json:"normalized_email"`
	EmailFingerprint string    `db:"email_fingerprint" json:"-"`
	Reason           string    `db:"reason" json:"reason"`
	Source           string    `db:"source" json:"source"`
	CreatedAt        time.Time `db:"created_at" json:"created_at"`
	UpdatedAt        time.Time `db:"updated_at" json:"updated_at"`
}
