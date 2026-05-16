import { AlertTriangle, CheckCircle2, Clock3, Loader2, Wifi, WifiOff } from 'lucide-react';
import type { ReactNode } from 'react';

export type LiveStateTone = 'healthy' | 'live' | 'delayed' | 'stale' | 'offline' | 'loading';

const toneClasses: Record<LiveStateTone, string> = {
  healthy: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  live: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  delayed: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  stale: 'border-rose-500/30 bg-rose-500/10 text-rose-200',
  offline: 'border-slate-700/70 bg-slate-900/70 text-slate-300',
  loading: 'border-slate-700/70 bg-slate-900/70 text-slate-300',
};

const iconMap = {
  healthy: CheckCircle2,
  live: Wifi,
  delayed: Clock3,
  stale: AlertTriangle,
  offline: WifiOff,
  loading: Loader2,
} satisfies Record<LiveStateTone, typeof CheckCircle2>;

export interface LiveStateBadgeProps {
  tone: LiveStateTone;
  label: ReactNode;
  detail?: ReactNode;
  className?: string;
}

export const LiveStateBadge = ({ tone, label, detail, className = '' }: LiveStateBadgeProps) => {
  const Icon = iconMap[tone];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold uppercase ${toneClasses[tone]} ${className}`.trim()}
    >
      <Icon className={`h-3.5 w-3.5 ${tone === 'loading' ? 'animate-spin' : ''}`} />
      <span>{label}</span>
      {detail && <span className="normal-case text-current/70">{detail}</span>}
    </span>
  );
};

export const getFreshnessTone = (
  updatedAt?: string | null,
  nowMs: number = Date.now()
): LiveStateTone => {
  if (!updatedAt) return 'offline';
  const updatedMs = new Date(updatedAt).getTime();
  if (!Number.isFinite(updatedMs)) return 'offline';
  const ageMs = Math.max(0, nowMs - updatedMs);
  if (ageMs <= 15000) return 'live';
  if (ageMs <= 45000) return 'delayed';
  return 'stale';
};

const backtestProgressSourceLabels: Record<string, string> = {
  status: 'live status',
  websocket: 'websocket',
  stale_resync: 'stale resync',
  polling_recovery: 'polling recovery',
  polling: 'polling',
  list_fallback: 'list fallback',
  details: 'details status',
};

export const formatBacktestProgressSourceLabel = (progressSource?: string | null): string => {
  if (!progressSource) return 'default';
  return backtestProgressSourceLabels[progressSource] || progressSource;
};

export interface BacktestStreamHealth {
  label: string;
  toneClasses: string;
  dotClass: string;
}

export interface BacktestStreamBadge {
  label: string;
  tone: LiveStateTone;
}

export const resolveBacktestStreamBadge = (
  progressSource: string | undefined,
  isConnected: boolean
): BacktestStreamBadge => {
  if (isConnected && progressSource === 'websocket') {
    return {
      label: 'Live stream healthy',
      tone: 'healthy',
    };
  }

  if (progressSource === 'stale_resync' || progressSource === 'polling_recovery') {
    return {
      label: 'Resyncing via fallback',
      tone: 'delayed',
    };
  }

  if (progressSource === 'polling') {
    return {
      label: 'Recovery polling active',
      tone: 'live',
    };
  }

  return {
    label: isConnected ? 'Live stream pending' : 'Awaiting stream',
    tone: 'offline',
  };
};

export const resolveBacktestStreamHealth = (
  progressSource: string | undefined,
  isConnected: boolean
): BacktestStreamHealth => {
  const badge = resolveBacktestStreamBadge(progressSource, isConnected);

  if (badge.tone === 'healthy') {
    return {
      label: badge.label,
      toneClasses: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
      dotClass: 'bg-emerald-400',
    };
  }

  if (badge.tone === 'delayed') {
    return {
      label: badge.label,
      toneClasses: 'border-amber-500/35 bg-amber-500/10 text-amber-200',
      dotClass: 'bg-amber-400',
    };
  }

  if (badge.tone === 'live') {
    return {
      label: badge.label,
      toneClasses: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
      dotClass: 'bg-cyan-400',
    };
  }

  return {
    label: badge.label,
    toneClasses: 'border-slate-700 bg-slate-900/70 text-slate-300',
    dotClass: 'bg-slate-400',
  };
};
