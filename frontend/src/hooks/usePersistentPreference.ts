import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

interface PersistentPreferenceOptions<T extends string> {
  allowedValues?: readonly T[];
  legacyKeys?: readonly string[];
}

const pickStoredValue = <T extends string>(
  value: string | null,
  defaultValue: T,
  allowedValues?: readonly T[]
): T => {
  if (!value) {
    return defaultValue;
  }

  if (allowedValues && allowedValues.length > 0) {
    return allowedValues.includes(value as T) ? (value as T) : defaultValue;
  }

  return value as T;
};

export function usePersistentPreference<T extends string>(
  storageKey: string,
  defaultValue: T,
  options?: PersistentPreferenceOptions<T>
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') {
      return defaultValue;
    }

    const keysToCheck = [storageKey, ...(options?.legacyKeys ?? [])];

    try {
      for (const key of keysToCheck) {
        const stored = window.localStorage.getItem(key);
        if (stored !== null) {
          return pickStoredValue(stored, defaultValue, options?.allowedValues);
        }
      }
    } catch {
      return defaultValue;
    }

    return defaultValue;
  });

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(storageKey, value);
    } catch {
      // Ignore storage write errors (private mode / quota / policy)
    }
  }, [storageKey, value]);

  return [value, setValue];
}
