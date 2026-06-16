import { Activity, ArrowRight, BarChart3, FlaskConical, Search, ShieldCheck } from 'lucide-react';
import {
  LaunchStatusStrip,
  PublicCapabilityList,
  PublicLaunchShell,
  PublicSectionHeading,
  PublicStatusPill,
  ProductWorkflow,
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
    title: 'Research and signal evaluation',
    body: 'Compare market context, strategy hypotheses, and evidence before anything moves toward runtime.',
  },
  {
    icon: FlaskConical,
    title: 'Strategy validation',
    body: 'Review backtests, assumptions, and run history before controlled promotion decisions.',
  },
  {
    icon: ShieldCheck,
    title: 'Controlled execution and monitoring',
    body: 'Keep runtime access gated behind approved credentials, health state, and operator review.',
  },
];

const workflowSteps = [
  {
    icon: Search,
    label: 'Research',
    description: 'Frame the signal and constraints.',
    status: 'Scope',
  },
  {
    icon: BarChart3,
    label: 'Validate',
    description: 'Review backtest behavior and risk context.',
    status: 'Evidence',
  },
  {
    icon: Activity,
    label: 'Execute',
    description: 'Promote only through approved workflows.',
    status: 'Gated',
  },
  {
    icon: ShieldCheck,
    label: 'Monitor',
    description: 'Keep runtime state visible for operators.',
    status: 'Live',
  },
];

export const ComingSoonPage = ({ message }: ComingSoonPageProps) => {
  const launchMessage =
    message?.trim() || 'Public onboarding remains paused while controlled access is prepared.';

  return (
    <PublicLaunchShell logoSubtitle="DeFi execution platform" backgroundVariant="launch">
      <section className="grid flex-1 items-center gap-8 py-10 md:py-12 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-12 lg:py-14">
        <div className="max-w-[720px]">
          <PublicStatusPill tone="info">Controlled launch in progress</PublicStatusPill>
          <h1 className="mt-6 max-w-4xl text-[clamp(2.75rem,6vw,4.5rem)] font-semibold leading-[1.02] tracking-normal text-white">
            Controlled public access is opening.
          </h1>
          <p className="mt-5 max-w-[68ch] text-lg leading-8 text-slate-300">
            ExecutionLab brings research review, strategy validation, and monitored DeFi execution
            into one gated workspace for professional operators.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <PrimaryButton to="/login" className="min-h-12 px-5">
              Existing user sign in
              <ArrowRight className="h-4 w-4" />
            </PrimaryButton>
            <SecondaryButton to="/ico" className="min-h-12 px-5">
              ICO briefing
            </SecondaryButton>
          </div>

          <div className="mt-8 max-w-3xl">
            <LaunchStatusStrip
              items={[
                { label: 'Public access', value: launchMessage, tone: 'warning' },
                {
                  label: 'Existing users',
                  value: 'Approved credentials remain available',
                  tone: 'success',
                },
                {
                  label: 'ICO briefing',
                  value: comingSoonMarketingContent.icoAnnouncement,
                  tone: 'info',
                },
              ]}
            />
          </div>
        </div>

        <ProductWorkflow steps={workflowSteps} />
      </section>

      <section id="product-scope" className="scroll-mt-8 pb-12 md:pb-16">
        <PublicSectionHeading
          eyebrow="Product scope"
          title="Evidence-first execution workflows."
          description="The public workspace is intentionally staged around three core capabilities rather than open-ended onboarding."
        />
        <div className="mt-6">
          <PublicCapabilityList items={capabilities} />
        </div>
      </section>
    </PublicLaunchShell>
  );
};

export default ComingSoonPage;
