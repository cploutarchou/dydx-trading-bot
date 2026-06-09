import type { ApiResponse } from '../api';

export type SettingValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | string[]
  | Record<string, unknown>
  | unknown[];

export interface SettingField {
  key: string;
  label?: string;
  value_type: string;
  description?: string;
  default_value: SettingValue;
  required?: boolean;
  value?: SettingValue;
  min_value?: number;
  max_value?: number;
  options?: string[];
  placeholder?: string;
}

export interface SettingSection {
  section: string;
  title: string;
  description: string;
  fields: SettingField[];
}

export interface SettingsSchema {
  sections: SettingSection[];
}

export interface SavedSettings {
  sections: Array<{
    section: string;
    settings: SettingField[];
  }>;
}

export interface LoadedSettingsData {
  schema: SettingsSchema;
  formValues: Record<string, Record<string, SettingValue>>;
}

export interface SettingsDataApi {
  initializeSettings: () => Promise<ApiResponse>;
  getSettingsSchema: () => Promise<ApiResponse>;
  getSettings: () => Promise<ApiResponse>;
}

const requireResponseData = <T>(response: ApiResponse, label: string): T => {
  if (!response.success || response.data == null) {
    throw new Error(response.message || `${label} request did not return data`);
  }
  return response.data as unknown as T;
};

export const parseSavedSettingValue = (setting: SettingField): SettingValue => {
  let value = setting.value;
  if (typeof value === 'string') {
    try {
      value = JSON.parse(value) as SettingValue;
    } catch {
      return value;
    }
  }
  return value !== undefined ? value : setting.default_value;
};

export const buildSettingsFormValues = (
  savedSettings: SavedSettings
): Record<string, Record<string, SettingValue>> => {
  const formValues: Record<string, Record<string, SettingValue>> = {};
  savedSettings.sections.forEach((section) => {
    formValues[section.section] = {};
    section.settings.forEach((setting) => {
      formValues[section.section][setting.key] = parseSavedSettingValue(setting);
    });
  });
  return formValues;
};

export const loadSettingsData = async (api: SettingsDataApi): Promise<LoadedSettingsData> => {
  const initializeResponse = await api.initializeSettings();
  if (!initializeResponse.success) {
    throw new Error(initializeResponse.message || 'Settings initialization failed');
  }

  const [schemaResponse, settingsResponse] = await Promise.all([
    api.getSettingsSchema(),
    api.getSettings(),
  ]);

  const schema = requireResponseData<SettingsSchema>(schemaResponse, 'Settings schema');
  const savedSettings = requireResponseData<SavedSettings>(settingsResponse, 'Settings');

  return {
    schema,
    formValues: buildSettingsFormValues(savedSettings),
  };
};

export const createSettingsDataLoader = (api: SettingsDataApi) => {
  let inFlight: Promise<LoadedSettingsData> | null = null;

  return () => {
    if (inFlight) {
      return inFlight;
    }

    inFlight = loadSettingsData(api).finally(() => {
      inFlight = null;
    });
    return inFlight;
  };
};
