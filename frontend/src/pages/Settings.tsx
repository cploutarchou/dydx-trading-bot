/**
 * Settings Page - User & System Configuration Management
 *
 * Allows users to view and modify:
 * - Profile Settings (avatar, name, email)
 * - dYdX Key Management (testnet/mainnet keys)
 * - Logging (log level, Loki integration)
 * - Telegram (notification settings)
 *
 * NOTE: Bot Settings and Backtesting moved to Strategies page for per-strategy configuration
 */

import {
	AlertCircle,
	BarChart2,
	ChevronRight,
	KeyRound,
	Loader,
	Mail,
	MessageSquare,
	Newspaper,
	RefreshCw,
	Save,
	Search,
	ShieldCheck,
	SlidersHorizontal,
	UserCircle,
	Users,
	Zap,
} from 'lucide-react';
import {
	type ComponentType,
	useCallback,
	useDeferredValue,
	useEffect,
	useMemo,
	useRef,
	useState,
} from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import apiClient from '../api';
import { getCurrentPortalType } from '../app/portal';
import { BACKOFFICE_ROLES, getUserWorkspaceRole, roleMatches } from '../auth/roles';
import { AdminAccessControlSettings } from '../components/AdminAccessControlSettings';
import { AdminComingSoonSettings } from '../components/AdminComingSoonSettings';
import { AIMarketSettings } from '../components/AIMarketSettings';
import { ArbitrageRuntimeSettings } from '../components/ArbitrageRuntimeSettings';
import { AuthSettingsComponent } from '../components/AuthSettings';
import { CodexSettings } from '../components/CodexSettings';
import { CoinDeskNewsSettings } from '../components/CoinDeskNewsSettings';
import { DYDXKeyManager } from '../components/DYDXKeyManager';
import { useToastStore } from '../components/ErrorBoundary';
import { MailgunSettings } from '../components/MailgunSettings';
import { PageContainer } from '../components/PageContainer';
import { ProfileSettings } from '../components/ProfileSettings';
import { TelegramSettings } from '../components/TelegramSettings';
import {
	InlineNotice,
	PlatformPageHeader,
	PlatformStatCard,
	StatusBadge,
} from '../components/ui/PlatformUI';
import { useAuthStore } from '../store/auth';
import {
  createSettingsDataLoader,
  type SettingField,
  type SettingSection,
  type SettingValue,
  type SettingsSchema,
} from './settingsData';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error) {
    return error.message;
  }

  if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
    const apiMessage = error.response.data.message;
    if (typeof apiMessage === 'string' && apiMessage.trim().length > 0) {
      return apiMessage;
    }
  }

  return fallback;
};

const getApiErrorCode = (error: unknown): string | null => {
  if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
    const code = error.response.data.code;
    if (typeof code === 'string' && code.trim().length > 0) {
      return code.trim().toLowerCase();
    }
  }

  return null;
};

type FieldErrors = Record<string, Record<string, string>>;

interface SidebarSectionItem {
  section: string;
  title: string;
  description: string;
}

interface PendingFocusTarget {
  section: string;
  fieldKey: string;
}

const SETTINGS_LAST_SECTION_KEY = 'settings:last-section';

const getSettingsFieldDomId = (section: string, fieldKey: string): string =>
  `settings-${section}-${fieldKey}`.replace(/[^a-zA-Z0-9_-]/g, '-');

const getSettingsFieldRefKey = (section: string, fieldKey: string): string =>
  `${section}.${fieldKey}`;

const MANUAL_SECTION_IDS = new Set([
  'codex_io',
  'ai_market_filters',
  'market_news',
  'mailgun',
  'telegram',
  'profile',
  'dydx_keys',
  'security',
  'access_control',
  'coming_soon',
  'arbitrage_runtime',
  'botsettings',
  'backtesting',
  'bot_settings',
  'platform',
]);

// ── Section icon map ──────────────────────────────────────────────────────────
const SECTION_ICON_MAP: Record<string, ComponentType<{ className?: string }>> = {
  profile: UserCircle,
  dydx_keys: KeyRound,
  ai_market_filters: Zap,
  codex_io: BarChart2,
  access_control: Users,
  arbitrage_runtime: SlidersHorizontal,
  telegram: MessageSquare,
  mailgun: Mail,
  market_news: Newspaper,
  security: ShieldCheck,
  coming_soon: ShieldCheck,
};
const getSectionIcon = (id: string): ComponentType<{ className?: string }> =>
  SECTION_ICON_MAP[id] ?? SlidersHorizontal;

