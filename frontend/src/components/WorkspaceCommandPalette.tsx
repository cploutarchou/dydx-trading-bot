import { Clock3, Command, CornerDownLeft, Search } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getUserWorkspaceRole } from '../auth/roles';
import {
    filterNavItemsForRole,
    type WorkspaceNavItem,
    workspaceNavItems,
    workspaceQuickActions,
} from '../navigation/workspaceNav';
import { useAuthStore } from '../store/auth';

const RECENT_ROUTES_STORAGE_KEY = 'workspace_recent_routes';

interface WorkspaceCommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  recentPaths: string[];
}

const uniquePaths = (paths: string[]): string[] => Array.from(new Set(paths)).slice(0, 6);

export const persistRecentPath = (path: string) => {
  if (!path.startsWith('/')) return;
  const current = getRecentPaths();
  const next = uniquePaths([path, ...current]);
  window.localStorage.setItem(RECENT_ROUTES_STORAGE_KEY, JSON.stringify(next));
};

export const getRecentPaths = (): string[] => {
  try {
    const raw = window.localStorage.getItem(RECENT_ROUTES_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((value): value is string => typeof value === 'string')
      : [];
  } catch {
    return [];
  }
};

const buildSearchText = (item: WorkspaceNavItem) =>
  [item.label, item.description, ...item.keywords, item.section].join(' ').toLowerCase();

export const WorkspaceCommandPalette: React.FC<WorkspaceCommandPaletteProps> = ({
  isOpen,
  onClose,
  recentPaths,
}) => {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);
  const role = getUserWorkspaceRole(user);
  const visibleNavItems = useMemo(() => filterNavItemsForRole(workspaceNavItems, role), [role]);
  const visibleQuickActions = useMemo(
    () => filterNavItemsForRole(workspaceQuickActions, role),
    [role]
  );

  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      return;
    }
    const frameId = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const recentItems = useMemo(
    () =>
      recentPaths
        .map((path) => visibleNavItems.find((item) => item.path === path))
        .filter((item): item is WorkspaceNavItem => Boolean(item)),
    [recentPaths, visibleNavItems]
  );

  const results = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const source = uniquePaths([
      ...visibleQuickActions.map((item) => item.path),
      ...visibleNavItems.map((item) => item.path),
    ])
      .map((path) =>
        [...visibleQuickActions, ...visibleNavItems].find((item) => item.path === path)
      )
      .filter((item): item is WorkspaceNavItem => Boolean(item));

    if (!normalizedQuery) {
      const starter = [...visibleQuickActions];
      const recents = recentItems.filter(
        (item) => !starter.some((candidate) => candidate.path === item.path)
      );
      return [...starter, ...recents].slice(0, 8);
    }

    return source.filter((item) => buildSearchText(item).includes(normalizedQuery)).slice(0, 10);
  }, [query, recentItems, visibleNavItems, visibleQuickActions]);

  if (!isOpen) return null;

  const handleSelect = (item: WorkspaceNavItem) => {
    persistRecentPath(item.path);
    navigate(item.path);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-90 flex items-start justify-center bg-slate-950/75 px-2 pt-3 sm:px-4 sm:pt-[12vh] backdrop-blur-sm">
      <button type="button" className="absolute inset-0 cursor-default" onClick={onClose} />
      <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl sm:rounded-[28px] border border-slate-800 bg-[linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] shadow-[0_24px_80px_rgba(2,6,23,0.55)]">
        <div className="border-b border-slate-800 p-3 sm:p-4">
          <div className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/75 px-4 py-3">
            <Search className="h-4 w-4 text-slate-500" />
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Jump to any cockpit, runtime, or research surface..."
              className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
            />
            <span className="hidden sm:inline-flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
              <Command className="h-3 w-3" />K
            </span>
          </div>
        </div>

        <div className="max-h-[calc(100dvh-9rem)] sm:max-h-[60vh] overflow-y-auto p-2 sm:p-3">
          {results.length > 0 ? (
            <div className="space-y-2">
              {results.map((item, index) => {
                const Icon = item.icon;
                const isRecent = recentItems.some((recent) => recent.path === item.path);
                return (
                  <button
                    key={`${item.path}-${index}`}
                    type="button"
                    onClick={() => handleSelect(item)}
                    className="flex w-full items-start gap-3 rounded-2xl border border-slate-800 bg-slate-950/65 px-4 py-3 text-left transition hover:border-cyan-500/30 hover:bg-slate-900"
                  >
                    <div className="mt-0.5 rounded-xl border border-slate-800 bg-slate-900 p-2 text-cyan-200">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-slate-100">{item.label}</p>
                        <span className="rounded-full border border-slate-800 bg-slate-900 px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                          {item.section}
                        </span>
                        {isRecent && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-slate-800 bg-slate-900 px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                            <Clock3 className="h-3 w-3" />
                            Recent
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-slate-400">{item.description}</p>
                    </div>
                    <div className="hidden sm:flex flex-col items-end gap-2">
                      {item.shortcut && (
                        <span className="rounded-lg border border-slate-800 bg-slate-900 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                          {item.shortcut}
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                        Open
                        <CornerDownLeft className="h-3 w-3" />
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-800 px-4 py-10 text-center text-sm text-slate-500">
              No matching workspace found for “{query}”.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WorkspaceCommandPalette;
