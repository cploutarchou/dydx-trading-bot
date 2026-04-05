import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { KeyRound, Loader2, MessageCircle, ShieldCheck, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import api from '../api';
import { useToastStore } from './ErrorBoundary';

const getMutationErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (typeof data?.error === 'string' && data.error.length > 0) return data.error;
    if (typeof data?.message === 'string' && data.message.length > 0) return data.message;
    return error.message;
  }

  return error instanceof Error ? error.message : 'Unknown error';
};

export function TelegramSettings() {
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');
  const [label, setLabel] = useState('Shared trading desk bot');
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const statusQuery = useQuery({
    queryKey: ['telegram', 'config'],
    queryFn: async () => {
      const response = await api.getTelegramStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.saveTelegramConfig({
        bot_token: botToken,
        chat_id: chatId.trim(),
        label,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setBotToken('');
      setChatId(data.chat_id ?? '');
      successToast('Telegram saved', 'Shared Telegram delivery is ready for runtime-managed bots.');
      void queryClient.invalidateQueries({ queryKey: ['telegram'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save Telegram config', getMutationErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const response = await api.deleteTelegramConfig();
      return response.data;
    },
    onSuccess: () => {
      setBotToken('');
      setChatId('');
      successToast('Telegram removed', 'Shared Telegram notifications have been cleared.');
      void queryClient.invalidateQueries({ queryKey: ['telegram'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to delete Telegram config', getMutationErrorMessage(error));
    },
  });

  const status = statusQuery.data;

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
    <div className="premium-panel">
      <div className="flex items-start gap-3">
        <div className="premium-icon-wrap text-sky-300">
          <MessageCircle className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-white">Telegram</h2>
          <p className="mt-1 text-sm text-slate-400">
            Manage the shared Telegram bot token and destination chat used by runtime-managed bot notifications.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <ShieldCheck className="h-4 w-4 text-emerald-300" />
            Delivery state
          </div>
          <p className="text-lg font-semibold text-white">
            {status?.configured ? 'Configured' : 'Not configured'}
          </p>
          <p className="mt-1 text-xs text-slate-500">{status?.message || 'Telegram is currently disabled.'}</p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <KeyRound className="h-4 w-4 text-amber-300" />
            Shared token
          </div>
          <p className="text-lg font-semibold text-white">
            {status?.shared_token_present ? 'Saved on backend' : 'Missing'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {status?.shared_token_label ? `Label: ${status.shared_token_label}` : 'The token never leaves the backend.'}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <MessageCircle className="h-4 w-4 text-sky-300" />
            Target chat
          </div>
          <p className="text-lg font-semibold text-white">
            {status?.chat_id ? status.chat_id_masked || status.chat_id : 'Not set'}
          </p>
          <p className="mt-1 text-xs text-slate-500">Applies to new runtime-managed bot instances and restarts after re-create.</p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
          <h3 className="text-lg font-semibold text-white">
            {status?.shared_token_present ? 'Update Telegram delivery' : 'Save Telegram delivery'}
          </h3>
          <div className="mt-5 space-y-4">
            {status?.shared_token_present && (
              <div className="rounded-xl border border-slate-700 bg-slate-950/60 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Current bot token</p>
                <p className="mt-2 font-mono text-sm text-slate-200">{status.shared_token_masked || 'Masked token on file'}</p>
              </div>
            )}
            <div>
              <label htmlFor="telegram-label" className="mb-2 block text-sm font-medium text-slate-200">
                Label
              </label>
              <input
                id="telegram-label"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-sky-500/60"
              />
            </div>
            <div>
              <label htmlFor="telegram-token" className="mb-2 block text-sm font-medium text-slate-200">
                Bot token
              </label>
              <input
                id="telegram-token"
                type="password"
                value={botToken}
                onChange={(event) => setBotToken(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-sky-500/60"
                placeholder={status?.shared_token_present ? 'Leave blank to keep the current token, or paste a replacement' : 'Paste your Telegram bot token'}
              />
            </div>
            <div>
              <label htmlFor="telegram-chat-id" className="mb-2 block text-sm font-medium text-slate-200">
                Chat ID
              </label>
              <input
                id="telegram-chat-id"
                value={chatId}
                onChange={(event) => setChatId(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-sky-500/60"
                placeholder="Paste the Telegram chat ID that should receive alerts"
              />
            </div>
            <button
              type="button"
              disabled={saveMutation.isPending || chatId.trim().length === 0}
              onClick={() => saveMutation.mutate()}
              className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              {status?.shared_token_present ? 'Update Telegram' : 'Save Telegram'}
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
          <h3 className="text-lg font-semibold text-white">Operational notes</h3>
          <ul className="mt-4 space-y-3 text-sm text-slate-300">
            <li>Telegram stays server-side and is injected into runtime-managed bot instance configs when those instances are created.</li>
            <li>The current token is always masked in the UI, and you can update the chat without retyping the token.</li>
            <li>If you change Telegram after a runtime already exists, recreate that instance so the new delivery target is applied.</li>
          </ul>
          <button
            type="button"
            disabled={deleteMutation.isPending || !status?.shared_token_present}
            onClick={() => deleteMutation.mutate()}
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
          >
            {deleteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Remove Telegram
          </button>
        </div>
      </div>
    </div>
  );
}
