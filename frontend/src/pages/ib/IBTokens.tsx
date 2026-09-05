import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, GitBranchPlus, KeyRound, Loader2, ShieldX } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { type CreateIBInvitationTokenPayload, type IBInvitationToken } from '../../api';
import { useToastStore } from '../../components/ErrorBoundary';
import { PageContainer } from '../../components/PageContainer';

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
};

const isTokenActive = (token: IBInvitationToken) => {
  if (token.revoked_at) return false;
  if (token.used_count >= token.max_uses) return false;
  if (token.expires_at) {
    const expires = new Date(token.expires_at).getTime();
    if (Number.isFinite(expires) && expires <= Date.now()) return false;
  }
  return true;
};

export const IBTokens = () => {
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
    queryFn: async () => (await api.listIBInvitationTokens(200, 0)).data,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: async (payload: CreateIBInvitationTokenPayload) =>
      api.createIBInvitationToken(payload),
    onSuccess: (response) => {
      successToast('Token created', 'IB invitation token is ready to share.');
      const code = response.data?.token?.token_code;
      if (typeof code === 'string' && code.trim().length > 0 && navigator.clipboard) {
        void navigator.clipboard.writeText(code).catch(() => undefined);
      }
      setForm({ label: '', ib_name: '', campaign_name: '', max_uses: 1, expires_in_hours: 168 });
      void queryClient.invalidateQueries({ queryKey: ['ib', 'invitation-tokens'] });
    },
    onError: (error: unknown) => {
      errorToast('Create failed', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (tokenCode: string) => api.revokeIBInvitationToken(tokenCode),
    onSuccess: () => {
      successToast('Token revoked', 'This invitation can no longer be used.');
      void queryClient.invalidateQueries({ queryKey: ['ib', 'invitation-tokens'] });
    },
    onError: (error: unknown) => {
      errorToast('Revoke failed', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const tokensData = tokensQuery.data?.tokens;
  const tokens = tokensData ?? [];

  const stats = useMemo(() => {
    const source = tokensData ?? [];
    const active = source.filter(isTokenActive).length;
    const consumed = source.filter((t) => t.used_count >= t.max_uses).length;
    const revoked = source.filter((t) => t.revoked_at != null).length;
    return { total: source.length, active, consumed, revoked };
  }, [tokensData]);

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Tokens</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">IB invitation token management</h1>
        <p className="mt-2 text-sm text-slate-400">
          Generate secure onboarding tokens for IB partner campaigns. Each token can be shared with
          a prospective partner to register with a sponsor link pre-filled. Available to admin and
          backoffice roles.
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-4">
        {[
          { label: 'Total issued', value: stats.total, icon: KeyRound, color: 'text-slate-300' },
          { label: 'Active', value: stats.active, icon: KeyRound, color: 'text-emerald-300' },
          {
            label: 'Consumed',
            value: stats.consumed,
            icon: GitBranchPlus,
            color: 'text-amber-300',
          },
          { label: 'Revoked', value: stats.revoked, icon: ShieldX, color: 'text-red-400' },
        ].map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4"
            >
              <div className={`flex items-center gap-2 text-slate-300`}>
                <Icon className={`h-4 w-4 ${stat.color}`} />
                {stat.label}
              </div>
              <p className="mt-3 text-2xl font-semibold text-white">{stat.value}</p>
            </div>
          );
        })}
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr,1.1fr]">
        {/* Create form */}
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Create invitation token</h2>
          <p className="mt-1 text-sm text-slate-400">
            Generate a campaign-level onboarding token in seconds.
          </p>
          <div className="mt-3 inline-flex items-center gap-2 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200">
            <GitBranchPlus className="h-4 w-4" />
            Token code is copied to clipboard automatically on creation.
          </div>
          <div className="mt-4 space-y-3">
            <input
              value={String(form.label ?? '')}
              onChange={(e) => setForm((p) => ({ ...p, label: e.target.value }))}
              placeholder="Label (e.g. Cyprus desk Q2)"
              className="premium-input"
            />
            <input
              value={String(form.ib_name ?? '')}
              onChange={(e) => setForm((p) => ({ ...p, ib_name: e.target.value }))}
              placeholder="IB name"
              className="premium-input"
            />
            <input
              value={String(form.campaign_name ?? '')}
              onChange={(e) => setForm((p) => ({ ...p, campaign_name: e.target.value }))}
              placeholder="Campaign name"
              className="premium-input"
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                type="number"
                min={1}
                max={1000}
                value={Number(form.max_uses ?? 1)}
                onChange={(e) => setForm((p) => ({ ...p, max_uses: Number(e.target.value || 1) }))}
                placeholder="Max uses"
                className="premium-input"
              />
              <input
                type="number"
                min={1}
                max={8760}
                value={Number(form.expires_in_hours ?? 168)}
                onChange={(e) =>
                  setForm((p) => ({ ...p, expires_in_hours: Number(e.target.value || 168) }))
                }
                placeholder="Expires in hours"
                className="premium-input"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={() => createMutation.mutate(form)}
            disabled={createMutation.isPending}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
          >
            {createMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <KeyRound className="h-4 w-4" />
            )}
            Generate IB token
          </button>
        </div>

        {/* Token list */}
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Issued tokens</h2>
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
                Use the form to generate your first IB invitation token.
              </p>
            </div>
          ) : (
            <div className="mt-4 max-h-[32rem] space-y-3 overflow-y-auto pr-1">
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
                          title="Copy token code"
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
                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-400">
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
    </PageContainer>
  );
};
