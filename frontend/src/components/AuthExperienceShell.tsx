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
}

const highlights = [
  {
    label: 'Realtime',
    title: 'Live runtime control',
    description: 'Websocket-first monitoring for backtests, bots, and execution context.',
    icon: Waves,
  },
  {
    label: 'Research',
    title: 'Operator-grade intelligence',
    description: 'Analytics, market context, and faster movement between research and runtime.',
    icon: Sparkles,
  },
  {
    label: 'Security',
    title: 'Trust designed into onboarding',
    description: '2FA readiness, clear access states, and stronger session expectations from day one.',
    icon: ShieldCheck,
  },
];

const securityPrinciples = [
  'Secure account entry',
  'Clear return navigation',
  'Onboarding before live access',
];

const plans = [
  { name: 'Explorer', detail: 'Evaluate workflows before monetization starts' },
  { name: 'Performance', detail: '12% net-profit share when live execution is enabled' },
  { name: 'Desk', detail: 'Custom rollout and desk-level commercial structure' },
];

const readinessRows = [
  ['Account', 'Create credentials or return to sign in'],
  ['Security', 'Confirm access state before runtime use'],
  ['Workspace', 'Enter research and operations after onboarding'],
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
  sideTitle = 'Enter a trading workspace with clear context, account state, and routes back.',
  sideDescription = 'Review pricing, return to the product overview, or continue into onboarding without losing your place.',
}) => {
  return (
    <PublicSiteShell hideFooter>
      <div className="auth-modern-stage">
        <div className="auth-modern-grid">
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
                  <p>Research, runtime, and pricing remain one step away</p>
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
                  <strong>Evaluation comes before live commercial terms.</strong>
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
                before operators move into live workflows.
              </p>
            </div>
          </section>
        </div>
      </div>
    </PublicSiteShell>
  );
};

export default AuthExperienceShell;
