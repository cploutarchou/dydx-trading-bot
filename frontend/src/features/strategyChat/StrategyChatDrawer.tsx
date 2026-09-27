import { useQueryClient } from '@tanstack/react-query';
import { Loader2, MessageSquare, Plus, RotateCcw, SendHorizontal, X } from 'lucide-react';
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import type { AIMarketProvider, StrategyChatMessage } from '../../api';
import { getApiErrorCode } from '../../api/requestError';
import { EvidenceSummaryChips } from '../ai/evidenceSummary';
import {
  AI_PROVIDER_ORDER,
  getAIProviderDisplayName,
  getAIProviderLabel,
  useAIProviderAvailability,
} from '../ai/providerAvailability';
import { describeStrategyChatError } from './chatErrors';
import {
  forgetFailedStrategyChatSend,
  useFailedStrategyChatSend,
  usePendingStrategyChatMessage,
  useRefreshStrategyChat,
  useSendStrategyChatMessage,
  useStartStrategyChatSession,
  useStrategyChat,
} from './hooks';
import { StrategyChatProposalCard } from './StrategyChatProposalCard';

const MAX_MESSAGE_LENGTH = 4000;

const STARTER_PROMPTS = [
  'How did my recent backtests do?',
  'How can I reduce drawdown?',
  'Suggest safer settings',
  'Create a more conservative variant',
] as const;

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

const providerLabelFor = (provider: string | undefined): string => {
  if (!provider) {
    return 'The assistant';
  }
  return (AI_PROVIDER_ORDER as string[]).includes(provider)
    ? getAIProviderLabel(provider as AIMarketProvider)
    : provider;
};

const formatMessageTime = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

function ChatMessageItem({
  message,
  strategyId,
  strategyName,
  runtimeActive,
}: {
  message: StrategyChatMessage;
  strategyId: number;
  strategyName: string;
  runtimeActive: boolean;
}) {
  const time = formatMessageTime(message.created_at);

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md border border-cyan-500/30 bg-cyan-500/10 px-3.5 py-2.5 text-sm text-cyan-50">
          <p className="whitespace-pre-line wrap-break-word">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[92%]">
        <p className="mb-1 text-[11px] text-slate-500">
          {providerLabelFor(message.provider)}
          {time ? ` · ${time}` : ''}
        </p>
        <div className="rounded-2xl rounded-bl-md border border-slate-700/70 bg-slate-800/60 px-3.5 py-2.5 text-sm leading-6 text-slate-200">
          <p className="whitespace-pre-line wrap-break-word">{message.content}</p>
        </div>
        {message.evidence_summary && (
          <EvidenceSummaryChips summary={message.evidence_summary} compact className="mt-1.5" />
        )}
        {message.proposal && (
          <StrategyChatProposalCard
            strategyId={strategyId}
            strategyName={strategyName}
            message={message}
            proposal={message.proposal}
            runtimeActive={runtimeActive}
          />
        )}
      </div>
    </div>
  );
}

interface StrategyChatDrawerProps {
  strategyId: number;
  strategyName: string;
  onClose: () => void;
}

/**
 * Right-side chat panel about one strategy. The assistant answers in plain
 * text and may attach a proposal; nothing is saved until the user applies it.
 * Rendered by the page root (never inside a strategy card, whose single-key
 * shortcuts would react to typing here) and portaled to the document body.
 */
