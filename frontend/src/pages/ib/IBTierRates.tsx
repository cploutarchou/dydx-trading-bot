import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Loader2, Percent, Plus, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import api, { type IBTierCommissionRate, type UpsertIBTierCommissionRatePayload } from '../../api';
import { useToastStore } from '../../components/ErrorBoundary';
import { PageContainer } from '../../components/PageContainer';

interface EditingState {
  tierLevel: number;
  commission_rate_pct: string;
  rebate_rate_pct: string;
  description: string;
  is_active: boolean;
}

const emptyEdit = (tier: number): EditingState => ({
  tierLevel: tier,
  commission_rate_pct: '0',
  rebate_rate_pct: '0',
  description: '',
  is_active: true,
});

const fromRate = (rate: IBTierCommissionRate): EditingState => ({
  tierLevel: rate.tier_level,
  commission_rate_pct: String(rate.commission_rate_pct),
  rebate_rate_pct: String(rate.rebate_rate_pct),
  description: rate.description,
  is_active: rate.is_active,
});

const TIER_BADGE_COLORS = [
  'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  'border-violet-500/30 bg-violet-500/10 text-violet-200',
  'border-amber-500/30 bg-amber-500/10 text-amber-200',
  'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  'border-rose-500/30 bg-rose-500/10 text-rose-200',
];

const tierColor = (tier: number) => TIER_BADGE_COLORS[(tier - 1) % TIER_BADGE_COLORS.length];

