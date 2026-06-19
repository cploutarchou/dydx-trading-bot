import { ArrowRight, CheckCircle2, Radar, ShieldCheck, TrendingUp, Waypoints } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import { DeFiHeroIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';
import SEOHead from '../components/SEOHead';

const workflowSteps = [
  {
    icon: Waypoints,
    label: 'Step 1',
    title: 'Research',
    body: 'Review market context and strategy assumptions before building or running a bot.',
    href: '/services/research',
  },
  {
    icon: ShieldCheck,
    label: 'Step 2',
    title: 'Backtest',
    body: 'Validate strategy logic and risk controls before promoting work toward runtime.',
    href: '/services/runtime',
  },
  {
    icon: TrendingUp,
    label: 'Step 3',
    title: 'Operate',
    body: 'Use backend-connected bot controls and status views to monitor live workflows.',
    href: '/services/intelligence',
  },
] as const;

const proofItems = [
  ['What it is', 'A controlled workspace for dYdX strategy research, backtests, and bot operations.'],
  ['Why it matters', 'Evidence, risk checks, and runtime state stay close to the action.'],
  ['Next action', 'Request access or review pricing before onboarding.'],
] as const;

const riskItems = [
  'Crypto trading involves volatility, liquidity, fee, latency, and execution risk.',
  'Backtests help planning. They do not guarantee live performance.',
  'Operators remain responsible for wallet security, compliance, and capital decisions.',
] as const;

export const LandingPage: React.FC = () => (
  <>
    <SEOHead
      title="ExecutionLab | Build. Test. Execute."
      description="Technical execution lab for building, testing, and operating dYdX trading bots with research-backed strategies."
      image="/og-images/landing.png"
      imageAlt="ExecutionLab - Technical execution platform for dYdX trading"
      url="/"
    />
    <PublicSiteShell hideFooter hideMarketTape>
      <div className="public-modern-page">
        <section className="public-modern-hero public-modern-hero-intelligence">
          <div className="public-modern-container public-modern-hero-grid">
            <MotionReveal className="public-modern-copy" distancePx={18}>
              <div className="surface-label">
                <Radar className="h-3.5 w-3.5" />
                DeFi execution workspace
              </div>
              <h1>Build, test, and operate dYdX trading bots.</h1>
              <p>
                ExecutionLab helps teams research strategies, validate them with backtests, and
                monitor backend-connected bot workflows from one workspace.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/register"
                  className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3.5 text-sm font-semibold text-white"
                >
                  Request access
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/pricing"
                  className="premium-button premium-button-secondary justify-center px-6 py-3.5 text-sm font-medium"
                >
                  View pricing
                </Link>
              </div>

              <div className="mt-6 flex flex-wrap gap-3 text-xs text-slate-400">
                <span className="rounded-lg border border-cyan-500/25 bg-cyan-500/10 px-3 py-2 text-cyan-200">
                  Research
                </span>
                <span className="rounded-lg border border-slate-700/70 bg-slate-950/40 px-3 py-2">
                  Backtest
                </span>
                <span className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-emerald-200">
                  Operate
                </span>
              </div>
            </MotionReveal>

            <MotionReveal className="public-modern-visual" delayMs={90} distancePx={18}>
              <div className="public-visual-photo" aria-hidden="true" />
              <div className="public-visual-terminal">
                <div className="public-terminal-bar">
                  <span />
                  <span />
                  <span />
                  <strong>EXECUTION LAB</strong>
                </div>
                <DeFiHeroIllustration />
              </div>
              <div className="public-visual-tags">
                <span>Market research</span>
                <span>Backtest evidence</span>
                <span>Runtime state</span>
              </div>
            </MotionReveal>
          </div>
        </section>

        <section className="public-modern-container public-proof-strip" aria-label="Page summary">
          {proofItems.map(([title, body], index) => (
            <MotionReveal key={title} className="public-proof-item" delayMs={index * 60}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </MotionReveal>
          ))}
        </section>

        <section className="public-modern-band">
          <div className="public-modern-container public-modern-split">
            <MotionReveal className="public-modern-section-copy" distancePx={18}>
              <div className="surface-label">
                <CheckCircle2 className="h-3.5 w-3.5" />
                How it works
              </div>
              <h2>Move from idea to monitored bot in three steps.</h2>
              <p>
                Each step has one job: make the next decision clearer before capital or runtime
                exposure increases.
              </p>
            </MotionReveal>

            <div className="public-capability-grid">
              {workflowSteps.map((step, index) => {
                const Icon = step.icon;
                return (
                  <MotionReveal
                    key={step.title}
                    className="public-capability-card landing-modern-card"
                    delayMs={index * 70}
                  >
                    <Icon className="landing-modern-icon" />
                    <span>{step.label}</span>
                    <h3>{step.title}</h3>
                    <p>{step.body}</p>
                    <Link
                      to={step.href}
                      className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-cyan-200 transition hover:text-white"
                    >
                      Learn more
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </MotionReveal>
                );
              })}
            </div>
          </div>
        </section>

        <section className="public-modern-container public-modern-cta">
          <MotionReveal className="public-modern-cta-inner" distancePx={18}>
            <div>
              <div className="surface-label">
                <ShieldCheck className="h-4 w-4" />
                Start here
              </div>
              <h2>Need access to the workspace?</h2>
              <p>
                Review the engagement model, then request access when you are ready to discuss
                onboarding and security requirements.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                to="/pricing"
                className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium"
              >
                View pricing
              </Link>
              <Link
                to="/register"
                className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white"
              >
                Request access
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </MotionReveal>
        </section>

        <section className="public-modern-container pb-16">
          <details className="public-disclosure">
            <summary>Trading risk disclosure</summary>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {riskItems.map((item) => (
                <p key={item} className="text-sm leading-6 text-slate-400">
                  {item}
                </p>
              ))}
            </div>
          </details>
        </section>
      </div>
    </PublicSiteShell>
  </>
);

export default LandingPage;
