export interface PublicNavItem {
  label: string;
  path: string;
  summary?: string;
}

export interface ServicePageData {
  slug: string;
  path: string;
  navLabel: string;
  kicker: string;
  title: string;
  summary: string;
  heroIntro: string;
  heroStats: Array<[string, string]>;
  corePoints: Array<{ title: string; body: string }>;
  outcomes: string[];
  operatorNotes: Array<{ label: string; body: string }>;
}

export const servicePages: ServicePageData[] = [
  {
    slug: 'research',
    path: '/services/research',
    navLabel: 'Research',
    kicker: 'Research Desk',
    title: 'Validate arbitrage strategies before they reach live operation.',
    summary: 'Backtests, rankings, and comparative analysis for disciplined operator decisions.',
    heroIntro:
      'Rank strategy candidates, inspect risk-adjusted performance, and decide what deserves operator attention before capital is exposed.',
    heroStats: [
      ['Compare', 'Backtest quality across candidates'],
      ['Control risk', 'Drawdown and Sharpe stay visible'],
      ['Audit', 'Every run remains inspectable'],
    ],
    corePoints: [
      {
        title: 'Backtest intelligence',
        body: 'Rank strategies with profitability, consistency, drawdown discipline, and risk-adjusted return in one place.',
      },
      {
        title: 'Operator-grade evidence',
        body: 'Surface the metrics that matter before promotion: PnL shape, win rate, Sharpe, and confidence from repeated runs.',
      },
      {
        title: 'Clean transition to runtime',
        body: 'Research outputs should naturally feed runtime decisions instead of becoming static reports nobody trusts.',
      },
    ],
    outcomes: [
      'Cut spreadsheet drift by keeping research evidence next to strategy rankings.',
      'Promote strategies with measurable performance and risk context.',
      'Keep historical runs available while new tests are still active.',
    ],
    operatorNotes: [
      {
        label: 'Research discipline',
        body: 'Strong operators need fast comparison, clear loss boundaries, and enough history to reject weak setups quickly.',
      },
      {
        label: 'Promotion standard',
        body: 'A strategy moves forward only when its return profile, drawdown behavior, and repeatability are easy to defend.',
      },
    ],
  },
  {
    slug: 'runtime',
    path: '/services/runtime',
    navLabel: 'Runtime',
    kicker: 'Runtime Control',
    title: 'Control live arbitrage bots with clear state, health, and recovery context.',
    summary:
      'Bot control, state visibility, and action flows designed for live operating conditions.',
    heroIntro:
      'Translate bot state into instant decisions by keeping stream health, execution context, and action paths visible without operational drag.',
    heroStats: [
      ['Realtime', 'Stream health stays visible'],
      ['Actionable', 'Controls stay near state'],
      ['Resilient', 'Degraded modes are explicit'],
    ],
    corePoints: [
      {
        title: 'Bot management',
        body: 'Create, start, stop, and inspect instances from a runtime desk that makes health and degraded-state cues obvious.',
      },
      {
        title: 'Stable live updates',
        body: 'Keep already-rendered context in place while the backend refreshes or reconnects instead of blowing away the screen.',
      },
      {
        title: 'Operational trust',
        body: 'If a stream is reconnecting or a runtime is degraded, the interface should say so clearly and immediately.',
      },
    ],
    outcomes: [
      'Spot state changes faster and act on them with less friction.',
      'Keep stream health and bot state visible so operators never guess about degradation.',
      'Reduce action lag by placing controls where the state is most urgent.',
    ],
    operatorNotes: [
      {
        label: 'Operating posture',
        body: 'A runtime desk needs compact state, clean action priority, and confidence that refreshes will not erase context.',
      },
      {
        label: 'Decision cost',
        body: 'Live operations punish ambiguity. Clear state and clean action hierarchy reduce the cost of every operational decision.',
      },
    ],
  },
  {
    slug: 'intelligence',
    path: '/services/intelligence',
    navLabel: 'Market Intel',
    kicker: 'Market Intelligence',
    title: 'Read market context beside every strategy and runtime decision.',
    summary:
      'Asset context, market pulse, and supporting intelligence that strengthens research and runtime judgment.',
    heroIntro:
      'Build operator conviction by pairing performance data, asset behavior, and market narrative so decisions rest on complete context.',
    heroStats: [
      ['Contextual', 'Signals tied to market conditions'],
      ['Readable', 'Fast summaries without noise'],
      ['Connected', 'Research and runtime stay informed'],
    ],
    corePoints: [
      {
        title: 'Asset context',
        body: 'Explain the assets behind the strategy so operators can connect performance with real market behavior.',
      },
      {
        title: 'Market awareness',
        body: 'Keep macro or narrative shifts available alongside product surfaces instead of hiding them in external tabs.',
      },
      {
        title: 'Decision support',
        body: 'The strongest intelligence helps operators decide what matters now without drowning them in unrelated feeds.',
      },
    ],
    outcomes: [
      'Connect research performance to live market behavior for stronger conviction.',
      'Give live operators the narrative context they need to trust their execution in real time.',
      'Reduce decision uncertainty by making market conditions and strategy reasoning equally visible.',
    ],
    operatorNotes: [
      {
        label: 'Signal quality',
        body: 'Market intelligence is most valuable when it explains current conditions without flooding the operator with noise.',
      },
      {
        label: 'Conviction building',
        body: 'When operators understand market conditions and strategy performance together, conviction becomes defensible and repeatable.',
      },
    ],
  },
  {
    slug: 'security',
    path: '/services/security',
    navLabel: 'Security',
    kicker: 'Security Onboarding',
    title: 'Move through premium account entry with clear security and access state.',
    summary: 'Security-aware entry, clearer account flow, and premium onboarding semantics.',
    heroIntro:
      'Sign-in, registration, and account readiness stay connected to the same operating journey, with clear routes back to the product overview.',
    heroStats: [
      ['Visible', 'Access state made explicit'],
      ['Connected', 'Auth shares main site navigation'],
      ['Structured', 'Security setup before live access'],
    ],
    corePoints: [
      {
        title: 'Return navigation',
        body: 'Auth pages need clear paths back to the site so users never feel trapped inside a disconnected utility flow.',
      },
      {
        title: 'Shared public chrome',
        body: 'Menu bar, CTAs, and page hierarchy should remain consistent across landing, service pages, pricing, login, and register.',
      },
      {
        title: 'Premium onboarding',
        body: 'Security setup, account readiness, and invitation state should be explained in plain product language.',
      },
    ],
    outcomes: [
      'Increase trust before users even create an account.',
      'Keep authentication connected to pricing, product context, and onboarding.',
      'Reduce confusion about what happens after registration or sign-in.',
    ],
    operatorNotes: [
      {
        label: 'Access confidence',
        body: 'Operators should understand where they are, what access they have, and what comes next before entering the workspace.',
      },
      {
        label: 'Trust signal',
        body: 'Clear onboarding reduces uncertainty around account setup, security posture, and live access.',
      },
    ],
  },
];

export const publicNavItems: PublicNavItem[] = [
  { label: 'Overview', path: '/' },
  ...servicePages.map((service) => ({
    label: service.navLabel,
    path: service.path,
    summary: service.summary,
  })),
  { label: 'Pricing', path: '/pricing' },
];

export const getPrimaryCta = (pathname: string) =>
  pathname === '/pricing'
    ? { href: '/register', label: 'Start free evaluation' }
    : { href: '/pricing', label: 'View pricing' };
