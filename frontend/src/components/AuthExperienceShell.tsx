import { ArrowRight, CheckCircle2, Shield, Sparkles, Waves } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';

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
    label: 'Execution',
    title: 'Live runtime control',
    description: 'Websocket-first operations, runtime recovery, and bot orchestration telemetry.',
    icon: Waves,
  },
  {
    label: 'Research',
    title: 'Backtest intelligence',
    description: 'Pair rankings, detailed analytics, live backtest streams, and high-density operator tables.',
    icon: Sparkles,
  },
  {
    label: 'Trust',
    title: 'Operator-grade security',
    description: 'Account hardening, 2FA onboarding, and controlled entry into execution surfaces.',
    icon: Shield,
  },
];

const plans = [
  { name: 'Explorer', price: '$0', detail: 'Evaluation workspace and delayed data snapshots' },
  { name: 'Performance', price: '12%', detail: 'Net-profit share with live execution and premium research access' },
  { name: 'Desk', price: 'Custom', detail: 'Negotiated success-fee structure with tailored operator rollout' },
];

export const AuthExperienceShell: React.FC<AuthExperienceShellProps> = ({
  kicker,
  title,
  description,
  children,
  sideLabel = 'DeFi Arbitrage Platform',
  sideTitle = 'Built for serious operators, not casual chart tourists.',
  sideDescription = 'Run quant research, monitor live bots, and understand strategy quality from a premium control plane designed for DeFi arbitrage teams.',
}) => {
  return (
    <div className="auth-stage flex min-h-screen items-center justify-center px-4 py-8 sm:px-6">
      <div className="premium-orb left-[6%] top-[12%] h-56 w-56 bg-cyan-500/12" />
      <div className="premium-orb right-[8%] bottom-[10%] h-64 w-64 bg-blue-500/12" />

      <div className="grid w-full max-w-7xl gap-8 lg:grid-cols-[1.1fr,0.9fr] lg:items-stretch">
        <div className="relative overflow-hidden rounded-[2rem] border border-slate-800 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.16),_transparent_26%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] p-8 shadow-[0_28px_90px_rgba(2,8,23,0.35)] sm:p-10">
          <div className="premium-kicker">{sideLabel}</div>
          <h1 className="mt-5 max-w-2xl text-4xl font-bold leading-tight text-white sm:text-5xl">
            {sideTitle}
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">{sideDescription}</p>

          <div className="mt-8 grid gap-4">
            {highlights.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.label}
                  className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5"
                >
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

          <div className="mt-8 rounded-[1.75rem] border border-slate-800 bg-slate-950/70 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Pricing Model</p>
                <p className="mt-1 text-lg font-semibold text-white">
                  Built around aligned fees instead of fixed monthly rent.
                </p>
              </div>
              <Link
                to="/pricing"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-700 hover:text-white"
              >
                View plans
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {plans.map((plan) => (
                <div key={plan.name} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{plan.name}</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{plan.price}</p>
                  <p className="mt-2 text-xs leading-5 text-slate-400">{plan.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="auth-panel w-full p-8 sm:p-10">
          <div className="mb-8">
            <div className="premium-kicker">{kicker}</div>
            <h2 className="mt-4 text-3xl font-bold text-white">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
          </div>
          {children}
          <div className="mt-8 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-400">
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            Production-ready UX for DeFi arbitrage desks, research teams, and live trading operators.
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthExperienceShell;
