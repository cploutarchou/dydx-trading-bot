export interface StrategyRef {
  id: number;
  name: string;
}

export interface BacktestRun {
  run_id: string;
  name?: string;
  status: string;
  total_pnl?: number;
  win_rate?: number;
  sharpe_ratio?: number;
  total_trades?: number;
  created_at: string;
  updated_at?: string;
  progress_pct?: number;
  max_drawdown?: number;
  max_drawdown_pct?: number;
  strategy_id?: number;
  strategy_name?: string;
  request?: Record<string, unknown>;
}

export interface StrategyAggregate {
  key: string;
  label: string;
  strategyId?: number;
  totalRuns: number;
  completedRuns: number;
  activeRuns: number;
  totalPnl: number;
  avgPnl: number;
  avgWinRatePct: number;
  avgSharpe: number;
  avgDrawdownPct: number;
  profitabilityRatePct: number;
  compositeScore: number;
  lastRunAt?: string;
}

export interface IntelligenceSnapshot {
  totalRuns: number;
  completedRuns: number;
  activeRuns: number;
  profitableRuns: number;
  profitableRatePct: number;
  totalPnl: number;
  avgSharpe: number;
  avgDrawdownPct: number;
  strategies: StrategyAggregate[];
  bestStrategy: StrategyAggregate | null;
  safestStrategy: StrategyAggregate | null;
  mostConsistentStrategy: StrategyAggregate | null;
  bestSingleRun: BacktestRun | null;
  topRuns: BacktestRun[];
}

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

export const safeNumber = (value: unknown, fallback = 0): number => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
};

export const normalizePercent = (value: unknown): number => {
  const numeric = safeNumber(value, 0);
  if (Math.abs(numeric) <= 1) {
    return numeric * 100;
  }
  return numeric;
};

const normalizeStatus = (status?: string): string => String(status ?? '').trim().toUpperCase();

const isCompleted = (run: BacktestRun): boolean => normalizeStatus(run.status) === 'COMPLETED';

export const isActiveBacktestRun = (run: BacktestRun): boolean => {
  const status = normalizeStatus(run.status);
  return status === 'RUNNING' || status === 'PENDING' || status === 'CREATED';
};

const average = (values: number[]): number =>
  values.length > 0 ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;

export const formatCurrency = (value: number): string =>
  `${value >= 0 ? '+' : '-'}$${Math.abs(value).toLocaleString('en-US', { maximumFractionDigits: 2 })}`;

export const formatPercent = (value: number): string => `${value.toFixed(1)}%`;

export const formatDateTime = (value?: string): string => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'N/A';
  return parsed.toISOString().replace('T', ' ').replace('Z', ' UTC');
};

export const extractBacktestRuns = (response: unknown): BacktestRun[] => {
  const payload = toRecord(response);
  const data = toRecord(payload.data);

  if (Array.isArray(data.backtests)) {
    return data.backtests as BacktestRun[];
  }
  if (Array.isArray(payload.backtests)) {
    return payload.backtests as BacktestRun[];
  }
  if (Array.isArray(data.runs)) {
    return data.runs as BacktestRun[];
  }
  if (Array.isArray(payload.runs)) {
    return payload.runs as BacktestRun[];
  }
  return [];
};

const getRunStrategyIdentity = (
  run: BacktestRun,
  strategiesById: Map<number, string>
): Pick<StrategyAggregate, 'key' | 'label' | 'strategyId'> => {
  const request = toRecord(run.request);
  const strategyId = safeNumber(run.strategy_id ?? request.strategy_id, 0);
  const resolvedStrategyId = Number.isInteger(strategyId) && strategyId > 0 ? strategyId : undefined;

  const labelFromStrategyId =
    resolvedStrategyId !== undefined ? strategiesById.get(resolvedStrategyId) : undefined;
  const label =
    (typeof run.strategy_name === 'string' && run.strategy_name.trim()) ||
    labelFromStrategyId ||
    ((typeof run.name === 'string' && run.name.trim()) || '').trim() ||
    'Ad-hoc setup';

  if (resolvedStrategyId !== undefined) {
    return {
      key: `strategy:${resolvedStrategyId}`,
      label,
      strategyId: resolvedStrategyId,
    };
  }

  return {
    key: `setup:${label.toLowerCase()}`,
    label,
  };
};

