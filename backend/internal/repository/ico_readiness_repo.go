package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type ICOReadinessRepository struct {
	db *sql.DB
}

func NewICOReadinessRepository(db *sql.DB) *ICOReadinessRepository {
	return &ICOReadinessRepository{db: db}
}

type ICOReadinessUpdateParams struct {
	TokenomicsAllocationFinalized bool
	TokenomicsAllocationNotes     string
	VestingScheduleFinalized      bool
	VestingScheduleNotes          string
	TokenPrice                    string
	AcceptedCurrencies            string
	SmartContractAddress          string
	SmartContractAuditStatus      string
	SmartContractAuditURL         string
	KYCProvider                   string
	KYCPolicyURL                  string
	RestrictedJurisdictions       string
	LegalEntityName               string
	ControllerContact             string
	ParticipationTermsURL         string
	PrivacyNoticeURL              string
	RiskDisclosureURL             string
	MailgunDNSVerified            bool
	SPFVerified                   bool
	DKIMVerified                  bool
	DMARCVerified                 bool
	ProductionSmokeTestPassed     bool
	MonitoringConfigured          bool
	AlertingConfigured            bool
	BackupsConfigured             bool
	BusinessApproved              bool
	LegalApproved                 bool
	TechnicalApproved             bool
	Published                     bool
}

func (r *ICOReadinessRepository) Get(ctx context.Context) (*models.ICOProductionReadiness, error) {
	if err := r.ensureSingleton(ctx); err != nil {
		return nil, err
	}
	row := r.db.QueryRowContext(ctx, readinessSelectSQL()+` WHERE id = 1 LIMIT 1`)
	readiness, err := scanICOProductionReadiness(row)
	if err != nil {
		return nil, err
	}
	return readiness, nil
}

func (r *ICOReadinessRepository) Update(ctx context.Context, params ICOReadinessUpdateParams, updatedBy *int) (*models.ICOProductionReadiness, error) {
	if err := r.ensureSingleton(ctx); err != nil {
		return nil, err
	}
	_, err := r.db.ExecContext(ctx, `
		UPDATE ico_production_readiness
		SET tokenomics_allocation_finalized = ?,
		    tokenomics_allocation_notes = ?,
		    vesting_schedule_finalized = ?,
		    vesting_schedule_notes = ?,
		    token_price = ?,
		    accepted_currencies = ?,
		    smart_contract_address = ?,
		    smart_contract_audit_status = ?,
		    smart_contract_audit_url = ?,
		    kyc_provider = ?,
		    kyc_policy_url = ?,
		    restricted_jurisdictions = ?,
		    legal_entity_name = ?,
		    controller_contact = ?,
		    participation_terms_url = ?,
		    privacy_notice_url = ?,
		    risk_disclosure_url = ?,
		    mailgun_dns_verified = ?,
		    spf_verified = ?,
		    dkim_verified = ?,
		    dmarc_verified = ?,
		    production_smoke_test_passed = ?,
		    monitoring_configured = ?,
		    alerting_configured = ?,
		    backups_configured = ?,
		    business_approved = ?,
		    legal_approved = ?,
		    technical_approved = ?,
		    published = ?,
		    updated_by = ?,
		    updated_at = ?
		WHERE id = 1
	`,
		params.TokenomicsAllocationFinalized,
		params.TokenomicsAllocationNotes,
		params.VestingScheduleFinalized,
		params.VestingScheduleNotes,
		params.TokenPrice,
		params.AcceptedCurrencies,
		params.SmartContractAddress,
		params.SmartContractAuditStatus,
		params.SmartContractAuditURL,
		params.KYCProvider,
		params.KYCPolicyURL,
		params.RestrictedJurisdictions,
		params.LegalEntityName,
		params.ControllerContact,
		params.ParticipationTermsURL,
		params.PrivacyNoticeURL,
		params.RiskDisclosureURL,
		params.MailgunDNSVerified,
		params.SPFVerified,
		params.DKIMVerified,
		params.DMARCVerified,
		params.ProductionSmokeTestPassed,
		params.MonitoringConfigured,
		params.AlertingConfigured,
		params.BackupsConfigured,
		params.BusinessApproved,
		params.LegalApproved,
		params.TechnicalApproved,
		params.Published,
		updatedBy,
		time.Now().UTC(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to update ICO production readiness: %w", err)
	}
	return r.Get(ctx)
}

func (r *ICOReadinessRepository) ensureSingleton(ctx context.Context) error {
	_, err := r.db.ExecContext(ctx, `INSERT IGNORE INTO ico_production_readiness (id) VALUES (1)`)
	if err != nil {
		return fmt.Errorf("failed to ensure ICO readiness row: %w", err)
	}
	return nil
}

func readinessSelectSQL() string {
	return `
		SELECT id, tokenomics_allocation_finalized, tokenomics_allocation_notes,
		       vesting_schedule_finalized, vesting_schedule_notes, token_price,
		       accepted_currencies, smart_contract_address, smart_contract_audit_status,
		       smart_contract_audit_url, kyc_provider, kyc_policy_url,
		       restricted_jurisdictions, legal_entity_name, controller_contact,
		       participation_terms_url, privacy_notice_url, risk_disclosure_url,
		       mailgun_dns_verified, spf_verified, dkim_verified, dmarc_verified,
		       production_smoke_test_passed, monitoring_configured, alerting_configured,
		       backups_configured, business_approved, legal_approved, technical_approved,
		       published, updated_by, created_at, updated_at
		FROM ico_production_readiness`
}

func scanICOProductionReadiness(scanner interface {
	Scan(dest ...interface{}) error
}) (*models.ICOProductionReadiness, error) {
	var readiness models.ICOProductionReadiness
	var updatedBy sql.NullInt64
	err := scanner.Scan(
		&readiness.ID,
		&readiness.TokenomicsAllocationFinalized,
		&readiness.TokenomicsAllocationNotes,
		&readiness.VestingScheduleFinalized,
		&readiness.VestingScheduleNotes,
		&readiness.TokenPrice,
		&readiness.AcceptedCurrencies,
		&readiness.SmartContractAddress,
		&readiness.SmartContractAuditStatus,
		&readiness.SmartContractAuditURL,
		&readiness.KYCProvider,
		&readiness.KYCPolicyURL,
		&readiness.RestrictedJurisdictions,
		&readiness.LegalEntityName,
		&readiness.ControllerContact,
		&readiness.ParticipationTermsURL,
		&readiness.PrivacyNoticeURL,
		&readiness.RiskDisclosureURL,
		&readiness.MailgunDNSVerified,
		&readiness.SPFVerified,
		&readiness.DKIMVerified,
		&readiness.DMARCVerified,
		&readiness.ProductionSmokeTestPassed,
		&readiness.MonitoringConfigured,
		&readiness.AlertingConfigured,
		&readiness.BackupsConfigured,
		&readiness.BusinessApproved,
		&readiness.LegalApproved,
		&readiness.TechnicalApproved,
		&readiness.Published,
		&updatedBy,
		&readiness.CreatedAt,
		&readiness.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to scan ICO production readiness: %w", err)
	}
	if updatedBy.Valid {
		value := int(updatedBy.Int64)
		readiness.UpdatedBy = &value
	}
	return &readiness, nil
}
