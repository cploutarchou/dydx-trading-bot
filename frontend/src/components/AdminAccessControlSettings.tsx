import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import {
	ChevronDown,
	EyeOff,
	Loader2,
	LockKeyhole,
	RotateCcw,
	Rocket,
	ShieldCheck,
	Trash2,
	UserCog,
	UserPlus,
	Users,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import api, {
	AccessControlPermission,
	AdminUser,
	CreateAdminUserPayload,
	CreateCustomRolePayload,
	ResetAdminUserMFAResponse,
	UpdateAdminUserPayload,
} from '../api';
import { ibPortalHref } from '../pages/ib/paths';
import { useAuthStore } from '../store/auth';
import { setPortalSubdomainConfig } from '../utils/portalSubdomainSettings';
import { useToastStore } from './ErrorBoundary';

interface UserDraft {
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  max_active_backtests: number;
  max_strategies: number;
  max_bot_instances: number;
}

type RegistrationMode = 'open' | 'disabled' | 'invitation_only';

interface SettingsSectionRecord {
  section: string;
  settings: Array<{
    key: string;
    value?: unknown;
    default_value?: unknown;
  }>;
}

interface SettingsPayload {
  sections?: SettingsSectionRecord[];
}

interface CustomRoleDraft {
  role: string;
  display_name: string;
  description: string;
}

type AccessControlSubmenuKey = 'overview' | 'platform_access' | 'team_access' | 'role_permissions';

interface AccessControlSubmenuItem {
  key: AccessControlSubmenuKey;
  label: string;
  description: string;
}

const ACCESS_CONTROL_SUBMENU_ITEMS: AccessControlSubmenuItem[] = [
  {
    key: 'overview',
    label: 'Overview',
    description: 'Summary and posture',
  },
  {
    key: 'platform_access',
    label: 'Platform Access',
    description: 'MFA, launch, registration, portals',
  },
  {
    key: 'team_access',
    label: 'Team Access',
    description: 'Users and limits',
  },
  {
    key: 'role_permissions',
    label: 'Role Permissions',
    description: 'Module permission matrix',
  },
];

const getErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    const payload = error.response?.data as Record<string, unknown> | undefined;
    if (typeof payload?.message === 'string' && payload.message.trim().length > 0) {
      return payload.message;
    }
    if (typeof payload?.error === 'string' && payload.error.trim().length > 0) {
      return payload.error;
    }
    return error.message;
  }

  return error instanceof Error ? error.message : 'Unknown error';
};

const createDraftFromUser = (user: AdminUser): UserDraft => ({
  email: user.email,
  full_name: user.full_name || '',
  role: user.role,
  is_active: user.is_active,
  max_active_backtests: Number(user.max_active_backtests ?? 10),
  max_strategies: Number(user.max_strategies ?? 10),
  max_bot_instances: Number(user.max_bot_instances ?? 10),
});

const hasDraftChanges = (user: AdminUser, draft: UserDraft | undefined): boolean => {
  if (!draft) return false;
  return (
    draft.email !== user.email ||
    draft.full_name !== (user.full_name || '') ||
    draft.role !== user.role ||
    draft.is_active !== user.is_active ||
    draft.max_active_backtests !== Number(user.max_active_backtests ?? 10) ||
    draft.max_strategies !== Number(user.max_strategies ?? 10) ||
    draft.max_bot_instances !== Number(user.max_bot_instances ?? 10)
  );
};

const readBooleanPlatformSetting = (
  payload: SettingsPayload | undefined,
  key: string,
  fallback: boolean
): boolean => {
  const platformSection = payload?.sections?.find((section) => section.section === 'platform');
  const setting = platformSection?.settings?.find((candidate) => candidate.key === key);
  const rawValue = setting?.value ?? setting?.default_value;

  if (typeof rawValue === 'boolean') return rawValue;
  if (typeof rawValue === 'string') {
    const normalized = rawValue.trim().toLowerCase();
    if (['true', '1', 'yes', 'on'].includes(normalized)) return true;
    if (['false', '0', 'no', 'off', ''].includes(normalized)) return false;
  }

  return fallback;
};

const readStringPlatformSetting = (
  payload: SettingsPayload | undefined,
  key: string,
  fallback: string
): string => {
  const platformSection = payload?.sections?.find((section) => section.section === 'platform');
  const setting = platformSection?.settings?.find((candidate) => candidate.key === key);
  const rawValue = setting?.value ?? setting?.default_value;

  if (typeof rawValue === 'string' && rawValue.trim().length > 0) {
    return rawValue.trim();
  }

  return fallback;
};

