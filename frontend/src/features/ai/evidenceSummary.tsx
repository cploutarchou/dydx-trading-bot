import type { AIEvidenceSummary, AIParamSuggestion } from '../../api';

const count = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.round(value) : 0;

const plural = (value: number, singular: string, pluralForm = `${singular}s`): string =>
  `${value} ${value === 1 ? singular : pluralForm}`;

/**
 * The chips shown under an AI answer, only for the parts the server actually
 * had: "5 completed runs · 312 trades · 12 pairs · 4 cointegrated pairs ·
 * live: 9 closed, 2 open".
 */
export const formatEvidenceSummaryChips = (summary: AIEvidenceSummary): string[] => {
  const chips: string[] = [];
  const completedRuns = count(summary.completed_runs);
  const trades = count(summary.trades_analysed);
  const pairs = count(summary.pairs_analysed);
  const cointegrated = count(summary.cointegrated_pairs);
  if (completedRuns > 0) {
    chips.push(plural(completedRuns, 'completed run'));
  }
  if (trades > 0) {
    chips.push(plural(trades, 'trade'));
  }
  if (pairs > 0) {
    chips.push(plural(pairs, 'pair'));
  }
  if (cointegrated > 0) {
    chips.push(plural(cointegrated, 'cointegrated pair'));
  }
  if (summary.live_available === true) {
    chips.push(
      `live: ${count(summary.live_closed_trades)} closed, ${count(summary.live_open_positions)} open`
    );
  }
  return chips;
};

const evidenceNotes = (summary: AIEvidenceSummary): string[] =>
  Array.isArray(summary.data_notes)
    ? summary.data_notes.filter(
        (note): note is string => typeof note === 'string' && note.trim().length > 0
      )
    : [];

interface EvidenceSummaryChipsProps {
  summary: AIEvidenceSummary | null | undefined;
  /** Smaller, quieter chips (chat messages). */
  compact?: boolean;
  /** Also list the summary's data_notes under the chips. */
  showNotes?: boolean;
  className?: string;
}

/** Small muted chips saying what the answer was grounded in; nothing when there is no data. */
export function EvidenceSummaryChips({
  summary,
  compact = false,
  showNotes = false,
  className = '',
}: EvidenceSummaryChipsProps) {
  if (!summary || typeof summary !== 'object') {
    return null;
  }
  const chips = formatEvidenceSummaryChips(summary);
  const notes = showNotes ? evidenceNotes(summary) : [];
  if (chips.length === 0 && notes.length === 0) {
    return null;
  }
  const chipClass = compact
    ? 'rounded-full border border-slate-700/70 bg-slate-800/50 px-2 py-0.5 text-[10px] text-slate-400'
    : 'rounded-full border border-slate-700 bg-slate-900/70 px-2.5 py-0.5 text-[11px] text-slate-300';

  return (
    <div className={className}>
      {chips.length > 0 && (
        <ul aria-label="Evidence" className="flex flex-wrap gap-1.5">
          {chips.map((chip) => (
            <li key={chip} className={chipClass}>
              {chip}
            </li>
          ))}
        </ul>
      )}
      {notes.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-[11px] leading-4 text-slate-500">
          {notes.map((note, index) => (
            <li key={`${index}-${note}`} className="wrap-break-word">
              {note}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const badgeClass =
  'inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide';

/** Same badge semantics as the strategy chat's proposal card. */
export function AISuggestionRiskBadges({
  risk,
  backtestOnly,
}: {
  risk: AIParamSuggestion['risk'] | undefined;
  backtestOnly: boolean | undefined;
}) {
  return (
    <>
      {risk === 'money' && (
        <span className={`${badgeClass} border-amber-500/40 bg-amber-500/10 text-amber-200`}>
          Changes trade size
        </span>
      )}
      {risk === 'risk_control' && (
        <span className={`${badgeClass} border-rose-500/40 bg-rose-500/10 text-rose-200`}>
          Changes a risk limit
        </span>
      )}
      {backtestOnly === true && (
        <span className={`${badgeClass} border-slate-700 bg-slate-800/70 text-slate-400`}>
          Backtest only
        </span>
      )}
    </>
  );
}

const formatNumber = (value: number): string =>
  Number.isInteger(value) ? String(value) : String(Number(value.toFixed(6)));

/** "50 USD", "15%", "On"; "—" when there is no value. */
export const formatAIParamValue = (value: unknown, unit: string): string => {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'boolean') {
    return value ? 'On' : 'Off';
  }
  const text = typeof value === 'number' ? formatNumber(value) : String(value);
  if (!unit) {
    return text;
  }
  return unit === '%' ? `${text}%` : `${text} ${unit}`;
};
