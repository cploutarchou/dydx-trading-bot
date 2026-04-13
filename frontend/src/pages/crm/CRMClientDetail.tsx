import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  RotateCcw,
  Save,
  Shield,
  ShieldOff,
  UserCheck,
  UserX,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../api';
import { useToastStore } from '../../components/ErrorBoundary';
import { PageContainer } from '../../components/PageContainer';
import { crmPath } from './paths';

const roleBadge: Record<string, string> = {
  admin: 'border-red-500/30 bg-red-500/10 text-red-200',
  backoffice: 'border-violet-500/30 bg-violet-500/10 text-violet-200',
  ib: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  sub_ib: 'border-teal-500/30 bg-teal-500/10 text-teal-200',
  client: 'border-slate-600/50 bg-slate-700/40 text-slate-300',
};

const outcomeTone: Record<string, string> = {
  success: 'text-emerald-400',
  failure: 'text-red-400',
  lockout: 'text-amber-400',
};

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
};

const AVAILABLE_ROLES = ['client', 'ib', 'sub_ib', 'backoffice', 'admin'];

export const CRMClientDetail = () => {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const queryClient = useQueryClient();
  const successToast = useToastStore((s) => s.success);
  const errorToast = useToastStore((s) => s.error);

  const [roleDraft, setRoleDraft] = useState<string | null>(null);
  const [activeDraft, setActiveDraft] = useState<boolean | null>(null);

  const userQuery = useQuery({
    queryKey: ['crm', 'user', userId],
    queryFn: async () => (await api.getAdminUser(userId)).data,
    enabled: !Number.isNaN(userId) && userId > 0,
    staleTime: 10_000,
  });

  const eventsQuery = useQuery({
    queryKey: ['crm', 'security-events'],
    queryFn: async () => (await api.getCRMSecurityEvents(500, 0)).data,
    staleTime: 20_000,
  });

  const user = userQuery.data?.user;

  // Filter events by this user's username when available
  const userEvents = (eventsQuery.data?.events ?? []).filter(
    (e) => user && (e.username === user.username || e.user_id === userId)
  );

  const updateMutation = useMutation({
    mutationFn: async () => {
      const payload: { role?: string; is_active?: boolean } = {};
      if (roleDraft !== null && roleDraft !== user?.role) payload.role = roleDraft;
      if (activeDraft !== null && activeDraft !== user?.is_active) payload.is_active = activeDraft;
      return api.updateAdminUser(userId, payload);
    },
    onSuccess: () => {
      successToast('User updated', 'Profile changes saved successfully.');
      setRoleDraft(null);
      setActiveDraft(null);
      void queryClient.invalidateQueries({ queryKey: ['crm', 'user', userId] });
      void queryClient.invalidateQueries({ queryKey: ['crm', 'users'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: unknown) => {
      errorToast('Update failed', err instanceof Error ? err.message : 'Unknown error');
    },
  });

  const resetMFAMutation = useMutation({
    mutationFn: async () => api.resetAdminUserMFA(userId),
    onSuccess: (response) => {
      const removed = response.data?.credential_removed;
      successToast(
        'MFA reset',
        removed ? 'TOTP credential removed. User must re-enroll.' : 'User had no MFA credential.'
      );
      void queryClient.invalidateQueries({ queryKey: ['crm', 'user', userId] });
      void queryClient.invalidateQueries({ queryKey: ['crm', 'users'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: unknown) => {
      errorToast('MFA reset failed', err instanceof Error ? err.message : 'Unknown error');
    },
  });

  const currentRole = roleDraft ?? user?.role ?? '';
  const currentActive = activeDraft ?? user?.is_active ?? true;
  const isDirty =
    (roleDraft !== null && roleDraft !== user?.role) ||
    (activeDraft !== null && activeDraft !== user?.is_active);

  if (!userId || Number.isNaN(userId)) {
    return (
      <PageContainer size="wide">
        <p className="text-sm text-slate-400">Invalid user ID.</p>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Back */}
      <Link
        to={crmPath('clients')}
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 transition hover:text-slate-200"
      >
        <ArrowLeft className="h-4 w-4" /> Back to client directory
      </Link>

      {userQuery.isLoading ? (
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading profile…
        </div>
      ) : !user ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6">
          <p className="text-sm text-red-300">User not found.</p>
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
          {/* Left column — profile + actions */}
          <div className="space-y-5">
            {/* Profile card */}
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-slate-700 bg-slate-800 text-lg font-bold uppercase text-slate-200">
                  {user.username.slice(0, 2)}
                </div>
                <div className="min-w-0 flex-1">
                  <h1 className="text-lg font-semibold text-white">{user.username}</h1>
                  <p className="text-sm text-slate-400">{user.email}</p>
                  {user.full_name && (
                    <p className="mt-0.5 text-xs text-slate-500">{user.full_name}</p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] ${roleBadge[user.role] ?? roleBadge.client}`}
                    >
                      {user.role.replace('_', ' ')}
                    </span>
                    {user.is_active ? (
                      <span className="flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-300">
                        <UserCheck className="h-3 w-3" /> Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] text-red-300">
                        <UserX className="h-3 w-3" /> Inactive
                      </span>
                    )}
                    {user.mfa_enabled ? (
                      <span className="flex items-center gap-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] text-cyan-300">
                        <Shield className="h-3 w-3" /> MFA on
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 rounded-full border border-slate-600/50 bg-slate-700/40 px-2 py-0.5 text-[10px] text-slate-400">
                        <ShieldOff className="h-3 w-3" /> MFA off
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-2 border-t border-slate-800/80 pt-4 text-xs text-slate-400">
                <p>
                  User ID: <span className="text-slate-200">#{user.id}</span>
                </p>
                <p>
                  Admin privileges:{' '}
                  <span className="text-slate-200">{user.is_admin ? 'Yes' : 'No'}</span>
                </p>
                <p>
                  Password change required:{' '}
                  <span className="text-slate-200">
                    {user.password_change_required ? 'Yes' : 'No'}
                  </span>
                </p>
                <p>
                  Joined: <span className="text-slate-200">{formatDateTime(user.created_at)}</span>
                </p>
              </div>
            </div>

            {/* Edit profile */}
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
              <h2 className="text-sm font-semibold text-white">Edit profile</h2>
              <p className="mt-1 text-xs text-slate-500">
                Change role or activation status. Saves are audit-logged.
              </p>

              <div className="mt-4 space-y-3">
                <div>
                  <label className="mb-1 block text-xs uppercase tracking-[0.14em] text-slate-500">
                    Role
                  </label>
                  <select
                    value={currentRole}
                    onChange={(e) => setRoleDraft(e.target.value)}
                    className="premium-input"
                  >
                    {AVAILABLE_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r.replace('_', ' ')}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs uppercase tracking-[0.14em] text-slate-500">
                    Account status
                  </label>
                  <select
                    value={currentActive ? 'active' : 'inactive'}
                    onChange={(e) => setActiveDraft(e.target.value === 'active')}
                    className="premium-input"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!isDirty || updateMutation.isPending}
                  onClick={() => updateMutation.mutate()}
                  className="flex items-center gap-1.5 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-50"
                >
                  {updateMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                  Save changes
                </button>
                {isDirty && (
                  <button
                    type="button"
                    onClick={() => {
                      setRoleDraft(null);
                      setActiveDraft(null);
                    }}
                    className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-300 transition hover:text-white"
                  >
                    <XCircle className="h-3.5 w-3.5" /> Discard
                  </button>
                )}
              </div>
            </div>

            {/* MFA management */}
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
              <h2 className="text-sm font-semibold text-white">MFA management</h2>
              <p className="mt-1 text-xs text-slate-500">
                Clearing MFA forces re-enrollment on next privileged login.
              </p>
              <div className="mt-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  {user.mfa_enabled ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      <span className="text-sm text-emerald-300">TOTP enrolled</span>
                    </>
                  ) : (
                    <>
                      <ShieldOff className="h-4 w-4 text-slate-500" />
                      <span className="text-sm text-slate-400">Not enrolled</span>
                    </>
                  )}
                </div>
                <button
                  type="button"
                  disabled={resetMFAMutation.isPending}
                  onClick={() => {
                    const confirmed = window.confirm(
                      `Reset MFA for ${user.username}? This removes the current TOTP credential and forces re-enrollment.`
                    );
                    if (confirmed) {
                      resetMFAMutation.mutate();
                    }
                  }}
                  className="flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200 transition hover:bg-amber-500/20 disabled:opacity-50"
                >
                  {resetMFAMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3.5 w-3.5" />
                  )}
                  Reset MFA
                </button>
              </div>
            </div>
          </div>

          {/* Right column — security events */}
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-white">Recent security events</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Authentication outcomes for this user, most recent first.
                </p>
              </div>
              {eventsQuery.isFetching && (
                <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
              )}
            </div>

            <div className="mt-4 max-h-[34rem] overflow-auto rounded-xl border border-slate-800/80">
              {userEvents.length === 0 ? (
                <div className="p-8 text-center">
                  <p className="text-sm text-slate-400">No events found for this user.</p>
                </div>
              ) : (
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-950/70 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    <tr>
                      <th className="px-3 py-2 text-left">When</th>
                      <th className="px-3 py-2 text-left">Outcome</th>
                      <th className="px-3 py-2 text-left">Reason</th>
                      <th className="px-3 py-2 text-left">IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {userEvents.map((event) => (
                      <tr key={event.id} className="border-t border-slate-800/80">
                        <td className="px-3 py-2 text-slate-400">
                          {formatDateTime(String(event.created_at ?? ''))}
                        </td>
                        <td
                          className={`px-3 py-2 font-medium ${outcomeTone[String(event.outcome)] ?? 'text-slate-300'}`}
                        >
                          {String(event.outcome ?? '—')}
                        </td>
                        <td className="px-3 py-2 text-slate-400">{String(event.reason ?? '—')}</td>
                        <td className="px-3 py-2 text-slate-500">
                          {String(event.ip_address ?? '—')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
};
