import {
    BarChart3,
    Bot,
    BriefcaseBusiness,
    Building2,
    GitBranch,
    History,
    Home,
    KeyRound,
    Library,
    LockKeyhole,
    MailPlus,
    Network,
    Percent,
    PlusCircle,
    ScrollText,
    Server,
    Settings,
    ShieldCheck,
    Sparkles,
    Target,
    UserCircle,
    Users,
    WalletCards,
    Workflow,
    type LucideIcon,
} from 'lucide-react';
import { getCurrentPortalType, type AppPortalType } from '../app/portal';
import {
    BACKOFFICE_ROLES,
    CLIENT_ROLES,
    IB_ROLES,
    roleMatches,
    type WorkspaceRole,
} from '../auth/roles';
import { crmPath, crmSectionFromPath } from '../pages/crm/paths';
import { ibPortalPath, ibPortalSectionFromPath } from '../pages/ib/paths';

export type WorkspaceSection =
  | 'Overview'
  | 'Strategy Lab'
  | 'Backtests'
  | 'Live Trading'
  | 'Intelligence'
  | 'Administration'
  | 'Account'
  | 'IB Portal';

export interface WorkspaceNavItem {
  label: string;
  path: string;
  description: string;
  section: WorkspaceSection;
  keywords: string[];
  exact?: boolean;
  icon: LucideIcon;
  shortcut?: string;
  allowedRoles?: WorkspaceRole[];
}

const clientNavItems: WorkspaceNavItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    description: 'Client portfolio overview, active runs, market pulse, and quick launch.',
    section: 'Overview',
    keywords: ['home', 'overview', 'kpi', 'pulse'],
    exact: true,
    icon: Home,
    shortcut: 'G D',
  },
  {
    label: 'Client Area / Account',
    path: '/client-area',
    description: 'Account progression, partner upgrade requests, and client onboarding state.',
    section: 'Account',
    keywords: ['client', 'account', 'onboarding', 'promotion', 'application'],
    exact: true,
    icon: Building2,
    shortcut: 'G C',
  },
  {
    label: 'Backtest Dashboard',
    path: '/backtests',
    description: 'Decision dashboard for validation quality, risk, and promotion readiness.',
    section: 'Backtests',
    keywords: ['dashboard', 'runs', 'simulation', 'history', 'results', 'report'],
    exact: true,
    icon: BarChart3,
    shortcut: 'G B',
  },
  {
    label: 'New Backtest',
    path: '/backtests/new',
    description: 'Create a new historical validation run from a strategy or configuration.',
    section: 'Backtests',
    keywords: ['new', 'create', 'run', 'launch', 'strategy'],
    exact: true,
    icon: PlusCircle,
    shortcut: 'N B',
  },
  {
    label: 'Backtest Runs',
    path: '/backtests/runs',
    description: 'Archive of historical runs, live progress, and detailed reports.',
    section: 'Backtests',
    keywords: ['runs', 'archive', 'history', 'progress', 'reports'],
    exact: true,
    icon: History,
  },
  {
    label: 'Compare Backtests',
    path: '/backtests/compare',
    description: 'Compare multiple runs and inspect relative performance.',
    section: 'Backtests',
    keywords: ['compare', 'benchmark', 'versus'],
    exact: false,
    icon: Target,
  },
  {
    label: 'Strategies',
    path: '/strategies',
    description: 'Build, validate, and organize reusable trading strategy blueprints.',
    section: 'Strategy Lab',
    keywords: ['library', 'templates', 'alpha', 'builder', 'validation'],
    exact: true,
    icon: Library,
    shortcut: 'G S',
  },
  {
    label: 'Bots',
    path: '/bots',
    description: 'Operate live and paper bot runtimes, health, positions, logs, and controls.',
    section: 'Live Trading',
    keywords: ['instances', 'operator', 'deploy', 'runtime', 'paper', 'live'],
    exact: false,
    icon: Bot,
    shortcut: 'G O',
  },
  {
    label: 'Market Intel',
    path: '/market-intel',
    description: 'Research hub for Codex token intelligence, news, filters, and opportunities.',
    section: 'Intelligence',
    keywords: ['intel', 'codex', 'analysis', 'assets', 'news', 'research', 'opportunities'],
    exact: false,
    icon: Sparkles,
  },
  {
    label: 'Settings',
    path: '/settings',
    description: 'Profile, security, wallet, dYdX keys, and Telegram delivery.',
    section: 'Account',
    keywords: ['settings', 'telegram', 'keys', 'preferences', 'profile', 'security', 'wallet'],
    exact: true,
    icon: Settings,
    shortcut: 'G ,',
  },
];