// ── Sidebar grouping ─────────────────────────────────────────────────────────
const SIDEBAR_GROUPS: Array<{ label: string; sectionIds: string[] }> = [
  { label: 'Identity', sectionIds: ['profile', 'security'] },
  { label: 'API Keys', sectionIds: ['dydx_keys', 'ai_market_filters', 'codex_io'] },
  {
    label: 'Integrations',
    sectionIds: ['access_control', 'telegram', 'mailgun', 'market_news', 'arbitrage_runtime'],
  },
  { label: 'Platform', sectionIds: ['coming_soon'] },
];

interface SidebarNavGroup {
  label: string;
  items: SidebarSectionItem[];
}

const buildGroupedNav = (sections: SidebarSectionItem[]): SidebarNavGroup[] => {
  const assigned = new Set<string>();
  const groups: SidebarNavGroup[] = [];
  for (const { label, sectionIds } of SIDEBAR_GROUPS) {
    const items = sectionIds
      .map((id) => sections.find((s) => s.section === id))
      .filter(Boolean) as SidebarSectionItem[];
    if (items.length > 0) {
      groups.push({ label, items });
      items.forEach((i) => assigned.add(i.section));
    }
  }
  const rest = sections.filter((s) => !assigned.has(s.section));
  if (rest.length > 0) groups.push({ label: 'System', items: rest });
  return groups;
};

// ── Toggle switch ─────────────────────────────────────────────────────────────
const ToggleSwitch = ({
  checked,
  onChange,
  id,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  id: string;
}) => (
  <button
    type="button"
    id={id}
    role="switch"
    aria-checked={checked}
    onClick={() => onChange(!checked)}
    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900 ${
      checked ? 'border-cyan-500 bg-cyan-500' : 'border-slate-600 bg-slate-700'
    }`}
  >
    <span
      className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform duration-200 ${
        checked ? 'translate-x-5' : 'translate-x-0.5'
      }`}
    />
  </button>
);

const parseFieldInputValue = (field: SettingField, rawValue: string): SettingValue => {
  if (field.value_type === 'float') {
    if (rawValue.trim() === '') return undefined;
    const parsed = Number.parseFloat(rawValue);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  if (field.value_type === 'int' || field.value_type === 'integer') {
    if (rawValue.trim() === '') return undefined;
    const parsed = Number.parseInt(rawValue, 10);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  return rawValue;
};

const isEmptySettingValue = (value: SettingValue): boolean => {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  return false;
};

const normalizeSettingValue = (value: unknown): unknown => {
  if (value === undefined) return '__undefined__';
  if (Array.isArray(value)) return value.map((item) => normalizeSettingValue(item));
  if (typeof value === 'object' && value !== null) {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        acc[key] = normalizeSettingValue((value as Record<string, unknown>)[key]);
        return acc;
      }, {});
  }
  return value;
};

const serializeFormValues = (values: Record<string, Record<string, SettingValue>>): string =>
  JSON.stringify(
    Object.keys(values)
      .sort()
      .reduce<Record<string, unknown>>((acc, sectionKey) => {
        const fields = values[sectionKey] || {};
        acc[sectionKey] = Object.keys(fields)
          .sort()
          .reduce<Record<string, unknown>>((fieldAcc, fieldKey) => {
            fieldAcc[fieldKey] = normalizeSettingValue(fields[fieldKey]);
            return fieldAcc;
          }, {});
        return acc;
      }, {})
  );

const validateFieldValue = (field: SettingField, value: SettingValue): string | null => {
  if (field.required && isEmptySettingValue(value)) {
    return `${field.label} is required.`;
  }

  if (
    (field.value_type === 'float' ||
      field.value_type === 'int' ||
      field.value_type === 'integer') &&
    value !== undefined &&
    value !== null &&
    value !== ''
  ) {
    const numericValue = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(numericValue)) {
      return `${field.label} must be a valid number.`;
    }
    if (field.min_value !== undefined && numericValue < field.min_value) {
      return `${field.label} must be at least ${field.min_value}.`;
    }
    if (field.max_value !== undefined && numericValue > field.max_value) {
      return `${field.label} must be at most ${field.max_value}.`;
    }
  }

  if (field.options && value !== undefined && value !== null && value !== '') {
    const optionValue = String(value);
    if (!field.options.includes(optionValue)) {
      return `${field.label} must be one of the allowed options.`;
    }
  }

  return null;
};

