export interface CountdownPart {
  label: 'Days' | 'Hours' | 'Minutes' | 'Seconds';
  value: string;
}

export interface CountdownState {
  status: 'active' | 'expired' | 'missing';
  remainingMs: number;
  targetMs: number | null;
  parts: CountdownPart[];
}

const EMPTY_COUNTDOWN_PARTS: CountdownPart[] = [
  { label: 'Days', value: '--' },
  { label: 'Hours', value: '--' },
  { label: 'Minutes', value: '--' },
  { label: 'Seconds', value: '--' },
];

export const parseConfiguredUtcDate = (value?: string | null): number | null => {
  const trimmed = String(value ?? '').trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Date.parse(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

export const getCountdownState = (
  targetUtc?: string | null,
  nowMs: number = Date.now()
): CountdownState => {
  const targetMs = parseConfiguredUtcDate(targetUtc);
  if (targetMs === null) {
    return {
      status: 'missing',
      remainingMs: 0,
      targetMs,
      parts: EMPTY_COUNTDOWN_PARTS,
    };
  }

  const remainingMs = Math.max(targetMs - nowMs, 0);
  if (remainingMs === 0) {
    return {
      status: 'expired',
      remainingMs,
      targetMs,
      parts: [
        { label: 'Days', value: '00' },
        { label: 'Hours', value: '00' },
        { label: 'Minutes', value: '00' },
        { label: 'Seconds', value: '00' },
      ],
    };
  }

  const totalSeconds = Math.floor(remainingMs / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return {
    status: 'active',
    remainingMs,
    targetMs,
    parts: [
      { label: 'Days', value: String(days).padStart(2, '0') },
      { label: 'Hours', value: String(hours).padStart(2, '0') },
      { label: 'Minutes', value: String(minutes).padStart(2, '0') },
      { label: 'Seconds', value: String(seconds).padStart(2, '0') },
    ],
  };
};

export const formatConfiguredDate = (
  targetUtc?: string | null,
  timeZone = 'UTC',
  locale = 'en-US'
): string => {
  const targetMs = parseConfiguredUtcDate(targetUtc);
  if (targetMs === null) {
    return 'Date to be confirmed';
  }

  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(targetMs));
};

export const isValidContactEmail = (value: string): boolean =>
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());

export const buildWhitelistMailto = ({
  contactEmail,
  requesterEmail,
  tokenSymbol,
}: {
  contactEmail: string;
  requesterEmail: string;
  tokenSymbol: string;
}): string => {
  const subject = encodeURIComponent(`Whitelist request - ${tokenSymbol} public sale`);
  const body = encodeURIComponent(
    [
      'Hello ExecutionLab team,',
      '',
      `Please consider ${requesterEmail.trim()} for whitelist review.`,
      '',
      'I understand that submission does not guarantee eligibility or allocation.',
    ].join('\n')
  );

  return `mailto:${contactEmail}?subject=${subject}&body=${body}`;
};
