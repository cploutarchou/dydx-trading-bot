import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import {
    KeyRound,
    Loader2,
    LucideIcon,
    MessageCircle,
    Send,
    ShieldCheck,
    Trash2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import api, { TelegramConfigPayload, TelegramSettingsScope } from '../api';
import { useToastStore } from './ErrorBoundary';

interface TelegramScopeSettingsPanelProps {
  scope: TelegramSettingsScope;
  icon: LucideIcon;
  title: string;
  description: string;
  tokenTitle: string;
  chatDescription: string;
  defaultLabel: string;
  badge?: string;
}

const getMutationErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (typeof data?.error === 'string' && data.error.length > 0) return data.error;
    if (typeof data?.message === 'string' && data.message.length > 0) return data.message;
    return error.message;
  }

  return error instanceof Error ? error.message : 'Unknown error';
};

const getStatus = (scope: TelegramSettingsScope) =>
  scope === 'global' ? api.getTelegramGlobalStatus() : api.getTelegramUserStatus();

const saveConfig = (scope: TelegramSettingsScope, payload: TelegramConfigPayload) =>
  scope === 'global' ? api.saveTelegramGlobalConfig(payload) : api.saveTelegramUserConfig(payload);

const deleteConfig = (scope: TelegramSettingsScope) =>
  scope === 'global' ? api.deleteTelegramGlobalConfig() : api.deleteTelegramUserConfig();

const preflightDelivery = (scope: TelegramSettingsScope) =>
  scope === 'global' ? api.preflightTelegramGlobalDelivery() : api.preflightTelegramUserDelivery();

