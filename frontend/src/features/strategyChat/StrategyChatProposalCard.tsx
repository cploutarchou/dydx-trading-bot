import { AlertTriangle, Check, Loader2 } from 'lucide-react';
import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import type {
  StrategyChatChange,
  StrategyChatMessage,
  StrategyChatProposal,
  StrategyChatValue,
} from '../../api';
import { getApiErrorCode } from '../../api/requestError';
import {
  describeStrategyChatError,
  PROPOSAL_NOT_PENDING,
  STRATEGY_RUNNING_ACK_REQUIRED,
} from './chatErrors';
import {
  useApplyStrategyChatProposal,
  useCreateStrategyFromChatProposal,
  useDismissStrategyChatProposal,
  useRefreshStrategyChat,
} from './hooks';

// backtest_strategies.name is VARCHAR(100).
const STRATEGY_NAME_MAX_LENGTH = 100;

const RUNNING_CONSEQUENCE =
  'This strategy is running. The change is saved now and only takes effect after you stop and start it.';

const formatNumber = (value: number): string =>
  Number.isInteger(value) ? String(value) : String(Number(value.toFixed(6)));

const formatChatValue = (value: StrategyChatValue | null | undefined, unit: string): string => {
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

const formatDroppedValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value).slice(0, 80);
  } catch {
    return '—';
  }
};

const defaultVariantName = (suggestedName: string, strategyName: string): string =>
  (suggestedName.trim() || `${strategyName} (variant)`).slice(0, STRATEGY_NAME_MAX_LENGTH);

const badgeClass =
  'inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide';

function ChangeBadges({ change }: { change: StrategyChatChange }) {
  return (
    <>
      {change.risk === 'money' && (
        <span className={`${badgeClass} border-amber-500/40 bg-amber-500/10 text-amber-200`}>
          Changes trade size
        </span>
      )}
      {change.risk === 'risk_control' && (
        <span className={`${badgeClass} border-rose-500/40 bg-rose-500/10 text-rose-200`}>
          Changes a risk limit
        </span>
      )}
      {change.backtest_only && (
        <span className={`${badgeClass} border-slate-700 bg-slate-800/70 text-slate-400`}>
          Backtest only
        </span>
      )}
    </>
  );
}

function ProposalOutcome({ message }: { message: StrategyChatMessage }) {
  const result = message.proposal_result;

  if (message.proposal_status === 'applied') {
    // Only the stored result knows how many changes were written; without it
    // the count is unknown, never the number of proposed changes.
    const count = result ? (result.applied_fields ?? []).length : null;
    return (
      <div
        role="status"
        className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100"
      >
        <p className="flex items-center gap-1.5 font-semibold">
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          <span>
            {count === null ? 'Applied' : `Applied ${count} ${count === 1 ? 'change' : 'changes'}`}
          </span>
        </p>
        {result?.acknowledged_running && (
          <p className="mt-1 text-emerald-100/80">
            Saved while the strategy was running. It takes effect after you stop and start it.
          </p>
        )}
      </div>
    );
  }

  if (message.proposal_status === 'created') {
    const newStrategyId = result?.new_strategy_id;
    const newStrategyName = result?.new_strategy_name || 'new strategy';
    return (
      <div
        role="status"
        className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100"
      >
        <p className="flex items-center gap-1.5 font-semibold">
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          <span>{`Created “${newStrategyName}”`}</span>
        </p>
        {newStrategyId ? (
          <Link
            to={`/strategies/${newStrategyId}/edit`}
            className="rounded-md border border-emerald-400/40 bg-emerald-500/15 px-2.5 py-1 font-semibold text-emerald-100 transition hover:bg-emerald-500/25"
          >
            Open strategy
          </Link>
        ) : null}
      </div>
    );
  }

  if (message.proposal_status === 'dismissed') {
    return <p className="mt-3 text-xs text-slate-500">Dismissed</p>;
  }

  return null;
}

interface StrategyChatProposalCardProps {
  strategyId: number;
  strategyName: string;
  message: StrategyChatMessage;
  proposal: StrategyChatProposal;
  /** True when the strategy runtime is active or its state is unknown. */
  runtimeActive: boolean;
}

/**
 * A structured proposal inside an assistant reply. Only a pending proposal can
 * be applied, turned into a new strategy or dismissed; the server re-validates
 * every change, so the values shown here are never sent back.
 */
