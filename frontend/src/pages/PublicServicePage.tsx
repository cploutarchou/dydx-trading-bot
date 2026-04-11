import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles } from 'lucide-react';
import React from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ServicePulseIllustration } from '../components/DeFiIllustrations';
import MotionReveal from '../components/MotionReveal';
import PublicSiteShell from '../components/PublicSiteShell';
import { servicePages } from '../content/publicSite';

export const PublicServicePage: React.FC = () => {
  const { slug } = useParams();
  const page = servicePages.find((item) => item.slug === slug);
  const isSecurityPage = page?.slug === 'security';

  const securityReadinessSteps = [
    {
      title: 'Account verification',
      body: 'Keep invitation state, registration mode, and access posture explicit before users move forward.',
    },
    {
      title: 'Security setup',
      body: 'Guide users through password quality, 2FA readiness, and account hardening before workspace access.',
    },
    {
      title: 'Evaluation handoff',
      body: 'Return users to pricing and evaluation routes with context, not dead-end auth pages.',
    },
  ] as const;

  const securityOutcomeFlow = [
    {
      stage: 'Trust entry',
      detail: 'Increase trust before users even create an account.',
      note: 'First impression establishes confidence',
    },
    {
      stage: 'Keep context',
      detail: 'Keep authentication connected to pricing, product context, and onboarding.',
      note: 'No disconnected auth dead-ends',
    },
    {
      stage: 'Next-step clarity',
      detail: 'Reduce confusion about what happens after registration or sign-in.',
      note: 'Operators always know what comes next',
    },
  ] as const;

  const serviceOutcomeFlow = (page?.outcomes ?? []).map((outcome, index) => ({
    stage: `Step ${index + 1}`,
    detail: outcome,
    note:
      page?.slug === 'runtime'
        ? ([
            'Reduce response lag in live operations.',
            'Spot degraded streams early.',
            'Keep controls close to state.',
          ][index] ?? 'Keep operational decisions clear.')
        : ([
            'Improve research with market context.',
            'Support live decisions with narrative context.',
            'Increase trust through complete operator visibility.',
          ][index] ?? 'Support higher-confidence operator decisions.'),
  }));

  const outcomesHeadline = isSecurityPage
    ? 'Security outcomes for operators.'
    : page?.slug === 'runtime'
      ? 'Runtime outcomes for live operators.'
      : page?.slug === 'intelligence'
        ? 'Intelligence outcomes for operator decisions.'
        : 'Decisions operators can make.';

  const outcomesIntro = isSecurityPage
    ? 'Keep entry trust high by making account state, onboarding flow, and next-step clarity obvious at every stage.'
    : page?.slug === 'runtime'
      ? 'Keep live execution clear with visible state, explicit stream health, and faster action paths during runtime pressure.'
      : page?.slug === 'intelligence'
        ? 'Translate market context into operator decisions by connecting research framing, live narrative signals, and timing clarity.'
        : 'Clear operating context helps teams decide when a strategy, account, or runtime workflow is ready for the next step.';

  const serviceVariant =
    page?.slug === 'runtime'
      ? 'runtime'
      : page?.slug === 'intelligence'
        ? 'intelligence'
        : page?.slug === 'security'
          ? 'security'
          : 'research';

  const serviceVisualTags =
    page?.slug === 'runtime'
      ? ['Stream health', 'Action priority', 'Runtime continuity']
      : page?.slug === 'intelligence'
        ? ['Narrative context', 'Timing clarity', 'Conviction support']
        : page?.slug === 'security'
          ? ['Access trust', '2FA readiness', 'Onboarding clarity']
          : ['Backtest ranking', 'Risk framing', 'Promotion standard'];

  if (!page) {
    return <Navigate to="/" replace />;
  }

  const outcomeCards = isSecurityPage ? securityOutcomeFlow : serviceOutcomeFlow;

  return (
    <PublicSiteShell>
      <section className="public-shell-container space-y-5 py-6 md:py-8">
        <MotionReveal
          className="public-hero-panel rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6"
          distancePx={18}
        >
          <div className="surface-label">
            <Sparkles className="h-3.5 w-3.5" />
            {page.kicker}
          </div>
          <h1 className="mt-3 text-3xl font-semibold text-white sm:text-4xl">{page.title}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">{page.heroIntro}</p>

          <div className="public-actions-row mt-6 flex flex-col gap-3 sm:flex-row">
            <Link
              to="/register"
              className="premium-button premium-button-primary public-cta-primary justify-center px-6 py-3 text-sm font-semibold text-white"
            >
              Start free evaluation
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/pricing"
              className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium"
            >
              View pricing
            </Link>
          </div>
        </MotionReveal>

        <div className="grid gap-4 md:grid-cols-3">
          {page.heroStats.slice(0, 3).map(([label, body], index) => (
            <MotionReveal
              key={label}
              delayMs={index * 60}
              className="public-metric-card rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4"
            >
              <p className="text-[11px] font-semibold uppercase text-slate-500">{label}</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">{body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="public-shell-container pb-8">
        <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
          <MotionReveal
            className="public-section-panel rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
            distancePx={18}
          >
            <h2 className="text-lg font-semibold text-white">Core capabilities</h2>
            <p className="mt-1 text-sm text-slate-400">
              Practical capabilities this service layer adds to your operator workflow.
            </p>

            <div className="mt-4 space-y-3">
              {page.corePoints.map((point, index) => (
                <div
                  key={point.title}
                  className="public-tile-card rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                >
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                    0{index + 1}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-white">{point.title}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-400">{point.body}</p>
                </div>
              ))}
            </div>
          </MotionReveal>

          <MotionReveal
            className="public-section-panel rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
            delayMs={120}
            distancePx={18}
          >
            <ServicePulseIllustration variant={serviceVariant} />

            <div className="mt-4 flex flex-wrap gap-2">
              {serviceVisualTags.map((tag) => (
                <span key={tag} className="data-chip">
                  <span className="h-2 w-2 rounded-full bg-cyan-300" />
                  {tag}
                </span>
              ))}
            </div>

            {isSecurityPage && (
              <div className="mt-5 space-y-3">
                {securityReadinessSteps.map((step, index) => (
                  <div
                    key={step.title}
                    className="public-tile-card rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                  >
                    <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      Readiness 0{index + 1}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-white">{step.title}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">{step.body}</p>
                  </div>
                ))}
              </div>
            )}
          </MotionReveal>
        </div>
      </section>

      <section className="public-shell-container pb-8">
        <MotionReveal
          className="public-section-panel rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
          distancePx={18}
        >
          <div className="surface-label">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Operator outcomes
          </div>
          <h2 className="mt-3 text-2xl font-semibold text-white">{outcomesHeadline}</h2>
          <p className="mt-2 text-sm leading-7 text-slate-400">{outcomesIntro}</p>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {outcomeCards.map((item) => (
              <div
                key={item.stage + item.detail}
                className="public-outcome-card rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
              >
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  {item.stage}
                </p>
                <p className="mt-1 text-sm font-semibold text-white">{item.detail}</p>
                <p className="mt-1 text-xs leading-5 text-slate-400">{item.note}</p>
              </div>
            ))}
          </div>
        </MotionReveal>
      </section>

      <section className="public-shell-container pb-8">
        <div className="grid gap-6 lg:grid-cols-2">
          {page.operatorNotes.map((note, index) => (
            <MotionReveal
              key={note.label}
              delayMs={index * 70}
              className="public-note-card rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
            >
              <p className="text-[11px] font-semibold uppercase text-slate-500">{note.label}</p>
              <p className="mt-3 text-sm leading-7 text-slate-300">{note.body}</p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section className="public-shell-container pb-10">
        <MotionReveal
          className="public-section-panel public-cta-panel rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6"
          distancePx={18}
        >
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr),auto] lg:items-center">
            <div>
              <div className="surface-label">
                <ShieldCheck className="h-4 w-4" />
                Continue the journey
              </div>
              <h2 className="mt-3 text-2xl font-semibold text-white">
                Continue from {page.navLabel.toLowerCase()} into evaluation.
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-400">
                Review pricing, create an account, and complete security onboarding before live
                access.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
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
                Start free evaluation
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </MotionReveal>
      </section>
    </PublicSiteShell>
  );
};

export default PublicServicePage;
