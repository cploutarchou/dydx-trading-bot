import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Loader2, Lock, Search, ShieldOff, UserCheck, UserX, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { type CRMUserRow } from '../../api';
import { PageContainer } from '../../components/PageContainer';
import { crmPath } from './paths';

const ROLE_OPTIONS = ['all', 'client', 'ib', 'sub_ib', 'backoffice', 'admin'] as const;
type RoleFilter = (typeof ROLE_OPTIONS)[number];

const roleBadge: Record<string, string> = {
  admin: 'border-red-500/30 bg-red-500/10 text-red-200',
  backoffice: 'border-violet-500/30 bg-violet-500/10 text-violet-200',
  ib: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  sub_ib: 'border-teal-500/30 bg-teal-500/10 text-teal-200',
  client: 'border-slate-600/50 bg-slate-700/40 text-slate-300',
};

const formatDate = (value?: string) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
};

const UserRow = ({ user, onClick }: { user: CRMUserRow; onClick: () => void }) => (
  <tr
    key={user.id}
    className="cursor-pointer border-t border-slate-800/80 transition hover:bg-slate-800/30"
    onClick={onClick}
  >
    <td className="px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800 text-xs font-semibold uppercase text-slate-300">
          {user.username.slice(0, 2)}
        </div>
        <div>
          <p className="text-sm font-medium text-white">{user.username}</p>
          <p className="text-xs text-slate-500">{user.email}</p>
        </div>
      </div>
    </td>
    <td className="px-4 py-3">
      <span
        className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] ${roleBadge[user.role] ?? roleBadge.client}`}
      >
        {user.role.replace('_', ' ')}
      </span>
    </td>
    <td className="px-4 py-3">
      {user.is_active ? (
        <span className="flex items-center gap-1 text-xs text-emerald-400">
          <UserCheck className="h-3.5 w-3.5" /> Active
        </span>
      ) : (
        <span className="flex items-center gap-1 text-xs text-red-400">
          <UserX className="h-3.5 w-3.5" /> Inactive
        </span>
      )}
    </td>
    <td className="px-4 py-3">
      <span className="text-xs text-slate-400">{user.sponsor_user_id || '—'}</span>
    </td>
    <td className="px-4 py-3 text-right">
      <span className="text-xs text-slate-400">{user.direct_partner_count}</span>
    </td>
    <td className="px-4 py-3 text-right">
      <span className="text-xs text-slate-500">{formatDate(user.created_at)}</span>
    </td>
    <td className="px-4 py-3 text-right">
      <button
        type="button"
        className="flex items-center gap-1 text-xs text-cyan-400 transition hover:text-cyan-200"
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        View <ArrowRight className="h-3.5 w-3.5" />
      </button>
    </td>
  </tr>
);

export const CRMClients = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');

  const usersQuery = useQuery({
    queryKey: ['crm', 'users'],
    queryFn: async () => (await api.getCRMUsersTable()).data,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });

  const allUsers = usersQuery.data?.users ?? [];

  const filtered = useMemo(() => {
    const term = search.toLowerCase().trim();
    return allUsers.filter((u) => {
      if (roleFilter !== 'all' && u.role !== roleFilter) return false;
      if (statusFilter === 'active' && !u.is_active) return false;
      if (statusFilter === 'inactive' && u.is_active) return false;
      if (term && !u.username.toLowerCase().includes(term) && !u.email.toLowerCase().includes(term))
        return false;
      return true;
    });
  }, [allUsers, search, roleFilter, statusFilter]);

  const clear = () => {
    setSearch('');
    setRoleFilter('all');
    setStatusFilter('all');
  };

  const isFiltered = search !== '' || roleFilter !== 'all' || statusFilter !== 'all';

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Client directory</div>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-white">All users & clients</h1>
            <p className="mt-1 text-sm text-slate-400">
              Search by username or email, filter by role and status, then click a row to open the
              full profile.
            </p>
          </div>
          {usersQuery.isFetching && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative min-w-52 flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search username or email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="premium-input pl-9"
          />
        </div>

        {/* Role */}
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as RoleFilter)}
          className="premium-input min-w-36"
        >
          {ROLE_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r === 'all' ? 'All roles' : r.replace('_', ' ')}
            </option>
          ))}
        </select>

        {/* Status */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
          className="premium-input min-w-32"
        >
          <option value="all">All status</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>

        {isFiltered && (
          <button
            type="button"
            onClick={clear}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs text-slate-300 transition hover:text-white"
          >
            <X className="h-3.5 w-3.5" /> Clear
          </button>
        )}

        <span className="ml-auto text-sm text-slate-500">
          {filtered.length} / {allUsers.length} users
        </span>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70">
        {usersQuery.isLoading ? (
          <div className="flex items-center justify-center gap-2 p-12 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading users…
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <ShieldOff className="mx-auto h-8 w-8 text-slate-600" />
            <p className="mt-3 text-sm font-medium text-slate-300">No users found</p>
            <p className="mt-1 text-xs text-slate-500">
              {isFiltered ? 'Try adjusting the search or filter.' : 'No users in the system yet.'}
            </p>
            {isFiltered && (
              <button
                type="button"
                onClick={clear}
                className="mt-4 text-xs text-cyan-400 hover:text-cyan-200"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs text-slate-300">
              <thead className="border-b border-slate-800 bg-slate-950/60">
                <tr>
                  <th className="px-4 py-3 text-left text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    User
                  </th>
                  <th className="px-4 py-3 text-left text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    Role
                  </th>
                  <th className="px-4 py-3 text-left text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    Sponsor
                  </th>
                  <th className="px-4 py-3 text-right text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    Partners
                  </th>
                  <th className="px-4 py-3 text-right text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    Joined
                  </th>
                  <th className="px-4 py-3 text-right text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    <Lock className="ml-auto h-3 w-3" />
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    onClick={() => navigate(`${crmPath('clients')}/${user.id}`)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageContainer>
  );
};
