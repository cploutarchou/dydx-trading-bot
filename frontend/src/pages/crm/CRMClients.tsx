import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Loader2, ShieldOff, UserCheck, UserX, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { type CRMUserRow } from '../../api';
import { PageContainer } from '../../components/PageContainer';
import TerminalDataGrid, { type TerminalColumn } from '../../components/TerminalDataGrid';
import {
  PlatformPageHeader,
  StatusBadge,
  toneForStatus,
} from '../../components/ui/PlatformUI';
import { ibPortalPath } from '../ib/paths';
import { crmPath } from './paths';

const ROLE_OPTIONS = ['all', 'client', 'ib', 'sub_ib', 'backoffice', 'admin'] as const;
type RoleFilter = (typeof ROLE_OPTIONS)[number];

const formatDate = (value?: string) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
};

export const CRMClients = () => {
  const navigate = useNavigate();
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [ibOnly, setIbOnly] = useState(false);

  const usersQuery = useQuery({
    queryKey: ['crm', 'users'],
    queryFn: async () => (await api.getCRMUsersTable()).data,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });

  const allUsers = usersQuery.data?.users ?? [];

  const filtered = useMemo(() => {
    return allUsers.filter((u) => {
      if (roleFilter !== 'all' && u.role !== roleFilter) return false;
      if (ibOnly && u.role !== 'ib' && u.role !== 'sub_ib') return false;
      if (statusFilter === 'active' && !u.is_active) return false;
      if (statusFilter === 'inactive' && u.is_active) return false;
      return true;
    });
  }, [allUsers, roleFilter, statusFilter, ibOnly]);

  const clear = () => {
    setRoleFilter('all');
    setStatusFilter('all');
    setIbOnly(false);
  };

  const isFiltered = roleFilter !== 'all' || statusFilter !== 'all' || ibOnly;

  const columns = useMemo<TerminalColumn<CRMUserRow>[]>(
    () => [
      {
        key: 'user',
        label: 'User',
        sortable: true,
        sortValue: (user) => user.username,
        render: (user) => (
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-800 text-xs font-semibold uppercase text-slate-300">
              {user.username.slice(0, 2)}
            </div>
            <div>
              <button
                type="button"
                onClick={() => navigate(`${crmPath('clients')}/${user.id}`)}
                className="text-left text-sm font-medium text-white transition hover:text-cyan-200"
              >
                {user.username}
              </button>
              <p className="text-xs text-slate-500">{user.email}</p>
            </div>
          </div>
        ),
      },
      {
        key: 'role',
        label: 'Role',
        sortable: true,
        sortValue: (user) => user.role,
        render: (user) => (
          <StatusBadge tone={toneForStatus(user.role)}>{user.role.replace('_', ' ')}</StatusBadge>
        ),
      },
      {
        key: 'status',
        label: 'Status',
        sortable: true,
        sortValue: (user) => (user.is_active ? 1 : 0),
        render: (user) =>
          user.is_active ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <UserCheck className="h-3.5 w-3.5" /> Active
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-red-400">
              <UserX className="h-3.5 w-3.5" /> Inactive
            </span>
          ),
      },
      {
        key: 'sponsor',
        label: 'Sponsor',
        sortable: true,
        sortValue: (user) => Number(user.sponsor_user_id || 0),
        render: (user) => <span className="text-xs text-slate-400">{user.sponsor_user_id || '—'}</span>,
      },
      {
        key: 'partners',
        label: 'Partners',
        align: 'right',
        sortable: true,
        sortValue: (user) => user.direct_partner_count,
        render: (user) => <span className="text-xs text-slate-300">{user.direct_partner_count}</span>,
      },
      {
        key: 'joined',
        label: 'Joined',
        align: 'right',
        sortable: true,
        sortValue: (user) => Date.parse(user.created_at ?? '') || 0,
        render: (user) => <span className="text-xs text-slate-500">{formatDate(user.created_at)}</span>,
      },
      {
        key: 'actions',
        label: 'Action',
        align: 'right',
        render: (user) => (
          <div className="flex items-center justify-end gap-2">
            {(user.role === 'ib' || user.role === 'sub_ib') && (
              <button
                type="button"
                className="rounded-lg border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-[10px] font-semibold uppercase text-violet-200 transition hover:bg-violet-500/20"
                onClick={() =>
                  navigate(
                    `${ibPortalPath('network')}?focus_user_id=${encodeURIComponent(String(user.id))}`
                  )
                }
              >
                IB Network
              </button>
            )}
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs text-cyan-400 transition hover:text-cyan-200"
              onClick={() => navigate(`${crmPath('clients')}/${user.id}`)}
            >
              View <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        ),
      },
    ],
    [navigate]
  );

  const getSearchText = (user: CRMUserRow) => {
    const fullName = String((user as Record<string, unknown>).full_name || '');
    return [
      user.username,
      user.email,
      String(user.id),
      String(user.sponsor_user_id || ''),
      user.role,
      String(user.relationship_type || ''),
      fullName,
    ].join(' ');
  };

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker="Client directory"
        title="All users and clients"
        description="Search by ID, username, name, email, sponsor ID, or role. Filter by role and status, then jump directly between CRM and IB views."
        icon={UserCheck}
        meta={usersQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin text-slate-400" /> : null}
      />

      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={ibOnly}
            onChange={(e) => setIbOnly(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-900 text-cyan-500"
          />
          IB / Sub-IB only
        </label>

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

      {usersQuery.isLoading ? (
        <div className="flex items-center justify-center gap-2 rounded-lg border border-slate-700/60 bg-slate-900/70 p-12 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading users...
        </div>
      ) : (
        <TerminalDataGrid
          title="Client operating directory"
          subtitle="Search, sort, filter, and open CRM or IB context without leaving the table."
          rows={filtered}
          columns={columns}
          rowKey={(user) => String(user.id)}
          searchPlaceholder="Search by ID, name, email, sponsor, or role"
          getSearchText={getSearchText}
          defaultSortKey="joined"
          defaultPageSize={20}
          filterToken={`${roleFilter}-${statusFilter}-${ibOnly}`}
          metrics={[
            { label: 'Visible', value: filtered.length, tone: 'accent' },
            { label: 'Total', value: allUsers.length },
            { label: 'IB / Sub-IB', value: allUsers.filter((u) => u.role === 'ib' || u.role === 'sub_ib').length, tone: 'positive' },
            { label: 'Inactive', value: allUsers.filter((u) => !u.is_active).length, tone: 'negative' },
          ]}
          emptyState={
            <div>
              <ShieldOff className="mx-auto h-8 w-8 text-slate-600" />
              <p className="mt-3 text-sm font-medium text-slate-300">No users found</p>
              <p className="mt-1 text-xs text-slate-500">
                {isFiltered ? 'Adjust the filters or clear them to widen the directory.' : 'No users are available yet.'}
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
          }
        />
      )}
    </PageContainer>
  );
};
