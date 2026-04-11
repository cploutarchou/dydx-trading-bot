import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Clock3, Loader2, Network, ShieldAlert, WalletCards } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { PartnerApplication } from '../api';
import { useToastStore } from '../components/ErrorBoundary';
import { PageContainer } from '../components/PageContainer';

const statusTone: Record<string, string> = {
  pending: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  reviewing: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  approved: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  rejected: 'border-red-500/30 bg-red-500/10 text-red-200',
};

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
};

const formatCurrency = (value?: number) => {
  const numeric = Number(value || 0);
  return `$${numeric.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
};

const buildNextStatus = (application: PartnerApplication): 'reviewing' | 'approved' | 'rejected' =>
  application.status === 'pending' ? 'reviewing' : 'approved';

export const CRMPage = () => {
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const [reviewNotes, setReviewNotes] = useState<Record<number, string>>({});
  const [commissionDraft, setCommissionDraft] = useState<Record<string, number>>({
    direct_clients: 0,
    sub_ib_count: 0,
    notional_volume_usd: 0,
    gross_commission_usd: 0,
    rebate_usd: 0,
    net_commission_usd: 0,
  });
  const [selectedCommissionUserId, setSelectedCommissionUserId] = useState<number | null>(null);

  const summaryQuery = useQuery({
    queryKey: ['crm', 'summary'],
    queryFn: async () => (await api.getCRMSummary()).data,
    staleTime: 15_000,
    refetchInterval: 20_000,
  });

  const applicationsQuery = useQuery({
    queryKey: ['portal', 'applications', 'crm'],
    queryFn: async () => (await api.listPartnerApplications(200, 0)).data,
    staleTime: 10_000,
    refetchInterval: 20_000,
  });

  const usersQuery = useQuery({
    queryKey: ['crm', 'users'],
    queryFn: async () => (await api.getCRMUsersTable()).data,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });

  const hierarchyQuery = useQuery({
    queryKey: ['crm', 'hierarchy'],
    queryFn: async () => (await api.getCRMHierarchyTable()).data,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });

  const securityEventsQuery = useQuery({
    queryKey: ['crm', 'security-events'],
    queryFn: async () => (await api.getCRMSecurityEvents(100, 0)).data,
    staleTime: 10_000,
    refetchInterval: 20_000,
  });

  const commissionQuery = useQuery({
    queryKey: ['crm', 'commission', selectedCommissionUserId],
    queryFn: async () => {
      if (!selectedCommissionUserId) return null;
      return (await api.getPartnerCommissionMetrics(selectedCommissionUserId)).data;
    },
    enabled: Boolean(selectedCommissionUserId),
    staleTime: 10_000,
  });

  const reviewMutation = useMutation({
    mutationFn: async ({
      applicationId,
      status,
    }: {
      applicationId: number;
      status: 'reviewing' | 'approved' | 'rejected';
    }) =>
      api.reviewPartnerApplication(applicationId, {
        status,
        review_notes: reviewNotes[applicationId] || '',
      }),
    onSuccess: (_response, variables) => {
      successToast(
        'Application updated',
        `Application #${variables.applicationId} is now ${variables.status}.`
      );
      void queryClient.invalidateQueries({ queryKey: ['crm', 'summary'] });
      void queryClient.invalidateQueries({ queryKey: ['portal', 'applications'] });
      void queryClient.invalidateQueries({ queryKey: ['crm', 'users'] });
      void queryClient.invalidateQueries({ queryKey: ['crm', 'hierarchy'] });
    },
    onError: (error: unknown) => {
      errorToast('Review failed', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const commissionMutation = useMutation({
    mutationFn: async () => {
      if (!selectedCommissionUserId) {
        throw new Error('Select an IB/sub-IB user first');
      }
      return api.upsertPartnerCommissionMetric(selectedCommissionUserId, {
        direct_clients: Number(commissionDraft.direct_clients || 0),
        sub_ib_count: Number(commissionDraft.sub_ib_count || 0),
        notional_volume_usd: Number(commissionDraft.notional_volume_usd || 0),
        gross_commission_usd: Number(commissionDraft.gross_commission_usd || 0),
        rebate_usd: Number(commissionDraft.rebate_usd || 0),
        net_commission_usd: Number(commissionDraft.net_commission_usd || 0),
      });
    },
    onSuccess: () => {
      successToast('Commission metrics saved', 'IB rebate and commission values were persisted.');
      void queryClient.invalidateQueries({ queryKey: ['crm', 'summary'] });
      void queryClient.invalidateQueries({
        queryKey: ['crm', 'commission', selectedCommissionUserId],
      });
    },
    onError: (error: unknown) => {
      errorToast(
        'Commission update failed',
        error instanceof Error ? error.message : 'Unknown error'
      );
    },
  });

  const applications = applicationsQuery.data?.applications ?? [];
  const users = usersQuery.data?.users ?? [];
  const relationships = hierarchyQuery.data?.relationships ?? [];
  const securityEvents = securityEventsQuery.data?.events ?? [];

  const ibCandidates = useMemo(
    () => users.filter((user) => user.role === 'ib' || user.role === 'sub_ib'),
    [users]
  );

  const pendingFirst = useMemo(
    () =>
      [...applications].sort((left, right) => {
        const leftPriority = left.status === 'pending' ? 0 : left.status === 'reviewing' ? 1 : 2;
        const rightPriority = right.status === 'pending' ? 0 : right.status === 'reviewing' ? 1 : 2;
        return leftPriority - rightPriority || right.id - left.id;
      }),
    [applications]
  );

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">CRM Backoffice</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">
          Client and partner operations desk
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Approve onboarding requests, inspect the live sponsor tree, and manage IB commission
          metrics — all without leaving this surface.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-6">
        {[
          { label: 'Active users', value: summaryQuery.data?.active_users ?? 0, icon: ShieldAlert },
          { label: 'Clients', value: summaryQuery.data?.clients ?? 0, icon: Clock3 },
          { label: 'IBs', value: summaryQuery.data?.ibs ?? 0, icon: CheckCircle2 },
          { label: 'Sub-IBs', value: summaryQuery.data?.sub_ibs ?? 0, icon: Clock3 },
          {
            label: 'Hierarchy edges',
            value: summaryQuery.data?.hierarchy_edges ?? relationships.length,
            icon: Network,
          },
          {
            label: 'Net commissions (all)',
            value: formatCurrency(summaryQuery.data?.net_commission_usd),
            icon: WalletCards,
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4"
            >
              <div className="flex items-center gap-2 text-slate-300">
                <Icon className="h-4 w-4 text-cyan-300" /> {card.label}
              </div>
              <p className="mt-3 text-2xl font-semibold text-white">{card.value}</p>
            </div>
          );
        })}
      </div>

      <section className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Partner application queue</h2>
            <p className="mt-1 text-sm text-slate-400">
              Move requests through pending → reviewing → approved/rejected. Each action is
              timestamped and persisted with your review notes.
            </p>
          </div>
          {applicationsQuery.isFetching && (
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
          )}
        </div>

        {applicationsQuery.isLoading ? (
          <div className="mt-4 flex items-center gap-2 text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading applications...
          </div>
        ) : pendingFirst.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-700/60 bg-slate-950/40 p-6 text-center">
            <p className="text-sm font-medium text-slate-300">Queue is clear</p>
            <p className="mt-1 text-xs text-slate-500">
              No partner applications in the system yet. They appear here as soon as users submit
              upgrade requests.
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {pendingFirst.map((application) => (
              <div
                key={application.id}
                className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">
                      #{application.id} · {application.business_name || 'Unnamed business'}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                      applicant {application.applicant_user_id} · sponsor{' '}
                      {application.sponsor_user_id ?? '—'} · requested {application.requested_role}
                    </p>
                  </div>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] ${statusTone[application.status] || 'border-slate-600 bg-slate-700/40 text-slate-300'}`}
                  >
                    {application.status}
                  </span>
                </div>

                <div className="mt-3 grid gap-2 text-sm text-slate-300 md:grid-cols-2">
                  <p>{application.notes || 'No notes provided.'}</p>
                  <div className="space-y-1 text-xs text-slate-400">
                    <p>
                      Submitted:{' '}
                      <span className="text-slate-200">
                        {formatDateTime(application.created_at)}
                      </span>
                    </p>
                    <p>
                      Reviewed:{' '}
                      <span className="text-slate-200">
                        {formatDateTime(application.reviewed_at)}
                      </span>
                    </p>
                  </div>
                </div>

                <textarea
                  value={reviewNotes[application.id] || application.review_notes || ''}
                  onChange={(event) =>
                    setReviewNotes((current) => ({
                      ...current,
                      [application.id]: event.target.value,
                    }))
                  }
                  rows={3}
                  placeholder="Internal review notes"
                  className="premium-input mt-4 min-h-24"
                />

                <div className="mt-4 flex flex-wrap gap-2">
                  {application.status === 'pending' && (
                    <button
                      type="button"
                      onClick={() =>
                        reviewMutation.mutate({
                          applicationId: application.id,
                          status: buildNextStatus(application),
                        })
                      }
                      disabled={reviewMutation.isPending}
                      className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20"
                    >
                      Mark reviewing
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() =>
                      reviewMutation.mutate({ applicationId: application.id, status: 'approved' })
                    }
                    disabled={reviewMutation.isPending}
                    className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      reviewMutation.mutate({ applicationId: application.id, status: 'rejected' })
                    }
                    disabled={reviewMutation.isPending}
                    className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-200 transition hover:bg-red-500/20"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">All users</h2>
          <p className="mt-1 text-sm text-slate-400">
            Workspace role, assigned sponsor, and direct partner count for every user in the system.
          </p>
          <div className="mt-4 max-h-120 overflow-auto rounded-xl border border-slate-700/60">
            <table className="min-w-full text-xs text-slate-300">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-[0.14em]">
                <tr>
                  <th className="px-3 py-2 text-left">User</th>
                  <th className="px-3 py-2 text-left">Role</th>
                  <th className="px-3 py-2 text-left">Sponsor</th>
                  <th className="px-3 py-2 text-right">Direct</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-3 py-10 text-center">
                      <p className="text-sm text-slate-400">No users in table yet</p>
                      <p className="mt-1 text-xs text-slate-600">
                        Populated once the backend serves user CRM data.
                      </p>
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.id} className="border-t border-slate-800/80">
                      <td className="px-3 py-2">
                        <p className="font-medium text-slate-100">{user.username}</p>
                        <p className="text-slate-500">{user.email}</p>
                      </td>
                      <td className="px-3 py-2 uppercase tracking-[0.14em]">{user.role}</td>
                      <td className="px-3 py-2">{user.sponsor_user_id || '—'}</td>
                      <td className="px-3 py-2 text-right">{user.direct_partner_count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Sponsor hierarchy graph</h2>
          <p className="mt-1 text-sm text-slate-400">
            Persisted parent → child edges. Edges are written automatically on approved applications
            that carry a sponsor ID.
          </p>
          <div className="mt-4 max-h-120 overflow-auto rounded-xl border border-slate-700/60">
            <table className="min-w-full text-xs text-slate-300">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-[0.14em]">
                <tr>
                  <th className="px-3 py-2 text-left">Sponsor</th>
                  <th className="px-3 py-2 text-left">Partner</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Updated</th>
                </tr>
              </thead>
              <tbody>
                {relationships.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-3 py-10 text-center">
                      <p className="text-sm text-slate-400">No hierarchy edges recorded yet</p>
                      <p className="mt-1 text-xs text-slate-600">
                        Edges appear here after the first application with a sponsor is approved.
                      </p>
                    </td>
                  </tr>
                ) : (
                  relationships.map((relationship) => (
                    <tr key={relationship.id} className="border-t border-slate-800/80">
                      <td className="px-3 py-2">{relationship.sponsor_user_id}</td>
                      <td className="px-3 py-2">{relationship.partner_user_id}</td>
                      <td className="px-3 py-2 uppercase tracking-[0.14em]">
                        {relationship.relationship_type}
                      </td>
                      <td className="px-3 py-2">{formatDateTime(relationship.updated_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Security login events</h2>
            <p className="mt-1 text-sm text-slate-400">
              Recent authentication outcomes for operational monitoring, incident response, and
              access anomaly triage.
            </p>
          </div>
          {securityEventsQuery.isFetching && (
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
          )}
        </div>

        <div className="mt-4 max-h-120 overflow-auto rounded-xl border border-slate-700/60">
          <table className="min-w-full text-xs text-slate-300">
            <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-[0.14em]">
              <tr>
                <th className="px-3 py-2 text-left">When</th>
                <th className="px-3 py-2 text-left">User</th>
                <th className="px-3 py-2 text-left">Outcome</th>
                <th className="px-3 py-2 text-left">Reason</th>
                <th className="px-3 py-2 text-left">IP</th>
              </tr>
            </thead>
            <tbody>
              {securityEvents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-10 text-center text-slate-500">
                    No security events available yet.
                  </td>
                </tr>
              ) : (
                securityEvents.map((event) => (
                  <tr key={event.id} className="border-t border-slate-800/80">
                    <td className="px-3 py-2">{formatDateTime(event.created_at as string)}</td>
                    <td className="px-3 py-2">{String(event.username || '—')}</td>
                    <td className="px-3 py-2 uppercase tracking-[0.14em]">
                      {String(event.outcome || '—')}
                    </td>
                    <td className="px-3 py-2">{String(event.reason || '—')}</td>
                    <td className="px-3 py-2">{String(event.ip_address || '—')}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <h2 className="text-lg font-semibold text-white">Commission &amp; rebate editor</h2>
        <p className="mt-1 text-sm text-slate-400">
          Record period-level commission and rebate figures for any IB or sub-IB user. Values are
          upserted — saving again updates the existing record rather than creating duplicates.
        </p>

        <div className="mt-4 grid gap-4 lg:grid-cols-[0.42fr,0.58fr]">
          <div className="space-y-3">
            <label className="block text-xs uppercase tracking-[0.16em] text-slate-500">
              IB or sub-IB account
            </label>
            <select
              value={selectedCommissionUserId ?? ''}
              onChange={(event) => {
                const selected = Number(event.target.value || 0);
                setSelectedCommissionUserId(selected || null);
              }}
              className="premium-input"
            >
              <option value="">— Select a user —</option>
              {ibCandidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  #{candidate.id} · {candidate.username} ({candidate.role})
                </option>
              ))}
            </select>

            {!selectedCommissionUserId && ibCandidates.length === 0 && (
              <p className="text-xs text-slate-500">
                No IB or sub-IB users found. Approve a partner application first to see candidates
                here.
              </p>
            )}
            {commissionQuery.data?.owner && (
              <div className="rounded-xl border border-slate-700/60 bg-slate-950/70 p-4 text-sm text-slate-300">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  Live metrics on file
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <p>
                    Net:{' '}
                    <span className="text-slate-100">
                      {formatCurrency(commissionQuery.data.owner.net_commission_usd)}
                    </span>
                  </p>
                  <p>
                    Gross:{' '}
                    <span className="text-slate-100">
                      {formatCurrency(commissionQuery.data.owner.gross_commission_usd)}
                    </span>
                  </p>
                  <p>
                    Rebate:{' '}
                    <span className="text-slate-100">
                      {formatCurrency(commissionQuery.data.owner.rebate_usd)}
                    </span>
                  </p>
                  <p>
                    Volume:{' '}
                    <span className="text-slate-100">
                      {formatCurrency(commissionQuery.data.owner.notional_volume_usd)}
                    </span>
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ['direct_clients', 'Direct clients'],
              ['sub_ib_count', 'Sub-IB count'],
              ['notional_volume_usd', 'Notional volume USD'],
              ['gross_commission_usd', 'Gross commission USD'],
              ['rebate_usd', 'Rebate USD'],
              ['net_commission_usd', 'Net commission USD'],
            ].map(([key, label]) => (
              <div key={key}>
                <label className="mb-1 block text-xs uppercase tracking-[0.14em] text-slate-500">
                  {label}
                </label>
                <input
                  type="number"
                  value={Number(commissionDraft[key] || 0)}
                  onChange={(event) =>
                    setCommissionDraft((current) => ({
                      ...current,
                      [key]: Number(event.target.value || 0),
                    }))
                  }
                  className="premium-input"
                />
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => commissionMutation.mutate()}
            disabled={!selectedCommissionUserId || commissionMutation.isPending}
            className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-60"
          >
            {commissionMutation.isPending ? 'Saving...' : 'Save metrics'}
          </button>
          <button
            type="button"
            onClick={() =>
              setCommissionDraft({
                direct_clients: 0,
                sub_ib_count: 0,
                notional_volume_usd: 0,
                gross_commission_usd: 0,
                rebate_usd: 0,
                net_commission_usd: 0,
              })
            }
            className="rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-slate-300 transition hover:text-white"
          >
            Reset form
          </button>
        </div>
      </section>
    </PageContainer>
  );
};
