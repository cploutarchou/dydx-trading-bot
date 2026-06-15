export interface IcoDocumentSection {
  title: string;
  body?: string[];
  bullets?: string[];
  table?: Array<[string, string, string?]>;
}

export interface IcoDocumentContent {
  slug: 'whitepaper' | 'tokenomics';
  eyebrow: string;
  title: string;
  summary: string;
  status: string;
  updated: string;
  backLabel: string;
  alternateLabel: string;
  alternatePath: string;
  facts: Array<{ label: string; value: string; helper?: string }>;
  sections: IcoDocumentSection[];
}

const sharedNotice =
  'This document is informational only and is not investment, financial, legal, or tax advice. Final sale terms, eligibility requirements, risk disclosures, token utility, and participation mechanics must be published and reviewed before any sale activation.';

export const icoDocuments: Record<IcoDocumentContent['slug'], IcoDocumentContent> = {
  whitepaper: {
    slug: 'whitepaper',
    eyebrow: 'Whitepaper preview',
    title: 'ExecutionLab Token whitepaper preview',
    summary:
      'A structured preview of the EXL token thesis, platform architecture, launch sequence, participation model, and risk framing.',
    status: 'Draft preview',
    updated: '2026-06-15',
    backLabel: 'Back to ICO briefing',
    alternateLabel: 'Tokenomics notes',
    alternatePath: '/ico/tokenomics',
    facts: [
      { label: 'Token', value: 'ExecutionLab Token (EXL)' },
      { label: 'Network', value: 'Ethereum + L2 settlement' },
      { label: 'Sale status', value: 'Pre-sale onboarding' },
      { label: 'Public allocation', value: '25% public sale' },
    ],
    sections: [
      {
        title: 'Important notice',
        body: [
          sharedNotice,
          'Submission of a whitelist request does not guarantee participation, eligibility, or allocation.',
        ],
      },
      {
        title: 'Executive summary',
        body: [
          'ExecutionLab is a controlled DeFi execution workspace for research review, strategy validation, and monitored runtime operations. EXL is intended to coordinate selected platform utility, governance participation, and access workflows for approved users, subject to final published terms.',
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
        body: [
          'ExecutionLab is designed around evidence-first execution. Public onboarding can remain paused while approved operators continue through authenticated workflows. The platform groups research, validation, and monitored execution into a controlled operating path.',
        ],
        bullets: [
          'Research and signal evaluation',
          'Strategy validation',
          'Controlled execution and monitoring',
        ],
      },
      {
        title: 'Intended token role',
        body: [
          'EXL is intended to support platform coordination rather than represent a claim on profits, revenue, or guaranteed platform outcomes. Utility remains subject to final terms, technical implementation, jurisdictional restrictions, and platform policy.',
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
        title: 'Risk overview',
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
      'Draft tokenomics notes covering configured supply, public allocation, fundraising parameters, vesting principles, treasury policy, and open publication items.',
    status: 'Draft notes',
    updated: '2026-06-15',
    backLabel: 'Back to ICO briefing',
    alternateLabel: 'Whitepaper preview',
    alternatePath: '/ico/whitepaper',
    facts: [
      { label: 'Total supply', value: '1,000,000,000 EXL' },
      { label: 'Public allocation', value: '25% public sale', helper: '250,000,000 EXL' },
      { label: 'Target raise', value: '$18M' },
      { label: 'Caps', value: '$6M soft / $24M hard' },
    ],
    sections: [
      {
        title: 'Important notice',
        body: [
          'These tokenomics notes are informational draft materials. They are not investment advice, financial advice, legal advice, tax advice, or final sale terms. All allocation, vesting, treasury, unlock, and participation mechanics must be confirmed before production publication.',
        ],
      },
      {
        title: 'Configured sale snapshot',
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
        body: [
          'Current configured public allocation is 25% of 1,000,000,000 EXL, equivalent to 250,000,000 EXL. The final sale document should specify purchase limits, jurisdiction restrictions, whitelist requirements, allocation method, refund mechanics, and unsold-token treatment.',
        ],
      },
      {
        title: 'Vesting and unlock principles',
        bullets: [
          'Public-sale unlocks should be clearly stated before participation.',
          'Team and contributor allocations should align with long-term platform development.',
          'Treasury unlocks should be governed by documented operating policy.',
          'Any ecosystem incentives should be measurable, auditable, and subject to abuse controls.',
        ],
      },
      {
        title: 'Open items before final publication',
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
};

export const getIcoDocument = (slug: string | undefined): IcoDocumentContent | null => {
  if (slug === 'whitepaper' || slug === 'tokenomics') {
    return icoDocuments[slug];
  }

  return null;
};
