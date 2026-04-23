import type { LucideIcon } from 'lucide-react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  Info,
  Loader2,
  XCircle,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

type Tone = 'default' | 'accent' | 'success' | 'warning' | 'danger' | 'muted' | 'violet';

const toneText: Record<Tone, string> = {
  default: 'text-slate-100',
  accent: 'text-cyan-200',
  success: 'text-emerald-200',
  warning: 'text-amber-200',
  danger: 'text-rose-200',
  muted: 'text-slate-300',
  violet: 'text-violet-200',
};

const toneSurface: Record<Tone, string> = {
  default: 'border-slate-700/60 bg-slate-900/70',
  accent: 'border-cyan-500/30 bg-cyan-500/10',
  success: 'border-emerald-500/30 bg-emerald-500/10',
  warning: 'border-amber-500/30 bg-amber-500/10',
  danger: 'border-rose-500/30 bg-rose-500/10',
  muted: 'border-slate-700/60 bg-slate-950/55',
  violet: 'border-violet-500/30 bg-violet-500/10',
};

const toneIcon: Record<Tone, string> = {
  default: 'text-slate-300 bg-slate-800/70 border-slate-700/70',
  accent: 'text-cyan-200 bg-cyan-500/10 border-cyan-500/25',
  success: 'text-emerald-200 bg-emerald-500/10 border-emerald-500/25',
  warning: 'text-amber-200 bg-amber-500/10 border-amber-500/25',
  danger: 'text-rose-200 bg-rose-500/10 border-rose-500/25',
  muted: 'text-slate-400 bg-slate-950/70 border-slate-700/70',
  violet: 'text-violet-200 bg-violet-500/10 border-violet-500/25',
};

interface PageHeaderAction {
  label: string;
  to?: string;
  href?: string;
  onClick?: () => void;
  icon?: LucideIcon;
  variant?: 'primary' | 'secondary';
}

interface PlatformPageHeaderProps {
  kicker: string;
  title: string;
  description: string;
  icon?: LucideIcon;
  actions?: PageHeaderAction[];
  meta?: ReactNode;
}