export const IBTierRates = () => {
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const [editingTier, setEditingTier] = useState<number | null>(null);
  const [editState, setEditState] = useState<EditingState | null>(null);
  const [addingNew, setAddingNew] = useState(false);
  const [newTierLevel, setNewTierLevel] = useState('');

  const ratesQuery = useQuery({
    queryKey: ['ib', 'tier-rates'],
    queryFn: async () => (await api.listIBTierRates()).data,
    staleTime: 30_000,
  });

  const upsertMutation = useMutation({
    mutationFn: async ({
      tier,
      payload,
    }: {
      tier: number;
      payload: UpsertIBTierCommissionRatePayload;
    }) => api.upsertIBTierRate(tier, payload),
    onSuccess: () => {
      successToast('Tier rate saved', 'Commission rate configuration updated.');
      setEditingTier(null);
      setEditState(null);
      setAddingNew(false);
      setNewTierLevel('');
      void queryClient.invalidateQueries({ queryKey: ['ib', 'tier-rates'] });
    },
    onError: (error: unknown) => {
      errorToast('Save failed', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (tier: number) => api.deleteIBTierRate(tier),
    onSuccess: () => {
      successToast('Tier deleted', 'Tier commission rate removed.');
      void queryClient.invalidateQueries({ queryKey: ['ib', 'tier-rates'] });
    },
    onError: (error: unknown) => {
      errorToast('Delete failed', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const rates = ratesQuery.data?.rates ?? [];

  const totalCommission = rates
    .filter((r) => r.is_active)
    .reduce((sum, r) => sum + r.commission_rate_pct, 0);

  const totalRebate = rates
    .filter((r) => r.is_active)
    .reduce((sum, r) => sum + r.rebate_rate_pct, 0);

  const existingTiers = new Set(rates.map((r) => r.tier_level));

  const startEdit = (rate: IBTierCommissionRate) => {
    setEditingTier(rate.tier_level);
    setEditState(fromRate(rate));
  };

  const cancelEdit = () => {
    setEditingTier(null);
    setEditState(null);
  };

  const saveEdit = () => {
    if (!editState) return;
    const commPct = parseFloat(editState.commission_rate_pct);
    const rebatePct = parseFloat(editState.rebate_rate_pct);
    if (isNaN(commPct) || commPct < 0 || commPct > 100) {
      errorToast('Invalid rate', 'Commission rate must be between 0 and 100.');
      return;
    }
    if (isNaN(rebatePct) || rebatePct < 0 || rebatePct > 100) {
      errorToast('Invalid rate', 'Rebate rate must be between 0 and 100.');
      return;
    }
    upsertMutation.mutate({
      tier: editState.tierLevel,
      payload: {
        commission_rate_pct: commPct,
        rebate_rate_pct: rebatePct,
        description: editState.description,
        is_active: editState.is_active,
      },
    });
  };

  const startAddNew = () => {
    // Find next unused tier
    let next = 1;
    while (existingTiers.has(next)) next++;
    setNewTierLevel(String(next));
    setEditingTier(-1); // -1 signals "new row"
    setEditState(emptyEdit(next));
    setAddingNew(true);
  };

  const saveNew = () => {
    if (!editState) return;
    const tier = parseInt(newTierLevel, 10);
    if (isNaN(tier) || tier < 1 || tier > 50) {
      errorToast('Invalid tier', 'Tier level must be between 1 and 50.');
      return;
    }
    if (existingTiers.has(tier)) {
      errorToast('Duplicate tier', `Tier ${tier} already exists. Edit it instead.`);
      return;
    }
    const commPct = parseFloat(editState.commission_rate_pct);
    const rebatePct = parseFloat(editState.rebate_rate_pct);
    if (isNaN(commPct) || commPct < 0 || commPct > 100) {
      errorToast('Invalid rate', 'Commission rate must be between 0 and 100.');
      return;
    }
    upsertMutation.mutate({
      tier,
      payload: {
        commission_rate_pct: commPct,
        rebate_rate_pct: rebatePct,
        description: editState.description,
        is_active: editState.is_active,
      },
    });
  };

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Tier Commission Rates</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">
          IB pyramid commission configuration
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Configure the commission and rebate percentage earned at each tier of the IB pyramid. The
          pyramid supports unlimited depth — add as many tiers as needed. Tier 1 = direct referral,
          Tier 2 = their referrals, and so on.
        </p>
      </div>

      {/* Aggregate summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Active tiers</p>
          <p className="mt-2 text-2xl font-semibold text-white">
            {rates.filter((r) => r.is_active).length}
            <span className="ml-1 text-sm font-normal text-slate-400">/ {rates.length}</span>
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Total commission stack
          </p>
          <p className="mt-2 text-2xl font-semibold text-white">
            {totalCommission.toFixed(2)}
            <span className="ml-1 text-sm font-normal text-slate-400">%</span>
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Total rebate stack</p>
          <p className="mt-2 text-2xl font-semibold text-white">
            {totalRebate.toFixed(2)}
            <span className="ml-1 text-sm font-normal text-slate-400">%</span>
          </p>
        </div>
      </div>

      {/* Tier rates table */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Per-tier rates</h2>
            <p className="mt-0.5 text-sm text-slate-400">
              Click a row to edit. Add new tiers for deeper pyramid levels.
            </p>
          </div>
          <button
            type="button"
            onClick={startAddNew}
            disabled={addingNew}
            className="flex items-center gap-1.5 rounded-lg border border-cyan-700/40 bg-cyan-900/20 px-3 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-900/35 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
            Add tier
          </button>
        </div>

        {ratesQuery.isLoading ? (
          <div className="mt-6 flex items-center gap-2 text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading tier rates...
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {/* Existing rates */}
            {rates.map((rate) => {
              const isEditing = editingTier === rate.tier_level;
              return (
                <div
                  key={rate.tier_level}
                  role={!isEditing && !addingNew ? 'button' : undefined}
                  tabIndex={!isEditing && !addingNew ? 0 : undefined}
                  aria-label={`Edit tier ${rate.tier_level} rates`}
                  className={`rounded-xl border p-4 transition ${
                    isEditing
                      ? 'border-cyan-500/40 bg-slate-950/80'
                      : 'border-slate-700/60 bg-slate-950/60 hover:border-slate-600/80 cursor-pointer'
                  }`}
                  onClick={() => !isEditing && !addingNew && startEdit(rate)}
                  onKeyDown={(e) => {
                    if (!isEditing && !addingNew && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      startEdit(rate);
                    }
                  }}
                >
                  {isEditing && editState ? (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3">
                        <span
                          className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${tierColor(rate.tier_level)}`}
                        >
                          Tier {rate.tier_level}
                        </span>
                        <span className="text-xs text-slate-400">Editing</span>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <label
                            className="text-xs uppercase tracking-[0.14em] text-slate-500"
                            htmlFor="commission-rate"
                          >
                            Commission rate (%)
                          </label>
                          <input
                            id="commission-rate"
                            type="number"
                            min={0}
                            max={100}
                            step={0.1}
                            value={editState.commission_rate_pct}
                            onChange={(e) =>
                              setEditState(
                                (s) => s && { ...s, commission_rate_pct: e.target.value }
                              )
                            }
                            className="premium-input mt-1"
                          />
                        </div>
                        <div>
                          <label
                            className="text-xs uppercase tracking-[0.14em] text-slate-500"
                            htmlFor="rebate-rate"
                          >
                            Rebate rate (%)
                          </label>
                          <input
                            id="rebate-rate"
                            type="number"
                            min={0}
                            max={100}
                            step={0.1}
                            value={editState.rebate_rate_pct}
                            onChange={(e) =>
                              setEditState((s) => s && { ...s, rebate_rate_pct: e.target.value })
                            }
                            className="premium-input mt-1"
                          />
                        </div>
                      </div>
                      <input
                        value={editState.description}
                        onChange={(e) =>
                          setEditState((s) => s && { ...s, description: e.target.value })
                        }
                        placeholder="Description (optional)"
                        className="premium-input"
                      />
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setEditState((s) => s && { ...s, is_active: !s.is_active })
                          }
                          className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                            editState.is_active
                              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
                              : 'border-slate-600 bg-slate-800/60 text-slate-400'
                          }`}
                        >
                          {editState.is_active ? 'Active' : 'Inactive'}
                        </button>
                        <div className="ml-auto flex gap-2">
                          <button
                            type="button"
                            onClick={cancelEdit}
                            className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:text-white"
                          >
                            <X className="h-3.5 w-3.5" /> Cancel
                          </button>
                          <button
                            type="button"
                            onClick={saveEdit}
                            disabled={upsertMutation.isPending}
                            className="flex items-center gap-1 rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-cyan-500 disabled:opacity-60"
                          >
                            {upsertMutation.isPending ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Check className="h-3.5 w-3.5" />
                            )}{' '}
                            Save
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-center gap-3">
                      <span
                        className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${tierColor(rate.tier_level)}`}
                      >
                        Tier {rate.tier_level}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-sm font-medium text-white">
                          {rate.description || `Level ${rate.tier_level} referrals`}
                        </p>
                      </div>
                      <div className="flex items-center gap-4 text-sm tabular-nums">
                        <span className="flex items-center gap-1 text-emerald-300">
                          <Percent className="h-3.5 w-3.5" />
                          {rate.commission_rate_pct.toFixed(2)}%
                          <span className="text-xs text-slate-500">commission</span>
                        </span>
                        <span className="flex items-center gap-1 text-violet-300">
                          {rate.rebate_rate_pct.toFixed(2)}%
                          <span className="text-xs text-slate-500">rebate</span>
                        </span>
                      </div>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${
                          rate.is_active
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            : 'border-slate-600 bg-slate-700/40 text-slate-500'
                        }`}
                      >
                        {rate.is_active ? 'Active' : 'Off'}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm(`Delete Tier ${rate.tier_level}?`)) {
                            deleteMutation.mutate(rate.tier_level);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                        className="rounded-lg border border-red-700/40 bg-red-900/20 p-1.5 text-red-300 transition hover:bg-red-900/40 disabled:opacity-50"
                        title="Delete tier"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* New tier entry row */}
            {addingNew && editState && (
              <div className="rounded-xl border border-cyan-500/40 bg-slate-950/80 p-4">
                <p className="mb-3 text-sm font-semibold text-white">New tier</p>
                <div className="space-y-3">
                  <div>
                    <label
                      className="text-xs uppercase tracking-[0.14em] text-slate-500"
                      htmlFor="tier-level-1-50"
                    >
                      Tier level (1–50)
                    </label>
                    <input
                      id="tier-level-1-50"
                      type="number"
                      min={1}
                      max={50}
                      value={newTierLevel}
                      onChange={(e) => setNewTierLevel(e.target.value)}
                      placeholder="e.g. 4"
                      className="premium-input mt-1"
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label
                        className="text-xs uppercase tracking-[0.14em] text-slate-500"
                        htmlFor="commission-rate"
                      >
                        Commission rate (%)
                      </label>
                      <input
                        id="commission-rate"
                        type="number"
                        min={0}
                        max={100}
                        step={0.1}
                        value={editState.commission_rate_pct}
                        onChange={(e) =>
                          setEditState((s) => s && { ...s, commission_rate_pct: e.target.value })
                        }
                        className="premium-input mt-1"
                      />
                    </div>
                    <div>
                      <label
                        className="text-xs uppercase tracking-[0.14em] text-slate-500"
                        htmlFor="rebate-rate"
                      >
                        Rebate rate (%)
                      </label>
                      <input
                        id="rebate-rate"
                        type="number"
                        min={0}
                        max={100}
                        step={0.1}
                        value={editState.rebate_rate_pct}
                        onChange={(e) =>
                          setEditState((s) => s && { ...s, rebate_rate_pct: e.target.value })
                        }
                        className="premium-input mt-1"
                      />
                    </div>
                  </div>
                  <input
                    value={editState.description}
                    onChange={(e) =>
                      setEditState((s) => s && { ...s, description: e.target.value })
                    }
                    placeholder="Description (optional)"
                    className="premium-input"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setAddingNew(false);
                        setEditingTier(null);
                        setEditState(null);
                      }}
                      className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:text-white"
                    >
                      <X className="h-3.5 w-3.5" /> Cancel
                    </button>
                    <button
                      type="button"
                      onClick={saveNew}
                      disabled={upsertMutation.isPending}
                      className="flex items-center gap-1 rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-cyan-500 disabled:opacity-60"
                    >
                      {upsertMutation.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Plus className="h-3.5 w-3.5" />
                      )}{' '}
                      Create tier
                    </button>
                  </div>
                </div>
              </div>
            )}

            {rates.length === 0 && !addingNew && (
              <div className="rounded-xl border border-dashed border-slate-700/60 bg-slate-950/40 p-8 text-center">
                <Percent className="mx-auto h-8 w-8 text-slate-600" />
                <p className="mt-3 text-sm font-medium text-slate-300">No tier rates configured</p>
                <p className="mt-1 text-xs text-slate-500">
                  Click &ldquo;Add tier&rdquo; to create your first pyramid commission tier.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Visual pyramid diagram */}
      {rates.length > 0 && (
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Pyramid structure preview</h2>
          <p className="mt-1 text-sm text-slate-400">
            Each active tier expands from the one above it. Unlimited depth — add more tiers as your
            network grows deeper.
          </p>
          <div className="mt-5 flex flex-col items-center gap-2">
            {rates
              .filter((r) => r.is_active)
              .map((rate, index) => {
                const widthPct = Math.max(20, 100 - index * 12);
                return (
                  <div
                    key={rate.tier_level}
                    style={{ width: `${widthPct}%` }}
                    className={`rounded-xl border px-4 py-3 text-center transition ${tierColor(rate.tier_level)}`}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.14em]">
                      Tier {rate.tier_level}
                    </p>
                    <p className="mt-0.5 text-sm">
                      {rate.commission_rate_pct.toFixed(2)}% commission ·{' '}
                      {rate.rebate_rate_pct.toFixed(2)}% rebate
                    </p>
                    {rate.description && (
                      <p className="mt-0.5 text-xs opacity-70">{rate.description}</p>
                    )}
                  </div>
                );
              })}
            {rates.filter((r) => r.is_active).length === 0 && (
              <p className="text-sm text-slate-500">Enable at least one tier to see the pyramid.</p>
            )}
          </div>
        </div>
      )}
    </PageContainer>
  );
};
