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
  const usesPricingOutcomeLayout = page?.slug === 'runtime' || page?.slug === 'intelligence';

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

  const outcomesModelLabel = page?.slug === 'runtime' ? 'Runtime model' : 'Intelligence model';
  const outcomesModelTitle =
    page?.slug === 'runtime' ? 'From state to action' : 'From context to conviction';
  const outcomesModelStatus = page?.slug === 'runtime' ? 'Live-ready' : 'Signal-rich';

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

  return (
    <PublicSiteShell>
      <section
        className={`service-hero public-shell-container ${isSecurityPage ? 'service-hero-security' : ''}`}
      >
        <MotionReveal className="service-hero-grid lg:items-end">
          <div>
            <div className="surface-label">
              <Sparkles className="h-3.5 w-3.5" />
              {page.kicker}
            </div>
            <h1
              className={`max-w-4xl text-4xl font-bold leading-[1.06] text-white sm:text-5xl ${
                isSecurityPage ? 'mt-4' : 'mt-6'
              }`}
            >
              {page.title}
            </h1>
          </div>
          <p
            className={`max-w-2xl text-base text-slate-300 ${
              isSecurityPage ? 'leading-7 lg:self-start lg:pt-1' : 'leading-8 lg:pb-1'
            }`}
          >
            {page.heroIntro}
          </p>
        </MotionReveal>

        <MotionReveal
          delayMs={100}
          className={`service-stats ${isSecurityPage ? 'mt-7' : 'mt-10'}`}
        >
          <div className="service-stats-grid">
            {page.heroStats.map(([label, body]) => (
              <div key={label} className="service-stat-item">
                <p className="text-sm font-semibold text-cyan-300">{label}</p>
                <p
                  className={`mt-2 leading-6 text-slate-300 ${isSecurityPage ? 'text-base' : 'text-sm'}`}
                >
                  {body}
                </p>
              </div>
            ))}
          </div>
        </MotionReveal>

        <MotionReveal delayMs={130} className="service-visual-panel mt-7">
          <ServicePulseIllustration variant={serviceVariant} />
          <div className="service-visual-tags mt-4">
            {serviceVisualTags.map((tag) => (
              <span key={tag} className="data-chip">
                <span className="h-2 w-2 rounded-full bg-cyan-300" />
                {tag}
              </span>
            ))}
          </div>
        </MotionReveal>

        {isSecurityPage && (
          <MotionReveal delayMs={150} className="security-readiness-panel mt-6">
            <div>
              <p className="text-[11px] font-semibold uppercase text-slate-500">Readiness flow</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                Security before workspace access.
              </p>
            </div>

            <div className="security-readiness-grid mt-6">
              {securityReadinessSteps.map((step, index) => (
                <div key={step.title} className="security-readiness-card">
                  <p className="font-mono text-xs text-cyan-300">0{index + 1}</p>
                  <p className="mt-2 text-base font-semibold text-white">{step.title}</p>
                  <p className="mt-2 text-sm leading-7 text-slate-300">{step.body}</p>
                </div>
              ))}
            </div>
          </MotionReveal>
        )}
      </section>

      <section className={`service-core-shell ${isSecurityPage ? 'service-core-security' : ''}`}>
        <div className="public-shell-container service-core-grid">
          {page.corePoints.map((point, index) => (
            <MotionReveal key={point.title} delayMs={index * 70} className="service-core-card">
              <p className="font-mono text-sm text-emerald-300">0{index + 1}</p>
              <h2 className="mt-4 text-2xl font-semibold text-white">{point.title}</h2>
              <p
                className={`mt-4 leading-7 text-slate-300 ${isSecurityPage ? 'text-base' : 'text-sm'}`}
              >
                {point.body}
              </p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section
        className={`service-outcomes public-shell-container ${
          isSecurityPage ? 'service-outcomes-security' : ''
        } ${usesPricingOutcomeLayout ? 'service-outcomes-compact' : ''}`}
      >
        <MotionReveal className="grid gap-8 lg:grid-cols-[minmax(0,0.95fr),minmax(22rem,0.65fr)]">
          <div>
            <div className="surface-label">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Operator outcomes
            </div>
            <h2 className="mt-5 text-3xl font-bold text-white">{outcomesHeadline}</h2>
          </div>
          {isSecurityPage ? (
            <p className="max-w-2xl text-base leading-8 text-slate-300 lg:pt-14">{outcomesIntro}</p>
          ) : (
            <p className="max-w-2xl text-sm leading-7 text-slate-400 lg:pt-10">{outcomesIntro}</p>
          )}
        </MotionReveal>

        {isSecurityPage ? (
          <MotionReveal delayMs={80} className="pricing-model-panel mt-6">
            <div className="pricing-model-header">
              <div>
                <p className="text-[11px] font-semibold uppercase text-slate-400">Security model</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  Clear onboarding progression
                </p>
              </div>
              <p className="pricing-model-open">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                Active
              </p>
            </div>

            <div className="pricing-model-flow mt-5">
              {securityOutcomeFlow.map((item, index) => (
                <div key={item.stage} className="pricing-model-card">
                  <p className="pricing-model-step">Step {index + 1}</p>
                  <p className="mt-2 text-base font-semibold text-white">{item.stage}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-200">{item.detail}</p>
                  <p className="mt-3 text-xs text-slate-400">{item.note}</p>
                </div>
              ))}
            </div>
          </MotionReveal>
        ) : usesPricingOutcomeLayout ? (
          <MotionReveal delayMs={80} className="pricing-model-panel mt-6">
            <div className="pricing-model-header">
              <div>
                <p className="text-[11px] font-semibold uppercase text-slate-400">
                  {outcomesModelLabel}
                </p>
                <p className="mt-2 text-2xl font-semibold text-white">{outcomesModelTitle}</p>
              </div>
              <p className="pricing-model-open">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                {outcomesModelStatus}
              </p>
            </div>

            <div className="pricing-model-flow mt-5">
              {serviceOutcomeFlow.map((item) => (
                <div key={item.detail} className="pricing-model-card">
                  <p className="pricing-model-step">{item.stage}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-200">{item.detail}</p>
                  <p className="mt-3 text-xs text-slate-400">{item.note}</p>
                </div>
              ))}
            </div>
          </MotionReveal>
        ) : (
          <div className="service-outcome-list mt-10">
            {page.outcomes.map((outcome, index) => (
              <MotionReveal key={outcome} delayMs={index * 60}>
                <div className="service-outcome-item grid gap-4 py-5 md:grid-cols-[4rem,1fr] md:items-start">
                  <span className="font-mono text-sm text-cyan-300">0{index + 1}</span>
                  <p className="text-lg leading-8 text-slate-200">{outcome}</p>
                </div>
              </MotionReveal>
            ))}
          </div>
        )}
      </section>

      <section
        className={`service-notes public-shell-container ${isSecurityPage ? 'service-notes-security' : ''}`}
      >
        <div
          className={`service-notes-grid grid lg:grid-cols-2 ${isSecurityPage ? 'gap-8' : 'gap-6'}`}
        >
          {page.operatorNotes.map((note, index) => (
            <MotionReveal key={note.label} delayMs={index * 80} className="service-note-card">
              <p className="text-[11px] font-semibold uppercase text-slate-500">{note.label}</p>
              <p
                className={`mt-3 leading-8 text-slate-200 ${isSecurityPage ? 'text-base' : 'text-lg'}`}
              >
                {note.body}
              </p>
            </MotionReveal>
          ))}
        </div>
      </section>

      <section
        className={`service-cta public-shell-container ${isSecurityPage ? 'service-cta-security' : ''}`}
      >
        <MotionReveal className="service-cta-inner grid gap-8 lg:grid-cols-[minmax(0,0.95fr),minmax(22rem,0.65fr)] lg:items-center">
          <div>
            <div className="surface-label">
              <ShieldCheck className="h-4 w-4" />
              Continue the journey
            </div>
            <h2 className="mt-5 text-3xl font-bold text-white">
              Continue from {page.navLabel.toLowerCase()} into evaluation.
            </h2>
          </div>
          <div>
            <p className="max-w-2xl text-sm leading-7 text-slate-400">
              Review pricing, create an account, and complete security onboarding before live
              access.
            </p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/pricing"
                className="premium-button premium-button-secondary justify-center px-6 py-3 text-sm font-medium"
              >
                View pricing
              </Link>
              <Link
                to="/register"
                className="premium-button premium-button-primary justify-center px-6 py-3 text-sm font-semibold text-white"
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
