import {
  ArrowRight,
  CheckCircle2,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  Waves,
} from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import PublicSiteShell from './PublicSiteShell';

interface AuthExperienceShellProps {
  kicker: string;
  title: string;
  description: string;
  children: React.ReactNode;
  sideLabel?: string;
  sideTitle?: string;
  sideDescription?: string;
  loginOnlyLock?: {
    enabled: boolean;
    reason?: string;
  };
}

const highlights = [
  {
    label: 'Execute',
    title: 'Delivery systems in motion',
    description: 'Live-ready monitoring for backtests, automation, and execution context.',
    icon: Waves,
  },
  {
    label: 'Experiment',
    title: 'Operator-grade intelligence',
    description: 'Analytics, workflow context, and faster movement between idea and shipped system.',
    icon: Sparkles,
  },
  {
    label: 'Security',
    title: 'Trust designed into onboarding',
    description: '2FA readiness, clear access states, and disciplined session expectations from day one.',
    icon: ShieldCheck,
  },
];

const securityPrinciples = [
  'Secure account entry',
  'Clear return navigation',
  'Readiness before execution',
];

const plans = [
  { name: 'Explore', detail: 'Evaluate fit and scope before delivery starts' },
  { name: 'Build', detail: 'Turn validated priorities into production-ready systems' },
  { name: 'Scale', detail: 'Custom rollout and execution partnership structure' },
];

const readinessRows = [
  ['Account', 'Create credentials or return to sign in'],
  ['Security', 'Confirm access state before runtime use'],
  ['Workspace', 'Enter execution and operations after onboarding'],
] as const;

const AuthReadinessPanel: React.FC = () => (
  <div className="auth-readiness-card">
    <div className="auth-readiness-header">
      <div>
        <p>Entry readiness</p>
        <strong>Know the next step before entering.</strong>
      </div>
      <span>Guided</span>
    </div>

    <div className="auth-readiness-rows">
      {readinessRows.map(([label, detail], index) => (
        <div key={label}>
          <span>0{index + 1}</span>
          <strong>{label}</strong>
          <p>{detail}</p>
        </div>
      ))}
    </div>
  </div>
);

export const AuthExperienceShell: React.FC<AuthExperienceShellProps> = ({
  kicker,
  title,
  description,
  children,
  sideLabel = 'Operator entry',
  sideTitle = 'Enter a technical execution workspace with clear context, account state, and routes back.',
  sideDescription = 'Review pricing, return to the product overview, or continue into onboarding without losing your place.',
  loginOnlyLock,
}) => {
  const lockEnabled = loginOnlyLock?.enabled === true;

  return (
    <PublicSiteShell hideFooter>
      <div className="relative auth-modern-stage">
        <div
          className={`auth-modern-grid transition duration-200 ${
            lockEnabled ? 'pointer-events-none select-none blur-sm opacity-35' : ''
          }`}
          aria-hidden={lockEnabled}
        >
          <section className="auth-modern-story">
            <div className="surface-label">
              <LockKeyhole className="h-3.5 w-3.5" />
              {sideLabel}
            </div>
            <h1>{sideTitle}</h1>
            <p>{sideDescription}</p>

            <div className="auth-principle-row">
              {securityPrinciples.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>

            <div className="auth-command-visual" aria-hidden="true">
              <div className="auth-command-header">
                <span />
                <span />
                <span />
                <strong>ENTRY CONTROL</strong>
              </div>
              <div className="auth-command-body">
                <div className="auth-command-line is-active">
                  <span>01</span>
                  <strong>Account state</strong>
                  <p>Available for existing operators</p>
                </div>
                <div className="auth-command-line">
                  <span>02</span>
                  <strong>Security posture</strong>
                  <p>Authentication and follow-up setup happen before live workflow access</p>
                </div>
                <div className="auth-command-line">
                  <span>03</span>
                  <strong>Workspace route</strong>
                  <p>Research, execution, and pricing remain one step away</p>
                </div>
              </div>
            </div>

            <AuthReadinessPanel />

            <div className="auth-highlight-grid">
              {highlights.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="auth-highlight-card">
                    <Icon className="h-5 w-5" />
                    <div>
                      <span>{item.label}</span>
                      <strong>{item.title}</strong>
                      <p>{item.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="auth-commercial-row">
              <div className="auth-commercial-heading">
                <div>
                  <span>Commercial model</span>
                  <strong>Evaluation comes before execution terms.</strong>
                </div>
                <Link to="/pricing" className="premium-button premium-button-secondary px-4 py-2 text-sm">
                  View pricing
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
              <div className="auth-plan-grid">
                {plans.map((plan) => (
                  <div key={plan.name}>
                    <span>{plan.name}</span>
                    <p>{plan.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="auth-modern-panel">
            <div className="auth-panel-heading">
              <div className="surface-label">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {kicker}
              </div>
              <h2>{title}</h2>
              <p>{description}</p>
            </div>

            {children}

            <div className="auth-panel-note">
              <CheckCircle2 className="h-4 w-4" />
              <p>
                Clear entry keeps account setup, onboarding, and workspace access predictable
                before operators move into execution workflows.
              </p>
            </div>
          </section>
        </div>

        {lockEnabled && (
          <div className="absolute inset-0 z-20 flex items-center justify-center px-4">
            <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900/95 p-6 text-center shadow-2xl shadow-black/40 backdrop-blur-sm">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-cyan-500/50 bg-cyan-500/10 text-cyan-300">
                <LockKeyhole className="h-5 w-5" />
              </div>
              <h3 className="text-xl font-semibold text-white">Login required</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                {loginOnlyLock.reason ||
                  'Registration is currently disabled. Sign in with an existing account to continue.'}
              </p>
              <Link to="/login" className="premium-button premium-button-primary mt-5 inline-flex px-5 py-2.5">
                Go to login
              </Link>
            </div>
          </div>
        )}
      </div>
    </PublicSiteShell>
  );
};

export default AuthExperienceShell;
