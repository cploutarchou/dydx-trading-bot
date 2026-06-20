import {
  ArrowRight,
  CheckCircle2,
  FileText,
  FlaskConical,
  LockKeyhole,
  Search,
  ShieldCheck,
} from 'lucide-react';
import {
  PublicLaunchShell,
  PublicStatusPill,
  PrimaryButton,
  SecondaryButton,
} from '../components/PublicPagePrimitives';
import { comingSoonMarketingContent } from '../content/publicSite';

interface ComingSoonPageProps {
  message?: string;
}

const capabilities = [
  {
    icon: Search,
    title: 'Research',
    body: 'Review market context and strategy assumptions before validation.',
  },
  {
    icon: FlaskConical,
    title: 'Validate',
    body: 'Use backtests and run history to check strategy behavior.',
  },
  {
    icon: ShieldCheck,
    title: 'Operate',
    body: 'Monitor approved dYdX bot workflows from the workspace.',
  },
];

const nextSteps = [
  {
    icon: LockKeyhole,
    title: 'Approved users',
    body: 'Sign in with your existing credentials.',
  },
  {
    icon: CheckCircle2,
    title: 'New access',
    body: 'Public onboarding is paused during launch preparation.',
  },
  {
    icon: FileText,
    title: 'ICO briefing',
    body: comingSoonMarketingContent.icoAnnouncement,
  },
];

export const ComingSoonPage = ({ message }: ComingSoonPageProps) => {
  const launchMessage =
    message?.trim() || 'Public onboarding remains paused while controlled access is prepared.';

  return (
    <PublicLaunchShell logoSubtitle="DeFi execution platform" backgroundVariant="launch">
      <section
        className="grid flex-1 items-center gap-8 py-10 md:py-12 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-12 lg:py-16"
        aria-labelledby="coming-soon-heading"
      >
        <div className="max-w-[680px]">
          <PublicStatusPill tone="info">Controlled access</PublicStatusPill>
          <h1
            id="coming-soon-heading"
            className="mt-6 max-w-4xl text-[clamp(2.5rem,5.4vw,4.3rem)] font-semibold leading-[1.02] tracking-normal text-white"
          >
            ExecutionLab is in controlled access.
          </h1>
          <p className="mt-5 max-w-[58ch] text-lg leading-8 text-slate-300">
            Approved users can sign in. Public onboarding is paused while launch access is
            prepared.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <PrimaryButton to="/login" className="min-h-12 px-5">
              Sign in
              <ArrowRight className="h-4 w-4" />
            </PrimaryButton>
            <SecondaryButton to="/ico" className="min-h-12 px-5">
              Review ICO briefing
            </SecondaryButton>
          </div>

          <div className="mt-8 rounded-lg border border-amber-400/20 bg-amber-500/10 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-200">
              Current status
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-200">{launchMessage}</p>
          </div>
        </div>

        <aside
          className="rounded-lg border border-slate-700/70 bg-slate-950/70 p-5 shadow-2xl shadow-black/25"
          aria-labelledby="next-steps-heading"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-cyan-300">
            What to do now
          </p>
          <h2 id="next-steps-heading" className="mt-2 text-2xl font-semibold text-white">
            Start with the right path.
          </h2>
          <div className="mt-5 space-y-3">
            {nextSteps.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.title}
                  className="flex gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-200">
                    <Icon className="h-4 w-4" />
                  </span>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{item.title}</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-400">{item.body}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>
      </section>

      <section id="product-scope" className="scroll-mt-8 pb-12 md:pb-16">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-cyan-300">
            Workspace focus
          </p>
          <h2 className="mt-2 text-3xl font-semibold leading-tight text-white md:text-4xl">
            Research, validate, operate.
          </h2>
          <p className="mt-3 text-base leading-7 text-slate-300">
            ExecutionLab is built around the core workflow needed before a strategy reaches live
            runtime.
          </p>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {capabilities.map((item) => {
            const Icon = item.icon;
            return (
              <article
                key={item.title}
                className="rounded-lg border border-slate-700/70 bg-slate-950/60 p-5"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-200">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold text-white">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">{item.body}</p>
              </article>
            );
          })}
        </div>
      </section>
    </PublicLaunchShell>
  );
};

export default ComingSoonPage;
