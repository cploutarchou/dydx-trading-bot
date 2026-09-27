import {
  type QueryClient,
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import api, {
  type AIMarketProvider,
  type StrategyChatMessage,
  type StrategyChatProposal,
  type StrategyChatProposalResult,
  type StrategyChatSendRequest,
  type StrategyChatSession,
  type StrategyChatState,
} from '../../api';
import { queryKeys } from '../../api/queryClient';

const asArray = <T>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : []);

// The backend encodes empty Go slices as null; the UI always reads arrays. A
// proposal without a kind is unreadable and is shown as no proposal at all.
const normalizeProposal = (proposal: StrategyChatProposal | null): StrategyChatProposal | null =>
  proposal && typeof proposal === 'object' && typeof proposal.kind === 'string'
    ? {
        ...proposal,
        changes: asArray(proposal.changes),
        dropped: asArray(proposal.dropped),
      }
    : null;

const normalizeProposalResult = (
  result: StrategyChatProposalResult | null
): StrategyChatProposalResult | null =>
  result
    ? {
        ...result,
        applied_fields: Array.isArray(result.applied_fields) ? result.applied_fields : undefined,
        unchanged_fields: Array.isArray(result.unchanged_fields)
          ? result.unchanged_fields
          : undefined,
      }
    : null;

const normalizeMessage = (message: StrategyChatMessage): StrategyChatMessage => ({
  ...message,
  proposal: normalizeProposal(message.proposal ?? null),
  proposal_result: normalizeProposalResult(message.proposal_result ?? null),
});

const normalizeMessages = (messages: unknown): StrategyChatMessage[] =>
  asArray<StrategyChatMessage>(messages).map(normalizeMessage);

/**
 * Chat state for one strategy. An unknown runtime state counts as running, so
 * the apply flow asks for the running acknowledgement unless the server said
 * the strategy is not running.
 */
const normalizeChatState = (data: StrategyChatState | undefined): StrategyChatState => ({
  session: data?.session ?? null,
  messages: normalizeMessages(data?.messages),
  runtime_active: data?.runtime_active !== false,
});

const strategyChatSendMutationKey = (strategyId: number) =>
  ['strategy-chat', strategyId, 'send'] as const;

// A turn can run for several minutes; keep its outcome long enough for a
// drawer that was closed meanwhile to restore a failed send when it reopens.
const STRATEGY_CHAT_SEND_GC_TIME = 30 * 60 * 1000;

const replaceChatMessage = (
  queryClient: QueryClient,
  strategyId: number,
  message: StrategyChatMessage | undefined
) => {
  if (!message) {
    return;
  }
  const updated = normalizeMessage(message);
  queryClient.setQueryData<StrategyChatState>(queryKeys.strategyChat(strategyId), (previous) =>
    previous
      ? {
          ...previous,
          messages: previous.messages.map((item) => (item.id === updated.id ? updated : item)),
        }
      : previous
  );
};

export function useStrategyChat(strategyId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.strategyChat(strategyId),
    queryFn: async () => {
      const response = await api.getStrategyChat(strategyId);
      return normalizeChatState(response.data);
    },
    staleTime: 30_000,
    // ApiRequestError has no `response`, so the default retry predicate would
    // retry a 404 or 500 with backoff; the panel offers "Try again" instead.
    retry: false,
    enabled: enabled && strategyId > 0,
  });
}

/**
 * Send one message. The server stores the user message and the reply together
 * only when the reply succeeded, so the cache is updated from the response.
 */
export function useSendStrategyChatMessage(strategyId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: strategyChatSendMutationKey(strategyId),
    mutationFn: (payload: StrategyChatSendRequest) =>
      api.sendStrategyChatMessage(strategyId, payload),
    retry: 0,
    gcTime: STRATEGY_CHAT_SEND_GC_TIME,
    onSuccess: (response) => {
      const data = response.data;
      const key = queryKeys.strategyChat(strategyId);
      if (!data) {
        void queryClient.invalidateQueries({ queryKey: key });
        return;
      }
      const incoming = normalizeMessages(data.messages);
      const incomingIds = new Set(incoming.map((message) => message.id));
      const previous = queryClient.getQueryData<StrategyChatState>(key);
      const sameSession =
        previous?.session != null &&
        data.session != null &&
        previous.session.id === data.session.id;
      const kept = sameSession
        ? previous.messages.filter((message) => !incomingIds.has(message.id))
        : [];
      queryClient.setQueryData<StrategyChatState>(key, {
        session: data.session ?? previous?.session ?? null,
        messages: [...kept, ...incoming],
        runtime_active: previous?.runtime_active ?? true,
      });
      if (!previous) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    },
  });
}

