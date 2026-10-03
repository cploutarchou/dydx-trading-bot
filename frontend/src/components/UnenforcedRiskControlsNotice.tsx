/**
 * Unenforced Risk Controls Notice
 *
 * Shown wherever a live bot is started while the strategy sets risk limits the
 * live runtime cannot enforce. The operator has to tick an explicit
 * acknowledgement before those limits can be turned off. Limits this screen
 * does not know how to resolve are listed as plain blockers instead.
 */

import { useId, useState } from 'react';
import type { UnenforcedRiskControl } from '../api';
import {
  formatRiskControlValue,
  riskControlLabel,
  splitUnenforcedRiskControls,
} from '../utils/unenforcedRiskControls';

export interface UnenforcedRiskControlsNoticeProps {
  controls: UnenforcedRiskControl[];
  network: 'testnet' | 'mainnet';
  busy: boolean;
  error: string | null;
  confirmLabel: string;
  onConfirm: (fields: string[]) => void;
  onCancel?: () => void;
  className?: string;
}

export const UnenforcedRiskControlsNotice = ({
  controls,
  network,
  busy,
  error,
  confirmLabel,
  onConfirm,
  onCancel,
  className = '',
}: UnenforcedRiskControlsNoticeProps) => {
  const headingId = useId();
  // The acknowledgement is only valid for the exact limits and network it was
  // ticked for: switching to mainnet or a changed limit clears it again.
  const [acknowledgedFor, setAcknowledgedFor] = useState<string | null>(null);

  if (controls.length === 0) {
    return null;
  }

  const { resolvable, unresolvable } = splitUnenforcedRiskControls(controls);
  const resolvableFields = resolvable.map((control) => control.field);
  const resolvableLabels = resolvableFields.map(riskControlLabel).join(', ');
  const acknowledgementKey = `${network}|${resolvable
    .map((control) => `${control.field}=${control.value}`)
    .join(',')}`;
  const acknowledged = acknowledgedFor === acknowledgementKey;
  const acknowledgementText =
    network === 'mainnet'
      ? `I understand this MAINNET bot will trade real funds without: ${resolvableLabels}.`
      : `I understand this live bot will run without: ${resolvableLabels}.`;

  return (
    <section
      aria-labelledby={headingId}
      className={`rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 ${className}`.trim()}
    >
      <h3 id={headingId} className="text-sm font-semibold text-amber-200">
        These risk limits are not available on live bots yet
      </h3>

      {resolvable.length > 0 && (
        <ul className="mt-3 space-y-2 text-sm text-amber-100">
          {resolvable.map((control) => (
            <li key={control.field} className="flex items-center justify-between gap-3">
              <span>{riskControlLabel(control.field)}</span>
              <span className="font-medium text-white">
                {formatRiskControlValue(control.value)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-sm text-amber-100">
        The live runtime refuses to start with a limit it cannot enforce, so you are never shown a
        protection that is not real.
        {resolvable.length > 0 &&
          ' The backtest did not apply these limits either, so its results do not depend on them.'}
      </p>
      <p className="mt-2 text-sm text-amber-100">
        Live bots do enforce: stop loss, take profit, position timeout, max positions, trade size,
        the minimum-collateral guard and the account-level portfolio guard.
      </p>

      {unresolvable.length > 0 && (
        <div className="mt-3">
          {resolvable.length > 0 && (
            <p className="text-sm font-semibold text-amber-200">These cannot be turned off here</p>
          )}
          <ul className="mt-2 space-y-2 text-sm text-amber-100">
            {unresolvable.map((control) => (
              <li key={control.field}>• {control.message || control.field}</li>
            ))}
          </ul>
        </div>
      )}

      {resolvable.length > 0 && (
        <label className="mt-4 flex items-start gap-3 text-sm text-amber-50">
          <input
            type="checkbox"
            checked={acknowledged}
            disabled={busy}
            onChange={(event) =>
              setAcknowledgedFor(event.target.checked ? acknowledgementKey : null)
            }
            className="mt-0.5 h-4 w-4 rounded border-slate-500 bg-slate-800"
          />
          <span>{acknowledgementText}</span>
        </label>
      )}

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          {error}
        </p>
      )}

      {resolvable.length > 0 && (
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={busy}
              className="rounded-2xl border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-45"
            >
              Cancel
            </button>
          )}
          <button
            type="button"
            onClick={() => onConfirm(resolvableFields)}
            disabled={!acknowledged || busy}
            className="rounded-2xl bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            {busy ? 'Working...' : confirmLabel}
          </button>
        </div>
      )}
    </section>
  );
};
