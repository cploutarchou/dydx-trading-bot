import type { DependencyList, RefObject } from 'react';
import { useEffect } from 'react';

type FocusTarget = {
  when: boolean;
  ref: RefObject<HTMLElement | null>;
};

/**
 * Focuses the first matching target in order whenever dependencies change.
 */
export function useFocusOnVisibleError(targets: FocusTarget[], deps: DependencyList): void {
  useEffect(() => {
    const activeTarget = targets.find((target) => target.when);
    activeTarget?.ref.current?.focus();
    // deps is this hook's pass-through contract: callers name the triggers
    // (targets are read once per trigger, intentionally not reactive).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