/**
 * The message still waiting for a reply, if any. Read from the mutation cache
 * so a drawer that was closed and reopened mid-turn still shows it.
 */
export function usePendingStrategyChatMessage(strategyId: number): {
  isSending: boolean;
  pendingMessage: StrategyChatSendRequest | undefined;
} {
  const pending = useMutationState({
    filters: { mutationKey: strategyChatSendMutationKey(strategyId), status: 'pending' },
    select: (mutation) => mutation.state.variables as StrategyChatSendRequest | undefined,
  });
  return { isSending: pending.length > 0, pendingMessage: pending[pending.length - 1] };
}

export interface FailedStrategyChatSend {
  mutationId: number;
  submittedAt: number;
  content: string;
  provider: AIMarketProvider | undefined;
  error: unknown;
}

/**
 * The newest send that failed after the last successful turn, if any. The
 * server stores nothing for a failed turn, so a drawer that was closed while
 * the turn ran reads it from the mutation cache to show the error and keep
 * the text; it then forgets the mutation so the restore happens once.
 */
export function useFailedStrategyChatSend(strategyId: number): FailedStrategyChatSend | undefined {
  const mutationKey = strategyChatSendMutationKey(strategyId);
  const failed = useMutationState({
    filters: { mutationKey, status: 'error' },
    select: (mutation): FailedStrategyChatSend => {
      const variables = mutation.state.variables as StrategyChatSendRequest | undefined;
      return {
        mutationId: mutation.mutationId,
        submittedAt: mutation.state.submittedAt,
        content: variables?.content ?? '',
        provider: variables?.provider,
        error: mutation.state.error,
      };
    },
  });
  const succeededAt = useMutationState({
    filters: { mutationKey, status: 'success' },
    select: (mutation) => mutation.state.submittedAt,
  });
  const newest = failed.reduce<FailedStrategyChatSend | undefined>(
    (best, item) => (!best || item.submittedAt >= best.submittedAt ? item : best),
    undefined
  );
  const lastSuccessAt = succeededAt.reduce((latest, at) => Math.max(latest, at), 0);
  return newest && newest.submittedAt > lastSuccessAt ? newest : undefined;
}

/** Drop one failed send from the mutation cache after the drawer restored it. */
export function forgetFailedStrategyChatSend(
  queryClient: QueryClient,
  strategyId: number,
  mutationId: number
): void {
  const cache = queryClient.getMutationCache();
  cache
    .findAll({ mutationKey: strategyChatSendMutationKey(strategyId), status: 'error' })
    .filter((mutation) => mutation.mutationId === mutationId)
    .forEach((mutation) => cache.remove(mutation));
}

/** Start a new conversation; the server archives the current one. */
export function useStartStrategyChatSession(strategyId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.startStrategyChatSession(strategyId),
    retry: 0,
    onSuccess: (response) => {
      const key = queryKeys.strategyChat(strategyId);
      const session: StrategyChatSession | null = response.data?.session ?? null;
      if (!session) {
        void queryClient.invalidateQueries({ queryKey: key });
        return;
      }
      const previous = queryClient.getQueryData<StrategyChatState>(key);
      queryClient.setQueryData<StrategyChatState>(key, {
        session,
        messages: normalizeMessages(response.data?.messages),
        runtime_active: previous?.runtime_active ?? true,
      });
    },
  });
}

export function useApplyStrategyChatProposal(strategyId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      messageId,
      fields,
      acknowledgeRunning = false,
    }: {
      messageId: number;
      fields: string[];
      acknowledgeRunning?: boolean;
    }) =>
      api.applyStrategyChatProposal(strategyId, messageId, {
        fields,
        ...(acknowledgeRunning ? { acknowledge_running: true } : {}),
      }),
    retry: 0,
    onSuccess: (response) => {
      replaceChatMessage(queryClient, strategyId, response.data?.message);
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });
}

export function useCreateStrategyFromChatProposal(strategyId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      messageId,
      name,
      fields,
    }: {
      messageId: number;
      name: string;
      fields: string[];
    }) => api.createStrategyFromChatProposal(strategyId, messageId, { name, fields }),
    retry: 0,
    onSuccess: (response) => {
      replaceChatMessage(queryClient, strategyId, response.data?.message);
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });
}

export function useDismissStrategyChatProposal(strategyId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId }: { messageId: number }) =>
      api.dismissStrategyChatProposal(strategyId, messageId),
    retry: 0,
    onSuccess: (response) => {
      replaceChatMessage(queryClient, strategyId, response.data?.message);
    },
  });
}

/** Re-read the conversation, for example after a proposal turned out to be handled already. */
export function useRefreshStrategyChat(strategyId: number) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.strategyChat(strategyId) });
}