export function StrategyChatDrawer({ strategyId, strategyName, onClose }: StrategyChatDrawerProps) {
  const kickerId = useId();
  const titleId = useId();
  const inputId = useId();
  const providerSelectId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const wasSendingRef = useRef(false);
  // True while a press that started on the backdrop itself is in progress.
  const backdropPressRef = useRef(false);
  const [draft, setDraft] = useState('');
  const [sendError, setSendError] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [restoredSendId, setRestoredSendId] = useState<number | null>(null);

  const queryClient = useQueryClient();
  const chatQuery = useStrategyChat(strategyId);
  const refreshChat = useRefreshStrategyChat(strategyId);
  const sendMutation = useSendStrategyChatMessage(strategyId);
  const newSessionMutation = useStartStrategyChatSession(strategyId);
  const { isSending, pendingMessage } = usePendingStrategyChatMessage(strategyId);
  const failedSend = useFailedStrategyChatSend(strategyId);
  const {
    availableProviders,
    statusMap,
    isLoading: providerStatusLoading,
    isError: providerStatusError,
    refetch: refetchProviderStatus,
  } = useAIProviderAvailability();

  // Grok is first in AI_PROVIDER_ORDER, so the first available provider is
  // Grok whenever it is configured. Repair an unavailable selection during
  // render instead of in an effect.
  const [provider, setProvider] = useState<AIMarketProvider>(availableProviders[0] ?? 'grok');
  const [prevAvailableProviders, setPrevAvailableProviders] = useState(availableProviders);
  if (availableProviders !== prevAvailableProviders) {
    setPrevAvailableProviders(availableProviders);
    const firstProvider = availableProviders[0];
    if (firstProvider && !availableProviders.includes(provider)) {
      setProvider(firstProvider);
    }
  }

  // A send that failed while the drawer was closed left nothing on the server
  // and no catch block ran here: restore its text and error once, keyed on
  // the mutation, then forget the mutation (in an effect below).
  if (failedSend && failedSend.mutationId !== restoredSendId) {
    setRestoredSendId(failedSend.mutationId);
    if (draft.trim() === '') {
      setDraft(failedSend.content);
    }
    setSendError(
      describeStrategyChatError(
        failedSend.error,
        failedSend.provider ? getAIProviderLabel(failedSend.provider) : undefined
      )
    );
  }

  const providerReady = availableProviders.includes(provider);
  // A failed status request is not "no provider": the composer stays usable
  // and Send waits until a provider is known.
  const providerStatusFailed = providerStatusError && availableProviders.length === 0;
  const noProvider =
    !providerStatusLoading && !providerStatusFailed && availableProviders.length === 0;
  const messages = chatQuery.data?.messages ?? [];
  const messageCount = messages.length;
  const session = chatQuery.data?.session ?? null;
  const runtimeActive = chatQuery.data?.runtime_active !== false;
  // Wait for the conversation so a message never goes out without its session.
  const chatLoaded = chatQuery.data !== undefined;
  const canSend =
    chatLoaded &&
    providerReady &&
    !isSending &&
    draft.trim().length > 0 &&
    draft.length <= MAX_MESSAGE_LENGTH;

  // Move focus into the drawer on open and give it back on close.
  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusTimer = window.setTimeout(() => {
      const textarea = textareaRef.current;
      (textarea && !textarea.disabled ? textarea : dialogRef.current)?.focus();
    }, 0);
    return () => {
      window.clearTimeout(focusTimer);
      window.setTimeout(() => previouslyFocused?.focus(), 0);
    };
  }, []);

  // One document-level listener: focus drops to the body whenever the control
  // that had it is disabled or unmounted (sending, New chat, proposal
  // actions), and a handler on the dialog would never see those keys.
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (!event.isComposing) {
          onClose();
        }
        return;
      }
      if (event.key !== 'Tab') {
        return;
      }
      // Keep Tab inside the modal drawer.
      const dialog = dialogRef.current;
      if (!dialog) {
        return;
      }
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) {
        event.preventDefault();
        return;
      }
      const active = document.activeElement;
      if (!active || !dialog.contains(active)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (event.shiftKey && (active === first || active === dialog)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // The restore above ran for this mutation; drop it so it happens once.
  useEffect(() => {
    if (failedSend) {
      forgetFailedStrategyChatSend(queryClient, strategyId, failedSend.mutationId);
    }
  }, [failedSend, queryClient, strategyId]);

  // Keep the newest message in view.
  useEffect(() => {
    const list = listRef.current;
    if (list) {
      list.scrollTop = list.scrollHeight;
    }
  }, [messageCount, isSending, sendError]);

  // The composer is disabled while a turn runs, which drops focus to the
  // body; hand it back once the reply is in unless the user moved on.
  useEffect(() => {
    const finishedSending = wasSendingRef.current && !isSending;
    wasSendingRef.current = isSending;
    if (!finishedSending) {
      return;
    }
    const active = document.activeElement;
    if (!active || active === document.body || active === dialogRef.current) {
      textareaRef.current?.focus();
    }
  }, [isSending]);

  const submit = async (rawContent: string, fromDraft: boolean) => {
    const content = rawContent.trim();
    if (
      !content ||
      content.length > MAX_MESSAGE_LENGTH ||
      isSending ||
      !providerReady ||
      !chatLoaded
    ) {
      return;
    }
    setSendError(null);
    setSessionError(null);
    if (fromDraft) {
      setDraft('');
    }
    try {
      await sendMutation.mutateAsync({
        ...(session ? { session_id: session.id } : {}),
        content,
        provider,
      });
    } catch (error: unknown) {
      // Keep the text so the user can retry or edit it.
      setDraft((current) => (current.trim() === '' ? content : current));
      setSendError(describeStrategyChatError(error, getAIProviderLabel(provider)));
      // The cached session is gone (another tab started a new chat): re-read
      // the conversation so Retry sends the current one.
      if (getApiErrorCode(error) === 'NOT_FOUND') {
        void refreshChat();
      }
    }
  };

  const startNewChat = async () => {
    setSendError(null);
    setSessionError(null);
    try {
      await newSessionMutation.mutateAsync();
    } catch (error: unknown) {
      setSessionError(describeStrategyChatError(error));
    }
  };

  const handleComposerKeyDown = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void submit(draft, true);
    }
  };

  if (typeof document === 'undefined') {
    return null;
  }

  const showEmptyState = chatLoaded && messageCount === 0 && !isSending;

  return createPortal(
    // Backdrop dismiss is a pointer-only convenience; the dialog below owns
    // the real semantics and closes on Escape and from its close button.
    // Both the press and the click must land on the backdrop itself, so a
    // text selection that starts in the drawer and ends outside it stays open.
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/50"
      role="presentation"
      onPointerDown={(event) => {
        backdropPressRef.current = event.target === event.currentTarget;
      }}
      onClick={(event) => {
        const pressStartedHere = backdropPressRef.current;
        backdropPressRef.current = false;
        if (pressStartedHere && event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${kickerId} ${titleId}`}
        tabIndex={-1}
        className="flex h-full w-full flex-col border-l border-slate-700 bg-slate-900 shadow-2xl shadow-black/50 focus:outline-none sm:max-w-xl"
      >
        <div className="shrink-0 border-b border-slate-800 px-4 py-4 sm:px-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p
                id={kickerId}
                className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300"
              >
                <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" />
                Strategy assistant
              </p>
              <h2 id={titleId} className="mt-1 truncate text-lg font-semibold text-white">
                {strategyName}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close chat"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-700 text-slate-400 transition hover:border-slate-500 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {availableProviders.length > 0 && (
              <>
                <label htmlFor={providerSelectId} className="text-xs text-slate-400">
                  Provider
                </label>
                <select
                  id={providerSelectId}
                  value={provider}
                  onChange={(event) => setProvider(event.target.value as AIMarketProvider)}
                  disabled={isSending}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none disabled:opacity-50"
                >
                  {availableProviders.map((item) => (
                    <option key={item} value={item}>
                      {getAIProviderDisplayName(statusMap[item])}
                    </option>
                  ))}
                </select>
              </>
            )}
            <button
              type="button"
              onClick={() => void startNewChat()}
              disabled={isSending || newSessionMutation.isPending || messageCount === 0}
              className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs font-semibold text-slate-100 transition hover:border-cyan-500/40 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {newSessionMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plus className="h-3.5 w-3.5" />
              )}
              New chat
            </button>
          </div>
        </div>

        <div
          ref={listRef}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-5"
        >
          {chatQuery.isLoading ? (
            <p role="status" className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading conversation…
            </p>
          ) : chatQuery.isError && chatQuery.data === undefined ? (
            <div
              role="alert"
              className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100"
            >
              <p>{describeStrategyChatError(chatQuery.error)}</p>
              <button
                type="button"
                onClick={() => void chatQuery.refetch()}
                className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-rose-400/40 px-2.5 py-1 text-xs font-semibold text-rose-100 transition hover:bg-rose-500/20"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Try again
              </button>
            </div>
          ) : (
            <>
              {/* A failed refetch keeps the loaded conversation; only say so. */}
              {chatQuery.isRefetchError && (
                <div
                  role="alert"
                  className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-100"
                >
                  <p className="min-w-0 flex-1 wrap-break-word">
                    {`Could not refresh the conversation. ${describeStrategyChatError(chatQuery.error)}`}
                  </p>
                  <button
                    type="button"
                    onClick={() => void chatQuery.refetch()}
                    className="inline-flex items-center gap-1.5 rounded-md border border-rose-400/40 px-2.5 py-1 font-semibold text-rose-100 transition hover:bg-rose-500/20"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Try again
                  </button>
                </div>
              )}
              <div role="log" aria-label="Conversation" className="space-y-4">
                {messages.map((message) => (
                  <ChatMessageItem
                    key={message.id}
                    message={message}
                    strategyId={strategyId}
                    strategyName={strategyName}
                    runtimeActive={runtimeActive}
                  />
                ))}
                {pendingMessage && (
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-br-md border border-cyan-500/20 bg-cyan-500/5 px-3.5 py-2.5 text-sm text-cyan-50/80">
                      <p className="whitespace-pre-line wrap-break-word">
                        {pendingMessage.content}
                      </p>
                    </div>
                  </div>
                )}
                {isSending && (
                  <p role="status" className="flex items-center gap-2 text-sm text-slate-400">
                    <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
                    {`${providerLabelFor(pendingMessage?.provider)} is thinking…`}
                  </p>
                )}
              </div>
            </>
          )}

          {showEmptyState && (
            <div className="mt-2">
              <p className="text-sm text-slate-300">
                Ask about the settings, recent backtests or risk of {strategyName}. Suggested
                changes are only saved when you apply them.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {STARTER_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => void submit(prompt, false)}
                    disabled={!providerReady || isSending}
                    className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="shrink-0 border-t border-slate-800 px-4 py-3 sm:px-5">
          {providerStatusFailed && (
            <div
              role="alert"
              className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100"
            >
              <p className="min-w-0 flex-1">Could not check AI providers.</p>
              <button
                type="button"
                onClick={() => void refetchProviderStatus()}
                className="inline-flex items-center gap-1.5 rounded-md border border-amber-400/40 px-2.5 py-1 font-semibold text-amber-100 transition hover:bg-amber-500/20"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry
              </button>
            </div>
          )}
          {noProvider && (
            <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100">
              No AI provider is available for chat. An admin can add a Grok key in Settings → AI
              Filters.
            </div>
          )}
          {sendError && (
            <div
              role="alert"
              className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-100"
            >
              <p className="min-w-0 flex-1 wrap-break-word">{sendError}</p>
              <button
                type="button"
                onClick={() => void submit(draft, true)}
                disabled={!canSend}
                className="inline-flex items-center gap-1.5 rounded-md border border-rose-400/40 px-2.5 py-1 font-semibold text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry
              </button>
            </div>
          )}
          {sessionError && (
            <p
              role="alert"
              className="mb-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-100"
            >
              {sessionError}
            </p>
          )}
          <label htmlFor={inputId} className="sr-only">
            Message
          </label>
          <textarea
            ref={textareaRef}
            id={inputId}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            maxLength={MAX_MESSAGE_LENGTH}
            rows={3}
            disabled={isSending || noProvider}
            placeholder="Ask about this strategy…"
            className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <div className="mt-2 flex items-center justify-between gap-3">
            <p className="text-[11px] text-slate-500">
              <span className="hidden sm:inline">Enter to send, Shift+Enter for a new line · </span>
              <span>{`${draft.length}/${MAX_MESSAGE_LENGTH}`}</span>
            </p>
            <button
              type="button"
              onClick={() => void submit(draft, true)}
              disabled={!canSend}
              className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-600 px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            >
              {isSending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <SendHorizontal className="h-3.5 w-3.5" />
              )}
              Send
            </button>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            Suggestions are not financial advice. Backtests do not guarantee future results.
          </p>
        </div>
      </div>
    </div>,
    document.body
  );
}
