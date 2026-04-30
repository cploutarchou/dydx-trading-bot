import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronRight, Filter, Loader2, Search, Users } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import api, { type IBPyramidNode } from '../../api';
import { BACKOFFICE_ROLES, getUserWorkspaceRole, roleMatches } from '../../auth/roles';
import { PageContainer } from '../../components/PageContainer';
import { useAuthStore } from '../../store/auth';
import { crmPath } from '../crm/paths';

const TIER_BADGE_COLORS = [
  'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  'border-violet-500/30 bg-violet-500/10 text-violet-200',
  'border-amber-500/30 bg-amber-500/10 text-amber-200',
  'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  'border-rose-500/30 bg-rose-500/10 text-rose-200',
];

const tierColor = (tier: number) =>
  TIER_BADGE_COLORS[Math.max(0, tier - 1) % TIER_BADGE_COLORS.length];

interface FlatRow {
  node: IBPyramidNode;
  depth: number;
  isLast: boolean;
  parentDepths: boolean[];
}

const PyramidRow = ({
  row,
  expanded,
  onToggle,
  onOpenCRM,
  canOpenCRM,
}: {
  row: FlatRow;
  expanded: boolean;
  onToggle: () => void;
  onOpenCRM: () => void;
  canOpenCRM: boolean;
}) => {
  const { node, depth, parentDepths } = row;
  const hasChildren = node.children.length > 0;

  return (
    <div
      className={`flex items-center border-t border-slate-800/60 py-2 px-3 text-sm transition hover:bg-slate-800/20 ${
        !node.is_active ? 'opacity-50' : ''
      }`}
    >
      {Array.from({ length: depth }).map((_, i) => (
        <span key={i} className="shrink-0 font-mono text-slate-600" style={{ width: '1.25rem' }}>
          {i === depth - 1 ? '\u2514' : parentDepths[i] ? '\u2502' : '\u00a0'}
        </span>
      ))}

      {hasChildren ? (
        <button
          type="button"
          onClick={onToggle}
          className="mr-1 shrink-0 rounded p-0.5 text-slate-400 transition hover:text-slate-200"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 transition-transform ${expanded ? 'rotate-90' : ''}`}
          />
        </button>
      ) : (
        <span className="mr-1 inline-block w-5 shrink-0" />
      )}

      {node.tier_level > 0 ? (
        <span
          className={`mr-2 shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${tierColor(node.tier_level)}`}
        >
          T{node.tier_level}
        </span>
      ) : (
        <span className="mr-2 shrink-0 rounded-full border border-slate-500/30 bg-slate-800/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300">
          ROOT
        </span>
      )}

      <span className="font-mono text-slate-100">#{node.user_id}</span>

      {node.relationship_type !== 'root' && (
        <span className="ml-2 text-xs uppercase tracking-[0.12em] text-slate-500">
          {node.relationship_type}
        </span>
      )}

      {hasChildren && (
        <span className="ml-auto text-xs text-slate-500">
          <Users className="mr-0.5 inline h-3 w-3" />
          {node.children.length}
        </span>
      )}

      <span
        className={`ml-2 shrink-0 rounded-full px-1.5 py-0.5 text-[9px] uppercase tracking-[0.1em] ${
          node.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700/40 text-slate-500'
        }`}
      >
        {node.is_active ? 'active' : 'off'}
      </span>

      {canOpenCRM && (
        <button
          type="button"
          onClick={onOpenCRM}
          className="ml-2 rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-cyan-200 transition hover:bg-cyan-500/20"
        >
          CRM
        </button>
      )}
    </div>
  );
};

export const IBNetwork = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const canOpenCRM = roleMatches(getUserWorkspaceRole(user), BACKOFFICE_ROLES);

  const treeQuery = useQuery({
    queryKey: ['portal', 'hierarchy', 'tree'],
    queryFn: async () => (await api.getPortalHierarchyTree()).data,
    staleTime: 15_000,
    refetchInterval: 60_000,
  });

  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [relationshipFilter, setRelationshipFilter] = useState<'all' | 'root' | 'ib' | 'sub_ib'>(
    'all'
  );

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const focusUserId = params.get('focus_user_id');
    if (focusUserId && /^\d+$/.test(focusUserId)) {
      setSearchTerm(focusUserId);
    }
  }, [location.search]);

  const toggleNode = (userId: number) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const tree = treeQuery.data;
  const roots = tree?.roots ?? [];

  const flattenWithCollapse = (
    nodes: IBPyramidNode[],
    depth: number,
    parentDepths: boolean[],
    out: FlatRow[]
  ) => {
    nodes.forEach((node, idx) => {
      const isLast = idx === nodes.length - 1;
      out.push({ node, depth, isLast, parentDepths: [...parentDepths] });
      if (node.children.length > 0 && !collapsed.has(node.user_id)) {
        flattenWithCollapse(node.children, depth + 1, [...parentDepths, !isLast], out);
      }
    });
  };

  const collectCollapsible = (nodes: IBPyramidNode[], acc: Set<number>) => {
    nodes.forEach((n) => {
      if (n.children.length) {
        acc.add(n.user_id);
        collectCollapsible(n.children, acc);
      }
    });
  };

  const rows: FlatRow[] = [];
  flattenWithCollapse(roots, 0, [], rows);

  const filteredRows = rows.filter((row) => {
    const node = row.node;
    if (statusFilter === 'active' && !node.is_active) return false;
    if (statusFilter === 'inactive' && node.is_active) return false;

    if (relationshipFilter !== 'all') {
      if (relationshipFilter === 'root' && node.relationship_type !== 'root') return false;
      if (relationshipFilter === 'ib' && node.relationship_type !== 'ib') return false;
      if (relationshipFilter === 'sub_ib' && node.relationship_type !== 'sub_ib') return false;
    }

    const term = searchTerm.trim().toLowerCase();
    if (term.length > 0) {
      const candidate = [
        String(node.user_id),
        String(node.sponsor_user_id || ''),
        String(node.tier_level),
        String(node.relationship_type || ''),
      ]
        .join(' ')
        .toLowerCase();
      if (!candidate.includes(term)) return false;
    }

    return true;
  });

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">My Network</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">IB pyramid network</h1>
        <p className="mt-2 text-sm text-slate-400">
          Unlimited-depth partner hierarchy. Direct referrals are Tier 1, their referrals are Tier
          2, and so on. Click a node with children to expand or collapse its subtree.
        </p>
      </div>

      {tree && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Total partners</p>
            <p className="mt-2 text-2xl font-semibold text-white">{tree.total_nodes}</p>
          </div>
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Max depth</p>
            <p className="mt-2 text-2xl font-semibold text-white">
              {tree.max_depth}
              <span className="ml-1 text-sm font-normal text-slate-400">tiers</span>
            </p>
          </div>
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Root sponsors</p>
            <p className="mt-2 text-2xl font-semibold text-white">{roots.length}</p>
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="relative min-w-60 flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by user ID, sponsor ID, tier, relationship..."
              className="premium-input pl-9"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
            className="premium-input min-w-32"
          >
            <option value="all">All status</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>

          <select
            value={relationshipFilter}
            onChange={(e) =>
              setRelationshipFilter(e.target.value as 'all' | 'root' | 'ib' | 'sub_ib')
            }
            className="premium-input min-w-36"
          >
            <option value="all">All relationships</option>
            <option value="root">Roots</option>
            <option value="ib">IB</option>
            <option value="sub_ib">Sub-IB</option>
          </select>

          <span className="ml-auto inline-flex items-center gap-1 text-xs text-slate-400">
            <Filter className="h-3.5 w-3.5" /> {filteredRows.length} / {rows.length}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Partner tree</h2>
          {rows.length > 0 && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setCollapsed(new Set())}
                className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs text-slate-300 transition hover:text-white"
              >
                Expand all
              </button>
              <button
                type="button"
                onClick={() => {
                  const allIds = new Set<number>();
                  collectCollapsible(roots, allIds);
                  setCollapsed(allIds);
                }}
                className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs text-slate-300 transition hover:text-white"
              >
                Collapse all
              </button>
            </div>
          )}
        </div>

        {treeQuery.isLoading ? (
          <div className="mt-4 flex items-center gap-2 text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading pyramid...
          </div>
        ) : filteredRows.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-700/60 bg-slate-950/40 p-10 text-center">
            <Users className="mx-auto h-8 w-8 text-slate-600" />
            <p className="mt-3 text-sm font-medium text-slate-300">No matching partners</p>
            <p className="mt-1 text-xs text-slate-500">Try clearing or broadening your filters.</p>
          </div>
        ) : (
          <div className="mt-4 overflow-auto rounded-xl border border-slate-700/60">
            {filteredRows.map((row) => (
              <PyramidRow
                key={`${row.node.user_id}-${row.depth}`}
                row={row}
                expanded={!collapsed.has(row.node.user_id)}
                onToggle={() => toggleNode(row.node.user_id)}
                canOpenCRM={canOpenCRM}
                onOpenCRM={() => navigate(`${crmPath('clients')}/${row.node.user_id}`)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <h2 className="text-base font-semibold text-white">Tier legend</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5].map((t) => (
            <span
              key={t}
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${tierColor(t)}`}
            >
              Tier {t}
              {t === 1 ? ' (direct)' : ''}
            </span>
          ))}
          <span className="rounded-full border border-slate-500/30 bg-slate-800/40 px-3 py-1 text-xs font-semibold text-slate-300">
            Root sponsor
          </span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Colors cycle for deeper tiers. Manage commission rates per tier in the Tier Rates tab.
        </p>
      </div>
    </PageContainer>
  );
};
