import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import api from '../../api';
import { useToastStore } from '../../components/ErrorBoundary';
import { PageContainer } from '../../components/PageContainer';
import { formatUsdFixed } from '../../utils/format';

const initialDraft = {
  direct_clients: 0,
  sub_ib_count: 0,
  notional_volume_usd: 0,
  gross_commission_usd: 0,
  rebate_usd: 0,
  net_commission_usd: 0,
};

export const CRMCommissions = () => {
  const queryClient = useQueryClient();
  const successToast = useToastStore((s) => s.success);
  const errorToast = useToastStore((s) => s.error);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [draft, setDraft] = useState<typeof initialDraft>(initialDraft);

  const usersQuery = useQuery({
    queryKey: ['crm', 'users'],
    queryFn: async () => (await api.getCRMUsersTable()).data,
    staleTime: 20_000,
  });

  const commissionQuery = useQuery({
    queryKey: ['crm', 'commission', selectedUserId],
    queryFn: async () => {
      if (!selectedUserId) return null;
      const resp = await api.getPartnerCommissionMetrics(selectedUserId);
      return resp.data ?? null;
    },
    enabled: Boolean(selectedUserId),
    staleTime: 10_000,
  });

  // Sync server data into the draft form when a selection loads
  useEffect(() => {
    const owner = commissionQuery.data?.owner;
    if (owner) {
      setDraft({
        direct_clients: owner.direct_clients,
        sub_ib_count: owner.sub_ib_count,
        notional_volume_usd: owner.notional_volume_usd,
        gross_commission_usd: owner.gross_commission_usd,
        rebate_usd: owner.rebate_usd,
        net_commission_usd: owner.net_commission_usd,
      });
    }
  }, [commissionQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!selectedUserId) throw new Error('Select an IB user first');
      return api.upsertPartnerCommissionMetric(selectedUserId, {
        direct_clients: Number(draft.direct_clients || 0),
        sub_ib_count: Number(draft.sub_ib_count || 0),
        notional_volume_usd: Number(draft.notional_volume_usd || 0),
        gross_commission_usd: Number(draft.gross_commission_usd || 0),
        rebate_usd: Number(draft.rebate_usd || 0),
        net_commission_usd: Number(draft.net_commission_usd || 0),
      });
    },
    onSuccess: () => {
      successToast('Commission saved', 'IB metrics updated successfully.');
      void queryClient.invalidateQueries({ queryKey: ['crm', 'summary'] });
      void queryClient.invalidateQueries({ queryKey: ['crm', 'commission', selectedUserId] });
    },
    onError: (err: unknown) => {
      errorToast('Save failed', err instanceof Error ? err.message : 'Unknown error');
    },
  });

  const usersData = usersQuery.data?.users;
  const ibCandidates = useMemo(
    () => (usersData ?? []).filter((u) => u.role === 'ib' || u.role === 'sub_ib'),
    [usersData]
  );

  const fields = [
    ['direct_clients', 'Direct clients'],
    ['sub_ib_count', 'Sub-IB count'],
    ['notional_volume_usd', 'Notional volume USD'],
    ['gross_commission_usd', 'Gross commission USD'],
    ['rebate_usd', 'Rebate USD'],
    ['net_commission_usd', 'Net commission USD'],
  ] as const;

  const summaryQuery = useQuery({
    queryKey: ['crm', 'summary'],
    queryFn: async () => (await api.getCRMSummary()).data,
    staleTime: 20_000,
  });

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Commission manager</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">IB commission & rebate editor</h1>
        <p className="mt-2 text-sm text-slate-400">
          Record period-level commission and rebate figures for IB and sub-IB accounts. Values are
          upserted — re-saving updates the existing record.
        </p>
      </div>

      {/* Aggregate totals */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <p className="text-xs text-slate-500">IB accounts</p>
          <p className="mt-1 text-2xl font-semibold text-white">{summaryQuery.data?.ibs ?? '—'}</p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <p className="text-xs text-slate-500">Sub-IB accounts</p>
          <p className="mt-1 text-2xl font-semibold text-white">
            {summaryQuery.data?.sub_ibs ?? '—'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <p className="text-xs text-slate-500">Total net commissions</p>
          <p className="mt-1 text-2xl font-semibold text-white">
            {formatUsdFixed(summaryQuery.data?.net_commission_usd)}
          </p>
        </div>
      </div>

      {/* Editor */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold text-white">Edit commission metrics</h2>
        <p className="mt-1 text-xs text-slate-500">
          Select an IB or sub-IB account, then enter the period metrics below.
        </p>

        <div className="mt-5 grid gap-6 lg:grid-cols-[0.45fr_0.55fr]">
          {/* User selector */}
          <div className="space-y-4">
            <div>
              <label
                className="mb-1.5 block text-xs uppercase tracking-[0.14em] text-slate-500"
                htmlFor="ib-sub-ib-account"
              >
                IB / sub-IB account
              </label>
              <select
                id="ib-sub-ib-account"
                value={selectedUserId ?? ''}
                onChange={(e) => {
                  const val = Number(e.target.value || 0);
                  setSelectedUserId(val || null);
                  if (!val) setDraft(initialDraft);
                }}
                className="premium-input"
              >
                <option value="">— Select a user —</option>
                {ibCandidates.map((u) => (
                  <option key={u.id} value={u.id}>
                    #{u.id} · {u.username} ({u.role.replace('_', ' ')})
                  </option>
                ))}
              </select>
              {!selectedUserId && ibCandidates.length === 0 && (
                <p className="mt-2 text-xs text-slate-500">
                  No IB / sub-IB users found. Approve a partner application first.
                </p>
              )}
            </div>

            {commissionQuery.data?.owner && (
              <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                  Current metrics on file
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <p>
                    Net:{' '}
                    <span className="font-medium text-white">
                      {formatUsdFixed(commissionQuery.data.owner.net_commission_usd)}
                    </span>
                  </p>
                  <p>
                    Gross:{' '}
                    <span className="font-medium text-white">
                      {formatUsdFixed(commissionQuery.data.owner.gross_commission_usd)}
                    </span>
                  </p>
                  <p>
                    Rebate:{' '}
                    <span className="font-medium text-white">
                      {formatUsdFixed(commissionQuery.data.owner.rebate_usd)}
                    </span>
                  </p>
                  <p>
                    Volume:{' '}
                    <span className="font-medium text-white">
                      {formatUsdFixed(commissionQuery.data.owner.notional_volume_usd)}
                    </span>
                  </p>
                  <p>
                    Direct clients:{' '}
                    <span className="font-medium text-white">
                      {commissionQuery.data.owner.direct_clients}
                    </span>
                  </p>
                  <p>
                    Sub-IBs:{' '}
                    <span className="font-medium text-white">
                      {commissionQuery.data.owner.sub_ib_count}
                    </span>
                  </p>
                </div>
              </div>
            )}

            {commissionQuery.isLoading && selectedUserId && (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading current metrics…
              </div>
            )}
          </div>

          {/* Fields */}
          <div className="grid grid-cols-2 gap-3">
            {fields.map(([key, label]) => (
              <div key={key}>
                <label className="mb-1 block text-xs uppercase tracking-[0.12em] text-slate-500">
                  {label}
                </label>
                <input
                  type="number"
                  value={draft[key as keyof typeof draft]}
                  onChange={(e) =>
                    setDraft((prev) => ({
                      ...prev,
                      [key]: Number(e.target.value || 0),
                    }))
                  }
                  className="premium-input"
                  min={0}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!selectedUserId || saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
            className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-60"
          >
            {saveMutation.isPending ? (
              <span className="flex items-center gap-1.5">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…
              </span>
            ) : (
              'Save metrics'
            )}
          </button>
          <button
            type="button"
            onClick={() => setDraft(initialDraft)}
            className="rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-2 text-sm text-slate-300 transition hover:text-white"
          >
            Reset form
          </button>
        </div>
      </div>
    </PageContainer>
  );
};