export const buildIntelligence = (
  runs: BacktestRun[],
  strategiesById: Map<number, string>
): IntelligenceSnapshot => {
  const completedRuns = runs.filter(isCompleted);
  const activeRuns = runs.filter(isActiveBacktestRun);
  const profitableRuns = completedRuns.filter((run) => safeNumber(run.total_pnl) > 0);
  const topRuns = [...completedRuns]
    .sort((a, b) => safeNumber(b.total_pnl) - safeNumber(a.total_pnl))
    .slice(0, 5);

  const grouped = new Map<string, StrategyAggregate & { completedRunCount: number; profitableRunCount: number }>();

  for (const run of runs) {
    const identity = getRunStrategyIdentity(run, strategiesById);
    const status = normalizeStatus(run.status);
    const group =
      grouped.get(identity.key) ??
      {
        ...identity,
        totalRuns: 0,
        completedRuns: 0,
        activeRuns: 0,
        totalPnl: 0,
        avgPnl: 0,
        avgWinRatePct: 0,
        avgSharpe: 0,
        avgDrawdownPct: 0,
        profitabilityRatePct: 0,
        compositeScore: 0,
        completedRunCount: 0,
        profitableRunCount: 0,
      };

    group.totalRuns += 1;
    if (status === 'COMPLETED') {
      group.completedRuns += 1;
      group.completedRunCount += 1;
      group.totalPnl += safeNumber(run.total_pnl);
      group.avgPnl += safeNumber(run.total_pnl);
      group.avgWinRatePct += normalizePercent(run.win_rate);
      group.avgSharpe += safeNumber(run.sharpe_ratio);
      group.avgDrawdownPct += safeNumber(run.max_drawdown_pct ?? run.max_drawdown);
      if (safeNumber(run.total_pnl) > 0) {
        group.profitableRunCount += 1;
      }
    }
    if (status === 'RUNNING' || status === 'PENDING' || status === 'CREATED') {
      group.activeRuns += 1;
    }

    const candidateDate = run.updated_at || run.created_at;
    if (candidateDate && (!group.lastRunAt || candidateDate > group.lastRunAt)) {
      group.lastRunAt = candidateDate;
    }

    grouped.set(identity.key, group);
  }

  const strategies = [...grouped.values()]
    .map((group) => {
      const completedCount = Math.max(group.completedRunCount, 1);
      const avgPnl = group.completedRunCount > 0 ? group.avgPnl / completedCount : 0;
      const avgWinRatePct = group.completedRunCount > 0 ? group.avgWinRatePct / completedCount : 0;
      const avgSharpe = group.completedRunCount > 0 ? group.avgSharpe / completedCount : 0;
      const avgDrawdownPct = group.completedRunCount > 0 ? group.avgDrawdownPct / completedCount : 0;
      const profitabilityRatePct =
        group.completedRunCount > 0 ? (group.profitableRunCount / group.completedRunCount) * 100 : 0;
      const sampleConfidence = Math.min(group.completedRunCount, 5) / 5;
      const compositeScore =
        avgPnl * 0.08 +
        avgSharpe * 18 +
        profitabilityRatePct * 0.7 -
        avgDrawdownPct * 1.3 +
        sampleConfidence * 10;

      return {
        key: group.key,
        label: group.label,
        strategyId: group.strategyId,
        totalRuns: group.totalRuns,
        completedRuns: group.completedRuns,
        activeRuns: group.activeRuns,
        totalPnl: group.totalPnl,
        avgPnl,
        avgWinRatePct,
        avgSharpe,
        avgDrawdownPct,
        profitabilityRatePct,
        compositeScore,
        lastRunAt: group.lastRunAt,
      };
    })
    .sort((left, right) => right.compositeScore - left.compositeScore);

  const profitableCandidates = strategies.filter(
    (strategy) => strategy.completedRuns > 0 && strategy.avgPnl >= 0
  );
  const safestPool = profitableCandidates.length > 0 ? profitableCandidates : strategies;

  return {
    totalRuns: runs.length,
    completedRuns: completedRuns.length,
    activeRuns: activeRuns.length,
    profitableRuns: profitableRuns.length,
    profitableRatePct:
      completedRuns.length > 0 ? (profitableRuns.length / completedRuns.length) * 100 : 0,
    totalPnl: completedRuns.reduce((sum, run) => sum + safeNumber(run.total_pnl), 0),
    avgSharpe: average(completedRuns.map((run) => safeNumber(run.sharpe_ratio))),
    avgDrawdownPct: average(
      completedRuns.map((run) => safeNumber(run.max_drawdown_pct ?? run.max_drawdown))
    ),
    strategies,
    bestStrategy: strategies[0] ?? null,
    safestStrategy:
      [...safestPool]
        .filter((strategy) => strategy.completedRuns > 0)
        .sort(
          (left, right) =>
            left.avgDrawdownPct - right.avgDrawdownPct ||
            right.avgSharpe - left.avgSharpe ||
            right.totalPnl - left.totalPnl
        )[0] ?? null,
    mostConsistentStrategy:
      [...strategies]
        .filter((strategy) => strategy.completedRuns > 0)
        .sort(
          (left, right) =>
            right.profitabilityRatePct - left.profitabilityRatePct ||
            right.avgSharpe - left.avgSharpe ||
            right.completedRuns - left.completedRuns
        )[0] ?? null,
    bestSingleRun: topRuns[0] ?? null,
    topRuns,
  };
};