const backofficeNavItems: WorkspaceNavItem[] = [
  {
    label: 'Admin Hub',
    path: '/dashboard',
    description: 'Platform operating center for access, controls, and cross-portal oversight.',
    section: 'Overview',
    keywords: ['admin', 'hub', 'controls', 'governance'],
    exact: true,
    icon: ShieldCheck,
    shortcut: 'G D',
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'CRM Dashboard',
    path: crmPath('dashboard'),
    description: 'Backoffice workflows for clients, IB approvals, and partner reviews.',
    section: 'Administration',
    keywords: ['crm', 'backoffice', 'approvals', 'partners', 'clients'],
    exact: true,
    icon: BriefcaseBusiness,
    shortcut: 'G R',
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Clients & Users',
    path: crmPath('clients'),
    description: 'Search users, roles, sponsors, status, and CRM context.',
    section: 'Administration',
    keywords: ['users', 'clients', 'roles', 'crm'],
    exact: false,
    icon: Users,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Registration Pipeline',
    path: crmPath('pipeline'),
    description: 'Review and approve IB, sub-IB, and client upgrade requests.',
    section: 'Administration',
    keywords: ['pipeline', 'applications', 'registration'],
    exact: true,
    icon: Workflow,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Client Hierarchy',
    path: crmPath('hierarchy'),
    description: 'Inspect IB, sub-IB, and client relationships.',
    section: 'Administration',
    keywords: ['hierarchy', 'tree', 'relationships'],
    exact: true,
    icon: GitBranch,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Commissions',
    path: crmPath('commissions'),
    description: 'Record and review IB commission and rebate metrics.',
    section: 'Administration',
    keywords: ['commissions', 'rebates', 'finance'],
    exact: true,
    icon: Percent,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Security Events',
    path: crmPath('security'),
    description: 'Review CRM security activity and account interventions.',
    section: 'Administration',
    keywords: ['security', 'events', 'audit'],
    exact: true,
    icon: LockKeyhole,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'IB Oversight',
    path: '/ib-portal/dashboard',
    description: 'Administer IB tokens, tier rates, reports, and network health.',
    section: 'IB Portal',
    keywords: ['ib', 'tokens', 'tier', 'partners'],
    exact: false,
    icon: KeyRound,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Celery Ops',
    path: '/admin/celery',
    description: 'Admin-only Celery task, queue, worker, and failure inspection.',
    section: 'Administration',
    keywords: ['celery', 'tasks', 'workers', 'queues', 'debug'],
    exact: true,
    icon: Server,
    allowedRoles: ['admin', 'super_admin', 'backoffice_admin'],
  },
  {
    label: 'Operator Settings',
    path: '/admin/settings',
    description:
      'Access control, registration policy, integrations, API, Redis, and trading config.',
    section: 'Administration',
    keywords: ['settings', 'access', 'email', 'plunk', 'telegram', 'redis', 'api'],
    exact: false,
    icon: Settings,
    shortcut: 'G ,',
    allowedRoles: BACKOFFICE_ROLES,
  },
];

const ibNavItems: WorkspaceNavItem[] = [
  {
    label: 'IB Dashboard',
    path: ibPortalPath('dashboard'),
    description: 'IB production, commission, applications, and network overview.',
    section: 'Overview',
    keywords: ['ib', 'dashboard', 'overview'],
    exact: true,
    icon: Home,
    shortcut: 'G D',
    allowedRoles: [...IB_ROLES, ...BACKOFFICE_ROLES],
  },
  {
    label: 'Client Tree',
    path: ibPortalPath('network'),
    description: 'Client, sub-IB, and referral relationships.',
    section: 'IB Portal',
    keywords: ['network', 'tree', 'relationships', 'sub ib'],
    exact: true,
    icon: Network,
    allowedRoles: [...IB_ROLES, ...BACKOFFICE_ROLES],
  },
  {
    label: 'Invitations',
    path: ibPortalPath('applications'),
    description: 'Client invitations and partner application flow.',
    section: 'IB Portal',
    keywords: ['applications', 'invitations', 'referrals'],
    exact: true,
    icon: MailPlus,
    allowedRoles: [...IB_ROLES, ...BACKOFFICE_ROLES],
  },
  {
    label: 'Commissions',
    path: ibPortalPath('commissions'),
    description: 'Commission metrics, rebates, and IB-specific reports.',
    section: 'IB Portal',
    keywords: ['commissions', 'reports', 'rebates'],
    exact: true,
    icon: WalletCards,
    allowedRoles: [...IB_ROLES, ...BACKOFFICE_ROLES],
  },
  {
    label: 'Referral Tokens',
    path: ibPortalPath('tokens'),
    description: 'Generate and manage referral links and invitation tokens.',
    section: 'IB Portal',
    keywords: ['tokens', 'referral', 'links'],
    exact: true,
    icon: KeyRound,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Tier Rates',
    path: ibPortalPath('tier-rates'),
    description: 'Configure IB pyramid commission rates.',
    section: 'IB Portal',
    keywords: ['tier', 'rates', 'commission'],
    exact: true,
    icon: ScrollText,
    allowedRoles: BACKOFFICE_ROLES,
  },
  {
    label: 'Profile',
    path: '/profile',
    description: 'Manage your IB profile and contact details.',
    section: 'Account',
    keywords: ['profile', 'identity'],
    exact: true,
    icon: UserCircle,
    allowedRoles: [...IB_ROLES, ...BACKOFFICE_ROLES],
  },
  {
    label: 'Security',
    path: '/security',
    description: 'Manage IB portal MFA and session security.',
    section: 'Account',
    keywords: ['security', 'mfa', '2fa'],
    exact: true,
    icon: LockKeyhole,
    allowedRoles: [...IB_ROLES, ...BACKOFFICE_ROLES],
  },
];