export const PlatformPageHeader = ({
  kicker,
  title,
  description,
  icon: Icon,
  actions = [],
  meta,
}: PlatformPageHeaderProps) => {
  return (
    <section className="platform-hero p-5 sm:p-6">
      <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-4xl">
          <div className="flex flex-wrap items-center gap-2">
            <span className="surface-label">
              {Icon && <Icon className="h-3.5 w-3.5" />}
              {kicker}
            </span>
            {meta}
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-white sm:text-3xl">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400 sm:text-base">
            {description}
          </p>
        </div>

        {actions.length > 0 && (
          <div className="flex flex-col gap-2 sm:flex-row lg:justify-end">
            {actions.map((action) => {
              const ActionIcon = action.icon ?? ArrowRight;
              const className =
                action.variant === 'secondary'
                  ? 'platform-button platform-button-secondary'
                  : 'platform-button platform-button-primary';
              const content = (
                <>
                  {action.label}
                  <ActionIcon className="h-4 w-4" />
                </>
              );

              if (action.to) {
                return (
                  <Link key={action.label} to={action.to} className={className}>
                    {content}
                  </Link>
                );
              }
              if (action.href) {
                return (
                  <a key={action.label} href={action.href} className={className}>
                    {content}
                  </a>
                );
              }
              return (
                <button
                  key={action.label}
                  type="button"
                  onClick={action.onClick}
                  className={className}
                >
                  {content}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
};

interface PlatformPanelProps {
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
  action?: ReactNode;
}

export const PlatformPanel = ({
  children,
  className = '',
  title,
  description,
  action,
}: PlatformPanelProps) => (
  <section className={`platform-panel ${className}`.trim()}>
    {(title || description || action) && (
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          {title && <h2 className="text-lg font-semibold text-white">{title}</h2>}
          {description && <p className="mt-1 text-sm leading-6 text-slate-400">{description}</p>}
        </div>
        {action}
      </div>
    )}
    {children}
  </section>
);

interface PlatformStatCardProps {
  label: string;
  value: ReactNode;
  icon?: LucideIcon;
  tone?: Tone;
  detail?: ReactNode;
  loading?: boolean;
}

export const PlatformStatCard = ({
  label,
  value,
  icon: Icon,
  tone = 'default',
  detail,
  loading = false,
}: PlatformStatCardProps) => (
  <div className={`platform-stat-card ${toneSurface[tone]}`}>
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-semibold uppercase text-slate-500">{label}</p>
        <div className={`mt-2 text-2xl font-semibold ${toneText[tone]}`}>
          {loading ? <Loader2 className="h-5 w-5 animate-spin text-slate-500" /> : value}
        </div>
      </div>
      {Icon && (
        <span className={`rounded-lg border p-2 ${toneIcon[tone]}`}>
          <Icon className="h-4 w-4" />
        </span>
      )}
    </div>
    {detail && <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>}
  </div>
);

interface StatusBadgeProps {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}

export const StatusBadge = ({ children, tone = 'muted', className = '' }: StatusBadgeProps) => (
  <span
    className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold uppercase ${toneSurface[tone]} ${toneText[tone]} ${className}`.trim()}
  >
    {children}
  </span>
);

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}

export const EmptyState = ({ icon: Icon, title, description, action }: EmptyStateProps) => (
  <div className="rounded-lg border border-dashed border-slate-700/60 bg-slate-950/35 p-8 text-center">
    {Icon && (
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg border border-slate-800 bg-slate-950 text-slate-500">
        <Icon className="h-5 w-5" />
      </div>
    )}
    <p className="mt-3 text-sm font-semibold text-slate-200">{title}</p>
    <p className="mx-auto mt-1 max-w-lg text-xs leading-5 text-slate-500">{description}</p>
    {action && <div className="mt-4">{action}</div>}
  </div>
);

interface InlineNoticeProps {
  title: string;
  description?: string;
  tone?: Tone;
  action?: ReactNode;
  className?: string;
}

const noticeIconMap: Record<Tone, LucideIcon> = {
  default: Info,
  accent: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  muted: Info,
  violet: Info,
};

export const InlineNotice = ({
  title,
  description,
  tone = 'muted',
  action,
  className = '',
}: InlineNoticeProps) => {
  const Icon = noticeIconMap[tone];

  return (
    <div
      className={`flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-start sm:justify-between ${toneSurface[tone]} ${className}`.trim()}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 rounded-lg border p-2 ${toneIcon[tone]}`}>
          <Icon className="h-4 w-4" />
        </span>
        <div>
          <p className={`text-sm font-semibold ${toneText[tone]}`}>{title}</p>
          {description && <p className="mt-1 text-sm leading-6 text-slate-400">{description}</p>}
        </div>
      </div>
      {action && <div className="sm:pl-4">{action}</div>}
    </div>
  );
};

interface ActionDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  confirmTone?: Extract<Tone, 'accent' | 'warning' | 'danger' | 'success'>;
  loading?: boolean;
  details?: ReactNode;
}

export const ActionDialog = ({
  open,
  title,
  description,
  confirmLabel,
  onConfirm,
  onClose,
  confirmTone = 'accent',
  loading = false,
  details,
}: ActionDialogProps) => {
  if (!open) return null;

  const confirmClassMap: Record<ActionDialogProps['confirmTone'], string> = {
    accent:
      'border-cyan-500/30 bg-cyan-500/15 text-cyan-50 hover:border-cyan-400/50 hover:bg-cyan-500/20',
    warning:
      'border-amber-500/30 bg-amber-500/15 text-amber-50 hover:border-amber-400/50 hover:bg-amber-500/20',
    danger:
      'border-rose-500/30 bg-rose-500/15 text-rose-50 hover:border-rose-400/50 hover:bg-rose-500/20',
    success:
      'border-emerald-500/30 bg-emerald-500/15 text-emerald-50 hover:border-emerald-400/50 hover:bg-emerald-500/20',
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center px-4 py-6">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-lg border border-slate-700/70 bg-slate-950/95 p-6 shadow-[0_40px_120px_rgba(2,6,23,0.7)]">
        <div className="flex items-start gap-3">
          <span className={`rounded-lg border p-2 ${toneIcon[confirmTone]}`}>
            <AlertTriangle className="h-4 w-4" />
          </span>
          <div>
            <p className="text-lg font-semibold text-white">{title}</p>
            <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
          </div>
        </div>

        {details && (
          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/80 p-4 text-sm text-slate-300">
            {details}
          </div>
        )}

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-700/70 bg-slate-900/70 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-900"
          >
            Keep as is
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${confirmClassMap[confirmTone]}`}
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export interface PortalTab {
  path: string;
  label: string;
  icon: LucideIcon;
  matchPrefix?: string;
}

interface PortalSubnavProps {
  tabs: readonly PortalTab[];
  label: string;
  externalHref?: string;
  externalLabel?: string;
}

export const PortalSubnav = ({
  tabs,
  label,
  externalHref,
  externalLabel = 'Open in subdomain',
}: PortalSubnavProps) => {
  const { pathname } = useLocation();

  return (
    <div className="portal-subnav sticky top-0 z-20">
      <div className="flex items-center gap-1 overflow-x-auto px-4 py-2 scrollbar-none">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const matchPath = tab.matchPrefix ?? tab.path;
          const isActive = pathname.startsWith(matchPath);
          return (
            <Link
              key={tab.path}
              to={tab.path}
              className={`portal-subnav-link ${isActive ? 'is-active' : ''}`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </Link>
          );
        })}
        <div className="ml-auto flex items-center gap-2">
          {externalHref?.startsWith('http') && (
            <a href={externalHref} className="portal-subnav-external">
              <ExternalLink className="h-3 w-3" />
              {externalLabel}
            </a>
          )}
          <StatusBadge>{label}</StatusBadge>
        </div>
      </div>
    </div>
  );
};

export const toneForStatus = (status?: string): Tone => {
  switch (String(status ?? '').toLowerCase()) {
    case 'approved':
    case 'active':
    case 'success':
    case 'completed':
    case 'ib':
      return 'success';
    case 'reviewing':
    case 'running':
      return 'accent';
    case 'pending':
    case 'lockout':
      return 'warning';
    case 'rejected':
    case 'failed':
    case 'inactive':
    case 'failure':
    case 'cancelled':
    case 'admin':
      return 'danger';
    case 'backoffice':
      return 'violet';
    case 'sub_ib':
      return 'accent';
    case 'client':
    case 'user':
      return 'muted';
    default:
      return 'muted';
  }
};