export function AdminAccessControlSettings() {
  const currentUser = useAuthStore((state) => state.user);
  const refreshCurrentUser = useAuthStore((state) => state.getCurrentUser);
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const [searchQuery, setSearchQuery] = useState('');
  const [drafts, setDrafts] = useState<Record<string, UserDraft>>({});
  const [registrationModeDraft, setRegistrationModeDraft] = useState<RegistrationMode>('open');
  const [invitationCodeDraft, setInvitationCodeDraft] = useState('');
  const [privilegedMfaRequiredDraft, setPrivilegedMfaRequiredDraft] = useState(false);
  const [comingSoonEnabledDraft, setComingSoonEnabledDraft] = useState(false);
  const [crmSubdomainEnabledDraft, setCrmSubdomainEnabledDraft] = useState(true);
  const [crmSubdomainHostDraft, setCrmSubdomainHostDraft] = useState('crm.localhost');
  const [ibSubdomainEnabledDraft, setIbSubdomainEnabledDraft] = useState(true);
  const [ibSubdomainHostDraft, setIbSubdomainHostDraft] = useState('ib-portal.localhost');
  const [customRoleDraft, setCustomRoleDraft] = useState<CustomRoleDraft>({
    role: '',
    display_name: '',
    description: '',
  });
  const [activeSubmenu, setActiveSubmenu] = useState<AccessControlSubmenuKey>('overview');
  const [mobileSubmenuOpen, setMobileSubmenuOpen] = useState(false);
  const subsectionRefs = useRef<Record<AccessControlSubmenuKey, HTMLDivElement | null>>({
    overview: null,
    platform_access: null,
    team_access: null,
    role_permissions: null,
  });
  const [createForm, setCreateForm] = useState<CreateAdminUserPayload>({
    username: '',
    email: '',
    password: '',
    role: 'client',
    full_name: '',
    is_active: true,
    max_active_backtests: 10,
    max_strategies: 10,
    max_bot_instances: 10,
  });

  const usersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: async () => {
      const response = await api.listAdminUsers();
      return response.data;
    },
    staleTime: 30_000,
  });

  const accessControlQuery = useQuery({
    queryKey: ['backoffice', 'access-control'],
    queryFn: async () => {
      const response = await api.getAccessControl();
      return response.data;
    },
    staleTime: 30_000,
  });

  const registrationStatusQuery = useQuery({
    queryKey: ['auth', 'registration-status', 'settings'],
    queryFn: async () => {
      const response = await api.getRegistrationStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  const mailgunStatusQuery = useQuery({
    queryKey: ['mailgun', 'status', 'access-control'],
    queryFn: async () => {
      const response = await api.getMailgunStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  const platformSettingsQuery = useQuery({
    queryKey: ['settings', 'platform', 'access-control'],
    queryFn: async () => {
      const response = await api.getSettings();
      return (response.data || {}) as SettingsPayload;
    },
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!usersQuery.data?.users) {
      return;
    }

    const nextDrafts = usersQuery.data.users.reduce<Record<string, UserDraft>>((acc, user) => {
      acc[String(user.id)] = createDraftFromUser(user);
      return acc;
    }, {});
    setDrafts(nextDrafts);
  }, [usersQuery.data]);

  useEffect(() => {
    if (!registrationStatusQuery.data) {
      return;
    }

    const mode = registrationStatusQuery.data.mode;
    if (mode === 'open' || mode === 'disabled' || mode === 'invitation_only') {
      setRegistrationModeDraft(mode);
    } else if (registrationStatusQuery.data.enabled) {
      setRegistrationModeDraft('open');
    } else {
      setRegistrationModeDraft('disabled');
    }
  }, [registrationStatusQuery.data]);

  useEffect(() => {
    setPrivilegedMfaRequiredDraft(
      readBooleanPlatformSetting(platformSettingsQuery.data, 'require_privileged_mfa', false)
    );
    setComingSoonEnabledDraft(
      readBooleanPlatformSetting(platformSettingsQuery.data, 'coming_soon_enabled', false)
    );

    setCrmSubdomainEnabledDraft(
      readBooleanPlatformSetting(platformSettingsQuery.data, 'crm_subdomain_enabled', true)
    );
    setCrmSubdomainHostDraft(
      readStringPlatformSetting(platformSettingsQuery.data, 'crm_subdomain_host', 'crm.localhost')
    );
    setIbSubdomainEnabledDraft(
      readBooleanPlatformSetting(platformSettingsQuery.data, 'ib_subdomain_enabled', true)
    );
    setIbSubdomainHostDraft(
      readStringPlatformSetting(
        platformSettingsQuery.data,
        'ib_subdomain_host',
        'ib-portal.localhost'
      )
    );
  }, [platformSettingsQuery.data]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        const topVisible = visibleEntries[0];
        if (!topVisible) {
          return;
        }

        const sectionKey = topVisible.target.getAttribute('data-access-control-section');
        if (!sectionKey) {
          return;
        }

        if (
          sectionKey === 'overview' ||
          sectionKey === 'platform_access' ||
          sectionKey === 'team_access' ||
          sectionKey === 'role_permissions'
        ) {
          setActiveSubmenu(sectionKey);
        }
      },
      {
        threshold: [0.2, 0.45, 0.7],
        rootMargin: '-110px 0px -45% 0px',
      }
    );

    const sectionElements = Object.values(subsectionRefs.current).filter(
      (element): element is HTMLDivElement => element !== null
    );

    sectionElements.forEach((element) => observer.observe(element));

    return () => {
      sectionElements.forEach((element) => observer.unobserve(element));
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!mobileSubmenuOpen) {
      return;
    }

    setMobileSubmenuOpen(false);
  }, [activeSubmenu, mobileSubmenuOpen]);

  const updateRegistrationPolicyMutation = useMutation({
    mutationFn: async ({
      mode,
      invitationCode,
    }: {
      mode: RegistrationMode;
      invitationCode: string;
    }) =>
      api.updateSettings({
        'platform.allow_public_registration': mode === 'open',
        'platform.registration_mode': mode,
        ...(mode === 'invitation_only'
          ? invitationCode.trim().length > 0
            ? { 'platform.registration_invitation_code': invitationCode }
            : {}
          : { 'platform.registration_invitation_code': '' }),
      }),
    onSuccess: (_, variables) => {
      const enabled = variables.mode === 'open';
      successToast(
        variables.mode === 'invitation_only'
          ? 'Invitation-only registration enabled'
          : enabled
            ? 'Public registration enabled'
            : 'Public registration disabled',
        variables.mode === 'invitation_only'
          ? 'Prospects can register only with a valid invitation code.'
          : enabled
            ? 'Prospects can create accounts directly again.'
            : 'Only admins can create new accounts right now.'
      );
      void queryClient.invalidateQueries({ queryKey: ['auth', 'registration-status'] });
      void queryClient.invalidateQueries({ queryKey: ['auth', 'registration-status', 'settings'] });
      void queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to update registration access', getErrorMessage(error));
    },
  });

  const createUserMutation = useMutation({
    mutationFn: async (payload: CreateAdminUserPayload) => api.createAdminUser(payload),
    onSuccess: (response) => {
      setCreateForm({
        username: '',
        email: '',
        password: '',
        role: 'client',
        full_name: '',
        is_active: true,
        max_active_backtests: 10,
        max_strategies: 10,
        max_bot_instances: 10,
      });
      successToast(
        'User created',
        'The new platform account is ready and assigned to the selected role.'
      );
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      void queryClient.invalidateQueries({ queryKey: ['mailgun'] });
      const notice = response.data?.onboarding_notice;
      if (typeof notice === 'string' && notice.trim().length > 0) {
        if (
          notice.toLowerCase().includes('skipped') ||
          notice.toLowerCase().includes('not configured')
        ) {
          errorToast('Onboarding email skipped', notice);
        } else {
          successToast('Onboarding notice', notice);
        }
      }
    },
    onError: (error: unknown) => {
      errorToast('Failed to create user', getErrorMessage(error));
    },
  });

  const createCustomRoleMutation = useMutation({
    mutationFn: async (payload: CreateCustomRolePayload) => api.createCustomRole(payload),
    onSuccess: () => {
      setCustomRoleDraft({ role: '', display_name: '', description: '' });
      successToast('Role created', 'The custom role is available for user assignment.');
      void queryClient.invalidateQueries({ queryKey: ['backoffice', 'access-control'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to create role', getErrorMessage(error));
    },
  });

  const updateRolePermissionsMutation = useMutation({
    mutationFn: async ({ role, permissionKeys }: { role: string; permissionKeys: string[] }) =>
      api.updateRolePermissions(role, permissionKeys),
    onSuccess: (_, variables) => {
      successToast('Permissions updated', `${variables.role} permissions are now active.`);
      void queryClient.invalidateQueries({ queryKey: ['backoffice', 'access-control'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to update role permissions', getErrorMessage(error));
    },
  });

  const deleteCustomRoleMutation = useMutation({
    mutationFn: async (role: string) => api.deleteCustomRole(role),
    onSuccess: (_, role) => {
      successToast('Role deleted', `${role} was removed from the custom role catalog.`);
      void queryClient.invalidateQueries({ queryKey: ['backoffice', 'access-control'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to delete role', getErrorMessage(error));
    },
  });

  const updatePrivilegedMfaMutation = useMutation({
    mutationFn: async (enabled: boolean) =>
      api.updateSettings({
        'platform.require_privileged_mfa': enabled,
      }),
    onSuccess: async (_, enabled) => {
      successToast(
        enabled ? 'Privileged MFA enabled' : 'Privileged MFA disabled',
        enabled
          ? 'Admin and CRM operators will be required to enroll in MFA before privileged actions.'
          : 'Privileged routes are no longer forcing MFA during development.'
      );
      await refreshCurrentUser();
      void queryClient.invalidateQueries({ queryKey: ['settings'] });
      void queryClient.invalidateQueries({ queryKey: ['settings', 'platform'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to update MFA policy', getErrorMessage(error));
    },
  });

  const updateComingSoonMutation = useMutation({
    mutationFn: async (enabled: boolean) =>
      api.updateSettings({
        'platform.coming_soon_enabled': enabled,
      }),
    onSuccess: (_, enabled) => {
      successToast(
        enabled ? 'Coming Soon mode enabled' : 'Coming Soon mode disabled',
        enabled
          ? 'Unauthenticated public client-portal traffic now sees the launch page.'
          : 'Public client-portal pages are available again.'
      );
      void queryClient.invalidateQueries({ queryKey: ['settings'] });
      void queryClient.invalidateQueries({ queryKey: ['settings', 'platform'] });
      void queryClient.invalidateQueries({ queryKey: ['settings', 'platform', 'access-control'] });
      void queryClient.invalidateQueries({ queryKey: ['public', 'app-config'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to update Coming Soon mode', getErrorMessage(error));
    },
  });

  const updatePortalSubdomainMutation = useMutation({
    mutationFn: async () =>
      api.updateSettings({
        'platform.crm_subdomain_enabled': crmSubdomainEnabledDraft,
        'platform.crm_subdomain_host': crmSubdomainHostDraft.trim(),
        'platform.ib_subdomain_enabled': ibSubdomainEnabledDraft,
        'platform.ib_subdomain_host': ibSubdomainHostDraft.trim(),
      }),
    onSuccess: async () => {
      setPortalSubdomainConfig('crm', {
        enabled: crmSubdomainEnabledDraft,
        host: crmSubdomainHostDraft,
      });
      setPortalSubdomainConfig('ib', {
        enabled: ibSubdomainEnabledDraft,
        host: ibSubdomainHostDraft,
      });

      successToast(
        'Subdomain routing settings saved',
        'CRM and IB portal subdomain preferences were updated.'
      );
      await refreshCurrentUser();
      void queryClient.invalidateQueries({ queryKey: ['settings'] });
      void queryClient.invalidateQueries({ queryKey: ['settings', 'platform'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to update subdomain settings', getErrorMessage(error));
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: async ({ userId, payload }: { userId: number; payload: UpdateAdminUserPayload }) =>
      api.updateAdminUser(userId, payload),
    onSuccess: () => {
      successToast('Access updated', 'Role and account status changes have been applied.');
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to update user', getErrorMessage(error));
    },
  });

  const resetUserMFAMutation = useMutation({
    mutationFn: async (userId: number) => api.resetAdminUserMFA(userId),
    onSuccess: async (response, userId) => {
      const data = response.data as ResetAdminUserMFAResponse | undefined;
      successToast(
        'MFA reset',
        data?.credential_removed
          ? 'Authenticator enrollment was cleared. The user must enroll again on next setup.'
          : 'No stored MFA credential was found, but the user MFA flag is now cleared.'
      );
      if (currentUser?.id === userId) {
        await refreshCurrentUser();
      }
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to reset MFA', getErrorMessage(error));
    },
  });

  const users = usersQuery.data?.users || [];
  const roles = accessControlQuery.data?.roles ||
    usersQuery.data?.roles || ['admin', 'user', 'accounting', 'marketing', 'agent', 'client'];
  const roleCatalog =
    accessControlQuery.data?.role_catalog ||
    roles.map((role) => ({
      role,
      display_name: role,
      description: '',
      is_system: true,
    }));
  const permissions = accessControlQuery.data?.permissions || [];
  const rolePermissions = accessControlQuery.data?.role_permissions || [];
  const permissionsByModule = useMemo(() => {
    return permissions.reduce<Record<string, AccessControlPermission[]>>((acc, permission) => {
      const moduleKey = permission.permission_key.split('.')[0] || 'general';
      acc[moduleKey] = [...(acc[moduleKey] || []), permission];
      return acc;
    }, {});
  }, [permissions]);
  const rolePermissionSet = useMemo(() => {
    return rolePermissions.reduce<Record<string, Set<string>>>((acc, row) => {
      const permissionSet = (acc[row.role] ??= new Set<string>());
      permissionSet.add(row.permission_key);
      return acc;
    }, {});
  }, [rolePermissions]);
  const activeAdmins = users.filter((user) => user.role === 'admin' && user.is_active).length;
  const filteredUsers = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return users;
    return users.filter((user) =>
      [user.username, user.email, user.full_name || '', user.role].some((value) =>
        value.toLowerCase().includes(query)
      )
    );
  }, [searchQuery, users]);
  const pendingPasswordChanges = users.filter(
    (user) => user.password_change_required && user.is_active
  ).length;

  const registrationMode =
    registrationStatusQuery.data?.mode === 'invitation_only' ||
    registrationStatusQuery.data?.mode === 'disabled' ||
    registrationStatusQuery.data?.mode === 'open'
      ? registrationStatusQuery.data.mode
      : (registrationStatusQuery.data?.enabled ?? true)
        ? 'open'
        : 'disabled';

  const handleDraftChange = (
    userId: number,
    field: keyof UserDraft,
    value: string | boolean | number
  ) => {
    setDrafts((prev) => ({
      ...prev,
      [String(userId)]: {
        ...(prev[String(userId)] || {
          email: '',
          full_name: '',
          role: 'client',
          is_active: true,
          max_active_backtests: 10,
          max_strategies: 10,
          max_bot_instances: 10,
        }),
        [field]: value,
      },
    }));
  };

  const handleSaveUser = (user: AdminUser) => {
    const draft = drafts[String(user.id)];
    if (!draft) return;

    const payload: UpdateAdminUserPayload = {};
    if (draft.email !== user.email) payload.email = draft.email;
    if (draft.full_name !== (user.full_name || '')) payload.full_name = draft.full_name;
    if (draft.role !== user.role) payload.role = draft.role;
    if (draft.is_active !== user.is_active) payload.is_active = draft.is_active;
    if (draft.max_active_backtests !== Number(user.max_active_backtests ?? 10)) {
      payload.max_active_backtests = draft.max_active_backtests;
    }
    if (draft.max_strategies !== Number(user.max_strategies ?? 10)) {
      payload.max_strategies = draft.max_strategies;
    }
    if (draft.max_bot_instances !== Number(user.max_bot_instances ?? 10)) {
      payload.max_bot_instances = draft.max_bot_instances;
    }

    if (Object.keys(payload).length === 0) {
      return;
    }

    updateUserMutation.mutate({ userId: user.id, payload });
  };

  const handleCreateCustomRole = () => {
    const role = customRoleDraft.role.trim().toLowerCase();
    if (!role) return;
    createCustomRoleMutation.mutate({
      role,
      display_name: customRoleDraft.display_name.trim() || role,
      description: customRoleDraft.description.trim(),
    });
  };

  const handleRolePermissionToggle = (role: string, permissionKey: string, enabled: boolean) => {
    const current = new Set(rolePermissionSet[role] || []);
    if (enabled) {
      current.add(permissionKey);
    } else {
      current.delete(permissionKey);
    }
    updateRolePermissionsMutation.mutate({
      role,
      permissionKeys: Array.from(current).sort(),
    });
  };

  const registrationEnabled = registrationStatusQuery.data?.enabled ?? true;

  const buildPortalPreviewUrl = (host: string, path: string): string => {
    if (typeof window === 'undefined') {
      return `https://${host}${path}`;
    }
    const { protocol, port } = window.location;
    const normalizedHost = host
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, '')
      .replace(/\/$/, '');
    const portPart = port ? `:${port}` : '';
    return `${protocol}//${normalizedHost}${portPart}${path}`;
  };

  const crmPreviewUrl = buildPortalPreviewUrl(
    crmSubdomainHostDraft || 'crm.localhost',
    '/dashboard'
  );
  const ibPreviewUrl = buildPortalPreviewUrl(
    ibSubdomainHostDraft || 'ib-portal.localhost',
    '/dashboard'
  );

  const handleSubmenuSelect = (key: AccessControlSubmenuKey) => {
    setActiveSubmenu(key);
    setMobileSubmenuOpen(false);
    subsectionRefs.current[key]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const activeSubmenuItem =
    ACCESS_CONTROL_SUBMENU_ITEMS.find((item) => item.key === activeSubmenu) ??
    ACCESS_CONTROL_SUBMENU_ITEMS[0]!;

  return (
    <div className="space-y-6">
      <div className="sticky top-4 z-10 rounded-2xl border border-slate-700/70 bg-slate-900/95 p-2 backdrop-blur">
        <div className="md:hidden">
          <button
            type="button"
            onClick={() => setMobileSubmenuOpen((prev) => !prev)}
            className="flex w-full items-center justify-between rounded-xl border border-slate-700/70 bg-slate-950/50 px-3 py-2 text-left text-slate-200 transition hover:border-slate-500"
            aria-expanded={mobileSubmenuOpen}
            aria-label="Toggle access control submenu"
          >
            <span>
              <p className="text-xs font-semibold uppercase tracking-[0.16em]">
                {activeSubmenuItem.label}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">{activeSubmenuItem.description}</p>
            </span>
            <ChevronDown
              className={`h-4 w-4 text-slate-400 transition-transform ${mobileSubmenuOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {mobileSubmenuOpen && (
            <div className="mt-2 space-y-2 rounded-xl border border-slate-700/70 bg-slate-950/50 p-2">
              {ACCESS_CONTROL_SUBMENU_ITEMS.map((item) => {
                const isActive = activeSubmenu === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => handleSubmenuSelect(item.key)}
                    className={`w-full rounded-lg border px-3 py-2 text-left transition ${
                      isActive
                        ? 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200'
                        : 'border-slate-700/70 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:text-slate-100'
                    }`}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.16em]">
                      {item.label}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-400">{item.description}</p>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="hidden gap-2 md:grid md:grid-cols-2 xl:grid-cols-4">
          {ACCESS_CONTROL_SUBMENU_ITEMS.map((item) => {
            const isActive = activeSubmenu === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => handleSubmenuSelect(item.key)}
                className={`rounded-xl border px-3 py-2 text-left transition ${
                  isActive
                    ? 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200'
                    : 'border-slate-700/70 bg-slate-950/40 text-slate-300 hover:border-slate-500 hover:text-slate-100'
                }`}
              >
                <p className="text-xs font-semibold uppercase tracking-[0.16em]">{item.label}</p>
                <p className="mt-1 text-[11px] text-slate-400">{item.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      <div
        ref={(element) => {
          subsectionRefs.current.overview = element;
        }}
        data-access-control-section="overview"
        className="premium-panel"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="premium-kicker">Admin Access Control</div>
            <h2 className="mt-3 text-2xl font-semibold text-white">
              Manage registrations, teams, and production roles from one place.
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              This is the platform control surface for who can enter the app and what operating lane
              they belong to.
            </p>
          </div>
          <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
            {currentUser?.role === 'admin'
              ? 'You are operating with admin privileges.'
              : 'Admin access required.'}
          </div>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
            <div className="flex items-center gap-2 text-slate-200">
              <LockKeyhole className="h-4 w-4 text-cyan-300" />
              Public registration
            </div>
            <p className="mt-3 text-2xl font-semibold text-white">
              {registrationMode === 'invitation_only'
                ? 'Invite-only'
                : registrationEnabled
                  ? 'Enabled'
                  : 'Locked'}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {registrationStatusQuery.data?.reason ||
                'Controls whether prospects can self-register.'}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
            <div className="flex items-center gap-2 text-slate-200">
              <EyeOff className="h-4 w-4 text-violet-300" />
              Public launch mode
            </div>
            <p className="mt-3 text-2xl font-semibold text-white">
              {comingSoonEnabledDraft ? 'Coming Soon' : 'Live'}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Controls the unauthenticated client-portal experience.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
            <div className="flex items-center gap-2 text-slate-200">
              <Users className="h-4 w-4 text-emerald-300" />
              Total users
            </div>
            <p className="mt-3 text-2xl font-semibold text-white">{users.length}</p>
            <p className="mt-1 text-xs text-slate-500">
              All active and archived platform accounts.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4 xl:col-span-1">
            <div className="flex items-center gap-2 text-slate-200">
              <ShieldCheck className="h-4 w-4 text-amber-300" />
              Active admins
            </div>
            <p className="mt-3 text-2xl font-semibold text-white">{activeAdmins}</p>
            <p className="mt-1 text-xs text-slate-500">
              The backend will not allow the last admin to be removed.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
            <div className="flex items-center gap-2 text-slate-200">
              <UserCog className="h-4 w-4 text-fuchsia-300" />
              Role catalog
            </div>
            <p className="mt-3 text-sm font-semibold text-white">{roles.join(', ')}</p>
            <p className="mt-1 text-xs text-slate-500">Predefined for the DeFi operating model.</p>
          </div>
        </div>

        {!mailgunStatusQuery.data?.configured && pendingPasswordChanges > 0 && (
          <div className="mt-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-4 text-sm text-amber-100">
            Mailgun is still not configured, and {pendingPasswordChanges} user account
            {pendingPasswordChanges === 1 ? '' : 's'} still require a first-login password change.
            The platform will enforce password rotation, but onboarding emails are currently
            skipped.
          </div>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.92fr,1.08fr]">
        <div
          ref={(element) => {
            subsectionRefs.current.platform_access = element;
          }}
          data-access-control-section="platform_access"
          className="premium-panel"
        >
          <h3 className="text-lg font-semibold text-white">Platform access</h3>
          <p className="mt-1 text-sm text-slate-400">
            Make registration policy obvious here instead of hiding it in generic configuration.
          </p>

          <div className="mt-5 rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-semibold text-white">Privileged MFA policy</p>
                <p className="mt-1 text-sm text-slate-400">
                  Keep this disabled while developing locally, then enable it before staging or
                  production cutover.
                </p>
              </div>
              <label className="flex items-center gap-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={privilegedMfaRequiredDraft}
                  onChange={(event) => setPrivilegedMfaRequiredDraft(event.target.checked)}
                  disabled={
                    updatePrivilegedMfaMutation.isPending || platformSettingsQuery.isLoading
                  }
                  className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500"
                />
                Require MFA for admin and CRM roles
              </label>
            </div>

            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => updatePrivilegedMfaMutation.mutate(privilegedMfaRequiredDraft)}
                disabled={updatePrivilegedMfaMutation.isPending || platformSettingsQuery.isLoading}
                className="inline-flex min-w-42.5 items-center justify-center rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
              >
                {updatePrivilegedMfaMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Save MFA policy'
                )}
              </button>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-violet-500/25 bg-violet-500/10 p-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Rocket className="h-4 w-4 text-violet-200" />
                  <p className="text-sm font-semibold text-white">Coming Soon mode</p>
                </div>
                <p className="mt-1 text-sm leading-6 text-slate-300">
                  Show the public launch page for unauthenticated client-portal traffic while
                  keeping sign-in, admin, CRM, and IB portals reachable.
                </p>
              </div>
              <label className="flex items-center gap-3 text-sm text-slate-100">
                <input
                  type="checkbox"
                  checked={comingSoonEnabledDraft}
                  onChange={(event) => setComingSoonEnabledDraft(event.target.checked)}
                  disabled={updateComingSoonMutation.isPending || platformSettingsQuery.isLoading}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-violet-500"
                />
                Enable public launch page
              </label>
            </div>

            <div className="mt-4 rounded-xl border border-slate-700/60 bg-slate-950/40 p-3 text-sm text-slate-300">
              {comingSoonEnabledDraft
                ? 'Public visitors will see the branded launch page. Existing operators can still sign in.'
                : 'Public visitors can access the normal website and onboarding routes.'}
            </div>

            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => updateComingSoonMutation.mutate(comingSoonEnabledDraft)}
                disabled={updateComingSoonMutation.isPending || platformSettingsQuery.isLoading}
                className="inline-flex min-w-42.5 items-center justify-center rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
              >
                {updateComingSoonMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Save launch mode'
                )}
              </button>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-semibold text-white">Registration mode</p>
                <p className="mt-1 text-sm text-slate-400">
                  Choose open access, lock registration, or require invitation codes.
                </p>
              </div>
              <select
                value={registrationModeDraft}
                onChange={(event) =>
                  setRegistrationModeDraft(event.target.value as RegistrationMode)
                }
                disabled={
                  registrationStatusQuery.isLoading || updateRegistrationPolicyMutation.isPending
                }
                className="premium-input min-w-55"
              >
                <option value="open">Open (public registration)</option>
                <option value="invitation_only">Invitation-only</option>
                <option value="disabled">Disabled</option>
              </select>
            </div>

            {registrationModeDraft === 'invitation_only' && (
              <div className="mt-4 grid gap-2">
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Invitation code
                </label>
                <input
                  value={invitationCodeDraft}
                  onChange={(event) => setInvitationCodeDraft(event.target.value)}
                  placeholder="Set invitation code"
                  className="premium-input"
                  disabled={updateRegistrationPolicyMutation.isPending}
                />
                <p className="text-xs text-slate-500">
                  Share this code privately with invited users.
                </p>
                <p className="text-xs text-slate-500">
                  Need one-time or expiring partner onboarding tokens?{' '}
                  <a
                    href={ibPortalHref('dashboard')}
                    className="text-cyan-300 hover:text-cyan-200 underline"
                  >
                    Open IB Portal
                  </a>
                  .
                </p>
              </div>
            )}

            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() =>
                  updateRegistrationPolicyMutation.mutate({
                    mode: registrationModeDraft,
                    invitationCode:
                      registrationModeDraft === 'invitation_only' ? invitationCodeDraft.trim() : '',
                  })
                }
                disabled={
                  updateRegistrationPolicyMutation.isPending || registrationStatusQuery.isLoading
                }
                className="inline-flex min-w-42.5 items-center justify-center rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
              >
                {updateRegistrationPolicyMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Save policy'
                )}
              </button>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
            <div>
              <p className="text-sm font-semibold text-white">Portal subdomain routing</p>
              <p className="mt-1 text-sm text-slate-400">
                Enable/disable subdomain shortcuts and override hostnames for CRM and IB portal.
              </p>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-700/60 bg-slate-900/40 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-white">CRM subdomain</p>
                  <label className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={crmSubdomainEnabledDraft}
                      onChange={(event) => setCrmSubdomainEnabledDraft(event.target.checked)}
                      disabled={updatePortalSubdomainMutation.isPending}
                      className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500"
                    />
                    Enabled
                  </label>
                </div>
                <label className="mt-3 block text-xs uppercase tracking-[0.14em] text-slate-500">
                  Host
                </label>
                <input
                  value={crmSubdomainHostDraft}
                  onChange={(event) => setCrmSubdomainHostDraft(event.target.value)}
                  placeholder="crm.localhost"
                  disabled={updatePortalSubdomainMutation.isPending}
                  className="premium-input mt-2"
                />
              </div>

              <div className="rounded-xl border border-slate-700/60 bg-slate-900/40 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-white">IB subdomain</p>
                  <label className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={ibSubdomainEnabledDraft}
                      onChange={(event) => setIbSubdomainEnabledDraft(event.target.checked)}
                      disabled={updatePortalSubdomainMutation.isPending}
                      className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500"
                    />
                    Enabled
                  </label>
                </div>
                <label className="mt-3 block text-xs uppercase tracking-[0.14em] text-slate-500">
                  Host
                </label>
                <input
                  value={ibSubdomainHostDraft}
                  onChange={(event) => setIbSubdomainHostDraft(event.target.value)}
                  placeholder="ib-portal.localhost"
                  disabled={updatePortalSubdomainMutation.isPending}
                  className="premium-input mt-2"
                />
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-slate-700/60 bg-slate-900/30 p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                Effective preview
              </p>
              <div className="mt-2 space-y-2 text-xs">
                <p className="text-slate-300">
                  CRM shortcut:{' '}
                  <span className="font-mono text-cyan-200">
                    {crmSubdomainEnabledDraft ? crmPreviewUrl : '/crm/dashboard'}
                  </span>
                </p>
                <p className="text-slate-300">
                  IB shortcut:{' '}
                  <span className="font-mono text-cyan-200">
                    {ibSubdomainEnabledDraft ? ibPreviewUrl : '/ib-portal/dashboard'}
                  </span>
                </p>
              </div>
            </div>

            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => updatePortalSubdomainMutation.mutate()}
                disabled={
                  updatePortalSubdomainMutation.isPending ||
                  crmSubdomainHostDraft.trim().length === 0 ||
                  ibSubdomainHostDraft.trim().length === 0
                }
                className="inline-flex min-w-42.5 items-center justify-center rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
              >
                {updatePortalSubdomainMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Save subdomain routing'
                )}
              </button>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-slate-700/60 bg-slate-950/50 p-5">
            <div className="flex items-center gap-2 text-white">
              <UserPlus className="h-4 w-4 text-cyan-300" />
              Create user
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <input
                value={createForm.username}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, username: event.target.value }))
                }
                placeholder="Username"
                className="premium-input"
              />
              <input
                value={createForm.email}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, email: event.target.value }))
                }
                placeholder="Email"
                className="premium-input"
              />
              <input
                value={createForm.full_name || ''}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, full_name: event.target.value }))
                }
                placeholder="Full name"
                className="premium-input"
              />
              <select
                value={createForm.role}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, role: event.target.value }))
                }
                className="premium-input"
              >
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              <input
                type="password"
                value={createForm.password}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, password: event.target.value }))
                }
                placeholder="Temporary password"
                className="premium-input md:col-span-2"
              />
              <input
                type="number"
                min={1}
                max={1000}
                value={Number(createForm.max_active_backtests ?? 10)}
                onChange={(event) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    max_active_backtests: Math.max(1, Number(event.target.value || 10)),
                  }))
                }
                placeholder="Max active backtests"
                className="premium-input"
              />
              <input
                type="number"
                min={1}
                max={1000}
                value={Number(createForm.max_strategies ?? 10)}
                onChange={(event) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    max_strategies: Math.max(1, Number(event.target.value || 10)),
                  }))
                }
                placeholder="Max strategies"
                className="premium-input"
              />
              <input
                type="number"
                min={1}
                max={1000}
                value={Number(createForm.max_bot_instances ?? 10)}
                onChange={(event) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    max_bot_instances: Math.max(1, Number(event.target.value || 10)),
                  }))
                }
                placeholder="Max bot instances"
                className="premium-input md:col-span-2"
              />
            </div>

            <label className="mt-4 flex items-center gap-3 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={createForm.is_active ?? true}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, is_active: event.target.checked }))
                }
                className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500"
              />
              Activate this account immediately
            </label>

            <button
              type="button"
              onClick={() => createUserMutation.mutate(createForm)}
              disabled={
                createUserMutation.isPending ||
                createForm.username.trim().length === 0 ||
                createForm.email.trim().length === 0 ||
                createForm.password.trim().length < 6
              }
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {createUserMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              Create platform user
            </button>
          </div>

          <div className="mt-6 rounded-2xl border border-slate-700/60 bg-slate-950/50 p-5">
            <div className="flex items-center gap-2 text-white">
              <UserCog className="h-4 w-4 text-violet-300" />
              Custom roles
            </div>
            <p className="mt-1 text-sm text-slate-400">
              Create role keys for testing or operations, then assign permissions by module below.
            </p>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <input
                value={customRoleDraft.role}
                onChange={(event) =>
                  setCustomRoleDraft((prev) => ({ ...prev, role: event.target.value }))
                }
                placeholder="role_key"
                className="premium-input"
              />
              <input
                value={customRoleDraft.display_name}
                onChange={(event) =>
                  setCustomRoleDraft((prev) => ({ ...prev, display_name: event.target.value }))
                }
                placeholder="Display name"
                className="premium-input"
              />
              <input
                value={customRoleDraft.description}
                onChange={(event) =>
                  setCustomRoleDraft((prev) => ({ ...prev, description: event.target.value }))
                }
                placeholder="Description"
                className="premium-input md:col-span-2"
              />
            </div>

            <button
              type="button"
              onClick={handleCreateCustomRole}
              disabled={
                createCustomRoleMutation.isPending || customRoleDraft.role.trim().length < 2
              }
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {createCustomRoleMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <UserCog className="h-4 w-4" />
              )}
              Create custom role
            </button>
          </div>
        </div>

        <div
          ref={(element) => {
            subsectionRefs.current.team_access = element;
          }}
          data-access-control-section="team_access"
          className="premium-panel"
        >
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">User roles and account state</h3>
              <p className="mt-1 text-sm text-slate-400">
                Update role assignments without leaving Settings.
              </p>
            </div>
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search users..."
              className="premium-input w-full max-w-xs"
            />
          </div>

          <div className="mt-5 space-y-4">
            {usersQuery.isLoading ? (
              <div className="flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-950/50 px-4 py-5 text-sm text-slate-300">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading team access...
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="rounded-2xl border border-slate-700 bg-slate-950/50 px-4 py-5 text-sm text-slate-400">
                No users match your search.
              </div>
            ) : (
              filteredUsers.map((user) => {
                const draft = drafts[String(user.id)] || createDraftFromUser(user);
                const isSelf = user.id === currentUser?.id;
                const dirty = hasDraftChanges(user, draft);
                const isSavingThisUser =
                  updateUserMutation.isPending && updateUserMutation.variables?.userId === user.id;
                const isResettingThisUser =
                  resetUserMFAMutation.isPending && resetUserMFAMutation.variables === user.id;

                return (
                  <div
                    key={user.id}
                    className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4"
                  >
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-lg font-semibold text-white">
                            {user.full_name || user.username}
                          </p>
                          <span className="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-300">
                            {user.role}
                          </span>
                          {user.is_active ? (
                            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-emerald-200">
                              Active
                            </span>
                          ) : (
                            <span className="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-400">
                              Inactive
                            </span>
                          )}
                          {isSelf && (
                            <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-cyan-200">
                              Your account
                            </span>
                          )}
                          {user.password_change_required && (
                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-amber-200">
                              Password reset pending
                            </span>
                          )}
                          {user.mfa_enabled ? (
                            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-emerald-200">
                              MFA enabled
                            </span>
                          ) : (
                            <span className="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-400">
                              MFA not enabled
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-slate-400">
                          {user.username} · {user.email}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => resetUserMFAMutation.mutate(user.id)}
                          disabled={isResettingThisUser}
                          className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm font-semibold text-amber-100 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
                        >
                          {isResettingThisUser ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RotateCcw className="h-4 w-4" />
                          )}
                          Reset MFA
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSaveUser(user)}
                          disabled={!dirty || isSavingThisUser}
                          className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700"
                        >
                          {isSavingThisUser ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            'Save changes'
                          )}
                        </button>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Email
                        </label>
                        <input
                          value={draft.email}
                          onChange={(event) =>
                            handleDraftChange(user.id, 'email', event.target.value)
                          }
                          className="premium-input"
                        />
                      </div>
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Full name
                        </label>
                        <input
                          value={draft.full_name}
                          onChange={(event) =>
                            handleDraftChange(user.id, 'full_name', event.target.value)
                          }
                          className="premium-input"
                        />
                      </div>
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Role
                        </label>
                        <select
                          value={draft.role}
                          onChange={(event) =>
                            handleDraftChange(user.id, 'role', event.target.value)
                          }
                          disabled={isSelf}
                          className="premium-input disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {roles.map((role) => (
                            <option key={role} value={role}>
                              {role}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Account status
                        </label>
                        <label className="flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">
                          <input
                            type="checkbox"
                            checked={draft.is_active}
                            onChange={(event) =>
                              handleDraftChange(user.id, 'is_active', event.target.checked)
                            }
                            disabled={isSelf}
                            className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500 disabled:cursor-not-allowed"
                          />
                          {draft.is_active
                            ? 'User can access the platform'
                            : 'User is suspended from login'}
                        </label>
                      </div>
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Max active backtests
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={1000}
                          value={draft.max_active_backtests}
                          onChange={(event) =>
                            handleDraftChange(
                              user.id,
                              'max_active_backtests',
                              Math.max(1, Number(event.target.value || 10))
                            )
                          }
                          className="premium-input"
                        />
                      </div>
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Max strategies
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={1000}
                          value={draft.max_strategies}
                          onChange={(event) =>
                            handleDraftChange(
                              user.id,
                              'max_strategies',
                              Math.max(1, Number(event.target.value || 10))
                            )
                          }
                          className="premium-input"
                        />
                      </div>
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Max bot instances
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={1000}
                          value={draft.max_bot_instances}
                          onChange={(event) =>
                            handleDraftChange(
                              user.id,
                              'max_bot_instances',
                              Math.max(1, Number(event.target.value || 10))
                            )
                          }
                          className="premium-input"
                        />
                      </div>
                    </div>

                    {isSelf && (
                      <p className="mt-3 text-xs text-slate-500">
                        Your own admin role and active state are locked here for safety. Use Profile
                        for your personal details. If you reset your own MFA while privileged MFA is
                        required, you will need to enroll again before returning to admin routes.
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      <div
        ref={(element) => {
          subsectionRefs.current.role_permissions = element;
        }}
        data-access-control-section="role_permissions"
        className="premium-panel"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Role permissions by module</h3>
            <p className="mt-1 text-sm text-slate-400">
              Toggle module permissions for built-in and custom roles. Backend route guards apply
              these changes immediately.
            </p>
          </div>
          {accessControlQuery.isLoading && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading permissions...
            </div>
          )}
        </div>

        <div className="mt-5 space-y-4">
          {roleCatalog.map((role) => {
            const roleKey = role.role;
            const selectedPermissions = rolePermissionSet[roleKey] || new Set<string>();
            const isDeletingRole =
              deleteCustomRoleMutation.isPending && deleteCustomRoleMutation.variables === roleKey;

            return (
              <div
                key={roleKey}
                className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-base font-semibold text-white">
                        {role.display_name || roleKey}
                      </p>
                      <span className="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-300">
                        {roleKey}
                      </span>
                      <span className="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        {role.is_system ? 'System' : 'Custom'}
                      </span>
                    </div>
                    {role.description && (
                      <p className="mt-1 text-sm text-slate-400">{role.description}</p>
                    )}
                  </div>
                  {!role.is_system && (
                    <button
                      type="button"
                      onClick={() => deleteCustomRoleMutation.mutate(roleKey)}
                      disabled={isDeletingRole}
                      className="inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
                    >
                      {isDeletingRole ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                      Delete role
                    </button>
                  )}
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                  {Object.entries(permissionsByModule).map(([moduleKey, modulePermissions]) => (
                    <div
                      key={`${roleKey}-${moduleKey}`}
                      className="rounded-xl border border-slate-700/60 bg-slate-900/35 p-4"
                    >
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {moduleKey}
                      </p>
                      <div className="mt-3 space-y-3">
                        {modulePermissions.map((permission) => {
                          const isChecked = selectedPermissions.has(permission.permission_key);
                          const isUpdating =
                            updateRolePermissionsMutation.isPending &&
                            updateRolePermissionsMutation.variables?.role === roleKey;

                          return (
                            <label
                              key={`${roleKey}-${permission.permission_key}`}
                              className="flex items-start gap-3 text-sm text-slate-300"
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                disabled={isUpdating}
                                onChange={(event) =>
                                  handleRolePermissionToggle(
                                    roleKey,
                                    permission.permission_key,
                                    event.target.checked
                                  )
                                }
                                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500 disabled:cursor-not-allowed"
                              />
                              <span>
                                <span className="block font-medium text-slate-100">
                                  {permission.permission_key}
                                </span>
                                <span className="block text-xs text-slate-500">
                                  {permission.description}
                                </span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
