import { create } from 'zustand';

export type ThemeMode = 'dark';
export type AppLanguage = 'en' | 'el';

interface UIPreferencesState {
  theme: ThemeMode;
  language: AppLanguage;
  setLanguage: (language: AppLanguage) => void;
}

const THEME_KEY = 'ui.theme';
const LANGUAGE_KEY = 'ui.language';

const getStoredTheme = (): ThemeMode => {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(THEME_KEY, 'dark');
    window.localStorage.removeItem('ui.publicTheme');
  }
  return 'dark';
};

const getStoredLanguage = (): AppLanguage => {
  if (typeof window === 'undefined') return 'en';
  const stored = window.localStorage.getItem(LANGUAGE_KEY);
  return stored === 'el' ? 'el' : 'en';
};

export const useUIPreferencesStore = create<UIPreferencesState>((set) => ({
  theme: getStoredTheme(),
  language: getStoredLanguage(),
  setLanguage: (language) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LANGUAGE_KEY, language);
    }
    set({ language });
  },
}));
