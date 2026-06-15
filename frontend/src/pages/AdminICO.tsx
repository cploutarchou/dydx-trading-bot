import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MailCheck, RefreshCcw, ShieldCheck } from 'lucide-react';
import api from '../api';
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

  const applications = whitelistQuery.data?.applications ?? [];
  const confirmed = applications.filter((row) => row.email_confirmed).length;
  const marketing = applications.filter((row) => row.marketing_confirmed && !row.unsubscribed).length;
  const withdrawn = applications.filter((row) => row.withdrawn).length;

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
        tone="warning"
        title="Not production ready"
        description="Token-sale, tokenomics, legal, jurisdiction, KYC, smart-contract, and participation terms still require authorised approval before publication."
      />

      <div className="grid gap-4 md:grid-cols-4">
        <PlatformStatCard label="Applications" value={applications.length} icon={ShieldCheck} tone="accent" loading={whitelistQuery.isLoading} />
        <PlatformStatCard label="Confirmed emails" value={confirmed} icon={MailCheck} tone="success" loading={whitelistQuery.isLoading} />
        <PlatformStatCard label="Marketing eligible" value={marketing} icon={MailCheck} tone="violet" loading={whitelistQuery.isLoading} />
        <PlatformStatCard label="Withdrawn" value={withdrawn} icon={RefreshCcw} tone="warning" loading={whitelistQuery.isLoading} />
      </div>

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
