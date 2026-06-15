package services

import (
	"context"
	"errors"
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

var ErrICOReadinessPublishBlocked = errors.New("ICO production readiness has unresolved blockers")

type ICOReadinessService struct {
	repo *repository.ICOReadinessRepository
}

func NewICOReadinessService(repo *repository.ICOReadinessRepository) *ICOReadinessService {
	return &ICOReadinessService{repo: repo}
}

type ICOReadinessSnapshot struct {
	Config   *models.ICOProductionReadiness `json:"config"`
	Ready    bool                           `json:"ready"`
	Blockers []string                       `json:"blockers"`
}

func (s *ICOReadinessService) Get(ctx context.Context) (*ICOReadinessSnapshot, error) {
	config, err := s.repo.Get(ctx)
	if err != nil {
		return nil, err
	}
	return BuildICOReadinessSnapshot(config), nil
}

func (s *ICOReadinessService) Update(ctx context.Context, params repository.ICOReadinessUpdateParams, updatedBy *int) (*ICOReadinessSnapshot, error) {
	candidate := &models.ICOProductionReadiness{
		TokenomicsAllocationFinalized: params.TokenomicsAllocationFinalized,
		TokenomicsAllocationNotes:     params.TokenomicsAllocationNotes,
		VestingScheduleFinalized:      params.VestingScheduleFinalized,
		VestingScheduleNotes:          params.VestingScheduleNotes,
		TokenPrice:                    params.TokenPrice,
		AcceptedCurrencies:            params.AcceptedCurrencies,
		SmartContractAddress:          params.SmartContractAddress,
		SmartContractAuditStatus:      params.SmartContractAuditStatus,
		SmartContractAuditURL:         params.SmartContractAuditURL,
		KYCProvider:                   params.KYCProvider,
		KYCPolicyURL:                  params.KYCPolicyURL,
		RestrictedJurisdictions:       params.RestrictedJurisdictions,
		LegalEntityName:               params.LegalEntityName,
		ControllerContact:             params.ControllerContact,
		ParticipationTermsURL:         params.ParticipationTermsURL,
		PrivacyNoticeURL:              params.PrivacyNoticeURL,
		RiskDisclosureURL:             params.RiskDisclosureURL,
		MailgunDNSVerified:            params.MailgunDNSVerified,
		SPFVerified:                   params.SPFVerified,
		DKIMVerified:                  params.DKIMVerified,
		DMARCVerified:                 params.DMARCVerified,
		ProductionSmokeTestPassed:     params.ProductionSmokeTestPassed,
		MonitoringConfigured:          params.MonitoringConfigured,
		AlertingConfigured:            params.AlertingConfigured,
		BackupsConfigured:             params.BackupsConfigured,
		BusinessApproved:              params.BusinessApproved,
		LegalApproved:                 params.LegalApproved,
		TechnicalApproved:             params.TechnicalApproved,
		Published:                     params.Published,
	}
	candidateSnapshot := BuildICOReadinessSnapshot(candidate)
	if params.Published && !candidateSnapshot.Ready {
		return candidateSnapshot, ErrICOReadinessPublishBlocked
	}

	config, err := s.repo.Update(ctx, params, updatedBy)
	if err != nil {
		return nil, err
	}
	return BuildICOReadinessSnapshot(config), nil
}

func BuildICOReadinessSnapshot(config *models.ICOProductionReadiness) *ICOReadinessSnapshot {
	blockers := make([]string, 0, 24)
	requireBool := func(ok bool, label string) {
		if !ok {
			blockers = append(blockers, label)
		}
	}
	requireText := func(value string, label string) {
		if strings.TrimSpace(value) == "" {
			blockers = append(blockers, label)
		}
	}

	requireBool(config.TokenomicsAllocationFinalized, "Final tokenomics allocation is not approved")
	requireText(config.TokenomicsAllocationNotes, "Final allocation notes are missing")
	requireBool(config.VestingScheduleFinalized, "Final vesting schedule is not approved")
	requireText(config.VestingScheduleNotes, "Final vesting and unlock notes are missing")
	requireText(config.TokenPrice, "Token price is missing")
	requireText(config.AcceptedCurrencies, "Accepted currencies are missing")
	requireText(config.SmartContractAddress, "Smart-contract address is missing")
	requireText(config.SmartContractAuditStatus, "Smart-contract audit status is missing")
	requireText(config.SmartContractAuditURL, "Smart-contract audit link is missing")
	requireText(config.KYCProvider, "KYC/AML provider is missing")
	requireText(config.KYCPolicyURL, "KYC/AML policy link is missing")
	requireText(config.RestrictedJurisdictions, "Restricted jurisdictions are missing")
	requireText(config.LegalEntityName, "Final legal entity/controller name is missing")
	requireText(config.ControllerContact, "Controller contact is missing")
	requireText(config.ParticipationTermsURL, "Final participation terms link is missing")
	requireText(config.PrivacyNoticeURL, "Final privacy notice link is missing")
	requireText(config.RiskDisclosureURL, "Final risk disclosure link is missing")
	requireBool(config.MailgunDNSVerified, "Mailgun DNS is not verified")
	requireBool(config.SPFVerified, "SPF is not verified")
	requireBool(config.DKIMVerified, "DKIM is not verified")
	requireBool(config.DMARCVerified, "DMARC is not verified")
	requireBool(config.ProductionSmokeTestPassed, "Production smoke test has not passed")
	requireBool(config.MonitoringConfigured, "Monitoring is not configured")
	requireBool(config.AlertingConfigured, "Alerting is not configured")
	requireBool(config.BackupsConfigured, "Backups are not configured")
	requireBool(config.BusinessApproved, "Business approval is missing")
	requireBool(config.LegalApproved, "Legal approval is missing")
	requireBool(config.TechnicalApproved, "Technical approval is missing")

	return &ICOReadinessSnapshot{
		Config:   config,
		Ready:    len(blockers) == 0,
		Blockers: blockers,
	}
}