export function TelegramScopeSettingsPanel({
  scope,
  icon: Icon,
  title,
  description,
  tokenTitle,
  chatDescription,
  defaultLabel,
  badge,
}: TelegramScopeSettingsPanelProps) {
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');
  const [label, setLabel] = useState(defaultLabel);
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const queryKey = ['telegram', scope, 'status'];

  const statusQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const response = await getStatus(scope);
      return response.data;
    },
    staleTime: 30_000,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await saveConfig(scope, {
        bot_token: botToken,
        chat_id: chatId.trim(),
        label,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setBotToken('');
      setChatId(typeof data?.chat_id === 'string' ? data.chat_id : '');
      successToast(
        scope === 'global' ? 'Platform Telegram saved' : 'Telegram saved',
        scope === 'global'
          ? 'Platform Telegram alerts are ready for global fallback delivery.'
          : 'Your Telegram delivery is ready for runtime-managed bots.'
      );
      void queryClient.invalidateQueries({ queryKey: ['telegram'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save Telegram config', getMutationErrorMessage(error));
    },
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      const response = await preflightDelivery(scope);
      return response.data;
    },
    onSuccess: (data) => {
      if (data?.valid) {
        successToast(
          'Telegram delivery verified',
          data.chat_name ? `Bot can reach ${data.chat_name}.` : 'Bot token and chat are reachable.'
        );
        return;
      }
      errorToast(
        'Telegram delivery failed',
        data?.error || 'Saved Telegram settings are not valid.'
      );
    },
    onError: (error: unknown) => {
      errorToast('Failed to test Telegram delivery', getMutationErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const response = await deleteConfig(scope);
      return response.data;
    },
    onSuccess: () => {
      setBotToken('');
      setChatId('');
      successToast(
        scope === 'global' ? 'Platform Telegram removed' : 'Telegram removed',
        scope === 'global'
          ? 'Platform Telegram alerts have been cleared.'
          : 'Your Telegram notifications have been cleared.'
      );
      void queryClient.invalidateQueries({ queryKey: ['telegram'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to delete Telegram config', getMutationErrorMessage(error));
    },
  });

  const status = statusQuery.data;
  const hasConfig = Boolean(status?.shared_token_present || status?.chat_id);

  useEffect(() => {
    if (!status) return;
    if (status.shared_token_label) {
      setLabel(status.shared_token_label);
    }
    if (status.chat_id) {
      setChatId(status.chat_id);
    }
  }, [status]);

  return (
    <section className="premium-panel p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="premium-icon-wrap text-cyan-300">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-semibold text-white">{title}</h2>
              {badge && (
                <span className="rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-amber-200">
                  {badge}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-400">{description}</p>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <ShieldCheck className="h-4 w-4 text-emerald-300" />
            Delivery state
          </div>
          <p className="text-lg font-semibold text-white">
            {status?.configured ? 'Configured' : 'Not configured'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {status?.message || 'Telegram is currently disabled.'}
          </p>
        </div>

        <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <KeyRound className="h-4 w-4 text-amber-300" />
            {tokenTitle}
          </div>
          <p className="text-lg font-semibold text-white">
            {status?.shared_token_present ? 'Saved on backend' : 'Missing'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {status?.shared_token_label
              ? `Label: ${status.shared_token_label}`
              : 'The token never leaves the backend.'}
          </p>
        </div>

        <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <MessageCircle className="h-4 w-4 text-cyan-300" />
            Target chat
          </div>
          <p className="max-w-full overflow-hidden break-all whitespace-normal text-lg font-semibold text-white">
            {status?.chat_id ? status.chat_id_masked || status.chat_id : 'Not set'}
          </p>
          <p className="mt-1 text-xs text-slate-500">{chatDescription}</p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
        <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-5">
          <h3 className="text-lg font-semibold text-white">
            {status?.shared_token_present ? 'Update Telegram delivery' : 'Save Telegram delivery'}
          </h3>
          <div className="mt-5 space-y-4">
            {status?.shared_token_present && (
              <div className="rounded-lg border border-slate-700 bg-slate-950/60 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Current bot token</p>
                <p className="mt-2 max-w-full overflow-hidden break-all whitespace-normal font-mono text-sm text-slate-200">
                  {status.shared_token_masked || 'Masked token on file'}
                </p>
              </div>
            )}
            <div>
              <label
                htmlFor={`telegram-${scope}-label`}
                className="mb-2 block text-sm font-medium text-slate-200"
              >
                Label
              </label>
              <input
                id={`telegram-${scope}-label`}
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                className="premium-input"
              />
            </div>
            <div>
              <label
                htmlFor={`telegram-${scope}-token`}
                className="mb-2 block text-sm font-medium text-slate-200"
              >
                Bot token
              </label>
              <input
                id={`telegram-${scope}-token`}
                type="password"
                value={botToken}
                onChange={(event) => setBotToken(event.target.value)}
                className="premium-input"
                placeholder={
                  status?.shared_token_present
                    ? 'Leave blank to keep the current token, or paste a replacement'
                    : 'Paste the Telegram bot token'
                }
              />
            </div>
            <div>
              <label
                htmlFor={`telegram-${scope}-chat-id`}
                className="mb-2 block text-sm font-medium text-slate-200"
              >
                Chat ID
              </label>
              <input
                id={`telegram-${scope}-chat-id`}
                value={chatId}
                onChange={(event) => setChatId(event.target.value)}
                className="premium-input"
                placeholder="Paste the Telegram chat ID that should receive alerts"
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={saveMutation.isPending || chatId.trim().length === 0}
                onClick={() => saveMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-900 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-300"
              >
                {saveMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <KeyRound className="h-4 w-4" />
                )}
                {status?.shared_token_present ? 'Update Telegram' : 'Save Telegram'}
              </button>
              <button
                type="button"
                disabled={testMutation.isPending || !status?.configured}
                onClick={() => testMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/70 px-4 py-2.5 text-sm font-semibold text-white transition hover:border-cyan-500/35 hover:bg-slate-900 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
              >
                {testMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                Test Saved
              </button>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-5">
          <h3 className="text-lg font-semibold text-white">Operational notes</h3>
          <ul className="mt-4 space-y-3 text-sm text-slate-300">
            <li>
              Telegram stays server-side and is injected when runtime-managed bots are created.
            </li>
            <li>
              The current token is always masked, and you can update the chat without retyping it.
            </li>
            <li>Personal settings take priority over platform settings when a runtime launches.</li>
          </ul>
          <button
            type="button"
            disabled={deleteMutation.isPending || !hasConfig}
            onClick={() => deleteMutation.mutate()}
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
          >
            {deleteMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            Remove Telegram
          </button>
        </div>
      </div>
    </section>
  );
}
