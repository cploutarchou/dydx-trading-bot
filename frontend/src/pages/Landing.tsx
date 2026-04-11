import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Compass,
  Radar,
  Shield,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Waypoints,
} from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import { DeFiHeroIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';

const pathItems = [
  [Waypoints, 'Research', 'Validate quality, risk, and consistency before exposure'],
  [ShieldCheck, 'Security', 'Complete account readiness with clear onboarding expectations'],
  [TrendingUp, 'Runtime', 'Enter live control when your operating desk is ready'],
] as const;

const valueItems = [
  [
    Radar,
    'Backtest confidence',
    'Compare strategy quality with risk context before teams spend effort on runtime decisions.',
  ],
  [
    ShieldCheck,
    'Secure onboarding',
    'Keep account setup, pricing, and live-access expectations plain and transparent.',
  ],
  [
    Sparkles,
    'Live clarity',
    'Make runtime state readable the moment your desk transitions from evaluation into operation.',
  ],
] as const;

export const LandingPage: React.FC = () => {
  return (
    <PublicSiteShell>
      <section className="public-shell-container grid gap-4 py-4 md:gap-5 md:py-7 xl:grid-cols-[minmax(0,1.2fr),minmax(20rem,0.8fr)] xl:items-stretch">
        <MotionReveal
          className="public-hero-panel h-full rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5 sm:p-6"
          distancePx={18}
        >
          <div className="surface-label">
            <Radar className="h-3.5 w-3.5" />
            DeFi operator platform
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-white sm:text-4xl">
            A calmer front door for evaluating, preparing, and running dYdX strategies.
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400 sm:leading-7">
            dYdX Arbitrage OS guides teams from research conviction to secure onboarding and live
            runtime control—without the noise of a long marketing funnel.
          </p>

          <div className="public-actions-row mt-6 flex flex-col gap-3 sm:flex-row">
            <Link
              to="/register"
              className="premium-button premium-button-primary public-cta-primary w-full justify-center px-6 py-3.5 text-sm font-semibold text-white sm:w-auto"
            >
              Start free evaluation
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/pricing"
              className="premium-button premium-button-secondary w-full justify-center px-6 py-3.5 text-sm font-medium sm:w-auto"
            >
              View pricing
            </Link>
          </div>
        </MotionReveal>

        <div className="grid content-start gap-4 md:grid-cols-3 xl:grid-cols-1 xl:auto-rows-fr">
          <MotionReveal
            className="public-metric-card rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4"
            delayMs={40}
          >
            <div className="flex items-center gap-2 text-slate-300">
              <Shield className="h-4 w-4 text-cyan-300" /> Security posture
            </div>
            <p className="mt-3 text-xl font-semibold text-white">Security-first onboarding</p>
            <p className="mt-1 text-xs text-slate-500">Clear access expectations from day one</p>
          </MotionReveal>

          <MotionReveal
            className="public-metric-card rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4"
            delayMs={80}
          >
            <div className="flex items-center gap-2 text-slate-300">
              <Compass className="h-4 w-4 text-emerald-300" /> Workflow clarity
            </div>
            <p className="mt-3 text-xl font-semibold text-white">Research → Security → Runtime</p>
            <p className="mt-1 text-xs text-slate-500">One practical path, no noisy detours</p>
          </MotionReveal>

          <MotionReveal
            className="public-metric-card rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4"
            delayMs={120}
          >
            <div className="flex items-center gap-2 text-slate-300">
              <Building2 className="h-4 w-4 text-violet-300" /> Commercial model
            </div>
            <p className="mt-3 text-xl font-semibold text-white">Start free, then scale</p>
            <p className="mt-1 text-xs text-slate-500">Validate process before live monetization</p>
          </MotionReveal>
        </div>
      </section>

      <section className="public-shell-container pb-8">
        <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
          <MotionReveal
            className="public-section-panel rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
            distancePx={18}
          >
            <h2 className="text-lg font-semibold text-white">Evaluation path</h2>
            <p className="mt-1 text-sm text-slate-400">
              Move from strategy confidence to secure onboarding and live runtime in clear stages.
            </p>

            <div className="mt-4 space-y-3">
              {pathItems.map(([Icon, title, body], index) => (
                <div
                  key={title}
                  className="public-tile-card rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-cyan-500/10 p-2 text-cyan-300">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                        Step {String(index + 1).padStart(2, '0')}
                      </p>
                      <p className="mt-1 text-sm font-semibold text-white">{title}</p>
                      <p className="mt-1 text-xs leading-5 text-slate-400">{body}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </MotionReveal>

          <MotionReveal
            className="public-section-panel rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
            delayMs={120}
            distancePx={18}
          >
            <DeFiHeroIllustration className="mb-4" />
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Product promise
            </div>
            <p className="mt-2 text-sm text-slate-400">
              Built for confidence before the first live action.
            </p>

            <div className="mt-4 space-y-3">
              {valueItems.map(([Icon, title, body]) => (
                <div
                  key={title}
                  className="public-tile-card rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-cyan-500/10 p-2 text-cyan-300">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{title}</p>
                      <p className="mt-1 text-xs leading-5 text-slate-400">{body}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </MotionReveal>
        </div>
      </section>

      <section className="landing-cta public-shell-container">
        <MotionReveal className="landing-cta-inner" distancePx={18}>
          <div>
            <div className="surface-label">
              <ShieldCheck className="h-4 w-4" />
              Ready for evaluation
            </div>
            <h2>Start with context. Continue into secure onboarding.</h2>
          </div>
          <div>
            <p>
              Review pricing, align on security expectations, and complete onboarding before any
              live workflow begins.
            </p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/register"
                className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white"
              >
                Start free evaluation
              </Link>
              <Link
                to="/services/security"
                className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium"
              >
                Review security
              </Link>
            </div>
          </div>
        </MotionReveal>
      </section>
    </PublicSiteShell>
  );
};

export default LandingPage;
