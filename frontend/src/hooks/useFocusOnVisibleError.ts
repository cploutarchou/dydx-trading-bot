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
  }, deps);
}

