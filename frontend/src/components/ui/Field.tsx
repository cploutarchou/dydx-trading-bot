import { cloneElement, isValidElement, useId } from 'react';
import type { ReactElement } from 'react';

interface FieldProps {
  /** Visible label text; programmatically associated with the control. */
  label: string;
  /** Marks the label with a required marker (visual only — set the actual
   * `required` attribute on the control element itself). */
  required?: boolean;
  /** Helper text rendered below the control and linked via aria-describedby. */
  hint?: string;
  /** Validation message; also linked via aria-describedby and aria-invalid. */
  error?: string | null;
  /** Classes for the wrapper div (defaults to a full-width block). */
  className?: string;
  /** Classes for the label element (forms have per-surface label styles). */
  labelClassName?: string;
  /** Classes for the hint paragraph. */
  hintClassName?: string;
  /** Classes for the error paragraph. */
  errorClassName?: string;
  /** The single form control (input/select/textarea). Its id and ARIA
   * wiring are injected automatically; all existing props are preserved. */
  children: ReactElement;
}

const DEFAULT_LABEL_CLASS = 'mb-2 block text-xs font-semibold uppercase text-slate-400';
const DEFAULT_HINT_CLASS = 'mt-1 text-xs text-gray-400';
const DEFAULT_ERROR_CLASS = 'mt-1 text-xs text-red-400';

/**
 * Accessible form field wrapper: generates the id linkage between label and
 * control plus hint/error description wiring, so every migrated form field
 * gets a real accessible name for free (audit FE-006 / FE-A11Y-01).
 */
export const Field = ({
  label,
  required = false,
  hint,
  error,
  className = 'w-full',
  labelClassName = DEFAULT_LABEL_CLASS,
  hintClassName = DEFAULT_HINT_CLASS,
  errorClassName = DEFAULT_ERROR_CLASS,
  children,
}: FieldProps) => {
  const generatedId = useId();
  const controlProps = isValidElement(children)
    ? (children.props as { id?: string } | undefined)
    : undefined;
  const controlId = controlProps?.id ?? generatedId;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={className}>
      <label htmlFor={controlId} className={labelClassName}>
        {label}
        {required && <span className="ml-1 text-red-400">*</span>}
      </label>
      {isValidElement(children)
        ? cloneElement(children as ReactElement<Record<string, unknown>>, {
            id: controlId,
            'aria-describedby': describedBy,
            ...(error ? { 'aria-invalid': true } : {}),
          })
        : children}
      {hint && (
        <p id={hintId} className={hintClassName}>
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className={errorClassName}>
          {error}
        </p>
      )}
    </div>
  );
};
