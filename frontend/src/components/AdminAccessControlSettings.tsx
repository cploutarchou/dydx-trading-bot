import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Loader2, LockKeyhole, ShieldCheck, UserCog, UserPlus, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { AdminUser, CreateAdminUserPayload, UpdateAdminUserPayload } from '../api';
import { useAuthStore } from '../store/auth';
import { useToastStore } from './ErrorBoundary';

interface UserDraft {
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

type RegistrationMode = 'open' | 'disabled' | 'invitation_only';

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
});

const hasDraftChanges = (user: AdminUser, draft: UserDraft | undefined): boolean => {
  if (!draft) return false;
  return (
    draft.email !== user.email ||
    draft.full_name !== (user.full_name || '') ||
    draft.role !== user.role ||
    draft.is_active !== user.is_active
  );
};

export function AdminAccessControlSettings() {
  const currentUser = useAuthStore((state) => state.user);
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const [searchQuery, setSearchQuery] = useState('');
  const [drafts, setDrafts] = useState<Record<string, UserDraft>>({});
  const [registrationModeDraft, setRegistrationModeDraft] = useState<RegistrationMode>('open');
  const [invitationCodeDraft, setInvitationCodeDraft] = useState('');
  const [createForm, setCreateForm] = useState<CreateAdminUserPayload>({
    username: '',
    email: '',
    password: '',
    role: 'client',
    full_name: '',
    is_active: true,
  });

  const usersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: async () => {
      const response = await api.listAdminUsers();
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

  const users = usersQuery.data?.users || [];
  const roles = usersQuery.data?.roles || [
    'admin',
    'user',
    'accounting',
    'marketing',
    'agent',
    'client',
  ];
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

  const handleDraftChange = (userId: number, field: keyof UserDraft, value: string | boolean) => {
    setDrafts((prev) => ({
      ...prev,
      [String(userId)]: {
        ...(prev[String(userId)] || {
          email: '',
          full_name: '',
          role: 'client',
          is_active: true,
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

    if (Object.keys(payload).length === 0) {
      return;
    }

    updateUserMutation.mutate({ userId: user.id, payload });
  };

  const registrationEnabled = registrationStatusQuery.data?.enabled ?? true;

  return (
    <div className="space-y-6">
      <div className="premium-panel">
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
              <Users className="h-4 w-4 text-emerald-300" />
              Total users
            </div>
            <p className="mt-3 text-2xl font-semibold text-white">{users.length}</p>
            <p className="mt-1 text-xs text-slate-500">
              All active and archived platform accounts.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
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
        <div className="premium-panel">
          <h3 className="text-lg font-semibold text-white">Platform access</h3>
          <p className="mt-1 text-sm text-slate-400">
            Make registration policy obvious here instead of hiding it in generic configuration.
          </p>

          <div className="mt-5 rounded-2xl border border-slate-700/60 bg-slate-950/50 p-4">
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
                  <Link to="/ib-portal" className="text-cyan-300 hover:text-cyan-200 underline">
                    Open IB Portal
                  </Link>
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
        </div>

        <div className="premium-panel">
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
                        </div>
                        <p className="mt-1 text-sm text-slate-400">
                          {user.username} · {user.email}
                        </p>
                      </div>

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
                    </div>

                    {isSelf && (
                      <p className="mt-3 text-xs text-slate-500">
                        Your own admin role and active state are locked here for safety. Use Profile
                        for your personal details.
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
