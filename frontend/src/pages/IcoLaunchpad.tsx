import { ArrowLeft, ArrowRight, FileText, ShieldCheck } from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Accordion,
  DocumentationPanel,
  PrimaryButton,
  PublicDisclosure,
  PublicLaunchShell,
  PublicSectionHeading,
  PublicStatusPill,
  SaleCountdown,
  SaleFacts,
  SaleTimeline,
  SecondaryButton,
  WhitelistForm,
} from '../components/PublicPagePrimitives';
import { icoLaunchpadContent } from '../content/publicSite';
import {
  buildWhitelistMailto,
  formatConfiguredDate,
  getCountdownState,
  isValidContactEmail,
} from '../utils/publicPages';

type WhitelistState = 'idle' | 'loading' | 'success' | 'error';

export const IcoLaunchpadPage = () => {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [whitelistEmail, setWhitelistEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [requestState, setRequestState] = useState<WhitelistState>('idle');

  useEffect(() => {
    const intervalId = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, []);

  const countdown = useMemo(
    () => getCountdownState(icoLaunchpadContent.countdownTargetUtc, nowMs),
    [nowMs]
  );

  const publicSaleDateLabel = useMemo(
    () =>
      formatConfiguredDate(
        icoLaunchpadContent.countdownTargetUtc,
        icoLaunchpadContent.saleTimezone
      ),
    []
  );

  const overviewFacts = [
    {
      label: 'Token',
      value: `${icoLaunchpadContent.tokenName} (${icoLaunchpadContent.tokenSymbol})`,
      helper: icoLaunchpadContent.network,
    },
    {
      label: 'Sale status',
      value: icoLaunchpadContent.saleStatus,
    },
    {
      label: 'Public sale date',
      value: publicSaleDateLabel,
      helper: icoLaunchpadContent.saleTimezone,
    },
    {
      label: 'Total supply',
      value: icoLaunchpadContent.totalSupply,
    },
    {
      label: 'Public allocation',
      value: icoLaunchpadContent.publicAllocation,
    },
  ];

  const keyFacts = [
    ...overviewFacts,
    {
      label: 'Fundraising target',
      value: icoLaunchpadContent.targetRaise,
      helper: `Soft cap ${icoLaunchpadContent.softCap}; hard cap ${icoLaunchpadContent.hardCap}`,
    },
  ];

  const handleWhitelistSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (requestState === 'loading' || requestState === 'success') {
      return;
    }

    const trimmedEmail = whitelistEmail.trim();

    if (!isValidContactEmail(trimmedEmail)) {
      setEmailError('Enter a valid email address.');
      setRequestState('error');
      return;
    }

    setEmailError('');
    setRequestState('loading');

    const mailto = buildWhitelistMailto({
      contactEmail: icoLaunchpadContent.whitelistContactEmail,
      requesterEmail: trimmedEmail,
      tokenSymbol: icoLaunchpadContent.tokenSymbol,
    });

    window.setTimeout(() => {
      try {
        window.location.href = mailto;
        setRequestState('success');
      } catch {
        setRequestState('error');
      }
    }, 250);
  };

  return (
    <PublicLaunchShell
      logoSubtitle="ICO briefing"
      utilityAction={{ label: 'Sign in', to: '/login' }}
    >
      <section className="py-10 md:py-12 lg:py-14">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_400px] lg:items-center">
          <div className="max-w-[760px]">
            <PublicStatusPill tone="warning">{icoLaunchpadContent.saleStatus}</PublicStatusPill>
            <h1 className="mt-6 text-[clamp(2.55rem,5vw,3.5rem)] font-semibold leading-[1.06] tracking-normal text-white">
              {icoLaunchpadContent.pageTitle}
            </h1>
            <p className="mt-5 max-w-[68ch] text-lg leading-8 text-slate-300">
              {icoLaunchpadContent.pageSummary}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <PrimaryButton href="#whitelist-request" className="min-h-12 px-5">
                {icoLaunchpadContent.whitelistCtaLabel}
                <ArrowRight className="h-4 w-4" />
              </PrimaryButton>
              <SecondaryButton href="#documentation" className="min-h-12 px-5">
                Review documentation
                <FileText className="h-4 w-4" />
              </SecondaryButton>
              <SecondaryButton to="/" className="min-h-12 px-5">
                <ArrowLeft className="h-4 w-4" />
                Launch page
              </SecondaryButton>
            </div>
          </div>

          <SaleCountdown
            state={countdown}
            label={icoLaunchpadContent.countdownLabel}
            targetLabel={publicSaleDateLabel}
            timezoneLabel={icoLaunchpadContent.saleTimezone}
            summary={[
              { label: 'Network', value: icoLaunchpadContent.network },
              { label: 'Token', value: icoLaunchpadContent.tokenSymbol },
              { label: 'Sale status', value: icoLaunchpadContent.saleStatus },
            ]}
          />
        </div>
      </section>

      <section className="space-y-6 pb-10 md:pb-12">
        <PublicSectionHeading
          eyebrow="Key sale information"
          title="Key sale facts"
          description="Configured campaign values are grouped here for quick review before final publication."
        />
        <SaleFacts facts={keyFacts} />
      </section>

      <section className="grid gap-6 pb-10 md:pb-12 lg:grid-cols-[minmax(0,1fr)_400px] lg:items-start">
        <div className="public-section-surface">
          <PublicSectionHeading
            eyebrow="Timeline"
            title="Sale timeline"
            description="Milestones stay compact on desktop and stack into a vertical sequence on mobile."
            compact
          />
          <div className="mt-6">
            <SaleTimeline items={icoLaunchpadContent.timeline} />
          </div>
        </div>

        <WhitelistForm
          email={whitelistEmail}
          emailError={emailError}
          requestState={requestState}
          helperCopy={icoLaunchpadContent.whitelistHelperCopy}
          ctaLabel={icoLaunchpadContent.whitelistCtaLabel}
          onEmailChange={(value) => {
            setWhitelistEmail(value);
            if (emailError) setEmailError('');
            if (requestState !== 'idle') setRequestState('idle');
          }}
          onSubmit={handleWhitelistSubmit}
        />
      </section>

      <section className="grid gap-6 pb-10 md:pb-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="public-section-surface">
          <PublicSectionHeading
            eyebrow="Token utility"
            title="Intended platform utility"
            description="Utility language is concise by design and remains subject to final published sale terms."
          />
          <div className="mt-6 space-y-3">
            {icoLaunchpadContent.utilityHighlights.map((item) => (
              <div key={item} className="flex gap-3 text-base leading-7 text-slate-300">
                <ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-cyan-200" />
                <span>{item}</span>
              </div>
            ))}
          </div>
          <p className="mt-5 text-sm leading-6 text-slate-400">
            Utility, eligibility, and access mechanics are subject to final published terms.
          </p>
        </div>

        <DocumentationPanel resources={icoLaunchpadContent.resources} />
      </section>

      <section className="pb-12 md:pb-16">
        <div className="grid gap-3 lg:grid-cols-3">
          <PublicDisclosure title="Risk and compliance notice">
            <p>{icoLaunchpadContent.legalNote}</p>
          </PublicDisclosure>
          <Accordion title="Participation policy">
            <p>
              Participation may require eligibility checks, KYC review, jurisdiction screening, and
              final sale terms. The configured documentation link will be updated when the policy is
              published.
            </p>
          </Accordion>
          <Accordion title="Calendar reminder">
            <p>
              Public sale timing is shown from the configured UTC date and displayed in{' '}
              {icoLaunchpadContent.saleTimezone}. If the configured date changes, this briefing and
              countdown update from the same content source.
            </p>
          </Accordion>
        </div>
      </section>
    </PublicLaunchShell>
  );
};

export default IcoLaunchpadPage;
