export interface IcoDocumentSection {
  title: string;
  eyebrow?: string;
  body?: string[];
  bullets?: string[];
  table?: Array<[string, string, string?]>;
  callout?: string;
}

export interface IcoDocumentContent {
  slug: 'whitepaper' | 'tokenomics' | 'privacy-notice' | 'participation-terms';
  eyebrow: string;
  title: string;
  summary: string;
  status: string;
  updated: string;
  reviewState: string;
  backLabel: string;
  alternateLabel: string;
  alternatePath: string;
  highlights: Array<{ label: string; value: string; helper?: string }>;
  facts: Array<{ label: string; value: string; helper?: string }>;
  sections: IcoDocumentSection[];
}

const sharedNotice =
  'This document is informational only and is not investment, financial, legal, regulatory, or tax advice. Final sale terms, eligibility requirements, risk disclosures, token utility, and participation mechanics require final legal and commercial review before any sale activation.';

export const icoDocuments: Record<IcoDocumentContent['slug'], IcoDocumentContent> = {
  whitepaper: {
    slug: 'whitepaper',
    eyebrow: 'Whitepaper preview',
    title: 'ExecutionLab Token whitepaper preview',
    summary:
      'A structured preview of the EXL token thesis, controlled platform context, launch sequence, participation model, and risk framing.',
    status: 'Draft preview',
    updated: '2026-06-16',
    reviewState: 'Requires final legal and technical review',
    backLabel: 'Back to ICO briefing',
    alternateLabel: 'Tokenomics notes',
    alternatePath: '/ico/tokenomics',
    highlights: [
      {
        label: 'Purpose',
        value: 'Execution workspace coordination',
        helper: 'Utility subject to final terms',
      },
      {
        label: 'Access model',
        value: 'Controlled launch',
        helper: 'Existing approved users remain eligible to sign in',
      },
      {
        label: 'Participation',
        value: 'Whitelist review',
        helper: 'Submission does not guarantee allocation',
      },
    ],
    facts: [
      { label: 'Token', value: 'ExecutionLab Token (EXL)' },
      { label: 'Network', value: 'Ethereum + L2 settlement', helper: 'Configured; final deployment details pending' },
      { label: 'Sale status', value: 'Pre-sale onboarding' },
      { label: 'Public allocation', value: '25% public sale' },
    ],
    sections: [
      {
        title: 'Important notice',
        eyebrow: 'Read first',
        body: [
          sharedNotice,
          'Submission of a whitelist request does not guarantee participation, eligibility, or allocation.',
        ],
        callout:
          'Any jurisdiction restrictions, KYC/AML requirements, tax treatment, token rights, transfer restrictions, and purchaser eligibility rules must be confirmed in final published terms.',
      },
      {
        title: 'Executive summary',
        eyebrow: 'Platform context',
        body: [
          'ExecutionLab is a controlled DeFi execution workspace for research review, strategy validation, and monitored runtime operations. EXL is intended to coordinate selected platform utility and access workflows for approved users, subject to final published terms.',
        ],
        bullets: [
          'Sale status: Pre-sale onboarding',
          'Planned public sale timing: September 15, 2026 at 12:00 UTC, displayed on the site in Asia/Dubai',
          'Total supply: 1,000,000,000 EXL',
          'Public allocation: 25% public sale',
          'Fundraising target: $18M, with configured soft cap $6M and hard cap $24M',
        ],
      },
      {
        title: 'Platform thesis',
        eyebrow: 'What the product is for',
        body: [
          'ExecutionLab is designed around evidence-first execution. Public onboarding can remain paused while approved operators continue through authenticated workflows. The platform groups research, validation, and monitored execution into a controlled operating path for professional users.',
        ],
        bullets: [
          'Research and signal evaluation',
          'Strategy validation',
          'Controlled execution and monitoring',
        ],
      },
      {
        title: 'Intended token role',
        eyebrow: 'Utility subject to terms',
        body: [
          'EXL is intended to support platform coordination rather than represent a claim on profits, revenue, equity, or guaranteed platform outcomes. Utility remains subject to final terms, technical implementation, jurisdictional restrictions, and platform policy.',
        ],
        bullets: [
          'Platform fee-tier eligibility for active workspace operators',
          'Governance participation on selected strategy and platform parameters',
          'Access coordination for new automation modules where token gating is enabled',
          'Contributor recognition for verified research and signal review workflows',
        ],
      },
      {
        title: 'Launch structure',
        eyebrow: 'Planned milestones',
        table: [
          ['Whitelist registration', 'Q3 2026', 'Open soon'],
          ['Public sale round', 'Q3 2026', 'Planned'],
          ['Token generation event', 'Q4 2026', 'Planned'],
          ['Exchange listings and utility unlock', 'Q4 2026', 'Planned'],
        ],
        body: [
          'Timeline labels are planning indicators only. Final dates, unlock timing, listing availability, and participation terms must be confirmed in published sale documentation.',
        ],
      },
      {
        title: 'Participation framework',
        eyebrow: 'Eligibility and communications',
        body: [
          'The whitelist process is intended to collect an expression of interest and begin review communication. It should remain separate from marketing subscription consent and separate from authenticated platform-account creation.',
        ],
        bullets: [
          'Whitelist review may require identity, eligibility, jurisdiction, and compliance screening.',
          'Marketing communication should require separate optional consent and a confirmation flow.',
          'Final participation terms should explain purchase limits, payment methods, refund mechanics, and excluded jurisdictions before activation.',
        ],
      },
      {
        title: 'Risk overview',
        eyebrow: 'Non-exhaustive risks',
        bullets: [
          'Regulatory and jurisdictional restrictions',
          'Smart contract, bridge, and settlement risk',
          'Market volatility and liquidity uncertainty',
          'Delays to sale activation, token generation, unlocks, or platform utility',
          'Changes to platform design, governance scope, token utility, or eligibility policy',
          'Operational, security, and integration risk across backend services and runtime systems',
        ],
      },
    ],
  },
  tokenomics: {
    slug: 'tokenomics',
    eyebrow: 'Tokenomics notes',
    title: 'ExecutionLab Token tokenomics notes',
    summary:
      'Draft tokenomics notes covering configured supply, public allocation, fundraising parameters, vesting principles, treasury controls, and open publication items.',
    status: 'Draft notes',
    updated: '2026-06-16',
    reviewState: 'Incomplete until final allocation and vesting schedules are approved',
    backLabel: 'Back to ICO briefing',
    alternateLabel: 'Whitepaper preview',
    alternatePath: '/ico/whitepaper',
    highlights: [
      {
        label: 'Known allocation',
        value: '25% public sale',
        helper: 'Configured from the public ICO briefing',
      },
      {
        label: 'Open model',
        value: '75% pending breakdown',
        helper: 'Do not publish as final until completed',
      },
      {
        label: 'Publication state',
        value: 'Draft notes',
        helper: 'Requires allocation, vesting, and legal review',
      },
    ],
    facts: [
      { label: 'Total supply', value: '1,000,000,000 EXL' },
      { label: 'Public allocation', value: '25% public sale', helper: '250,000,000 EXL' },
      { label: 'Target raise', value: '$18M' },
      { label: 'Caps', value: '$6M soft / $24M hard' },
    ],
    sections: [
      {
        title: 'Important notice',
        eyebrow: 'Read first',
        body: [
          'These tokenomics notes are informational draft materials. They are not investment advice, financial advice, legal advice, tax advice, or final sale terms. All allocation, vesting, treasury, unlock, and participation mechanics must be confirmed before production publication.',
        ],
        callout:
          'The remaining allocation categories, vesting schedule, token price, accepted currencies, smart-contract references, audit status, and eligibility terms are not finalized in this draft.',
      },
      {
        title: 'Configured sale snapshot',
        eyebrow: 'Current public configuration',
        table: [
          ['Token', 'ExecutionLab Token (EXL)'],
          ['Network', 'Ethereum + L2 settlement'],
          ['Sale status', 'Pre-sale onboarding'],
          ['Public sale date', '2026-09-15T12:00:00Z'],
          ['Display timezone', 'Asia/Dubai'],
          ['Total supply', '1,000,000,000 EXL'],
          ['Public allocation', '25% public sale'],
          ['Fundraising target', '$18M'],
          ['Soft cap', '$6M'],
          ['Hard cap', '$24M'],
        ],
        body: [
          'These values are currently sourced from the frontend public campaign configuration.',
        ],
      },
      {
        title: 'Allocation model',
        eyebrow: 'Draft structure',
        body: [
          'The public briefing currently specifies a 25% public-sale allocation. A complete tokenomics model should define the remaining 75% before final publication.',
        ],
        bullets: [
          'Public sale allocation',
          'Ecosystem and contributor programs',
          'Treasury and reserves',
          'Team, advisors, and long-term contributors',
          'Liquidity and market operations',
          'Community incentives, where legally permitted',
        ],
      },
      {
        title: 'Public sale allocation',
        eyebrow: 'Configured allocation',
        body: [
          'Current configured public allocation is 25% of 1,000,000,000 EXL, equivalent to 250,000,000 EXL. The final sale document should specify purchase limits, jurisdiction restrictions, whitelist requirements, allocation method, refund mechanics, and unsold-token treatment.',
        ],
      },
      {
        title: 'Vesting and unlock principles',
        eyebrow: 'Controls to define',
        bullets: [
          'Public-sale unlocks should be clearly stated before participation.',
          'Team and contributor allocations should align with long-term platform development.',
          'Treasury unlocks should be governed by documented operating policy.',
          'Any ecosystem incentives should be measurable, auditable, and subject to abuse controls.',
        ],
      },
      {
        title: 'Treasury and reserve policy',
        eyebrow: 'Governance controls',
        body: [
          'Any treasury, reserve, ecosystem, liquidity, or market-operations allocation should be governed by documented controls before publication. The public document should explain who can authorize movement, what reporting cadence applies, and which actions require additional governance or legal review.',
        ],
        bullets: [
          'Define signer and approval requirements for treasury-controlled balances.',
          'Document lockup and release mechanics for non-public allocations.',
          'Separate operating reserves from marketing, liquidity, ecosystem, and contributor programs.',
        ],
      },
      {
        title: 'Open items before final publication',
        eyebrow: 'Required before final terms',
        bullets: [
          'Final allocation table for the full 1,000,000,000 EXL supply',
          'Vesting and unlock schedule by category',
          'Public-sale price or pricing method, if applicable',
          'Smart-contract audit status and deployment references',
          'Jurisdiction and KYC policy',
          'Treasury governance process',
          'Unsold-token treatment',
          'Exchange listing policy and risk disclosure',
        ],
      },
    ],
  },
  'privacy-notice': {
    slug: 'privacy-notice',
    eyebrow: 'Privacy notice',
    title: 'ICO whitelist privacy notice',
    summary:
      'Draft notice describing how ExecutionLab handles whitelist request data and consent evidence.',
    status: 'Draft notice',
    updated: '2026-06-16',
    reviewState: 'Requires final controller, retention, and legal review',
    backLabel: 'Back to ICO briefing',
    alternateLabel: 'Participation terms',
    alternatePath: '/ico/participation-terms',
    highlights: [
      { label: 'Purpose', value: 'Whitelist request review', helper: 'No platform account is created' },
      { label: 'Marketing', value: 'Separate optional consent', helper: 'Unchecked by default' },
      { label: 'Retention', value: 'Requires final policy', helper: 'Suppression evidence should be retained safely' },
    ],
    facts: [
      { label: 'Data used', value: 'Email address and consent evidence' },
      { label: 'Legal state', value: 'Draft requiring legal review' },
      { label: 'Marketing consent', value: 'Optional and separate' },
    ],
    sections: [
      {
        title: 'Important notice',
        eyebrow: 'Draft legal material',
        body: [
          'This draft is provided for product implementation and review. It is not final legal wording and must be approved by authorised legal and business owners before production publication.',
        ],
      },
      {
        title: 'Data-processing purpose',
        eyebrow: 'Whitelist request',
        body: [
          'ExecutionLab uses the submitted email address to receive, confirm, and review a whitelist request and to communicate about that request. A whitelist applicant is not automatically created as an authenticated platform user.',
        ],
      },
      {
        title: 'Marketing consent',
        eyebrow: 'Separate choice',
        body: [
          'Optional ICO update emails require separate consent. The whitelist request can be submitted without marketing consent, and marketing consent can be withdrawn without deleting the whitelist application.',
        ],
      },
      {
        title: 'Open legal items',
        eyebrow: 'Required before publication',
        bullets: [
          'Final legal entity and controller contact details',
          'Retention period for application, consent, and suppression records',
          'Access, export, withdrawal, erasure, and anonymisation process',
          'Jurisdiction-specific privacy and electronic-marketing review',
        ],
      },
    ],
  },
  'participation-terms': {
    slug: 'participation-terms',
    eyebrow: 'Participation terms',
    title: 'ICO whitelist participation terms',
    summary:
      'Draft participation notice explaining that whitelist submission is not approval, allocation, or an offer where prohibited.',
    status: 'Draft terms',
    updated: '2026-06-16',
    reviewState: 'Requires final eligibility, KYC, jurisdiction, and sale-term review',
    backLabel: 'Back to ICO briefing',
    alternateLabel: 'Privacy notice',
    alternatePath: '/ico/privacy-notice',
    highlights: [
      { label: 'Application', value: 'Expression of interest', helper: 'Not approval or allocation' },
      { label: 'Eligibility', value: 'Subject to final checks', helper: 'KYC/AML may be required' },
      { label: 'Risk', value: 'Digital asset risk', helper: 'No profit or listing guarantee' },
    ],
    facts: [
      { label: 'Whitelist status', value: 'Request review only' },
      { label: 'KYC/AML', value: 'May be required' },
      { label: 'Final terms', value: 'Not yet published' },
    ],
    sections: [
      {
        title: 'Important notice',
        eyebrow: 'Read first',
        body: [
          'Submitting a whitelist request does not guarantee participation, eligibility, allocation, token availability, or access to any sale. Final participation terms must be published before sale activation.',
        ],
      },
      {
        title: 'Eligibility review',
        eyebrow: 'No automatic approval',
        body: [
          'Participation may require identity verification, jurisdiction screening, sanctions checks, and acceptance of final sale documents. ExecutionLab should not process a sale until required policies and approvals are complete.',
        ],
      },
      {
        title: 'Risk acknowledgement',
        eyebrow: 'Material risks',
        bullets: [
          'Digital assets may be volatile, illiquid, delayed, restricted, or lose value.',
          'Smart-contract, bridge, custody, market, regulatory, operational, and technical risks may apply.',
          'No statement on this site should be treated as investment, financial, legal, regulatory, or tax advice.',
        ],
      },
      {
        title: 'Open production items',
        eyebrow: 'Required before publication',
        bullets: [
          'Final restricted jurisdictions and eligibility criteria',
          'KYC/AML provider and policy',
          'Token price, accepted currencies, purchase limits, refund rules, and allocation method',
          'Final risk disclosure and legally approved sale terms',
        ],
      },
    ],
  },
};

export const getIcoDocument = (slug: string | undefined): IcoDocumentContent | null => {
  if (
    slug === 'whitepaper' ||
    slug === 'tokenomics' ||
    slug === 'privacy-notice' ||
    slug === 'participation-terms'
  ) {
    return icoDocuments[slug];
  }

  return null;
};
