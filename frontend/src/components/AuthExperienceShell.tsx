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
  <div className="border-y border-stone-800 py-5">
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-[11px] font-semibold uppercase text-slate-500">Entry readiness</p>
        <p className="mt-2 text-2xl font-semibold text-white">Know the next step before entering.</p>
      </div>
      <span className="text-sm font-semibold text-emerald-300">Guided</span>
    </div>

    <div className="mt-6 divide-y divide-stone-800 border-y border-stone-800">
      {readinessRows.map(([label, detail], index) => (
        <div key={label} className="grid gap-1 py-4 text-sm sm:grid-cols-[2rem,0.7fr,1fr] sm:gap-4">
          <span className="font-mono text-cyan-300">0{index + 1}</span>
          <span className="font-semibold text-white">{label}</span>
          <span className="text-slate-400">{detail}</span>
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
      <div className="auth-stage px-4 py-8 sm:px-6">
        <div className="mx-auto w-full max-w-[96rem]">
          <div className="grid gap-8 lg:grid-cols-[minmax(25rem,0.82fr),minmax(0,1.18fr)] lg:items-start">
            <div className="auth-panel order-1 w-full p-7 sm:p-10 lg:sticky lg:top-24">
              <div className="mb-8">
                <div className="surface-label">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {kicker}
                </div>
                <h2 className="mt-4 text-3xl font-bold text-white sm:text-4xl">{title}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
              </div>

              {children}

              <div className="mt-8 border-l border-stone-800 pl-4">
                <div className="flex items-start gap-3 text-sm text-slate-300">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                  <p>
                    Clear entry keeps account setup, onboarding, and workspace access predictable
                    before operators move into live workflows.
                  </p>
                </div>
              </div>
            </div>

            <div className="relative order-2 border-y border-stone-800 py-6 sm:py-8">
              <div className="surface-label">
                <LockKeyhole className="h-3.5 w-3.5" />
                {sideLabel}
              </div>
              <h1 className="mt-5 max-w-4xl text-3xl font-bold leading-tight text-white sm:text-4xl xl:text-5xl">
                {sideTitle}
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">
                {sideDescription}
              </p>

              <div className="mt-7 flex flex-wrap gap-3">
                {securityPrinciples.map((item) => (
                  <div key={item} className="data-chip">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    {item}
                  </div>
                ))}
              </div>

              <div className="mt-8">
                <AuthReadinessPanel />
              </div>

              <div className="mt-8 divide-y divide-stone-800 border-y border-stone-800">
                {highlights.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.label} className="px-1 py-5">
                      <div className="flex items-start gap-4">
                        <div className="rounded-lg border border-stone-800 bg-stone-950 p-3 text-cyan-200">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-[11px] uppercase text-slate-500">{item.label}</p>
                          <p className="mt-1 text-lg font-semibold text-white">{item.title}</p>
                          <p className="mt-1 text-sm leading-6 text-slate-400">
                            {item.description}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-8 border-y border-stone-800 py-5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-[11px] uppercase text-slate-500">Commercial model</p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      Evaluation comes before live commercial terms.
                    </p>
                  </div>
                  <Link
                    to="/pricing"
                    className="premium-button premium-button-secondary px-4 py-2 text-sm"
                  >
                    View pricing
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {plans.map((plan) => (
                    <div key={plan.name} className="border-l border-stone-800 px-4 py-2">
                      <p className="text-[11px] uppercase text-slate-500">{plan.name}</p>
                      <p className="mt-2 text-sm leading-6 text-slate-300">{plan.detail}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PublicSiteShell>
  );
};

export default AuthExperienceShell;