const buildFieldErrors = (
  sections: SettingSection[],
  values: Record<string, Record<string, SettingValue>>
): FieldErrors => {
  const nextErrors: FieldErrors = {};

  sections.forEach((section) => {
    section.fields.forEach((field) => {
      const value = values[section.section]?.[field.key] ?? field.default_value;
      const error = validateFieldValue(field, value);
      if (!error) return;

      if (!nextErrors[section.section]) {
        nextErrors[section.section] = {};
      }

      nextErrors[section.section][field.key] = error;
    });
  });

  return nextErrors;
};

const hasAnyFieldErrors = (errors: FieldErrors): boolean =>
  Object.values(errors).some((sectionErrors) => Object.keys(sectionErrors).length > 0);

export default function Settings() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const portal = getCurrentPortalType();
  const isBackofficeSettingsSurface = portal === 'backoffice';
  const isAdminUser = isBackofficeSettingsSurface && Boolean(user?.is_admin);
  const canManageBackofficeSettings =
    isBackofficeSettingsSurface && roleMatches(getUserWorkspaceRole(user), BACKOFFICE_ROLES);
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedSection = searchParams.get('section')?.trim().toLowerCase() || '';
  const [schema, setSchema] = useState<SettingsSchema | null>(null);
  const [formValues, setFormValues] = useState<Record<string, Record<string, SettingValue>>>({});
  const [initialFormValues, setInitialFormValues] = useState<
    Record<string, Record<string, SettingValue>>
  >({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settingsLoadError, setSettingsLoadError] = useState<string | null>(null);
  const [mfaEnrollmentRequired, setMfaEnrollmentRequired] = useState(false);
  const [activeSection, setActiveSection] = useState<string>(requestedSection || 'profile');
  const [pendingFocusTarget, setPendingFocusTarget] = useState<PendingFocusTarget | null>(null);
  const [sectionSearchQuery, setSectionSearchQuery] = useState('');
  const [testingConnection, setTestingConnection] = useState(false);
  const fieldRefs = useRef<Record<string, HTMLInputElement | HTMLSelectElement | null>>({});
  const settingsDataLoaderRef = useRef(createSettingsDataLoader(apiClient));
  const hasRestoredSectionRef = useRef(false);
  const urlSyncEnabledRef = useRef(true);
  const lastRequestedSectionRef = useRef(requestedSection);
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const infoToast = useToastStore((state) => state.info);
  const deferredSectionSearchQuery = useDeferredValue(sectionSearchQuery);

  const visibleSchemaSections = useMemo(
    () =>
      (schema?.sections || []).filter(
        (section) => !MANUAL_SECTION_IDS.has(section.section.toLowerCase())
      ),
    [schema]
  );

  const sidebarSections = useMemo<SidebarSectionItem[]>(() => {
    const manualSections: SidebarSectionItem[] = [
      { section: 'profile', title: 'Profile', description: 'Account & avatar' },
      { section: 'security', title: 'Security', description: '2FA & sessions' },
      { section: 'dydx_keys', title: 'dYdX Keys', description: 'Testnet & mainnet' },
      { section: 'telegram', title: 'Telegram', description: 'Bot notifications' },
      ...(isAdminUser
        ? [
            {
              section: 'ai_market_filters',
              title: 'AI Filters',
              description: 'OpenAI, DeepSeek, Claude',
            },
            { section: 'codex_io', title: 'Codex.io', description: 'Market data key' },
          ]
        : []),
      ...(canManageBackofficeSettings
        ? [
            {
              section: 'access_control',
              title: 'Access Control',
              description: 'Roles & registration',
            },
            { section: 'mailgun', title: 'Mailgun', description: 'Outbound email' },
            {
              section: 'coming_soon',
              title: 'Coming Soon',
              description: 'Public launch gate',
            },
            { section: 'market_news', title: 'Market News', description: 'CoinDesk feed' },
            {
              section: 'arbitrage_runtime',
              title: 'Arbitrage Runtime',
              description: 'Feature flags & pair ranking',
            },
          ]
        : []),
    ];

    return [
      ...manualSections,
      ...visibleSchemaSections.map((section) => ({
        section: section.section,
        title: section.title,
        description: section.description,
      })),
    ];
  }, [canManageBackofficeSettings, isAdminUser, visibleSchemaSections]);

  const filteredSidebarSections = useMemo(() => {
    const query = deferredSectionSearchQuery.trim().toLowerCase();
    if (!query) return sidebarSections;

    return sidebarSections.filter((section) =>
      [section.title, section.description, section.section].some((value) =>
        value.toLowerCase().includes(query)
      )
    );
  }, [deferredSectionSearchQuery, sidebarSections]);

  const hasUnsavedChanges = useMemo(
    () => serializeFormValues(formValues) !== serializeFormValues(initialFormValues),
    [formValues, initialFormValues]
  );

  const fieldErrors = useMemo(
    () => buildFieldErrors(schema?.sections || [], formValues),
    [formValues, schema?.sections]
  );

  const hasValidationErrors = useMemo(() => hasAnyFieldErrors(fieldErrors), [fieldErrors]);

  const fetchSettingsData = useCallback(async () => {
    try {
      setLoading(true);
      setSettingsLoadError(null);
      setMfaEnrollmentRequired(false);

      if (!canManageBackofficeSettings) {
        setSchema({ sections: [] });
        setFormValues({});
        setInitialFormValues({});
        return;
      }

      const { schema: schemaData, formValues: formVals } = await settingsDataLoaderRef.current();

      setFormValues(formVals);
      setInitialFormValues(formVals);
      setSchema(schemaData);
    } catch (error: unknown) {
      const apiErrorCode = getApiErrorCode(error);
      if (apiErrorCode === 'mfa_required') {
        setSchema(null);
        setSettingsLoadError('Complete 2FA enrollment to access operator settings.');
        setMfaEnrollmentRequired(true);
        errorToast(
          'MFA enrollment required',
          'Complete 2FA enrollment to access operator settings.'
        );
        return;
      }

      const message = getApiErrorMessage(error, 'Unknown error');
      setSchema(null);
      setSettingsLoadError(message);
      errorToast('Failed to load settings', message);
    } finally {
      setLoading(false);
    }
  }, [canManageBackofficeSettings, errorToast]);

  useEffect(() => {
    void fetchSettingsData();
  }, [fetchSettingsData]);

  useEffect(() => {
    if (hasRestoredSectionRef.current || sidebarSections.length === 0) {
      return;
    }

    hasRestoredSectionRef.current = true;

    if (
      requestedSection &&
      sidebarSections.some((section) => section.section === requestedSection)
    ) {
      setActiveSection(requestedSection);
      return;
    }

    try {
      const savedSection = localStorage.getItem(SETTINGS_LAST_SECTION_KEY);
      if (savedSection && sidebarSections.some((section) => section.section === savedSection)) {
        setActiveSection(savedSection);
      }
    } catch (error) {
      console.warn('⚠️ Settings.tsx: Failed to restore last opened section', error);
    }
  }, [requestedSection, sidebarSections]);

  useEffect(() => {
    if (sidebarSections.length === 0) {
      return;
    }

    if (!sidebarSections.some((section) => section.section === activeSection)) {
      setActiveSection(sidebarSections[0].section);
    }
  }, [activeSection, sidebarSections]);

  useEffect(() => {
    if (!urlSyncEnabledRef.current) {
      return;
    }

    if (requestedSection === lastRequestedSectionRef.current) {
      return;
    }

    lastRequestedSectionRef.current = requestedSection;

    if (!requestedSection || requestedSection === activeSection) {
      return;
    }

    if (sidebarSections.some((section) => section.section === requestedSection)) {
      setActiveSection(requestedSection);
    }
  }, [activeSection, requestedSection, sidebarSections]);

  useEffect(() => {
    if (!sidebarSections.some((section) => section.section === activeSection)) {
      return;
    }

    try {
      localStorage.setItem(SETTINGS_LAST_SECTION_KEY, activeSection);
    } catch (error) {
      console.warn('⚠️ Settings.tsx: Failed to persist last opened section', error);
    }

    if (!urlSyncEnabledRef.current || requestedSection === activeSection) {
      return;
    }

    try {
      setSearchParams(
        (currentParams) => {
          const nextParams = new URLSearchParams(currentParams);
          nextParams.set('section', activeSection);
          return nextParams;
        },
        { replace: true }
      );
    } catch (error) {
      urlSyncEnabledRef.current = false;
      console.warn('⚠️ Settings.tsx: URL sync disabled (history update blocked)', error);
    }
  }, [activeSection, requestedSection, setSearchParams, sidebarSections]);

  useEffect(() => {
    if (!pendingFocusTarget || pendingFocusTarget.section !== activeSection) {
      return;
    }

    const refKey = getSettingsFieldRefKey(pendingFocusTarget.section, pendingFocusTarget.fieldKey);
    const fieldElement = fieldRefs.current[refKey];
    if (!fieldElement) {
      return;
    }

    fieldElement.focus();
    fieldElement.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setPendingFocusTarget(null);
  }, [activeSection, pendingFocusTarget]);

  const handleFieldChange = (section: string, key: string, value: SettingValue) => {
    setFormValues((prev) => {
      const nextValues = {
        ...prev,
        [section]: {
          ...prev[section],
          [key]: value,
        },
      };

      return nextValues;
    });
  };

  const handleSave = async () => {
    if (!schema) return;

    const nextErrors = fieldErrors;
    if (hasAnyFieldErrors(nextErrors)) {
      const firstInvalidSection = schema.sections.find(
        (section) =>
          nextErrors[section.section] && Object.keys(nextErrors[section.section]).length > 0
      );
      if (firstInvalidSection) {
        const firstInvalidFieldKey = Object.keys(nextErrors[firstInvalidSection.section] || {})[0];
        if (firstInvalidFieldKey) {
          setPendingFocusTarget({
            section: firstInvalidSection.section,
            fieldKey: firstInvalidFieldKey,
          });
        }
        setActiveSection(firstInvalidSection.section);
      }
      errorToast('Validation errors', 'Please fix validation errors before saving your changes.');
      return;
    }

    if (!hasUnsavedChanges) {
      infoToast('No changes to save');
      return;
    }

    try {
      setSaving(true);

      // Flatten formValues for API
      const updates: Record<string, SettingValue> = {};
      Object.entries(formValues).forEach(([section, fields]) => {
        Object.entries(fields).forEach(([key, value]) => {
          updates[`${section}.${key}`] = value;
        });
      });

      const response = await apiClient.updateSettings(updates);

      if (response.success) {
        successToast('Settings saved', 'Your configuration has been updated successfully.');
        setInitialFormValues(formValues);
        // Refresh settings to confirm changes
        window.setTimeout(() => {
          void fetchSettingsData();
        }, 1000);
      } else {
        errorToast('Failed to save settings', response.message || 'Please try again.');
      }
    } catch (error: unknown) {
      errorToast('Error saving settings', getApiErrorMessage(error, 'Unknown error'));
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      setTestingConnection(true);
      const response = await apiClient.testRedisConnection();
      if (response.success && response.data) {
        const data = response.data as {
          connected: boolean;
          message: string;
          host?: string;
          port?: number;
          latency_ms?: number;
        };
        if (data.connected) {
          successToast(
            'Redis connection successful',
            data.latency_ms !== undefined && data.host && data.port
              ? `${data.host}:${data.port} responded in ${data.latency_ms} ms`
              : data.message
          );
        } else {
          errorToast('Redis connection failed', data.message || 'Connection test failed');
        }
      } else {
        errorToast('Redis connection failed', response.message || 'Connection test failed');
      }
    } catch (error: unknown) {
      errorToast('Redis connection failed', getApiErrorMessage(error, 'Connection test failed'));
    } finally {
      setTestingConnection(false);
    }
  };

  const handleReset = () => {
    setFormValues(initialFormValues);
    infoToast('Changes reset', 'Unsaved edits have been reverted for this session.');
  };

  if (loading) {
    return (
      <PageContainer size="wide">
        <div className="premium-panel flex h-64 items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <Loader className="h-8 w-8 animate-spin text-cyan-400" />
            <p className="text-sm text-slate-400">
              Loading operator settings, access controls, and integration defaults...
            </p>
          </div>
        </div>
      </PageContainer>
    );
  }

  if (!schema) {
    if (mfaEnrollmentRequired) {
      return (
        <PageContainer size="wide">
          <InlineNotice
            tone="warning"
            title="MFA enrollment required"
            description="Operator settings are protected. Complete 2FA enrollment before accessing this control surface."
            action={
              <button
                type="button"
                onClick={() => navigate('/2fa-setup')}
                className="rounded-lg border border-amber-500/30 bg-amber-500/15 px-4 py-2 text-sm font-medium text-amber-100 transition hover:border-amber-400/40 hover:bg-amber-500/20"
              >
                Open 2FA setup
              </button>
            }
          />
        </PageContainer>
      );
    }

    return (
      <PageContainer size="wide">
        <InlineNotice
          tone="danger"
          title="Settings could not be loaded"
          description={
            settingsLoadError ||
            'The control surface is unavailable right now. Retry the request and confirm the backend is healthy if the problem continues.'
          }
          action={
            <button
              type="button"
              onClick={fetchSettingsData}
              className="rounded-lg border border-rose-500/30 bg-rose-500/15 px-4 py-2 text-sm font-medium text-rose-100 transition hover:border-rose-400/40 hover:bg-rose-500/20"
            >
              Retry
            </button>
          }
        />
      </PageContainer>
    );
  }

  const currentSection = visibleSchemaSections.find((s) => s.section === activeSection);
  const CurrentSectionIcon = getSectionIcon(activeSection);
  const groupedNav = buildGroupedNav(filteredSidebarSections);
  const totalFieldErrors = Object.values(fieldErrors).reduce(
    (n, e) => n + Object.keys(e).length,
    0
  );
  const secondaryButtonClass =
    'inline-flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2 text-sm font-medium text-white transition hover:border-cyan-500/35 hover:bg-slate-900 disabled:opacity-40';

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker={canManageBackofficeSettings ? 'System' : 'Account'}
        title="Settings"
        description={
          canManageBackofficeSettings
            ? 'Profile, access, wallet keys, integrations, and runtime defaults now live in one responsive control surface with clearer save state and validation cues.'
            : 'Manage your profile, security, dYdX address and keys, Telegram notifications, and account integrations from one place.'
        }
        icon={SlidersHorizontal}
        meta={
          hasUnsavedChanges ? (
            <StatusBadge tone="warning">Unsaved changes</StatusBadge>
          ) : (
            <StatusBadge tone="success">All changes saved</StatusBadge>
          )
        }
      />

      <section className="grid gap-4 md:grid-cols-3">
        <PlatformStatCard
          label="Configured sections"
          value={sidebarSections.length}
          tone="default"
          detail="Identity, integrations, and runtime controls in one workspace."
          icon={SlidersHorizontal}
        />
        <PlatformStatCard
          label="Validation"
          value={totalFieldErrors}
          tone={totalFieldErrors > 0 ? 'danger' : 'success'}
          detail={
            totalFieldErrors > 0
              ? 'Resolve highlighted fields before saving.'
              : 'No blocking validation issues detected.'
          }
          icon={AlertCircle}
        />
        <PlatformStatCard
          label="Save state"
          value={hasUnsavedChanges ? 'Draft edits' : 'Synced'}
          tone={hasUnsavedChanges ? 'warning' : 'accent'}
          detail={
            hasUnsavedChanges
              ? 'Review and save your pending changes.'
              : 'Workspace configuration matches the backend.'
          }
          icon={Save}
        />
      </section>

      {hasUnsavedChanges && (
        <InlineNotice
          tone="warning"
          title="You have pending configuration edits"
          description="Save once you are comfortable with the current values, or discard if this session was exploratory."
        />
      )}

      {/* Main Layout */}
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start">
        {/* Sidebar */}
        <aside className="w-full shrink-0 xl:sticky xl:top-20 xl:w-72">
          <div className="premium-panel overflow-hidden p-0 shadow-2xl">
            {/* Search */}
            <div className="border-b border-slate-700/60 px-3 py-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <input
                  type="search"
                  placeholder="Search…"
                  value={sectionSearchQuery}
                  onChange={(e) => setSectionSearchQuery(e.target.value)}
                  className="premium-input py-2 pl-9 pr-3 text-sm"
                />
              </div>
            </div>

            {/* Grouped nav */}
            <nav className="p-2">
              {filteredSidebarSections.length === 0 ? (
                <p className="px-3 py-6 text-center text-xs text-slate-500">No sections match.</p>
              ) : (
                groupedNav.map((group) => (
                  <div key={group.label} className="mb-3 last:mb-0">
                    {!sectionSearchQuery && (
                      <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
                        {group.label}
                      </p>
                    )}
                    {group.items.map((s) => {
                      const Icon = getSectionIcon(s.section);
                      const isActive = activeSection === s.section;
                      const sectionFieldErrors = fieldErrors[s.section];
                      const hasErrors =
                        sectionFieldErrors && Object.keys(sectionFieldErrors).length > 0;
                      return (
                        <button
                          key={s.section}
                          type="button"
                          onClick={() => setActiveSection(s.section)}
                          className={`group mb-0.5 flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-all ${
                            isActive
                              ? 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30'
                              : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                          }`}
                        >
                          <span
                            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                              isActive
                                ? 'bg-cyan-500/20 text-cyan-400'
                                : 'bg-slate-800 text-slate-500 group-hover:text-slate-300'
                            }`}
                          >
                            <Icon className="h-4 w-4" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-xs font-semibold leading-tight">
                              {s.title}
                            </p>
                            <p className="truncate text-[11px] leading-tight opacity-60">
                              {s.description}
                            </p>
                          </div>
                          {hasErrors && (
                            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
                          )}
                          {isActive && !hasErrors && (
                            <ChevronRight className="h-3 w-3 shrink-0 opacity-60" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </nav>

            {/* Sidebar footer */}
            <div className="border-t border-slate-700/60 px-4 py-3">
              {totalFieldErrors > 0 ? (
                <p className="text-[11px] text-red-400">
                  {totalFieldErrors} validation error{totalFieldErrors !== 1 ? 's' : ''} across
                  sections
                </p>
              ) : (
                <p className="text-[11px] text-slate-600">
                  {sidebarSections.length} section{sidebarSections.length !== 1 ? 's' : ''}{' '}
                  configured
                </p>
              )}
            </div>
          </div>
        </aside>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {activeSection === 'profile' && <ProfileSettings />}
          {activeSection === 'dydx_keys' && <DYDXKeyManager />}
          {activeSection === 'ai_market_filters' && isAdminUser && <AIMarketSettings />}
          {activeSection === 'codex_io' && isAdminUser && <CodexSettings />}
          {activeSection === 'access_control' && canManageBackofficeSettings && (
            <AdminAccessControlSettings />
          )}
          {activeSection === 'coming_soon' && canManageBackofficeSettings && (
            <AdminComingSoonSettings />
          )}
          {activeSection === 'mailgun' && canManageBackofficeSettings && <MailgunSettings />}
          {activeSection === 'telegram' && <TelegramSettings />}
          {activeSection === 'market_news' && canManageBackofficeSettings && (
            <CoinDeskNewsSettings />
          )}
          {activeSection === 'arbitrage_runtime' && canManageBackofficeSettings && (
            <ArbitrageRuntimeSettings />
          )}
          {activeSection === 'security' && <AuthSettingsComponent />}

          {/* Schema-driven sections */}
          {currentSection && (
            <div className="premium-panel overflow-hidden p-0 shadow-xl">
              {/* Section header */}
              <div className="border-b border-slate-700/60 px-6 py-5">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-400">
                    <CurrentSectionIcon className="h-5 w-5" />
                  </span>
                  <div>
                    <h2 className="text-base font-bold text-white">{currentSection.title}</h2>
                    <p className="text-xs text-slate-400">{currentSection.description}</p>
                  </div>
                  <div className="ml-auto flex items-center gap-2">
                    {hasUnsavedChanges && (
                      <span className="rounded-full border border-amber-600/40 bg-amber-900/20 px-2.5 py-0.5 text-xs text-amber-300">
                        Unsaved
                      </span>
                    )}
                    {fieldErrors[activeSection] &&
                      Object.keys(fieldErrors[activeSection]).length > 0 && (
                        <span className="rounded-full border border-red-700/40 bg-red-900/20 px-2.5 py-0.5 text-xs text-red-300">
                          Errors
                        </span>
                      )}
                  </div>
                </div>
              </div>

              {/* Fields */}
              <div className="divide-y divide-slate-700/50">
                {currentSection.fields.map((field) => {
                  const value = formValues[activeSection]?.[field.key] ?? field.default_value;
                  const inputValue =
                    typeof value === 'string' || typeof value === 'number' ? value : '';
                  const selectValue =
                    typeof value === 'string' || typeof value === 'number' ? String(value) : '';
                  const fieldDomId = getSettingsFieldDomId(activeSection, field.key);
                  const fieldRefKey = getSettingsFieldRefKey(activeSection, field.key);
                  const errorMessage = fieldErrors[activeSection]?.[field.key];

                  return (
                    <div key={field.key} className="grid grid-cols-5 gap-4 px-6 py-5">
                      {/* Label column */}
                      <div className="col-span-2 flex flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <label
                            htmlFor={fieldDomId}
                            className="text-sm font-semibold text-slate-200"
                          >
                            {field.label}
                          </label>
                          {field.required && (
                            <span className="rounded border border-red-700/40 bg-red-900/20 px-1.5 py-0.5 text-[10px] font-medium text-red-400">
                              Required
                            </span>
                          )}
                        </div>
                        <p className="text-xs leading-snug text-slate-500">{field.description}</p>
                        {(field.min_value !== undefined || field.max_value !== undefined) && (
                          <div className="flex flex-wrap gap-2 pt-1">
                            {field.min_value !== undefined && (
                              <span className="workspace-chip border-slate-700/70 px-1.5 py-0.5 text-[10px] text-slate-500">
                                min {field.min_value}
                              </span>
                            )}
                            {field.max_value !== undefined && (
                              <span className="workspace-chip border-slate-700/70 px-1.5 py-0.5 text-[10px] text-slate-500">
                                max {field.max_value}
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Control column */}
                      <div className="col-span-3 flex flex-col gap-1.5">
                        {field.value_type === 'bool' || field.value_type === 'boolean' ? (
                          <div className="flex items-center gap-3 pt-1">
                            <ToggleSwitch
                              id={fieldDomId}
                              checked={Boolean(value)}
                              onChange={(v) => handleFieldChange(activeSection, field.key, v)}
                            />
                            <span className="text-xs text-slate-400">
                              {value ? 'Enabled' : 'Disabled'}
                            </span>
                          </div>
                        ) : field.options ? (
                          <select
                            id={fieldDomId}
                            ref={(element) => {
                              fieldRefs.current[fieldRefKey] = element;
                            }}
                            value={selectValue}
                            aria-invalid={!!errorMessage}
                            aria-describedby={errorMessage ? `${fieldDomId}-error` : undefined}
                            onChange={(e) =>
                              handleFieldChange(activeSection, field.key, e.target.value)
                            }
                            className="premium-input"
                          >
                            {field.options.map((opt) => (
                              <option key={opt} value={opt}>
                                {opt}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            id={fieldDomId}
                            ref={(element) => {
                              fieldRefs.current[fieldRefKey] = element;
                            }}
                            type={
                              field.value_type === 'float' ||
                              field.value_type === 'int' ||
                              field.value_type === 'integer'
                                ? 'number'
                                : 'text'
                            }
                            aria-invalid={!!errorMessage}
                            aria-describedby={errorMessage ? `${fieldDomId}-error` : undefined}
                            value={inputValue}
                            placeholder={field.placeholder ?? ''}
                            step={field.value_type === 'float' ? 'any' : undefined}
                            onChange={(e) =>
                              handleFieldChange(
                                activeSection,
                                field.key,
                                parseFieldInputValue(field, e.target.value)
                              )
                            }
                            className={`premium-input ${errorMessage ? 'border-red-600 focus:border-red-500 focus:ring-red-500' : ''}`}
                          />
                        )}
                        {errorMessage && (
                          <p
                            id={`${fieldDomId}-error`}
                            role="alert"
                            className="flex items-center gap-1.5 text-xs text-red-400"
                          >
                            <AlertCircle className="h-3 w-3 shrink-0" />
                            {errorMessage}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Action bar */}
              <div className="flex items-center justify-between border-t border-slate-700/60 px-6 py-4">
                <div>
                  {activeSection === 'redis' && (
                    <button
                      type="button"
                      onClick={handleTestConnection}
                      disabled={testingConnection}
                      className={`${secondaryButtonClass} disabled:opacity-50`}
                    >
                      {testingConnection ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Zap className="h-4 w-4" />
                      )}
                      Test connection
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleReset}
                    disabled={!hasUnsavedChanges}
                    className={secondaryButtonClass}
                  >
                    <RefreshCw className="h-4 w-4" />
                    Discard
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving || !hasUnsavedChanges || hasValidationErrors}
                    className="premium-button inline-flex items-center gap-2 disabled:opacity-50"
                  >
                    {saving ? (
                      <Loader className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save changes
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Operational note */}
      <p className="mt-5 text-[10px] uppercase tracking-widest text-slate-600">
        {canManageBackofficeSettings
          ? 'Changes to runtime config take effect on next bot restart · Schema-driven sections persist to database · Manual sections (profile, keys, integrations) use dedicated APIs · Backoffice-only sections are hidden for non-admin users'
          : 'Profile, security, dYdX keys, and Telegram settings use dedicated account APIs · Platform-only settings are hidden for non-admin users'}
      </p>
    </PageContainer>
  );
}
