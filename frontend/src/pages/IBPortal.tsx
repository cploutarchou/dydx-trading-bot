import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, GitBranchPlus, KeyRound, Loader2, ShieldX, Users, WalletCards } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { CreateIBInvitationTokenPayload, IBInvitationToken } from '../api';
import {
  BACKOFFICE_ROLES,
  IB_ROLES,
  getUserWorkspaceRole,
  roleMatches,
} from '../auth/roles';
import { useToastStore } from '../components/ErrorBoundary';
import { PageContainer } from '../components/PageContainer';
import { useAuthStore } from '../store/auth';

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString();
};

const formatCurrency = (value?: number) => {
  const numeric = Number(value || 0);
  return `$${numeric.toLocaleString('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  })}`;
};

const isTokenActive = (token: IBInvitationToken) => {
  if (token.revoked_at) return false;
  if (token.used_count >= token.max_uses) return false;
  if (token.expires_at) {
    const expires = new Date(token.expires_at).getTime();
    if (Number.isFinite(expires) && expires <= Date.now()) {
      return false;
    }
  }
  return true;
};

export const IBPortalPage = () => {
  const user = useAuthStore((state) => state.user);
  const role = getUserWorkspaceRole(user);
  const canUseIBPortal = roleMatches(role, [...IB_ROLES, ...BACKOFFICE_ROLES]);
  const canManageIB = roleMatches(role, BACKOFFICE_ROLES);
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const [form, setForm] = useState<CreateIBInvitationTokenPayload>({
    label: '',
    ib_name: '',
    campaign_name: '',
    max_uses: 1,
    expires_in_hours: 168,
  });

  const tokensQuery = useQuery({
    queryKey: ['ib', 'invitation-tokens'],
    queryFn: async () => {
      const response = await api.listIBInvitationTokens(200, 0);
      return response.data;
    },
    staleTime: 20_000,
    refetchInterval: 30_000,
    enabled: canManageIB,
  });

  const overviewQuery = useQuery({
    queryKey: ['portal', 'overview', 'ib'],
    queryFn: async () => (await api.getPortalOverview()).data,
    staleTime: 20_000,
  });

  const applicationsQuery = useQuery({
    queryKey: ['portal', 'applications', 'ib'],
    queryFn: async () => (await api.listPartnerApplications(100, 0)).data,
    staleTime: 10_000,
    refetchInterval: 20_000,
  });

  const hierarchyQuery = useQuery({
    queryKey: ['portal', 'hierarchy', 'ib'],
    queryFn: async () => (await api.getPartnerHierarchy()).data,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const commissionQuery = useQuery({
    queryKey: ['portal', 'commission-metrics', 'ib'],
    queryFn: async () => (await api.getPartnerCommissionMetrics()).data,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const createTokenMutation = useMutation({
    mutationFn: async (payload: CreateIBInvitationTokenPayload) =>
      api.createIBInvitationToken(payload),
    onSuccess: (response) => {
      successToast('IB invitation token created', 'Share the token with your invited IB partner.');
      const code = response.data?.token?.token_code;
      if (typeof code === 'string' && code.trim().length > 0 && navigator.clipboard) {
        void navigator.clipboard.writeText(code).catch(() => undefined);
      }
      void queryClient.invalidateQueries({ queryKey: ['ib', 'invitation-tokens'] });
    },
    onError: (error: unknown) => {
      errorToast(
        'Failed to create token',
        error instanceof Error ? error.message : 'Unknown error'
      );
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (tokenCode: string) => api.revokeIBInvitationToken(tokenCode),
    onSuccess: () => {
      successToast('Token revoked', 'This invitation can no longer be used.');
      void queryClient.invalidateQueries({ queryKey: ['ib', 'invitation-tokens'] });
    },
    onError: (error: unknown) => {
      errorToast(
        'Failed to revoke token',
        error instanceof Error ? error.message : 'Unknown error'
      );
    },
  });

  const tokens = tokensQuery.data?.tokens ?? [];
  const applications = applicationsQuery.data?.applications ?? [];
  const overview = overviewQuery.data;
  const relationships = hierarchyQuery.data?.relationships ?? [];
  const ownerCommission = commissionQuery.data?.owner;
  const downlineCommission = commissionQuery.data?.downline;

  const stats = useMemo(() => {
    const active = tokens.filter((token) => isTokenActive(token)).length;
    const consumed = tokens.filter((token) => token.used_count >= token.max_uses).length;
    return { total: tokens.length, active, consumed };
  }, [tokens]);

  if (!canUseIBPortal) {
    return (
      <PageContainer size="wide" className="space-y-6">
        <div className="rounded-2xl border border-red-700/60 bg-red-900/25 p-6">
          <p className="text-sm font-semibold text-red-200">Access restricted</p>
          <p className="mt-2 text-sm text-slate-300">
            Your current workspace role (
            <span className="font-mono text-slate-100">{role || 'viewer'}</span>) does not include
            IB portal access. Contact an administrator to request an upgrade to IB, sub-IB, or
            back-office.
          </p>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">IB Portal</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">
          Invitation and partner onboarding control center
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Manage invitation tokens, track partner onboarding requests, inspect the live sponsor
          hierarchy, and monitor commission metrics — all from one control center.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <Users className="h-4 w-4 text-cyan-300" /> Issued tokens
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">{stats.total}</p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <KeyRound className="h-4 w-4 text-emerald-300" /> Active tokens
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {canManageIB ? stats.active : (overview?.counts?.ibs ?? 0)}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <ShieldX className="h-4 w-4 text-amber-300" /> Open applications
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {
              applications.filter(
                (item) => item.status === 'pending' || item.status === 'reviewing'
              ).length
            }
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <WalletCards className="h-4 w-4 text-cyan-300" /> Net commission
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {ownerCommission?.net_commission_usd
              ? formatCurrency(ownerCommission.net_commission_usd)
              : '\u2014'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <WalletCards className="h-4 w-4 text-emerald-300" /> Gross commission
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {ownerCommission?.gross_commission_usd
              ? formatCurrency(ownerCommission.gross_commission_usd)
              : '\u2014'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <WalletCards className="h-4 w-4 text-violet-300" /> Rebate paid
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {ownerCommission?.rebate_usd ? formatCurrency(ownerCommission.rebate_usd) : '\u2014'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <Users className="h-4 w-4 text-amber-300" /> Downline notional
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {downlineCommission?.notional_volume_usd
              ? formatCurrency(downlineCommission.notional_volume_usd)
              : '\u2014'}
          </p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Partner operating overview</h2>
          <p className="mt-1 text-sm text-slate-400">
            Current workspace role, enabled modules, and team-wide context.
          </p>
          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Current role</p>
              <p className="mt-2 text-xl font-semibold uppercase tracking-[0.14em] text-white">
                {overview?.role || role}
              </p>
            </div>
            <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Available modules
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(overview?.modules ?? []).map((module) => (
                  <span
                    key={module.key}
                    className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-cyan-200"
                  >
                    {module.title}
                  </span>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Partner applications in view
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">{applications.length}</p>
            </div>
            <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Direct hierarchy edges
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">{relationships.length}</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Partner application feed</h2>
          <p className="mt-1 text-sm text-slate-400">
            Track your own requests and sponsored promotions in one stream.
          </p>
          {applicationsQuery.isLoading ? (
            <div className="mt-4 flex items-center gap-2 text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading applications...
            </div>
          ) : applications.length === 0 ? (
            <div className="mt-4 rounded-xl border border-dashed border-slate-700/60 bg-slate-950/40 p-6 text-center">
              <p className="text-sm font-medium text-slate-300">No applications in scope</p>
              <p className="mt-1 text-xs text-slate-500">
                Applications appear here once users submit partner upgrade requests visible to your
                role.
              </p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {applications.slice(0, 6).map((application) => (
                <div
                  key={application.id}
                  className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">
                        {application.business_name || `Application #${application.id}`}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                        Requested {application.requested_role} · applicant{' '}
                        {application.applicant_user_id}
                      </p>
                    </div>
                    <span className="rounded-full border border-slate-600 bg-slate-700/40 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-200">
                      {application.status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    {application.notes || 'No application notes provided.'}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <h2 className="text-lg font-semibold text-white">Partner hierarchy graph</h2>
        <p className="mt-1 text-sm text-slate-400">
          Persisted sponsor → partner edges. Populated automatically when applications with a
          sponsor ID are approved.
        </p>
        {hierarchyQuery.isLoading ? (
          <div className="mt-4 flex items-center gap-2 text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading hierarchy...
          </div>
        ) : relationships.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-700/60 bg-slate-950/40 p-6 text-center">
            <p className="text-sm font-medium text-slate-300">No edges on record yet</p>
            <p className="mt-1 text-xs text-slate-500">
              Hierarchy edges appear once a partner application carrying a sponsor ID is approved.
            </p>
          </div>
        ) : (
          <div className="mt-4 overflow-auto rounded-xl border border-slate-700/60">
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
                {relationships.map((relationship) => (
                  <tr key={relationship.id} className="border-t border-slate-800/80">
                    <td className="px-3 py-2">{relationship.sponsor_user_id}</td>
                    <td className="px-3 py-2">{relationship.partner_user_id}</td>
                    <td className="px-3 py-2 uppercase tracking-[0.14em]">
                      {relationship.relationship_type}
                    </td>
                    <td className="px-3 py-2">{formatDateTime(relationship.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {canManageIB && (
        <div className="grid gap-6 xl:grid-cols-[0.9fr,1.1fr]">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold text-white">Create invitation token</h2>
            <p className="mt-1 text-sm text-slate-400">
              Generate secure IB onboarding tokens in seconds.
            </p>

            <div className="mt-3 inline-flex items-center gap-2 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200">
              <GitBranchPlus className="h-4 w-4" /> Admin-only issuance controls for campaign-level
              onboarding.
            </div>

            <div className="mt-4 space-y-3">
              <input
                value={String(form.label ?? '')}
                onChange={(event) => setForm((prev) => ({ ...prev, label: event.target.value }))}
                placeholder="Label (e.g. Cyprus desk Q2)"
                className="premium-input"
              />
              <input
                value={String(form.ib_name ?? '')}
                onChange={(event) => setForm((prev) => ({ ...prev, ib_name: event.target.value }))}
                placeholder="IB name"
                className="premium-input"
              />
              <input
                value={String(form.campaign_name ?? '')}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, campaign_name: event.target.value }))
                }
                placeholder="Campaign name"
                className="premium-input"
              />
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={Number(form.max_uses ?? 1)}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, max_uses: Number(event.target.value || 1) }))
                  }
                  placeholder="Max uses"
                  className="premium-input"
                />
                <input
                  type="number"
                  min={1}
                  max={8760}
                  value={Number(form.expires_in_hours ?? 168)}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      expires_in_hours: Number(event.target.value || 168),
                    }))
                  }
                  placeholder="Expires in hours"
                  className="premium-input"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={() => createTokenMutation.mutate(form)}
              disabled={createTokenMutation.isPending}
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {createTokenMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <KeyRound className="h-4 w-4" />
              )}
              Generate IB token
            </button>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold text-white">Issued invitation tokens</h2>
            <p className="mt-1 text-sm text-slate-400">
              Monitor usage and instantly revoke compromised tokens.
            </p>

            {tokensQuery.isLoading ? (
              <div className="mt-4 flex items-center gap-2 text-slate-300">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading tokens...
              </div>
            ) : tokens.length === 0 ? (
              <div className="mt-4 rounded-xl border border-dashed border-slate-700/60 bg-slate-950/40 p-6 text-center">
                <p className="text-sm font-medium text-slate-300">No tokens issued yet</p>
                <p className="mt-1 text-xs text-slate-500">
                  Use the form on the left to generate your first IB invitation token.
                </p>
              </div>
            ) : (
              <div className="mt-4 max-h-130 space-y-3 overflow-y-auto pr-1">
                {tokens.map((token) => {
                  const active = isTokenActive(token);
                  return (
                    <div
                      key={token.id}
                      className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-mono text-sm text-cyan-200">{token.token_code}</p>
                          <p className="mt-1 text-sm font-semibold text-white">
                            {token.label || token.ib_name || 'Untitled token'}
                          </p>
                          <p className="text-xs text-slate-500">
                            IB: {token.ib_name || '—'} · Campaign: {token.campaign_name || '—'}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] ${
                              active
                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                                : 'border-slate-600 bg-slate-700/40 text-slate-300'
                            }`}
                          >
                            {active ? 'Active' : 'Inactive'}
                          </span>
                          <button
                            type="button"
                            onClick={() => navigator.clipboard?.writeText(token.token_code)}
                            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-slate-300 transition hover:text-white"
                            title="Copy token"
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </button>
                          {!token.revoked_at && (
                            <button
                              type="button"
                              onClick={() => revokeMutation.mutate(token.token_code)}
                              disabled={revokeMutation.isPending}
                              className="rounded-lg border border-red-700/60 bg-red-900/30 px-2.5 py-1 text-xs font-medium text-red-200 transition hover:bg-red-900/45 disabled:opacity-60"
                            >
                              Revoke
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-slate-400 sm:grid-cols-3">
                        <p>
                          Uses:{' '}
                          <span className="font-medium text-slate-200">
                            {token.used_count}/{token.max_uses}
                          </span>
                        </p>
                        <p>
                          Expires:{' '}
                          <span className="font-medium text-slate-200">
                            {formatDateTime(token.expires_at)}
                          </span>
                        </p>
                        <p>
                          Last used:{' '}
                          <span className="font-medium text-slate-200">
                            {formatDateTime(token.last_used_at)}
                          </span>
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </PageContainer>
  );
};
