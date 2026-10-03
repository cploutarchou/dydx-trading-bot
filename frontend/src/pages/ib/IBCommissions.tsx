import { useQuery } from '@tanstack/react-query';
import { Loader2, WalletCards } from 'lucide-react';
import api from '../../api';
import { PageContainer } from '../../components/PageContainer';
import { formatUsdFixed , formatPct } from '../../utils/format';

const formatDate = (value?: string) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
};

export const IBCommissions = () => {
  const commissionQuery = useQuery({
    queryKey: ['portal', 'commission-metrics', 'ib'],
    queryFn: async () => (await api.getPartnerCommissionMetrics()).data,
    staleTime: 15_000,
    refetchInterval: 60_000,
  });

  const tierRatesQuery = useQuery({
    queryKey: ['ib', 'tier-rates'],
    queryFn: async () => (await api.listIBTierRates()).data,
    staleTime: 60_000,
  });

  const ownerCommission = commissionQuery.data?.owner;
  const downlineCommission = commissionQuery.data?.downline;
  const directPartnerIds = commissionQuery.data?.direct_partner_ids ?? [];
  const tierRates = tierRatesQuery.data?.rates ?? [];

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Commissions</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">Commission metrics</h1>
        <p className="mt-2 text-sm text-slate-400">
          Your own commission period summary and aggregated downline statistics. Admins can query
          any user by passing a user_id query parameter.
        </p>
      </div>

      {commissionQuery.isLoading ? (
        <div className="flex items-center gap-2 text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading commission data...
        </div>
      ) : (
        <>
          {/* Own commission period */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold text-white">Your commission period</h2>
            {ownerCommission ? (
              <>
                <p className="mt-1 text-xs text-slate-500">
                  {formatDate(ownerCommission.period_start)} —{' '}
                  {formatDate(ownerCommission.period_end)}
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    {
                      label: 'Net commission',
                      value: formatUsdFixed(ownerCommission.net_commission_usd),
                      color: 'text-emerald-300',
                    },
                    {
                      label: 'Gross commission',
                      value: formatUsdFixed(ownerCommission.gross_commission_usd),
                      color: 'text-cyan-300',
                    },
                    {
                      label: 'Rebate paid',
                      value: formatUsdFixed(ownerCommission.rebate_usd),
                      color: 'text-violet-300',
                    },
                    {
                      label: 'Notional volume',
                      value: formatUsdFixed(ownerCommission.notional_volume_usd),
                      color: 'text-amber-300',
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                    >
                      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                        {item.label}
                      </p>
                      <p className={`mt-2 text-xl font-semibold ${item.color}`}>{item.value}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                      Direct clients
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-white">
                      {ownerCommission.direct_clients}
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                      Sub-IB count
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-white">
                      {ownerCommission.sub_ib_count}
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <p className="mt-4 text-sm text-slate-400">
                No commission data on record for this period.
              </p>
            )}
          </div>

          {/* Downline aggregate */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold text-white">Downline aggregate</h2>
            <p className="mt-1 text-sm text-slate-400">
              Sum across your entire downline network for the same period.
            </p>
            {downlineCommission ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: 'Net commission',
                    value: formatUsdFixed(downlineCommission.net_commission_usd),
                  },
                  {
                    label: 'Gross commission',
                    value: formatUsdFixed(downlineCommission.gross_commission_usd),
                  },
                  { label: 'Rebate paid', value: formatUsdFixed(downlineCommission.rebate_usd) },
                  {
                    label: 'Notional volume',
                    value: formatUsdFixed(downlineCommission.notional_volume_usd),
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                  >
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                      {item.label}
                    </p>
                    <p className="mt-2 text-xl font-semibold text-slate-200">{item.value}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-400">No downline data available.</p>
            )}
          </div>

          {/* Direct partner IDs */}
          {directPartnerIds.length > 0 && (
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
              <h2 className="text-lg font-semibold text-white">Direct partners</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {directPartnerIds.map((id) => (
                  <span
                    key={id}
                    className="rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 font-mono text-xs text-slate-300"
                  >
                    #{id}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Active tier rates reference */}
          {tierRates.length > 0 && (
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
              <h2 className="flex items-center gap-2 text-base font-semibold text-white">
                <WalletCards className="h-4 w-4 text-cyan-300" />
                Active tier rates applied to your network
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                These rates are applied to your pyramid when commissions are calculated.
              </p>
              <div className="mt-4 overflow-auto rounded-xl border border-slate-700/60">
                <table className="min-w-full text-sm text-slate-300">
                  <thead className="bg-slate-950/80 uppercase tracking-[0.14em] text-xs text-slate-400">
                    <tr>
                      <th className="px-3 py-2 text-left">Tier</th>
                      <th className="px-3 py-2 text-left">Commission</th>
                      <th className="px-3 py-2 text-left">Rebate</th>
                      <th className="px-3 py-2 text-left">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tierRates
                      .filter((r) => r.is_active)
                      .map((rate) => (
                        <tr key={rate.tier_level} className="border-t border-slate-800/80">
                          <td className="px-3 py-2 font-semibold text-slate-100">
                            Tier {rate.tier_level}
                          </td>
                          <td className="px-3 py-2 tabular-nums text-emerald-300">
                            {formatPct(rate.commission_rate_pct, 2)}
                          </td>
                          <td className="px-3 py-2 tabular-nums text-violet-300">
                            {formatPct(rate.rebate_rate_pct, 2)}
                          </td>
                          <td className="px-3 py-2 text-slate-400">{rate.description || '—'}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
};