export function StrategyChatProposalCard({
  strategyId,
  strategyName,
  message,
  proposal,
  runtimeActive,
}: StrategyChatProposalCardProps) {
  const [selected, setSelected] = useState<ReadonlySet<string>>(
    () => new Set(proposal.changes.map((change) => change.field))
  );
  const [mode, setMode] = useState<'idle' | 'confirm-running' | 'create'>('idle');
  const [newName, setNewName] = useState(() =>
    defaultVariantName(proposal.suggested_name ?? '', strategyName)
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const nameInputId = useId();
  const applyMutation = useApplyStrategyChatProposal(strategyId);
  const createMutation = useCreateStrategyFromChatProposal(strategyId);
  const dismissMutation = useDismissStrategyChatProposal(strategyId);
  const refreshChat = useRefreshStrategyChat(strategyId);

  const actionable = message.proposal_status === 'pending';
  const busy = applyMutation.isPending || createMutation.isPending || dismissMutation.isPending;
  // Proposal order, never an empty list: the backend reads a missing list as "all changes".
  const selectedFields = proposal.changes
    .filter((change) => selected.has(change.field))
    .map((change) => change.field);
  const nothingSelected = selectedFields.length === 0;
  // Once applied or created, the result lists what was written: a change
  // outside applied_fields was not applied unless the strategy already had
  // that value (unchanged_fields). A missing list means nothing was written.
  const outcomeKnown =
    message.proposal_status === 'applied' || message.proposal_status === 'created';
  const appliedFields = outcomeKnown ? (message.proposal_result?.applied_fields ?? []) : undefined;
  const unchangedFields = outcomeKnown
    ? (message.proposal_result?.unchanged_fields ?? [])
    : undefined;

  const toggleField = (field: string) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(field)) {
        next.delete(field);
      } else {
        next.add(field);
      }
      return next;
    });
  };

  const handleActionError = (error: unknown) => {
    if (getApiErrorCode(error) === PROPOSAL_NOT_PENDING) {
      void refreshChat();
    }
    setActionError(describeStrategyChatError(error));
  };

  const runApply = async (acknowledgeRunning: boolean) => {
    if (nothingSelected) {
      return;
    }
    setActionError(null);
    try {
      await applyMutation.mutateAsync({
        messageId: message.id,
        fields: selectedFields,
        acknowledgeRunning,
      });
      setMode('idle');
    } catch (error: unknown) {
      if (!acknowledgeRunning && getApiErrorCode(error) === STRATEGY_RUNNING_ACK_REQUIRED) {
        setMode('confirm-running');
        return;
      }
      handleActionError(error);
    }
  };

  const startApply = () => {
    setActionError(null);
    if (runtimeActive) {
      setMode('confirm-running');
      return;
    }
    void runApply(false);
  };

  const runCreate = async () => {
    const name = newName.trim();
    if (!name) {
      setActionError('Enter a name for the new strategy.');
      return;
    }
    if (nothingSelected) {
      return;
    }
    setActionError(null);
    try {
      await createMutation.mutateAsync({ messageId: message.id, name, fields: selectedFields });
      setMode('idle');
    } catch (error: unknown) {
      handleActionError(error);
    }
  };

  const runDismiss = async () => {
    setActionError(null);
    try {
      await dismissMutation.mutateAsync({ messageId: message.id });
      setMode('idle');
    } catch (error: unknown) {
      handleActionError(error);
    }
  };

  const primaryButtonClass =
    'inline-flex items-center gap-1.5 rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400';
  const secondaryButtonClass =
    'inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs font-semibold text-slate-100 transition hover:border-cyan-500/40 disabled:cursor-not-allowed disabled:opacity-50';
  const createFirst = proposal.kind === 'new_strategy';

  const applyButton = (
    <button
      key="apply"
      type="button"
      onClick={startApply}
      disabled={busy || nothingSelected}
      className={createFirst ? secondaryButtonClass : primaryButtonClass}
    >
      {applyMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      Apply to strategy
    </button>
  );
  const createButton = (
    <button
      key="create"
      type="button"
      onClick={() => {
        setActionError(null);
        setMode('create');
      }}
      disabled={busy || nothingSelected}
      className={createFirst ? primaryButtonClass : secondaryButtonClass}
    >
      Create new strategy
    </button>
  );

  return (
    <section
      aria-label={proposal.title || 'Proposed changes'}
      className="mt-2 rounded-xl border border-cyan-500/25 bg-slate-950/60 p-3"
    >
      <h3 className="text-sm font-semibold text-white">{proposal.title || 'Proposed changes'}</h3>
      {proposal.summary && (
        <p className="mt-1 whitespace-pre-line wrap-break-word text-xs leading-5 text-slate-300">
          {proposal.summary}
        </p>
      )}

      {proposal.changes.length > 0 && (
        <ul className="mt-3 space-y-2">
          {proposal.changes.map((change) => {
            const label = change.label || change.field;
            const alreadySet = unchangedFields?.includes(change.field) ?? false;
            const notApplied = appliedFields
              ? !alreadySet && !appliedFields.includes(change.field)
              : false;
            return (
              <li
                key={change.field}
                className={`rounded-lg border border-slate-700/70 bg-slate-900/60 px-3 py-2 ${
                  notApplied ? 'opacity-60' : ''
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  {actionable ? (
                    <label className="flex min-w-0 items-center gap-2 text-sm font-medium text-slate-100">
                      <input
                        type="checkbox"
                        checked={selected.has(change.field)}
                        onChange={() => toggleField(change.field)}
                        disabled={busy}
                        className="h-4 w-4 shrink-0 accent-cyan-500"
                      />
                      <span className="wrap-break-word">{label}</span>
                    </label>
                  ) : (
                    <p className="min-w-0 text-sm font-medium text-slate-100">
                      <span className="wrap-break-word">{label}</span>
                      {alreadySet && (
                        <span className="ml-2 text-[11px] font-normal text-slate-500">
                          Already set
                        </span>
                      )}
                      {notApplied && (
                        <span className="ml-2 text-[11px] font-normal text-slate-500">
                          Not applied
                        </span>
                      )}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    <ChangeBadges change={change} />
                  </div>
                </div>
                <p className="mt-1 font-mono text-xs text-slate-300">
                  <span className="text-slate-400">
                    {formatChatValue(change.current, change.unit)}
                  </span>
                  {' → '}
                  <span className="text-cyan-200">
                    {formatChatValue(change.proposed, change.unit)}
                  </span>
                </p>
                {change.reason && (
                  <p className="mt-1 whitespace-pre-line wrap-break-word text-xs leading-5 text-slate-400">
                    {change.reason}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {proposal.dropped.length > 0 && (
        <div className="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-xs text-amber-100/90">
          <p className="font-semibold text-amber-200">Left out of this proposal</p>
          <ul className="mt-1 space-y-1">
            {proposal.dropped.map((item, index) => (
              <li key={`${item.field}-${index}`} className="wrap-break-word">
                <span className="font-mono">{item.field || 'unknown'}</span>
                {` = ${formatDroppedValue(item.value)}: ${item.reason}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {actionable && mode === 'idle' && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {createFirst ? [createButton, applyButton] : [applyButton, createButton]}
          <button
            type="button"
            onClick={() => void runDismiss()}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-400 transition hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {dismissMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Dismiss
          </button>
          {proposal.changes.length > 1 && (
            <span className="text-[11px] text-slate-500">
              {`${selectedFields.length} of ${proposal.changes.length} selected`}
            </span>
          )}
        </div>
      )}

      {actionable && mode === 'confirm-running' && (
        <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
          <p className="flex gap-2 text-xs leading-5 text-amber-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
            <span>{RUNNING_CONSEQUENCE}</span>
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void runApply(true)}
              disabled={busy || nothingSelected}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            >
              {applyMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Save changes
            </button>
            <button
              type="button"
              onClick={() => setMode('idle')}
              disabled={busy}
              className={secondaryButtonClass}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {actionable && mode === 'create' && (
        <div className="mt-3 rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-3">
          <label htmlFor={nameInputId} className="block text-xs font-medium text-slate-300">
            New strategy name
          </label>
          <input
            id={nameInputId}
            type="text"
            value={newName}
            maxLength={STRATEGY_NAME_MAX_LENGTH}
            onChange={(event) => setNewName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                void runCreate();
              }
            }}
            disabled={busy}
            className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-white focus:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
          />
          <p className="mt-1.5 text-[11px] leading-4 text-slate-500">
            The new strategy copies the settings of {strategyName} with the selected changes. It is
            private and does not start trading.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void runCreate()}
              disabled={busy || nothingSelected || newName.trim() === ''}
              className={primaryButtonClass}
            >
              {createMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create strategy
            </button>
            <button
              type="button"
              onClick={() => setMode('idle')}
              disabled={busy}
              className={secondaryButtonClass}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {actionError && (
        <p role="alert" className="mt-2 text-xs text-rose-300">
          {actionError}
        </p>
      )}

      <ProposalOutcome message={message} />
    </section>
  );
}
