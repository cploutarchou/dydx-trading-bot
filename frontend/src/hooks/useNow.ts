import { useEffect, useState } from 'react';

/**
 * Ticking wall-clock for render-time age/freshness math.
 *
 * `Date.now()` read directly during render is impure (two renders of the same
 * props can disagree), so components that display "updated Ns ago" derive from
 * this state instead. The clock advances on an interval — never during render —
 * and pauses cleanly on unmount. Components choose a cadence matching how fast
 * their displayed age label actually changes (30s default; 1s is enough for
 * "just now"-precision, use sparingly).
 */
export function useNow(tickMs: number = 30_000): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), tickMs);
    return () => clearInterval(timer);
  }, [tickMs]);

  return now;
}
