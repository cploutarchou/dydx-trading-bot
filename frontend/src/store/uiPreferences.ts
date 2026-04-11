import { create } from 'zustand';

export type ThemeMode = 'dark' | 'light';
export type AppLanguage = 'en' | 'el';

interface UIPreferencesState {
  theme: ThemeMode;
  language: AppLanguage;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  setLanguage: (language: AppLanguage) => void;
}

const THEME_KEY = 'ui.theme';
const LANGUAGE_KEY = 'ui.language';

const getStoredTheme = (): ThemeMode => {
  if (typeof window === 'undefined') return 'dark';
  const stored = window.localStorage.getItem(THEME_KEY);
  return stored === 'light' ? 'light' : 'dark';
};

const getStoredLanguage = (): AppLanguage => {
  if (typeof window === 'undefined') return 'en';
  const stored = window.localStorage.getItem(LANGUAGE_KEY);
  return stored === 'el' ? 'el' : 'en';
};

export const useUIPreferencesStore = create<UIPreferencesState>((set) => ({
  theme: getStoredTheme(),
  language: getStoredLanguage(),
  setTheme: (theme) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_KEY, theme);
    }
    set({ theme });
  },
  toggleTheme: () =>
    set((state) => {
      const nextTheme: ThemeMode = state.theme === 'dark' ? 'light' : 'dark';
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(THEME_KEY, nextTheme);
      }
      return { theme: nextTheme };
    }),
  setLanguage: (language) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LANGUAGE_KEY, language);
    }
    set({ language });
  },
}));
