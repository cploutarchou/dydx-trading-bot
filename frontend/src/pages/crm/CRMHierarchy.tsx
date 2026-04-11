import { useQuery } from '@tanstack/react-query';
import { GitBranch, Loader2 } from 'lucide-react';
import api from '../../api';
import { PageContainer } from '../../components/PageContainer';

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
};

export const CRMHierarchy = () => {
  const usersQuery = useQuery({
    queryKey: ['crm', 'users'],
    queryFn: async () => (await api.getCRMUsersTable()).data,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });

  const hierarchyQuery = useQuery({
    queryKey: ['crm', 'hierarchy'],
    queryFn: async () => (await api.getCRMHierarchyTable()).data,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });

  const users = usersQuery.data?.users ?? [];
  const relationships = hierarchyQuery.data?.relationships ?? [];

  const usernameMap = Object.fromEntries(users.map((u) => [u.id, u.username]));

  const isLoading = usersQuery.isLoading || hierarchyQuery.isLoading;

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Sponsor hierarchy</div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-white">Partner network tree</h1>
            <p className="mt-1 text-sm text-slate-400">
              Persisted sponsor → partner edges. Edges are written automatically when applications
              carrying a sponsor ID are approved.
            </p>
          </div>
          {(hierarchyQuery.isFetching || usersQuery.isFetching) && (
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Total users', value: users.length },
          { label: 'Hierarchy edges', value: relationships.length },
          {
            label: 'IB accounts',
            value: users.filter((u) => u.role === 'ib' || u.role === 'sub_ib').length,
          },
        ].map((s) => (
          <div key={s.label} className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
            <p className="text-xs text-slate-500">{s.label}</p>
            <p className="mt-1 text-2xl font-semibold text-white">
              {isLoading ? <Loader2 className="h-5 w-5 animate-spin text-slate-500" /> : s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Hierarchy table */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold text-white">All hierarchy edges</h2>
        <p className="mt-1 text-xs text-slate-500">
          Each row is a sponsor → partner relationship with its type and last updated time.
        </p>

        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800/80">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 p-10 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin" /> Loading hierarchy…
            </div>
          ) : relationships.length === 0 ? (
            <div className="p-10 text-center">
              <GitBranch className="mx-auto h-8 w-8 text-slate-700" />
              <p className="mt-3 text-sm text-slate-400">No hierarchy edges recorded yet</p>
              <p className="mt-1 text-xs text-slate-600">
                Edges appear after the first application with a sponsor ID is approved.
              </p>
            </div>
          ) : (
            <table className="min-w-full text-xs text-slate-300">
              <thead className="bg-slate-950/60 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 text-left">ID</th>
                  <th className="px-4 py-2.5 text-left">Sponsor</th>
                  <th className="px-4 py-2.5 text-left">Partner</th>
                  <th className="px-4 py-2.5 text-left">Type</th>
                  <th className="px-4 py-2.5 text-left">Active</th>
                  <th className="px-4 py-2.5 text-left">Updated</th>
                </tr>
              </thead>
              <tbody>
                {relationships.map((rel) => (
                  <tr key={rel.id} className="border-t border-slate-800/80">
                    <td className="px-4 py-2.5 text-slate-500">#{rel.id}</td>
                    <td className="px-4 py-2.5">
                      <span className="font-medium text-white">
                        {usernameMap[rel.sponsor_user_id] ?? `#${rel.sponsor_user_id}`}
                      </span>
                      <span className="ml-1 text-slate-500">#{rel.sponsor_user_id}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-medium text-slate-100">
                        {usernameMap[rel.partner_user_id] ?? `#${rel.partner_user_id}`}
                      </span>
                      <span className="ml-1 text-slate-500">#{rel.partner_user_id}</span>
                    </td>
                    <td className="px-4 py-2.5 uppercase tracking-[0.12em] text-slate-400">
                      {rel.relationship_type}
                    </td>
                    <td className="px-4 py-2.5">
                      {rel.is_active ? (
                        <span className="text-emerald-400">Yes</span>
                      ) : (
                        <span className="text-slate-500">No</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">{formatDateTime(rel.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Per-user partner counts */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold text-white">User partner counts</h2>
        <p className="mt-1 text-xs text-slate-500">
          Users with at least one direct partner, sorted by partner count descending.
        </p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800/80">
          <table className="min-w-full text-xs text-slate-300">
            <thead className="bg-slate-950/60 text-[10px] uppercase tracking-[0.14em] text-slate-500">
              <tr>
                <th className="px-4 py-2.5 text-left">User</th>
                <th className="px-4 py-2.5 text-left">Role</th>
                <th className="px-4 py-2.5 text-right">Direct partners</th>
              </tr>
            </thead>
            <tbody>
              {users
                .filter((u) => u.direct_partner_count > 0)
                .sort((a, b) => b.direct_partner_count - a.direct_partner_count)
                .map((u) => (
                  <tr key={u.id} className="border-t border-slate-800/80">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-white">{u.username}</p>
                      <p className="text-slate-500">{u.email}</p>
                    </td>
                    <td className="px-4 py-2.5 uppercase tracking-[0.12em] text-slate-400">
                      {u.role.replace('_', ' ')}
                    </td>
                    <td className="px-4 py-2.5 text-right font-semibold text-white">
                      {u.direct_partner_count}
                    </td>
                  </tr>
                ))}
              {users.filter((u) => u.direct_partner_count > 0).length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                    No users with partners yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </PageContainer>
  );
};
