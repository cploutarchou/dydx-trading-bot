const isPerfEnabled = import.meta.env.DEV;

export const perfMark = (name: string): void => {
  if (!isPerfEnabled || typeof performance === 'undefined') {
    return;
  }

  performance.mark(name);
  console.log(`[perf] mark ${name}`);
};

export const perfMeasure = (name: string, startMark: string, endMark: string): void => {
  if (!isPerfEnabled || typeof performance === 'undefined') {
    return;
  }

  try {
    performance.measure(name, startMark, endMark);
    const entries = performance.getEntriesByName(name, 'measure');
    const last = entries[entries.length - 1];
    if (last) {
      console.log(`[perf] ${name}: ${last.duration.toFixed(2)}ms`);
    }
  } catch {
    // Ignore when marks are missing during partial flows.
  }
};

