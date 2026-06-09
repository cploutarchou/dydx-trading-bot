import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';
export type AppLanguage = 'en' | 'el';

interface UIPreferencesState {
  theme: ThemeMode;
  resolvedTheme: ResolvedTheme;
  language: AppLanguage;
  setTheme: (theme: ThemeMode) => void;
  setResolvedTheme: (theme: ResolvedTheme) => void;
  setLanguage: (language: AppLanguage) => void;
}

const THEME_KEY = 'ui.theme';
const LANGUAGE_KEY = 'ui.language';
const FORCE_DARK_THEME = true;

const getLocalStorageValue = (key: string): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

const setLocalStorageValue = (key: string, value: string): void => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore storage failures; the in-memory store still updates for this session.
  }
};

const removeLocalStorageValue = (key: string): void => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore storage failures; this is a legacy cleanup path only.
  }
};

const isThemeMode = (value: string | null): value is ThemeMode =>
  value === 'light' || value === 'dark' || value === 'system';

export const getSystemTheme = (): ResolvedTheme => {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return 'dark';
  }
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
};

const normalizeThemeMode = (theme: ThemeMode): ThemeMode => {
  if (!FORCE_DARK_THEME) {
    return theme;
  }

  return theme === 'light' ? 'dark' : theme;
};

export const resolveTheme = (theme: ThemeMode): ResolvedTheme => {
  if (FORCE_DARK_THEME) {
    return 'dark';
  }

  return theme === 'system' ? getSystemTheme() : theme;
};

const getStoredTheme = (): ThemeMode => {
  if (typeof window === 'undefined') {
    return 'system';
  }

  const stored = getLocalStorageValue(THEME_KEY);
  if (isThemeMode(stored)) {
    return normalizeThemeMode(stored);
  }

  const legacyPublicTheme = getLocalStorageValue('ui.publicTheme');
  if (isThemeMode(legacyPublicTheme)) {
    const normalized = normalizeThemeMode(legacyPublicTheme);
    setLocalStorageValue(THEME_KEY, normalized);
    removeLocalStorageValue('ui.publicTheme');
    return normalized;
  }

  return 'system';
};

const getStoredLanguage = (): AppLanguage => {
  if (typeof window === 'undefined') return 'en';
  const stored = getLocalStorageValue(LANGUAGE_KEY);
  return stored === 'el' ? 'el' : 'en';
};

export const useUIPreferencesStore = create<UIPreferencesState>((set) => {
  const initialTheme = getStoredTheme();

  return {
    theme: initialTheme,
    resolvedTheme: resolveTheme(initialTheme),
    language: getStoredLanguage(),
    setTheme: (theme) => {
      const normalizedTheme = normalizeThemeMode(theme);
      setLocalStorageValue(THEME_KEY, normalizedTheme);
      set({ theme: normalizedTheme, resolvedTheme: resolveTheme(normalizedTheme) });
    },
    setResolvedTheme: (theme) => {
      set({ resolvedTheme: theme });
    },
    setLanguage: (language) => {
      setLocalStorageValue(LANGUAGE_KEY, language);
      set({ language });
    },
  };
});
