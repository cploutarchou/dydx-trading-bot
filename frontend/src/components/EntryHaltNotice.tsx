/**
 * Entry Halt Notice
 *
 * Shown for a strategy whose bot has stopped opening new pairs because an
 * emergency close failed and a position leg may be open without its hedge. The
 * bot keeps managing exits. The operator has to check the account on dYdX and
 * tick an explicit acknowledgement before the halt can be cleared. A halt this
 * screen cannot fully read is shown, but is never offered for clearing.
 */

import { useId, useState } from 'react';
import type { EntryHaltState } from '../api';
import { useClearStrategyEntryHaltMutation, useStrategyEntryHalt } from '../api/hooks';
import {
  ENTRY_HALT_NOTE_MAX_LENGTH,
  entryHaltAccountLabel,
  entryHaltErrorText,
  entryHaltPairLabel,
  formatEntryHaltTime,
  isEntryHaltVisible,
} from '../utils/entryHalt';

export interface EntryHaltNoticeProps {
  state: EntryHaltState | null | undefined;
  busy: boolean;
  error: string | null;
  onClear: (note: string) => void;
  className?: string;
}

export const EntryHaltNotice = ({
  state,
  busy,
  error,
  onClear,
  className = '',
}: EntryHaltNoticeProps) => {
  const headingId = useId();
  const noteId = useId();
  // The acknowledgement is only valid for the exact halt it was ticked for: a
  // new halt on the same account has to be checked and acknowledged again.
  const [acknowledgedFor, setAcknowledgedFor] = useState<number | null>(null);
  const [note, setNote] = useState('');

  if (!state || !isEntryHaltVisible(state)) {
    return null;
  }

  const halt = state.unverified ? null : state.halt;
  const sectionClass =
    `rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-left ${className}`.trim();

  if (halt === null) {
    return (
      <section aria-labelledby={headingId} className={sectionClass}>
        <h3 id={headingId} className="text-sm font-semibold text-red-200">
          Entry halt state could not be read
        </h3>
        <p className="mt-2 text-sm text-red-100">
          The bot opens no new pairs while it cannot confirm whether entries are halted on this
          account. Open positions are still managed. It checks again on every cycle; nothing can be
          cleared from here until the state is readable.
        </p>
      </section>
    );
  }

  const accountLabel = entryHaltAccountLabel(halt);
  const haltedAt = formatEntryHaltTime(halt.halted_at);
  const pairLabel = entryHaltPairLabel(halt.details);
  const errorText = entryHaltErrorText(halt.details);
  const acknowledged = acknowledgedFor === halt.id;
  const acknowledgementText =
    halt.network === 'mainnet'
      ? `I checked MAINNET subaccount ${halt.subaccount_number} on dYdX: no position is left without its hedge, and real funds are at stake if I am wrong.`
      : `I checked testnet subaccount ${halt.subaccount_number} on dYdX: no position is left without its hedge.`;

  return (
    <section aria-labelledby={headingId} className={sectionClass}>
      <h3 id={headingId} className="text-sm font-semibold text-red-200">
        New entries are halted
      </h3>

      <dl className="mt-3 space-y-2 text-sm text-red-100">
        <div className="flex items-center justify-between gap-3">
          <dt>Account</dt>
          <dd className="font-medium text-white">{accountLabel}</dd>
        </div>
        {haltedAt && (
          <div className="flex items-center justify-between gap-3">
            <dt>Halted since</dt>
            <dd className="font-medium text-white">{haltedAt}</dd>
          </div>
        )}
        {pairLabel && (
          <div className="flex items-center justify-between gap-3">
            <dt>Pair</dt>
            <dd className="font-medium text-white">{pairLabel}</dd>
          </div>
        )}
      </dl>

      <p className="mt-3 text-sm text-red-100">{halt.reason || 'No reason was recorded.'}</p>
      {errorText && (
        <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-red-500/20 bg-slate-950/60 p-3 text-xs text-red-100">
          {errorText}
        </pre>
      )}

      <p className="mt-3 text-sm text-red-100">
        An emergency close failed, so a position leg may be open without its hedge. The bot keeps
        managing open positions and exits, and opens no new pairs on this account until the halt is
        cleared. Check the open positions of this subaccount on dYdX before clearing it. The halt
        covers every bot on this account.
      </p>

      <label className="mt-4 flex items-start gap-3 text-sm text-red-50">
        <input
          type="checkbox"
          checked={acknowledged}
          disabled={busy}
          onChange={(event) => setAcknowledgedFor(event.target.checked ? halt.id : null)}
          className="mt-0.5 h-4 w-4 rounded border-slate-500 bg-slate-800"
        />
        <span>{acknowledgementText}</span>
      </label>

      <label htmlFor={noteId} className="mt-4 block text-sm text-red-100">
        What you verified (optional, kept with the audit record)
      </label>
      <textarea
        id={noteId}
        value={note}
        maxLength={ENTRY_HALT_NOTE_MAX_LENGTH}
        rows={2}
        disabled={busy}
        onChange={(event) => setNote(event.target.value)}
        className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-red-400 focus:outline-none"
        placeholder="e.g. no AVAX-USD position on chain, 9 older positions unchanged"
      />

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          {error}
        </p>
      )}

      <div className="mt-4 flex flex-wrap justify-end gap-3">
        <button
          type="button"
          onClick={() => onClear(note)}
          disabled={!acknowledged || busy}
          className="rounded-2xl bg-red-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        >
          {busy ? 'Working...' : 'Clear halt and resume entries'}
        </button>
      </div>
    </section>
  );
};

export interface StrategyEntryHaltNoticeProps {
  strategyId: number;
  /** Poll only for runtimes that are live, or while the start dialog is open. */
  enabled: boolean;
  className?: string;
}

/** Entry-halt state of one strategy, with the acknowledged clear action. */
export const StrategyEntryHaltNotice = ({
  strategyId,
  enabled,
  className,
}: StrategyEntryHaltNoticeProps) => {
  const haltQuery = useStrategyEntryHalt(strategyId, { enabled });
  const clearMutation = useClearStrategyEntryHaltMutation();
  const [error, setError] = useState<string | null>(null);

  if (!enabled) {
    return null;
  }

  const handleClear = (note: string) => {
    setError(null);
    clearMutation.mutate(
      { strategyId, note },
      {
        onError: (mutationError: unknown) =>
          setError(
            mutationError instanceof Error && mutationError.message
              ? mutationError.message
              : 'Failed to clear the entry halt'
          ),
      }
    );
  };

  return (
    <EntryHaltNotice
      state={haltQuery.data}
      busy={clearMutation.isPending}
      error={error}
      onClear={handleClear}
      className={className}
    />
  );
};
