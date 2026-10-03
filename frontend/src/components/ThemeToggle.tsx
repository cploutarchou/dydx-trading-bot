import { type LucideIcon, Monitor, Moon, Sun } from 'lucide-react';
import React from 'react';
import { useI18n } from '../i18n/useI18n';
import { type ThemeMode, useUIPreferencesStore } from '../store/uiPreferences';

const LIGHT_MODE_TEMPORARILY_DISABLED = true;

const allThemeOptions: Array<{ value: ThemeMode; icon: LucideIcon }> = [
  { value: 'system', icon: Monitor },
  { value: 'dark', icon: Moon },
  { value: 'light', icon: Sun },
];

// While light mode is disabled, hide the option instead of rendering a dead
// disabled control in the header of every page.
const themeOptions = LIGHT_MODE_TEMPORARILY_DISABLED
  ? allThemeOptions.filter((option) => option.value !== 'light')
  : allThemeOptions;

export const ThemeToggle: React.FC = () => {
  const theme = useUIPreferencesStore((state) => state.theme);
  const setTheme = useUIPreferencesStore((state) => state.setTheme);
  const { t } = useI18n();
  const activeOption =
    themeOptions.find((option) => option.value === theme) ??
    allThemeOptions.find((option) => option.value === theme) ??
    themeOptions[0]!;
  const ActiveIcon = activeOption.icon;

  const labels: Record<ThemeMode, string> = {
    system: t('System', 'Σύστημα'),
    dark: t('Dark', 'Σκούρο'),
    light: t('Light', 'Φωτεινό'),
  };

  return (
    <label className="theme-toggle inline-flex items-center gap-2 rounded-lg border px-2 py-2 text-xs">
      <ActiveIcon className="h-4 w-4" />
      <span className="sr-only">{t('Theme', 'Θέμα')}</span>
      <select
        value={theme}
        onChange={(event) => setTheme(event.target.value as ThemeMode)}
        className="bg-transparent text-xs outline-none"
        aria-label={t('Theme', 'Θέμα')}
      >
        {themeOptions.map((option) => (
          <option key={option.value} value={option.value}>
            {labels[option.value]}
          </option>
        ))}
      </select>
    </label>
  );
};
