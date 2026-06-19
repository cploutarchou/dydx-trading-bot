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

export interface IcoResourceItem {
  title: string;
  description: string;
  href?: string;
  ctaLabel: string;
}

export interface IcoTimelineItem {
  phase: string;
  window: string;
  status: string;
}

export const servicePages: ServicePageData[] = [
  {
    slug: 'research',
    path: '/services/research',
    navLabel: 'Research',
    kicker: 'Discovery Lab',
    title: 'Validate technical direction before execution work starts.',
    summary:
      'Research, system framing, and comparative analysis for disciplined product decisions.',
    heroIntro:
      'Turn ambiguous ideas into evidence-backed execution plans by clarifying scope, risk, system constraints, and the next build decision.',
    heroStats: [
      ['Compare', 'Execution paths across candidates'],
      ['Control risk', 'Scope and constraints stay visible'],
      ['Audit', 'Every decision remains inspectable'],
    ],
    corePoints: [
      {
        title: 'Discovery intelligence',
        body: 'Rank product and automation ideas by feasibility, implementation cost, risk, and expected operational value.',
      },
      {
        title: 'Operator-grade evidence',
        body: 'Surface the signals that matter before promotion: constraints, dependencies, failure modes, and delivery confidence.',
      },
      {
        title: 'Clean transition to build',
        body: 'Research outputs should naturally feed engineering execution instead of becoming static documents nobody uses.',
      },
    ],
    outcomes: [
      'Reduce ambiguity by keeping research evidence next to delivery decisions.',
      'Promote initiatives with measurable value and risk context.',
      'Keep historical decisions available while new experiments are still active.',
    ],
    operatorNotes: [
      {
        label: 'Research discipline',
        body: 'Strong teams need fast comparison, clear constraints, and enough context to reject weak execution paths quickly.',
      },
      {
        label: 'Promotion standard',
        body: 'An idea moves forward only when value, risk, constraints, and implementation approach are easy to defend.',
      },
    ],
  },
  {
    slug: 'runtime',
    path: '/services/runtime',
    navLabel: 'Runtime',
    kicker: 'Automation Runtime',
    title: 'Run automated systems with clear state, health, and recovery context.',
    summary:
      'Runtime control, state visibility, and action flows designed for production operating conditions.',
    heroIntro:
      'Translate system state into instant decisions by keeping health, execution context, and action paths visible without operational drag.',
    heroStats: [
      ['Realtime', 'System health stays visible'],
      ['Actionable', 'Controls stay near state'],
      ['Resilient', 'Degraded modes are explicit'],
    ],
    corePoints: [
      {
        title: 'Runtime management',
        body: 'Create, start, stop, and inspect automations from a runtime desk that makes health and degraded-state cues obvious.',
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
      'Keep system health and runtime state visible so operators never guess about degradation.',
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
    navLabel: 'Intelligence',
    kicker: 'Execution Intelligence',
    title: 'Read product and system context beside every execution decision.',
    summary:
      'System context, signal review, and supporting intelligence that strengthens research and runtime judgment.',
    heroIntro:
      'Build operator conviction by pairing delivery signals, system behavior, and technical narrative so decisions rest on complete context.',
    heroStats: [
      ['Contextual', 'Signals tied to system conditions'],
      ['Readable', 'Fast summaries without noise'],
      ['Connected', 'Research and runtime stay informed'],
    ],
    corePoints: [
      {
        title: 'System context',
        body: 'Explain the systems behind the workflow so operators can connect performance with real implementation behavior.',
      },
      {
        title: 'Execution awareness',
        body: 'Keep technical shifts, constraints, and delivery narrative available alongside product surfaces instead of hiding them in external tabs.',
      },
      {
        title: 'Decision support',
        body: 'The strongest intelligence helps operators decide what matters now without drowning them in unrelated feeds.',
      },
    ],
    outcomes: [
      'Connect research performance to live system behavior for stronger conviction.',
      'Give operators the technical context they need to trust execution in real time.',
      'Reduce decision uncertainty by making market conditions and strategy reasoning equally visible.',
    ],
    operatorNotes: [
      {
        label: 'Signal quality',
        body: 'Execution intelligence is most valuable when it explains current conditions without flooding the operator with noise.',
      },
      {
        label: 'Conviction building',
        body: 'When operators understand system conditions and delivery performance together, conviction becomes defensible and repeatable.',
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
      'Sign-in, registration, and account readiness stay connected to the same execution journey, with clear routes back to the product overview.',
    heroStats: [
      ['Visible', 'Access state made explicit'],
      ['Connected', 'Auth shares main site navigation'],
      ['Structured', 'Security setup before execution access'],
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
        body: 'Clear onboarding reduces uncertainty around account setup, security posture, and execution access.',
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
    ? { href: '/register', label: 'Start execution review' }
    : { href: '/register', label: 'Request access' };

/**
 * Launch campaign copy lives here.
 * Update `icoAnnouncement` for marketing edits instead of touching page JSX.
 */
export const comingSoonMarketingContent: {
  icoAnnouncement: string;
} = {
  icoAnnouncement: 'ICO briefing available for review',
};

/**
 * ICO page campaign content lives here.
 * Update links/copy without editing page JSX.
 */
export const icoLaunchpadContent: {
  pageKicker: string;
  pageTitle: string;
  pageSummary: string;
  countdownLabel: string;
  countdownTargetUtc: string;
  saleTimezone: string;
  tokenName: string;
  tokenSymbol: string;
  network: string;
  saleStatus: string;
  totalSupply: string;
  publicAllocation: string;
  targetRaise: string;
  softCap: string;
  hardCap: string;
  utilityHighlights: string[];
  timeline: IcoTimelineItem[];
  resources: IcoResourceItem[];
  whitelistContactEmail: string;
  whitelistCtaLabel: string;
  whitelistHelperCopy: string;
  calendarCtaLabel: string;
  calendarEventTitle: string;
  calendarEventDescription: string;
  calendarEventStartUtc: string;
  calendarEventEndUtc: string;
  calendarEventLocation: string;
  legalNote: string;
} = {
  pageKicker: 'ExecutionLab token launch',
  pageTitle: 'Initial Coin Offering (ICO) briefing',
  pageSummary:
    'Review configured token details, sale timing, documentation, and whitelist request steps before participating.',
  countdownLabel: 'Countdown to public sale',
  countdownTargetUtc: '2026-09-15T12:00:00Z',
  saleTimezone: 'Asia/Dubai',
  tokenName: 'ExecutionLab Token',
  tokenSymbol: 'EXL',
  network: 'Ethereum + L2 settlement',
  saleStatus: 'Pre-sale onboarding',
  totalSupply: '1,000,000,000 EXL',
  publicAllocation: '25% public sale',
  targetRaise: '$18M',
  softCap: '$6M',
  hardCap: '$24M',
  utilityHighlights: [
    'Platform fee-tier eligibility for active workspace operators',
    'Governance participation on selected strategy and platform parameters',
    'Access coordination for new automation modules where token gating is enabled',
    'Contributor recognition for verified research and signal review workflows',
  ],
  timeline: [
    { phase: 'Whitelist registration', window: 'Q3 2026', status: 'Open soon' },
    { phase: 'Public sale round', window: 'Q3 2026', status: 'Planned' },
    { phase: 'Token generation event', window: 'Q4 2026', status: 'Planned' },
    { phase: 'Exchange listings + utility unlock', window: 'Q4 2026', status: 'Planned' },
  ],
  resources: [
    {
      title: 'Whitepaper (preview)',
      description: 'Token thesis, protocol architecture, economics, and risk disclosures.',
      href: '/ico/whitepaper',
      ctaLabel: 'Open whitepaper preview',
    },
    {
      title: 'Tokenomics overview',
      description: 'Allocation model, vesting principles, treasury policy, and unlock schedule.',
      href: '/ico/tokenomics',
      ctaLabel: 'View tokenomics notes',
    },
    {
      title: 'KYC and participation policy',
      description: 'Participation eligibility, jurisdiction constraints, and compliance checklist.',
      ctaLabel: 'Publishing soon',
    },
  ],
  whitelistContactEmail: 'launchpad@executionlab.io',
  whitelistCtaLabel: 'Request whitelist access',
  whitelistHelperCopy:
    'Submit an email request for whitelist consideration. The team will share eligibility steps when participation details are available.',
  calendarCtaLabel: 'Add sale reminder to calendar',
  calendarEventTitle: 'ExecutionLab ICO Public Sale Window',
  calendarEventDescription:
    'ExecutionLab token launch public-sale reminder. Review whitepaper, tokenomics, and participation checklist before the sale opens.',
  calendarEventStartUtc: '2026-09-15T12:00:00Z',
  calendarEventEndUtc: '2026-09-15T13:00:00Z',
  calendarEventLocation: 'Online',
  legalNote:
    'This page is informational only and does not constitute investment advice or an offer where prohibited by law. Final terms will be published before sale activation.',
};
