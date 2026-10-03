import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Eye,
  EyeOff,
  FileText,
  Loader,
  type LucideIcon,
} from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import type { IcoResourceItem } from '../content/publicSite';
import type { CountdownState } from '../utils/publicPages';
import { BrandMark } from './BrandMark';
import { CryptoBackground, type CryptoBackgroundVariant } from './CryptoBackground';

interface PublicPageShellProps {
  children: React.ReactNode;
  logoSubtitle: string;
  backgroundVariant?: CryptoBackgroundVariant;
  utilityAction?: {
    label: string;
    to: string;
  };
  className?: string;
}

export const PublicPageShell: React.FC<PublicPageShellProps> = ({
  children,
  logoSubtitle,
  backgroundVariant,
  utilityAction,
  className = '',
}) => (
  <main
    className={`public-page-shell relative isolate min-h-screen overflow-x-hidden bg-[#050816] text-white ${className}`}
  >
    {backgroundVariant && <CryptoBackground variant={backgroundVariant} />}
    <PageContainer className="relative z-10 flex min-h-screen flex-col py-5 sm:py-6">
      <PublicHeader logoSubtitle={logoSubtitle} utilityAction={utilityAction} />
      {children}
    </PageContainer>
  </main>
);

export const PublicLaunchShell = PublicPageShell;

export const PageContainer: React.FC<{
  children: React.ReactNode;
  className?: string;
}> = ({ children, className = '' }) => (
  <div className={`public-page-container mx-auto w-full ${className}`}>{children}</div>
);

export const PublicHeader: React.FC<{
  logoSubtitle: string;
  utilityAction?: {
    label: string;
    to: string;
  };
}> = ({ logoSubtitle, utilityAction }) => (
  <header className="public-header">
    <Link to="/" className="min-w-0 shrink">
      <BrandMark subtitle={logoSubtitle} />
    </Link>
    {utilityAction && (
      <nav className="shrink-0" aria-label="Public page navigation">
        <Link to={utilityAction.to} className="public-link-button">
          {utilityAction.label}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </nav>
    )}
  </header>
);

export const StatusBadge: React.FC<{
  children: React.ReactNode;
  tone?: 'info' | 'success' | 'warning' | 'neutral';
  icon?: LucideIcon;
}> = ({ children, tone = 'info', icon: Icon = CheckCircle2 }) => {
  const toneClass = {
    info: 'border-cyan-400/25 bg-cyan-500/10 text-cyan-100',
    success: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-100',
    warning: 'border-amber-400/25 bg-amber-500/10 text-amber-100',
    neutral: 'border-slate-600/50 bg-slate-900/60 text-slate-200',
  }[tone];

  return (
    <span className={`public-status-badge ${toneClass}`}>
      <Icon className="h-4 w-4 shrink-0" />
      <span>{children}</span>
    </span>
  );
};

export const PublicStatusPill = StatusBadge;

export const PrimaryButton: React.FC<{
  children: React.ReactNode;
  to?: string;
  href?: string;
  type?: 'button' | 'submit';
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
}> = ({
  children,
  to,
  href,
  type = 'button',
  disabled = false,
  loading = false,
  className = '',
  onClick,
}) => {
  const content = (
    <>
      {loading && <Loader className="h-4 w-4 animate-spin" />}
      {children}
    </>
  );
  const buttonClass = `public-primary-button ${className}`;

  if (to) {
    return (
      <Link to={to} className={buttonClass}>
        {content}
      </Link>
    );
  }

  if (href) {
    return (
      <a href={href} className={buttonClass}>
        {content}
      </a>
    );
  }

  return (
    <button type={type} disabled={disabled || loading} className={buttonClass} onClick={onClick}>
      {content}
    </button>
  );
};

export const SecondaryButton: React.FC<{
  children: React.ReactNode;
  to?: string;
  href?: string;
  className?: string;
}> = ({ children, to, href, className = '' }) => {
  const buttonClass = `public-secondary-button ${className}`;
  if (to) {
    return (
      <Link to={to} className={buttonClass}>
        {children}
      </Link>
    );
  }

  return (
    <a href={href} className={buttonClass}>
      {children}
    </a>
  );
};

