import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, MailCheck, RefreshCcw, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import api, {
  classifyApiError,
  ICOProductionReadiness,
  ICOProductionReadinessUpdate,
} from '../api';
import { PageContainer } from '../components/PageContainer';
import {
  EmptyState,
  InlineNotice,
  PlatformPageHeader,
  PlatformPanel,
  PlatformStatCard,
} from '../components/ui/PlatformUI';

export const AdminICOPage = () => {
  const queryClient = useQueryClient();
  const whitelistQuery = useQuery({
    queryKey: ['admin', 'ico', 'whitelist'],
    queryFn: async () => (await api.listICOWhitelistApplications()).data,
    staleTime: 15_000,
  });

  const processOutboxMutation = useMutation({
    mutationFn: async () => (await api.processICOEmailOutbox()).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'ico'] });
    },
  });
  const readinessQuery = useQuery({
    queryKey: ['admin', 'ico', 'readiness'],
    queryFn: async () => (await api.getICOProductionReadiness()).data,
    staleTime: 15_000,
  });

  const applications = whitelistQuery.data?.applications ?? [];
  const confirmed = applications.filter((row) => row.email_confirmed).length;
  const marketing = applications.filter((row) => row.marketing_confirmed && !row.unsubscribed).length;
  const withdrawn = applications.filter((row) => row.withdrawn).length;
  const readiness = readinessQuery.data;
  const [readinessForm, setReadinessForm] = useState<ICOProductionReadinessUpdate | null>(null);

  useEffect(() => {
    if (readiness?.config) {
      setReadinessForm(toReadinessUpdate(readiness.config));
    }
  }, [readiness?.config]);

  const readinessCompleteCount = useMemo(() => {
    if (!readiness) return 0;
    return readinessChecklistLabels.length - readiness.blockers.length;
  }, [readiness]);

  const readinessMutation = useMutation({
    mutationFn: async (payload: ICOProductionReadinessUpdate) =>
      (await api.updateICOProductionReadiness(payload)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'ico', 'readiness'] });
    },
  });

  const readinessError = readinessMutation.error
    ? classifyApiError(readinessMutation.error).message
    : null;

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker="ICO administration"
        title="Whitelist and delivery controls"
        description="Review public whitelist requests, consent state, and transactional email processing without exposing applicant account data."
        icon={ShieldCheck}
        actions={[
          {
            label: processOutboxMutation.isPending ? 'Processing...' : 'Process email outbox',
            onClick: () => processOutboxMutation.mutate(),
            variant: 'secondary',
          },
        ]}
      />

      <InlineNotice
        tone={readiness?.ready ? 'success' : 'warning'}
        title={readiness?.ready ? 'ICO production gate clear' : 'Not production ready'}
        description={
          readiness?.ready
            ? 'All configured legal, token, Mailgun, and operations checks are recorded as complete.'
            : 'Token-sale, tokenomics, legal, jurisdiction, KYC, smart-contract, Mailgun DNS, and operations checks must be completed before publication.'
        }
      />

      <div className="grid gap-4 md:grid-cols-4">
        <PlatformStatCard label="Applications" value={applications.length} icon={ShieldCheck} tone="accent" loading={whitelistQuery.isLoading} />
        <PlatformStatCard label="Confirmed emails" value={confirmed} icon={MailCheck} tone="success" loading={whitelistQuery.isLoading} />
        <PlatformStatCard label="Marketing eligible" value={marketing} icon={MailCheck} tone="violet" loading={whitelistQuery.isLoading} />
        <PlatformStatCard label="Withdrawn" value={withdrawn} icon={RefreshCcw} tone="warning" loading={whitelistQuery.isLoading} />
      </div>

      <PlatformPanel
        title="Production readiness gate"
        description="Track final tokenomics, sale terms, Mailgun DNS, and operating checks. Publication is blocked by the API until every required item is complete."
        action={
          <span className="surface-label">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {readinessQuery.isLoading
              ? 'Loading'
              : `${readinessCompleteCount}/${readinessChecklistLabels.length} complete`}
          </span>
        }
      >
        {readinessQuery.isLoading || !readinessForm ? (
          <p className="text-sm text-slate-400">Loading readiness controls...</p>
        ) : (
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              readinessMutation.mutate(readinessForm);
            }}
          >
            {!readiness?.ready && (
              <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-4">
                <p className="text-sm font-semibold text-amber-100">
                  {readiness?.blockers.length ?? 0} blocker(s) remaining
                </p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {readiness?.blockers.slice(0, 12).map((blocker) => (
                    <p key={blocker} className="text-xs leading-5 text-amber-100/80">
                      {blocker}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {readinessError && (
              <InlineNotice
                tone="danger"
                title="Readiness update rejected"
                description={readinessError}
              />
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              {readinessTextFields.map((field) => (
                <label key={field.key} className="space-y-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {field.label}
                  </span>
                  {field.multiline ? (
                    <textarea
                      value={String(readinessForm[field.key])}
                      onChange={(event) =>
                        setReadinessForm({
                          ...readinessForm,
                          [field.key]: event.target.value,
                        })
                      }
                      rows={field.rows ?? 3}
                      className="min-h-24 w-full rounded-lg border border-slate-700/70 bg-slate-950/70 px-3 py-2.5 text-sm leading-6 text-white outline-none transition focus:border-cyan-400/70 focus:ring-2 focus:ring-cyan-400/20"
                      placeholder={field.placeholder}
                    />
                  ) : (
                    <input
                      value={String(readinessForm[field.key])}
                      onChange={(event) =>
                        setReadinessForm({
                          ...readinessForm,
                          [field.key]: event.target.value,
                        })
                      }
                      className="h-11 w-full rounded-lg border border-slate-700/70 bg-slate-950/70 px-3 text-sm text-white outline-none transition focus:border-cyan-400/70 focus:ring-2 focus:ring-cyan-400/20"
                      placeholder={field.placeholder}
                    />
                  )}
                </label>
              ))}
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {readinessBooleanFields.map((field) => (
                <label
                  key={field.key}
                  className="flex min-h-14 items-start gap-3 rounded-lg border border-slate-800 bg-slate-950/45 p-3 text-sm text-slate-300 transition hover:border-slate-700 hover:bg-slate-900/55"
                >
                  <input
                    type="checkbox"
                    checked={Boolean(readinessForm[field.key])}
                    onChange={(event) =>
                      setReadinessForm({
                        ...readinessForm,
                        [field.key]: event.target.checked,
                      })
                    }
                    className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400 focus:ring-cyan-400"
                  />
                  <span>{field.label}</span>
                </label>
              ))}
            </div>

            <div className="flex flex-col gap-3 border-t border-slate-800 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <label className="flex items-start gap-3 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={readinessForm.published}
                  onChange={(event) =>
                    setReadinessForm({
                      ...readinessForm,
                      published: event.target.checked,
                    })
                  }
                  className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400 focus:ring-cyan-400"
                />
                <span>Mark ICO briefing as publish-ready after all computed blockers are clear.</span>
              </label>
              <button
                type="submit"
                disabled={readinessMutation.isPending}
                className="platform-button platform-button-primary min-h-11 justify-center disabled:cursor-not-allowed disabled:opacity-60"
              >
                {readinessMutation.isPending ? 'Saving readiness...' : 'Save readiness gate'}
                <ShieldCheck className="h-4 w-4" />
              </button>
            </div>
          </form>
        )}
      </PlatformPanel>

      {processOutboxMutation.data && (
        <InlineNotice
          tone="success"
          title="Outbox processed"
          description={`${processOutboxMutation.data.processed ?? 0} pending email job(s) were checked.`}
        />
      )}

      <PlatformPanel title="Whitelist applications" description="List view masks applicant emails and keeps whitelist leads separate from platform users.">
        {whitelistQuery.isLoading ? (
          <p className="text-sm text-slate-400">Loading whitelist applications...</p>
        ) : applications.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="No whitelist requests" description="Submitted public whitelist requests will appear here after persistence succeeds." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Confirmed</th>
                  <th className="px-3 py-2">Marketing</th>
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-300">
                {applications.map((row) => (
                  <tr key={row.id}>
                    <td className="px-3 py-3 font-medium text-white">{row.email_masked}</td>
                    <td className="px-3 py-3">{row.status}</td>
                    <td className="px-3 py-3">{row.email_confirmed ? 'Yes' : 'No'}</td>
                    <td className="px-3 py-3">
                      {row.unsubscribed ? 'Unsubscribed' : row.marketing_confirmed ? 'Confirmed' : row.marketing_consent ? 'Pending' : 'No'}
                    </td>
                    <td className="px-3 py-3">{row.source}</td>
                    <td className="px-3 py-3">{new Date(row.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PlatformPanel>
    </PageContainer>
  );
};

export default AdminICOPage;

type ReadinessTextField = {
  key: keyof ICOProductionReadinessUpdate;
  label: string;
  placeholder: string;
  multiline?: boolean;
  rows?: number;
};

type ReadinessBooleanField = {
  key: keyof ICOProductionReadinessUpdate;
  label: string;
};

const readinessTextFields: ReadinessTextField[] = [
  {
    key: 'tokenomics_allocation_notes',
    label: 'Final tokenomics allocation',
    placeholder: 'Final allocation table, totaling 100%',
    multiline: true,
  },
  {
    key: 'vesting_schedule_notes',
    label: 'Final vesting and unlock schedule',
    placeholder: 'Vesting cliffs, cadence, unlock rules, treasury policy',
    multiline: true,
  },
  { key: 'token_price', label: 'Token price', placeholder: 'Example: 0.00 USDC per token' },
  {
    key: 'accepted_currencies',
    label: 'Accepted currencies',
    placeholder: 'Example: USDC only',
  },
  {
    key: 'smart_contract_address',
    label: 'Smart-contract address',
    placeholder: 'Final deployed contract address',
  },
  {
    key: 'smart_contract_audit_status',
    label: 'Audit status',
    placeholder: 'Auditor, report status, date',
  },
  {
    key: 'smart_contract_audit_url',
    label: 'Audit link',
    placeholder: 'https://...',
  },
  { key: 'kyc_provider', label: 'KYC/AML provider', placeholder: 'Provider name' },
  { key: 'kyc_policy_url', label: 'KYC/AML policy link', placeholder: 'https://...' },
  {
    key: 'restricted_jurisdictions',
    label: 'Restricted jurisdictions',
    placeholder: 'Final jurisdiction exclusions',
    multiline: true,
  },
  { key: 'legal_entity_name', label: 'Legal entity/controller', placeholder: 'Final entity name' },
  { key: 'controller_contact', label: 'Controller contact', placeholder: 'privacy@example.com' },
  {
    key: 'participation_terms_url',
    label: 'Participation terms',
    placeholder: '/ico/participation-terms or final hosted URL',
  },
  {
    key: 'privacy_notice_url',
    label: 'Privacy notice',
    placeholder: '/ico/privacy-notice or final hosted URL',
  },
  {
    key: 'risk_disclosure_url',
    label: 'Risk disclosure',
    placeholder: 'Final risk disclosure URL',
  },
];

const readinessBooleanFields: ReadinessBooleanField[] = [
  { key: 'tokenomics_allocation_finalized', label: 'Allocation approved' },
  { key: 'vesting_schedule_finalized', label: 'Vesting approved' },
  { key: 'mailgun_dns_verified', label: 'Mailgun DNS verified' },
  { key: 'spf_verified', label: 'SPF verified' },
  { key: 'dkim_verified', label: 'DKIM verified' },
  { key: 'dmarc_verified', label: 'DMARC verified' },
  { key: 'production_smoke_test_passed', label: 'Production smoke test passed' },
  { key: 'monitoring_configured', label: 'Monitoring configured' },
  { key: 'alerting_configured', label: 'Alerting configured' },
  { key: 'backups_configured', label: 'Backups configured' },
  { key: 'business_approved', label: 'Business approved' },
  { key: 'legal_approved', label: 'Legal approved' },
  { key: 'technical_approved', label: 'Technical approved' },
];

const readinessChecklistLabels = [...readinessTextFields, ...readinessBooleanFields];

const toReadinessUpdate = (config: ICOProductionReadiness): ICOProductionReadinessUpdate => ({
  tokenomics_allocation_finalized: config.tokenomics_allocation_finalized,
  tokenomics_allocation_notes: config.tokenomics_allocation_notes,
  vesting_schedule_finalized: config.vesting_schedule_finalized,
  vesting_schedule_notes: config.vesting_schedule_notes,
  token_price: config.token_price,
  accepted_currencies: config.accepted_currencies,
  smart_contract_address: config.smart_contract_address,
  smart_contract_audit_status: config.smart_contract_audit_status,
  smart_contract_audit_url: config.smart_contract_audit_url,
  kyc_provider: config.kyc_provider,
  kyc_policy_url: config.kyc_policy_url,
  restricted_jurisdictions: config.restricted_jurisdictions,
  legal_entity_name: config.legal_entity_name,
  controller_contact: config.controller_contact,
  participation_terms_url: config.participation_terms_url,
  privacy_notice_url: config.privacy_notice_url,
  risk_disclosure_url: config.risk_disclosure_url,
  mailgun_dns_verified: config.mailgun_dns_verified,
  spf_verified: config.spf_verified,
  dkim_verified: config.dkim_verified,
  dmarc_verified: config.dmarc_verified,
  production_smoke_test_passed: config.production_smoke_test_passed,
  monitoring_configured: config.monitoring_configured,
  alerting_configured: config.alerting_configured,
  backups_configured: config.backups_configured,
  business_approved: config.business_approved,
  legal_approved: config.legal_approved,
  technical_approved: config.technical_approved,
  published: config.published,
});