export const workspaceNavItemsByPortal: Record<AppPortalType, WorkspaceNavItem[]> = {
  client: clientNavItems.map((item) => ({
    ...item,
    allowedRoles: item.allowedRoles || CLIENT_ROLES,
  })),
  backoffice: backofficeNavItems,
  ib: ibNavItems,
};

export const getWorkspaceNavItems = (
  portal: AppPortalType = getCurrentPortalType()
): WorkspaceNavItem[] => workspaceNavItemsByPortal[portal];

export const workspaceNavItems = getWorkspaceNavItems();

export const getWorkspaceQuickActions = (
  portal: AppPortalType = getCurrentPortalType()
): WorkspaceNavItem[] => {
  const navItems = getWorkspaceNavItems(portal);
  if (portal === 'client') {
    return [
      {
        label: 'New Strategy',
        path: '/strategies/new',
        description: 'Create a fresh strategy blueprint.',
        section: 'Strategy Lab',
        keywords: ['create', 'new', 'builder', 'strategy'],
        exact: false,
        icon: PlusCircle,
        shortcut: 'N S',
        allowedRoles: CLIENT_ROLES,
      },
      {
        label: 'Run Backtest',
        path: '/backtests/new',
        description: 'Launch a historical validation run from the Backtests desk.',
        section: 'Backtests',
        keywords: ['create', 'run', 'launch', 'backtest'],
        exact: false,
        icon: Target,
        shortcut: 'N B',
        allowedRoles: CLIENT_ROLES,
      },
      ...navItems.filter((item) => item.path === '/bots'),
    ];
  }
  return navItems.slice(0, 3);
};

export const workspaceQuickActions = getWorkspaceQuickActions();

export const workspaceSections: WorkspaceSection[] = [
  'Overview',
  'Strategy Lab',
  'Backtests',
  'Live Trading',
  'Intelligence',
  'Administration',
  'IB Portal',
  'Account',
];

export const filterNavItemsForRole = (
  items: WorkspaceNavItem[],
  role: WorkspaceRole
): WorkspaceNavItem[] => items.filter((item) => roleMatches(role, item.allowedRoles));

export const isNavItemActive = (pathname: string, item: WorkspaceNavItem): boolean =>
  item.exact ? pathname === item.path : pathname.startsWith(item.path);

export const getWorkspaceBreadcrumbs = (
  pathname: string,
  portal: AppPortalType = getCurrentPortalType()
) => {
  const navItems = getWorkspaceNavItems(portal);
  const breadcrumbs = [{ label: 'Home', path: '/dashboard' }];
  const directMatch = navItems.find((item) => isNavItemActive(pathname, item));

  if (directMatch) {
    if (directMatch.path !== '/dashboard') {
      breadcrumbs.push({ label: directMatch.label, path: directMatch.path });
    }
    return breadcrumbs;
  }

  const paths = pathname.split('/').filter(Boolean);
  const crmSection = crmSectionFromPath(pathname);
  const ibSection = ibPortalSectionFromPath(pathname);

  if (paths.includes('backtests') || paths.includes('backtest')) {
    const backtestIndex = paths.findIndex(
      (segment) => segment === 'backtests' || segment === 'backtest'
    );
    const runId = backtestIndex >= 0 ? paths[backtestIndex + 1] : undefined;
    breadcrumbs.push({ label: 'Backtests', path: '/backtests' });
    if (runId && runId !== 'compare') {
      breadcrumbs.push({ label: `Run ${runId}`, path: `/backtest/${runId}` });
    } else if (runId === 'compare') {
      breadcrumbs.push({ label: 'Compare Backtests', path: '/backtests/compare' });
    }
  } else if (crmSection) {
    breadcrumbs.push({ label: 'CRM', path: crmPath('dashboard') });
  } else if (ibSection) {
    breadcrumbs.push({ label: 'IB Portal', path: ibPortalPath('dashboard') });
  }

  return breadcrumbs;
};
