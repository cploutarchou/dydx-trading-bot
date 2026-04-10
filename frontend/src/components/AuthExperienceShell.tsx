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
import { ProfitShareIllustration } from './DeFiIllustrations';

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
    description: 'Dense analytics, market context, and faster navigation between decision surfaces.',
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
  'Backend-only integration boundary',
  'Premium onboarding before live access',
  'Explicit security setup before runtime actions',
];

const plans = [
  { name: 'Explorer', detail: 'Evaluate workflows before monetization starts' },
  { name: 'Performance', detail: '12% net-profit share when live execution is enabled' },
  { name: 'Desk', detail: 'Custom rollout and desk-level commercial structure' },
];

export const AuthExperienceShell: React.FC<AuthExperienceShellProps> = ({
  kicker,
  title,
  description,
  children,
  sideLabel = 'Operator entry',
  sideTitle = 'Authentication should feel like the front door to a trading product, not a utility screen.',
  sideDescription = 'The public site, commercial model, and account setup flow should all reinforce the same thing: this workspace is built for serious operators who need trust and speed at the same time.',
}) => {
  return (
    <div className="auth-stage flex min-h-screen items-center justify-center px-4 py-8 sm:px-6">
      <div className="premium-orb left-[6%] top-[12%] h-56 w-56 bg-cyan-500/12" />
      <div className="premium-orb right-[8%] bottom-[10%] h-64 w-64 bg-blue-500/12" />

      <div className="grid w-full max-w-[112rem] gap-8 lg:grid-cols-[1.04fr,0.96fr] lg:items-stretch">
        <div className="editorial-band relative py-4 sm:py-6">
          <div className="surface-label">
            <LockKeyhole className="h-3.5 w-3.5" />
            {sideLabel}
          </div>
          <h1 className="mt-5 max-w-3xl text-4xl font-bold leading-tight text-white sm:text-5xl">
            {sideTitle}
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">{sideDescription}</p>

          <div className="mt-7 flex flex-wrap gap-3">
            {securityPrinciples.map((item) => (
              <div key={item} className="data-chip">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                {item}
              </div>
            ))}
          </div>

          <div className="market-illustration-shell market-illustration-compact mt-8 p-4 sm:p-5">
            <ProfitShareIllustration className="mx-auto max-w-2xl" />
          </div>

          <div className="mt-8 grid gap-4">
            {highlights.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.label} className="signal-card px-5 py-5">
                  <div className="flex items-start gap-4">
                    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-3 text-cyan-200">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                        {item.label}
                      </p>
                      <p className="mt-1 text-lg font-semibold text-white">{item.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-400">{item.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="signal-card mt-8 px-5 py-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  Commercial model
                </p>
                <p className="mt-1 text-lg font-semibold text-white">
                  Entry feels premium because the commercial story is clear.
                </p>
              </div>
              <Link
                to="/pricing"
                className="premium-button premium-button-secondary rounded-[1.05rem] px-4 py-2 text-sm"
              >
                View pricing
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {plans.map((plan) => (
                <div key={plan.name} className="metric-tile px-4 py-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    {plan.name}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{plan.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="auth-panel w-full rounded-[2rem] p-7 sm:p-10">
          <div className="mb-8">
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {kicker}
            </div>
            <h2 className="mt-4 text-3xl font-bold text-white">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
          </div>

          {children}

          <div className="signal-card mt-8 px-4 py-4">
            <div className="flex items-start gap-3 text-sm text-slate-300">
              <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
              <p>
                This entry flow is part of the product experience: clearer trust signals, cleaner
                next steps, and less friction before operators reach the workspace.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthExperienceShell;
