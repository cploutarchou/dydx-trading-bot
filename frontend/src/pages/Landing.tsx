import { ArrowRight, CheckCircle2, ShieldCheck, TrendingUp, Waypoints } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import { MotionReveal } from '../components/MotionReveal';
import { PublicSiteShell } from '../components/PublicSiteShell';
import { SEOHead } from '../components/SEOHead';

const workflowSteps = [
  {
    icon: Waypoints,
    label: 'Research',
    title: 'Shape the strategy',
    body: 'Compare market context and assumptions before work moves into testing.',
    href: '/services/research',
    cta: 'Research overview',
  },
  {
    icon: ShieldCheck,
    label: 'Backtest',
    title: 'Check the evidence',
    body: 'Use backtests and risk checks before a strategy is promoted toward runtime.',
    href: '/services/runtime',
    cta: 'Runtime overview',
  },
  {
    icon: TrendingUp,
    label: 'Operate',
    title: 'Monitor the bot',
    body: 'Follow backend-connected bot state, health, and action paths in one workspace.',
    href: '/services/intelligence',
    cta: 'Intelligence overview',
  },
] as const;

const startSteps = [
  ['1', 'Review pricing', 'Understand the engagement model before requesting access.'],
  ['2', 'Request access', 'Share the basics needed for onboarding review.'],
  ['3', 'Sign in', 'Approved users enter the protected workspace.'],
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
        <section className="public-modern-hero public-modern-hero-intelligence landing-focus-hero">
          <div className="public-modern-container landing-focus-grid">
            <MotionReveal className="public-modern-copy landing-focus-copy" distancePx={18}>
              <div className="surface-label">
                <Waypoints className="h-3.5 w-3.5" />
                dYdX trading bot workspace
              </div>
              <h1>Research, backtest, and monitor dYdX trading bots.</h1>
              <p>
                ExecutionLab keeps strategy research, backtest evidence, and backend-connected bot
                operations in one protected workspace.
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

              <p className="landing-focus-helper">
                Already onboarded? <Link to="/login">Sign in</Link>.
              </p>
            </MotionReveal>

            <MotionReveal className="landing-focus-panel" delayMs={90} distancePx={18}>
              <div className="landing-focus-panel-header">
                <span>Start here</span>
                <strong>Request access after reviewing the model.</strong>
              </div>
              <div className="landing-focus-start-list">
                {startSteps.map(([number, title, body]) => (
                  <div key={title} className="landing-focus-start-row">
                    <span>{number}</span>
                    <div>
                      <strong>{title}</strong>
                      <p>{body}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="landing-focus-panel-actions">
                <Link
                  to="/pricing"
                  className="premium-button premium-button-secondary justify-center px-4 py-3 text-sm font-medium"
                >
                  View pricing
                </Link>
                <Link
                  to="/register"
                  className="premium-button premium-button-primary public-cta-primary justify-center px-4 py-3 text-sm font-semibold text-white"
                >
                  Request access
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </MotionReveal>
          </div>
        </section>

        <section
          className="public-modern-container landing-focus-section"
          aria-labelledby="workflow-heading"
        >
          <MotionReveal className="landing-focus-section-header" distancePx={14}>
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              What the workspace does
            </div>
            <h2 id="workflow-heading">One flow from idea to monitored bot.</h2>
          </MotionReveal>

          <div className="landing-focus-workflow">
            {workflowSteps.map((step, index) => {
              const Icon = step.icon;
              return (
                <MotionReveal
                  key={step.title}
                  as="article"
                  className="landing-focus-workflow-card"
                  delayMs={index * 70}
                >
                  <div className="landing-focus-card-top">
                    <Icon className="h-5 w-5" />
                    <span>{step.label}</span>
                  </div>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                  <Link to={step.href}>
                    {step.cta}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </MotionReveal>
              );
            })}
          </div>
        </section>

        <section className="public-modern-container landing-focus-risk">
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
