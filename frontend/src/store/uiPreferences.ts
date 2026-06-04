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

export const resolveTheme = (theme: ThemeMode): ResolvedTheme =>
  theme === 'system' ? getSystemTheme() : theme;

const getStoredTheme = (): ThemeMode => {
  if (typeof window === 'undefined') {
    return 'system';
  }

  const stored = getLocalStorageValue(THEME_KEY);
  if (isThemeMode(stored)) {
    return stored;
  }

  const legacyPublicTheme = getLocalStorageValue('ui.publicTheme');
  if (isThemeMode(legacyPublicTheme)) {
    setLocalStorageValue(THEME_KEY, legacyPublicTheme);
    removeLocalStorageValue('ui.publicTheme');
    return legacyPublicTheme;
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
      setLocalStorageValue(THEME_KEY, theme);
      set({ theme, resolvedTheme: resolveTheme(theme) });
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
