import { useMemo } from 'react';
import { useUIPreferencesStore, type AppLanguage } from '../store/uiPreferences';

type BilingualText =
  | string
  | {
      en?: string;
      el?: string;
    };

const resolveBilingualText = (value: BilingualText, language: AppLanguage): string => {
  if (typeof value === 'string') {
    return value;
  }

  if (language === 'el') {
    return value.el ?? value.en ?? '';
  }

  return value.en ?? value.el ?? '';
};

export const useI18n = () => {
  const language = useUIPreferencesStore((state) => state.language);

  const locale = useMemo(() => (language === 'el' ? 'el-GR' : 'en-US'), [language]);

  const t = (english: string, greek?: string): string =>
    language === 'el' ? (greek ?? english) : english;

  const tr = (value: BilingualText): string => resolveBilingualText(value, language);

  return {
    language,
    locale,
    t,
    tr,
  };
};

export type UseI18nReturn = ReturnType<typeof useI18n>;
