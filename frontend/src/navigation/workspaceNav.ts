import {
  BarChart3,
  Bot,
  BriefcaseBusiness,
  Building2,
  GitBranch,
  Home,
  KeyRound,
  Library,
  LockKeyhole,
  MailPlus,
  Network,
  Newspaper,
  Percent,
  PlayCircle,
  PlusCircle,
  ScrollText,
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
    label: 'Client Area',
    path: '/client-area',
    description: 'Onboarding, account progression, and partner upgrade requests.',
    section: 'Overview',
    keywords: ['client', 'account', 'onboarding', 'promotion'],
    exact: true,
    icon: Building2,
    shortcut: 'G C',
  },
  {
    label: 'Backtests',
    path: '/backtests',
    description: 'Explore client-visible backtest runs, rankings, and strategy intelligence.',
    section: 'Strategy Lab',
    keywords: ['runs', 'simulation', 'history', 'results'],
    exact: true,
    icon: Target,
    shortcut: 'G B',
  },
  {
    label: 'Compare Backtests',
    path: '/backtests/compare',
    description: 'Compare multiple runs and inspect relative performance.',
    section: 'Strategy Lab',
    keywords: ['compare', 'benchmark', 'versus'],
    exact: false,
    icon: BarChart3,
  },
  {
    label: 'Strategies',
    path: '/strategies',
    description: 'Browse and organize reusable trading strategies.',
    section: 'Strategy Lab',
    keywords: ['library', 'templates', 'alpha'],
    exact: true,
    icon: Library,
    shortcut: 'G S',
  },
  {
    label: 'Strategy Runtime',
    path: '/strategies/manage',
    description: 'Monitor client strategy runtime state and execution health.',
    section: 'Live Trading',
    keywords: ['runtime', 'signals', 'live', 'manage'],
    exact: false,
    icon: PlayCircle,
  },
  {
    label: 'Bot Manager',
    path: '/bots',
    description: 'Operate client-authorized bot instances and control flows.',
    section: 'Live Trading',
    keywords: ['instances', 'operator', 'deploy'],
    exact: false,
    icon: Bot,
    shortcut: 'G O',
  },
  {
    label: 'Market Intel',
    path: '/codex',
    description: 'AI-assisted asset intelligence and research context.',
    section: 'Intelligence',
    keywords: ['intel', 'codex', 'analysis', 'assets'],
    exact: true,
    icon: Sparkles,
  },
  {
    label: 'Market News',
    path: '/news',
    description: 'News flow, narratives, and market context.',
    section: 'Intelligence',
    keywords: ['news', 'headlines', 'coindesk'],
    exact: true,
    icon: Newspaper,
  },
  {
    label: 'Profile',
    path: '/profile',
    description: 'Manage your client profile and contact details.',
    section: 'Account',
    keywords: ['profile', 'account', 'identity'],
    exact: true,
    icon: UserCircle,
  },
  {
    label: 'Security',
    path: '/security',
    description: 'Manage 2FA and client session security.',
    section: 'Account',
    keywords: ['security', '2fa', 'mfa', 'sessions'],
    exact: true,
    icon: LockKeyhole,
  },
  {
    label: 'Wallet & API Keys',
    path: '/wallet',
    description: 'Manage client-facing wallet and dYdX API key access.',
    section: 'Account',
    keywords: ['wallet', 'keys', 'api', 'dydx'],
    exact: true,
    icon: WalletCards,
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
    label: 'Operator Settings',
    path: '/settings',
    description: 'Access control, registration policy, integrations, API, Redis, and trading config.',
    section: 'Administration',
    keywords: ['settings', 'access', 'mailgun', 'telegram', 'redis', 'api'],
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
  client: clientNavItems.map((item) => ({ ...item, allowedRoles: CLIENT_ROLES })),
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
      ...navItems.filter((item) => ['/backtests', '/bots'].includes(item.path)),
    ];
  }
  return navItems.slice(0, 3);
};

export const workspaceQuickActions = getWorkspaceQuickActions();

export const workspaceSections: WorkspaceSection[] = [
  'Overview',
  'Strategy Lab',
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