export const PublicSectionHeading: React.FC<{
  eyebrow?: string;
  title: string;
  description?: string;
  compact?: boolean;
}> = ({ eyebrow, title, description, compact = false }) => (
  <div className={compact ? 'max-w-2xl' : 'max-w-3xl'}>
    {eyebrow && <p className="public-eyebrow">{eyebrow}</p>}
    <h2 className="mt-2 text-[clamp(1.75rem,3vw,2.25rem)] font-semibold leading-tight tracking-normal text-white">
      {title}
    </h2>
    {description && <p className="mt-3 text-base leading-7 text-slate-300">{description}</p>}
  </div>
);

export const ProductWorkflow: React.FC<{
  steps: Array<{ label: string; description: string; status: string; icon: LucideIcon }>;
}> = ({ steps }) => (
  <aside className="product-workflow" aria-label="ExecutionLab workflow">
    <div className="product-workflow__grid" aria-hidden="true" />
    <div className="relative">
      <p className="public-eyebrow">Execution workflow</p>
      <h2 className="mt-2 text-xl font-semibold text-white">From research to monitored runtime</h2>
      <p className="mt-2 text-sm leading-6 text-slate-400">
        A controlled path for promoting strategy ideas into validated operator workflows.
      </p>
    </div>
    <ol className="product-workflow__steps">
      {steps.map((step, index) => {
        const Icon = step.icon;
        return (
          <li key={step.label} className="product-workflow__step">
            <div className="product-workflow__node">
              <Icon className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold text-white">{step.label}</h3>
                <span className="rounded-md border border-cyan-400/20 bg-cyan-500/10 px-2 py-1 text-xs font-semibold text-cyan-100">
                  {step.status}
                </span>
              </div>
              <p className="mt-1 text-sm leading-6 text-slate-400">{step.description}</p>
            </div>
            {index < steps.length - 1 && <span className="product-workflow__connector" />}
          </li>
        );
      })}
    </ol>
  </aside>
);

export const PublicCapabilityList: React.FC<{
  items: Array<{ icon: LucideIcon; title: string; body: string }>;
}> = ({ items }) => (
  <div className="public-capability-grid">
    {items.slice(0, 3).map((item) => {
      const Icon = item.icon;
      return (
        <article key={item.title} className="public-capability-card">
          <div className="public-capability-card__icon" aria-hidden="true">
            <Icon />
          </div>
          <h3 className="public-capability-card__title">{item.title}</h3>
          <p className="public-capability-card__body">{item.body}</p>
        </article>
      );
    })}
  </div>
);

export const LaunchStatusStrip: React.FC<{
  items: Array<{ label: string; value: string; tone?: 'info' | 'success' | 'warning' | 'neutral' }>;
}> = ({ items }) => (
  <dl className="launch-status-strip">
    {items.map((item) => (
      <div key={item.label} className="launch-status-strip__item">
        <dt>{item.label}</dt>
        <dd>
          <span className={`launch-status-dot is-${item.tone ?? 'info'}`} />
          {item.value}
        </dd>
      </div>
    ))}
  </dl>
);

export const SaleFacts: React.FC<{
  facts: Array<{ label: string; value: string; helper?: string }>;
}> = ({ facts }) => (
  <dl className="sale-facts-grid">
    {facts.map((fact) => (
      <div key={fact.label} className="sale-fact-card">
        <dt>{fact.label}</dt>
        <dd>{fact.value}</dd>
        {fact.helper && <p>{fact.helper}</p>}
      </div>
    ))}
  </dl>
);

export const PublicFactGrid = SaleFacts;

export const SaleTimeline: React.FC<{
  items: Array<{ phase: string; window: string; status: string }>;
}> = ({ items }) => (
  <ol className="sale-timeline">
    {items.map((item, index) => (
      <li key={`${item.phase}-${item.window}`} className="sale-timeline__item">
        <span className="sale-timeline__marker">{String(index + 1).padStart(2, '0')}</span>
        <div className="min-w-0">
          <div className="sale-timeline__heading">
            <h3>{item.phase}</h3>
            <span>{item.status}</span>
          </div>
          <p>{item.window}</p>
        </div>
      </li>
    ))}
  </ol>
);

export const PublicTimeline = SaleTimeline;

