import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Coins, ExternalLink, FileText, ShieldCheck } from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import BrandMark from '../components/BrandMark';
import { icoLaunchpadContent } from '../content/publicSite';

export const IcoLaunchpadPage = () => {
  const [countdownNow, setCountdownNow] = useState<number>(() => Date.now());
  const [whitelistEmail, setWhitelistEmail] = useState('');

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setCountdownNow(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  const countdown = useMemo(() => {
    const targetTime = new Date(icoLaunchpadContent.countdownTargetUtc).getTime();
    const remainingMs = Math.max(targetTime - countdownNow, 0);

    const totalSeconds = Math.floor(remainingMs / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    return {
      isLive: remainingMs === 0,
      parts: [
        { label: 'Days', value: String(days).padStart(2, '0') },
        { label: 'Hours', value: String(hours).padStart(2, '0') },
        { label: 'Minutes', value: String(minutes).padStart(2, '0') },
        { label: 'Seconds', value: String(seconds).padStart(2, '0') },
      ],
    };
  }, [countdownNow]);

  const whitelistMailto = useMemo(() => {
    const subject = encodeURIComponent(
      `Whitelist request - ${icoLaunchpadContent.tokenSymbol} public sale`
    );
    const body = encodeURIComponent(
      `Hello ExecutionLab team,\n\nPlease consider this email for ICO whitelist access:\n${whitelistEmail || '[your email]'}\n\nThanks.`
    );
    return `mailto:${icoLaunchpadContent.whitelistContactEmail}?subject=${subject}&body=${body}`;
  }, [whitelistEmail]);

  const calendarDetails = useMemo(() => {
    const startDate = new Date(icoLaunchpadContent.calendarEventStartUtc);
    const endDate = new Date(icoLaunchpadContent.calendarEventEndUtc);
    const dubaiTimezone = 'Asia/Dubai';

    const formatGoogleTimestamp = (value: Date): string =>
      value
        .toISOString()
        .replace(/[-:]/g, '')
        .replace(/\.\d{3}Z$/, 'Z');

    const escapeIcsText = (value: string): string =>
      value.replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');

    const googleUrl = new URL('https://calendar.google.com/calendar/render');
    googleUrl.searchParams.set('action', 'TEMPLATE');
    googleUrl.searchParams.set('text', icoLaunchpadContent.calendarEventTitle);
    googleUrl.searchParams.set('details', icoLaunchpadContent.calendarEventDescription);
    googleUrl.searchParams.set('location', icoLaunchpadContent.calendarEventLocation);
    googleUrl.searchParams.set(
      'dates',
      `${formatGoogleTimestamp(startDate)}/${formatGoogleTimestamp(endDate)}`
    );

    const icsContent = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//ExecutionLab//ICO Launchpad//EN',
      'CALSCALE:GREGORIAN',
      'BEGIN:VEVENT',
      `UID:exl-ico-${formatGoogleTimestamp(startDate)}@executionlab.io`,
      `DTSTAMP:${formatGoogleTimestamp(new Date())}`,
      `DTSTART:${formatGoogleTimestamp(startDate)}`,
      `DTEND:${formatGoogleTimestamp(endDate)}`,
      `SUMMARY:${escapeIcsText(icoLaunchpadContent.calendarEventTitle)}`,
      `DESCRIPTION:${escapeIcsText(icoLaunchpadContent.calendarEventDescription)}`,
      `LOCATION:${escapeIcsText(icoLaunchpadContent.calendarEventLocation)}`,
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n');

    return {
      googleCalendarUrl: googleUrl.toString(),
      icsContent,
      localEventTimeLabel: startDate.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: dubaiTimezone,
      }),
      dubaiTimezone,
    };
  }, []);

  const handleWhitelistSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!whitelistEmail.trim()) {
      return;
    }
    window.location.href = whitelistMailto;
  };

  const handleDownloadIcs = () => {
    const file = new Blob([calendarDetails.icsContent], { type: 'text/calendar;charset=utf-8' });
    const fileUrl = URL.createObjectURL(file);
    const anchor = document.createElement('a');
    anchor.href = fileUrl;
    anchor.download = 'executionlab-ico-reminder.ics';
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(fileUrl);
  };

  return (
    <main className="premium-shell light-dark-surface coming-soon-surface min-h-screen overflow-hidden text-white">
      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center sm:gap-4">
          <BrandMark subtitle="Token launch briefing" />
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <Link
              to="/"
              className="premium-button premium-button-secondary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to coming soon
            </Link>
            <Link
              to="/login"
              className="premium-button premium-button-primary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm text-white"
            >
              Existing credentials sign in
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </header>

        <section className="grid flex-1 items-stretch gap-6 py-10 lg:grid-cols-2 lg:py-12">
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="relative overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-950/70 p-6 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.75)] sm:p-7 lg:p-8"
          >
            <motion.div
              aria-hidden="true"
              className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-cyan-500/10 blur-3xl"
              animate={{ scale: [1, 1.08, 1], opacity: [0.35, 0.55, 0.35] }}
              transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }}
            />

            <div className="surface-label">
              <Coins className="h-3.5 w-3.5" />
              {icoLaunchpadContent.pageKicker}
            </div>

            <h1 className="fintech-heading mt-5 text-3xl font-semibold text-white sm:text-4xl lg:text-5xl">
              {icoLaunchpadContent.pageTitle}
            </h1>

            <p className="fintech-copy mt-4 max-w-2xl text-sm sm:text-base">
              {icoLaunchpadContent.pageSummary}
            </p>

            <div className="fintech-soft-strip mt-5 px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-white">
                  {icoLaunchpadContent.countdownLabel}
                </p>
                <span className="fintech-pill inline-flex px-2 py-0.5 text-[11px] text-slate-300">
                  {countdown.isLive ? 'Live now' : 'Pending'}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {countdown.parts.map((part) => (
                  <div
                    key={part.label}
                    className="rounded-lg border border-slate-700/60 bg-slate-900/70 px-3 py-2"
                  >
                    <p className="text-lg font-semibold text-white">{part.value}</p>
                    <p className="text-[11px] uppercase tracking-wide text-slate-400">
                      {part.label}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                <a
                  href={calendarDetails.googleCalendarUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="premium-button premium-button-secondary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs sm:text-sm"
                >
                  {icoLaunchpadContent.calendarCtaLabel}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
                <button
                  type="button"
                  onClick={handleDownloadIcs}
                  className="premium-button premium-button-secondary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs sm:text-sm"
                >
                  Download calendar file (.ics)
                </button>
              </div>

              <p className="mt-2 text-xs text-slate-400">
                Event time in Dubai timezone: {calendarDetails.localEventTimeLabel} ({' '}
                {calendarDetails.dubaiTimezone})
              </p>
            </div>

            <div className="grid gap-3 pt-6 sm:grid-cols-2">
              <div className="fintech-soft-strip px-4 py-3">
                <p className="text-[11px] uppercase text-slate-500">Token</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {icoLaunchpadContent.tokenName} ({icoLaunchpadContent.tokenSymbol})
                </p>
                <p className="mt-1 text-xs text-slate-400">{icoLaunchpadContent.network}</p>
              </div>
              <div className="fintech-soft-strip px-4 py-3">
                <p className="text-[11px] uppercase text-slate-500">Sale status</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {icoLaunchpadContent.saleStatus}
                </p>
                <p className="mt-1 text-xs text-slate-400">Controlled release</p>
              </div>
              <div className="fintech-soft-strip px-4 py-3">
                <p className="text-[11px] uppercase text-slate-500">Supply</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {icoLaunchpadContent.totalSupply}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {icoLaunchpadContent.publicAllocation}
                </p>
              </div>
              <div className="fintech-soft-strip px-4 py-3">
                <p className="text-[11px] uppercase text-slate-500">Fundraising target</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {icoLaunchpadContent.targetRaise}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Soft cap {icoLaunchpadContent.softCap} • Hard cap {icoLaunchpadContent.hardCap}
                </p>
              </div>
            </div>

            <div className="fintech-flow-divider mt-5 pt-4">
              <p className="fintech-kicker">Utility highlights</p>
              <ul className="mt-3 space-y-2">
                {icoLaunchpadContent.utilityHighlights.map((item) => (
                  <li key={item} className="text-sm text-slate-300">
                    • {item}
                  </li>
                ))}
              </ul>
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06, duration: 0.35, ease: 'easeOut' }}
            className="space-y-6 rounded-2xl border border-slate-700/70 bg-slate-950/70 p-6 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.75)] sm:p-7 lg:p-8"
          >
            <div className="flex items-center gap-2 text-cyan-300">
              <FileText className="h-4 w-4" />
              <p className="text-sm font-semibold text-white">Launch resources</p>
            </div>

            <form
              onSubmit={handleWhitelistSubmit}
              className="fintech-soft-strip space-y-3 px-4 py-4"
            >
              <div>
                <p className="text-sm font-semibold text-white">Whitelist request</p>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  {icoLaunchpadContent.whitelistHelperCopy}
                </p>
              </div>

              <div>
                <label
                  htmlFor="ico-whitelist-email"
                  className="mb-2 block text-xs font-medium text-slate-300"
                >
                  Contact email
                </label>
                <input
                  id="ico-whitelist-email"
                  type="email"
                  value={whitelistEmail}
                  onChange={(event) => setWhitelistEmail(event.target.value)}
                  className="premium-input"
                  placeholder="you@company.com"
                  required
                />
              </div>

              <button
                type="submit"
                className="premium-button premium-button-primary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm text-white"
              >
                {icoLaunchpadContent.whitelistCtaLabel}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>

            <div className="grid gap-3">
              {icoLaunchpadContent.resources.map((resource) => (
                <div key={resource.title} className="fintech-soft-strip px-4 py-4">
                  <p className="text-sm font-semibold text-white">{resource.title}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-400">{resource.description}</p>

                  {resource.href ? (
                    <a
                      href={resource.href}
                      target="_blank"
                      rel="noreferrer"
                      className="premium-button premium-button-secondary mt-3 inline-flex items-center gap-2 px-3 py-2 text-xs"
                    >
                      {resource.ctaLabel}
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : (
                    <span className="fintech-pill mt-3 inline-flex px-2.5 py-1 text-xs text-slate-300">
                      {resource.ctaLabel}
                    </span>
                  )}
                </div>
              ))}
            </div>

            <div className="fintech-flow-divider pt-4">
              <div className="flex items-center gap-2 text-emerald-300">
                <ShieldCheck className="h-4 w-4" />
                <p className="text-sm font-semibold text-white">Sale timeline</p>
              </div>

              <div className="mt-3 grid gap-2">
                {icoLaunchpadContent.timeline.map((item) => (
                  <div
                    key={`${item.phase}-${item.window}`}
                    className="fintech-soft-strip px-4 py-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-white">{item.phase}</p>
                      <span className="fintech-pill inline-flex px-2 py-0.5 text-[11px] text-slate-300">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{item.window}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-xs leading-5 text-amber-100/85">
              {icoLaunchpadContent.legalNote}
            </div>
          </motion.section>
        </section>
      </div>
    </main>
  );
};

export default IcoLaunchpadPage;
