package models

import "time"

type ICOProductionReadiness struct {
	ID                            int       `db:"id" json:"id"`
	TokenomicsAllocationFinalized bool      `db:"tokenomics_allocation_finalized" json:"tokenomics_allocation_finalized"`
	TokenomicsAllocationNotes     string    `db:"tokenomics_allocation_notes" json:"tokenomics_allocation_notes"`
	VestingScheduleFinalized      bool      `db:"vesting_schedule_finalized" json:"vesting_schedule_finalized"`
	VestingScheduleNotes          string    `db:"vesting_schedule_notes" json:"vesting_schedule_notes"`
	TokenPrice                    string    `db:"token_price" json:"token_price"`
	AcceptedCurrencies            string    `db:"accepted_currencies" json:"accepted_currencies"`
	SmartContractAddress          string    `db:"smart_contract_address" json:"smart_contract_address"`
	SmartContractAuditStatus      string    `db:"smart_contract_audit_status" json:"smart_contract_audit_status"`
	SmartContractAuditURL         string    `db:"smart_contract_audit_url" json:"smart_contract_audit_url"`
	KYCProvider                   string    `db:"kyc_provider" json:"kyc_provider"`
	KYCPolicyURL                  string    `db:"kyc_policy_url" json:"kyc_policy_url"`
	RestrictedJurisdictions       string    `db:"restricted_jurisdictions" json:"restricted_jurisdictions"`
	LegalEntityName               string    `db:"legal_entity_name" json:"legal_entity_name"`
	ControllerContact             string    `db:"controller_contact" json:"controller_contact"`
	ParticipationTermsURL         string    `db:"participation_terms_url" json:"participation_terms_url"`
	PrivacyNoticeURL              string    `db:"privacy_notice_url" json:"privacy_notice_url"`
	RiskDisclosureURL             string    `db:"risk_disclosure_url" json:"risk_disclosure_url"`
	MailgunDNSVerified            bool      `db:"mailgun_dns_verified" json:"mailgun_dns_verified"`
	SPFVerified                   bool      `db:"spf_verified" json:"spf_verified"`
	DKIMVerified                  bool      `db:"dkim_verified" json:"dkim_verified"`
	DMARCVerified                 bool      `db:"dmarc_verified" json:"dmarc_verified"`
	ProductionSmokeTestPassed     bool      `db:"production_smoke_test_passed" json:"production_smoke_test_passed"`
	MonitoringConfigured          bool      `db:"monitoring_configured" json:"monitoring_configured"`
	AlertingConfigured            bool      `db:"alerting_configured" json:"alerting_configured"`
	BackupsConfigured             bool      `db:"backups_configured" json:"backups_configured"`
	BusinessApproved              bool      `db:"business_approved" json:"business_approved"`
	LegalApproved                 bool      `db:"legal_approved" json:"legal_approved"`
	TechnicalApproved             bool      `db:"technical_approved" json:"technical_approved"`
	Published                     bool      `db:"published" json:"published"`
	UpdatedBy                     *int      `db:"updated_by" json:"updated_by,omitempty"`
	CreatedAt                     time.Time `db:"created_at" json:"created_at"`
	UpdatedAt                     time.Time `db:"updated_at" json:"updated_at"`
}