export const SaleCountdown: React.FC<{
  state: CountdownState;
  label: string;
  targetLabel: string;
  timezoneLabel: string;
  summary: Array<{ label: string; value: string }>;
}> = ({ state, label, targetLabel, timezoneLabel, summary }) => {
  const statusCopy = {
    active: 'Scheduled',
    expired: 'Configured date reached',
    missing: 'Date to be confirmed',
  }[state.status];

  return (
    <section className="sale-summary-panel" aria-labelledby="ico-countdown-heading">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="public-eyebrow">Sale summary</p>
          <h2 id="ico-countdown-heading" className="mt-2 text-xl font-semibold text-white">
            {label}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            {targetLabel} ({timezoneLabel})
          </p>
        </div>
        <StatusBadge tone={state.status === 'active' ? 'info' : 'neutral'}>
          {statusCopy}
        </StatusBadge>
      </div>

      <div className="sale-countdown-grid" role="timer" aria-live="polite">
        {state.parts.map((part) => (
          <div key={part.label}>
            <p>{part.value}</p>
            <span>{part.label}</span>
          </div>
        ))}
      </div>

      <dl className="sale-summary-list">
        {summary.map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
};

export const PublicCountdown = SaleCountdown;

export const DocumentationPanel: React.FC<{
  resources: IcoResourceItem[];
}> = ({ resources }) => (
  <section
    id="documentation"
    className="documentation-panel scroll-mt-24"
    aria-labelledby="documentation-heading"
  >
    <div className="flex items-start gap-3">
      <span className="public-icon-surface">
        <FileText className="h-5 w-5 text-cyan-200" />
      </span>
      <div>
        <p className="public-eyebrow">Documentation</p>
        <h2 id="documentation-heading" className="mt-2 text-2xl font-semibold text-white">
          Review materials
        </h2>
      </div>
    </div>
    <div className="mt-5 divide-y divide-slate-800/80">
      {resources.map((resource) => (
        <PublicResourceLink key={resource.title} {...resource} />
      ))}
    </div>
  </section>
);

export const PublicResourceLink: React.FC<IcoResourceItem> = ({
  title,
  description,
  href,
  ctaLabel,
}) => {
  const isInternalLink = href?.startsWith('/');

  return (
    <div className="public-resource-row">
      <div>
        <h3 className="text-base font-semibold text-white">{title}</h3>
        <p className="mt-1 text-sm leading-6 text-slate-400">{description}</p>
      </div>
      {href && isInternalLink && (
        <Link to={href} className="public-link-button">
          {ctaLabel}
          <ArrowRight className="h-4 w-4" />
        </Link>
      )}
      {href && !isInternalLink && (
        <a href={href} target="_blank" rel="noreferrer" className="public-link-button">
          {ctaLabel}
          <ExternalLink className="h-4 w-4" />
        </a>
      )}
      {!href && <span className="public-resource-state">{ctaLabel}</span>}
    </div>
  );
};

export const Accordion: React.FC<{
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}> = ({ title, children, defaultOpen = false }) => (
  <details className="public-disclosure" open={defaultOpen}>
    <summary>
      <span>{title}</span>
      <ChevronDown className="h-4 w-4" />
    </summary>
    <div className="pt-3 text-sm leading-6 text-slate-300">{children}</div>
  </details>
);

export const PublicDisclosure = Accordion;

export const FormField: React.FC<
  Omit<React.InputHTMLAttributes<HTMLInputElement>, 'className'> & {
    label: string;
    error?: string;
    helper?: string;
    inputRef?: React.Ref<HTMLInputElement>;
  }
> = ({ label, error, helper, id, inputRef, ...inputProps }) => {
  const describedBy = [helper ? `${id}-help` : '', error ? `${id}-error` : '']
    .filter(Boolean)
    .join(' ');

  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-sm font-semibold text-white">
        {label}
      </label>
      <input
        id={id}
        ref={inputRef}
        className="premium-input"
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy || undefined}
        {...inputProps}
      />
      {helper && (
        <p id={`${id}-help`} className="mt-2 text-sm leading-6 text-slate-400">
          {helper}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-2 text-sm text-rose-300" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};

export const PasswordField: React.FC<{
  id: string;
  label: string;
  value: string;
  error?: string;
  disabled?: boolean;
  showPassword: boolean;
  onShowPasswordChange: (value: boolean) => void;
  onChange: React.ChangeEventHandler<HTMLInputElement>;
}> = ({ id, label, value, error, disabled, showPassword, onShowPasswordChange, onChange }) => (
  <div>
    <label htmlFor={id} className="mb-2 block text-sm font-semibold text-white">
      {label}
    </label>
    <div className="relative">
      <input
        id={id}
        type={showPassword ? 'text' : 'password'}
        autoComplete="current-password"
        value={value}
        onChange={onChange}
        className="premium-input pr-12"
        placeholder="Enter your password"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        disabled={disabled}
        required
      />
      <button
        type="button"
        onClick={() => onShowPasswordChange(!showPassword)}
        className="password-visibility-button"
        aria-label={showPassword ? 'Hide password' : 'Show password'}
        disabled={disabled}
      >
        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
    {error && (
      <p id={`${id}-error`} className="mt-2 text-sm text-rose-300" role="alert">
        {error}
      </p>
    )}
  </div>
);

export const WhitelistForm: React.FC<{
  email: string;
  emailError: string;
  privacyAccepted: boolean;
  marketingConsent: boolean;
  requestState: 'idle' | 'loading' | 'success' | 'error';
  helperCopy: string;
  ctaLabel: string;
  onEmailChange: (value: string) => void;
  onPrivacyAcceptedChange: (value: boolean) => void;
  onMarketingConsentChange: (value: boolean) => void;
  onSubmit: React.FormEventHandler<HTMLFormElement>;
}> = ({
  email,
  emailError,
  privacyAccepted,
  marketingConsent,
  requestState,
  helperCopy,
  ctaLabel,
  onEmailChange,
  onPrivacyAcceptedChange,
  onMarketingConsentChange,
  onSubmit,
}) => (
  <form
    id="whitelist-request"
    onSubmit={onSubmit}
    className="whitelist-form scroll-mt-24"
    noValidate
  >
    <div>
      <p className="public-eyebrow">Whitelist</p>
      <h2 className="mt-2 text-2xl font-semibold text-white">Whitelist request</h2>
      <p className="mt-2 text-base leading-7 text-slate-300">{helperCopy}</p>
    </div>

    <FormField
      id="ico-whitelist-email"
      label="Email address"
      type="email"
      inputMode="email"
      autoComplete="email"
      value={email}
      onChange={(event) => onEmailChange(event.target.value)}
      placeholder="you@company.com"
      error={emailError}
      helper="Submission starts review communication only. It does not guarantee participation, eligibility, or allocation."
      disabled={requestState === 'loading' || requestState === 'success'}
      required
    />

    <input
      type="text"
      name="company_website"
      tabIndex={-1}
      autoComplete="off"
      className="hidden"
      aria-hidden="true"
    />

    <div className="grid gap-3">
      <label className="public-consent-option">
        <input
          type="checkbox"
          checked={privacyAccepted}
          onChange={(event) => onPrivacyAcceptedChange(event.target.checked)}
          disabled={requestState === 'loading' || requestState === 'success'}
          required
        />
        <span>
          <strong>I accept the ICO Privacy Notice.</strong>
          <small>
            ExecutionLab may process this email address to review and communicate about this
            whitelist request. Review the <Link to="/ico/privacy-notice">Privacy Notice</Link> and{' '}
            <Link to="/ico/participation-terms">participation terms</Link>.
          </small>
        </span>
      </label>

      <label className="public-consent-option">
        <input
          type="checkbox"
          checked={marketingConsent}
          onChange={(event) => onMarketingConsentChange(event.target.checked)}
          disabled={requestState === 'loading' || requestState === 'success'}
        />
        <span>
          <strong>Send me optional ICO updates.</strong>
          <small>
            Optional marketing emails may include document updates and token-launch notices. This is
            separate from whitelist review and can be unsubscribed from later.
          </small>
        </span>
      </label>
    </div>

    <PrimaryButton
      type="submit"
      disabled={requestState === 'loading' || requestState === 'success'}
      loading={requestState === 'loading'}
      className="w-full"
    >
      {requestState === 'loading'
        ? 'Preparing request...'
        : requestState === 'success'
          ? 'Request prepared'
          : ctaLabel}
    </PrimaryButton>

    {requestState === 'success' && (
      <p className="text-sm leading-6 text-emerald-200" role="status">
        If the address is eligible to receive whitelist communications, a confirmation email will be
        sent. Submission does not guarantee participation, eligibility, or allocation.
      </p>
    )}

    {requestState === 'error' && !emailError && (
      <p className="text-sm leading-6 text-rose-200" role="alert">
        The request could not be submitted. Try again in a moment.
      </p>
    )}
  </form>
);
