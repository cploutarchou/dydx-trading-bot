import { getApiErrorCode } from '../../api/requestError';

/** Backend code for an apply on a strategy whose runtime is (or may be) active. */
export const STRATEGY_RUNNING_ACK_REQUIRED = 'STRATEGY_RUNNING_ACK_REQUIRED';
/** Backend code for an action on a proposal that was already applied, created or dismissed. */
export const PROPOSAL_NOT_PENDING = 'PROPOSAL_NOT_PENDING';

/**
 * Text for a failed chat call. Codes the user can act on get guidance; any
 * other failure shows the backend's own message.
 */
export const describeStrategyChatError = (error: unknown, providerLabel?: string): string => {
  const provider = providerLabel || 'This AI provider';
  switch (getApiErrorCode(error)) {
    case 'CHAT_RATE_LIMITED':
      return 'You are sending messages too quickly. Wait a minute, then try again.';
    case 'CHAT_BUSY':
      return 'The assistant is still answering another message. Try again when it has finished.';
    case 'AI_PROVIDER_NOT_CONFIGURED':
      return `${provider} has no API key. An admin can add one in Settings → AI Filters.`;
    case 'AI_PROVIDER_DISABLED':
      return `${provider} is turned off by an administrator. Pick another provider.`;
    case 'AI_TIMEOUT':
      return 'The assistant took too long to answer. Try again.';
    case PROPOSAL_NOT_PENDING:
      return 'This proposal was already handled.';
    default:
      return error instanceof Error && error.message
        ? error.message
        : 'Something went wrong. Try again.';
  }
};
