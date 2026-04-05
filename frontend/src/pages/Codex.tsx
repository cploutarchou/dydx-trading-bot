import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertCircle, ArrowRight, Bot, Loader2, ShieldCheck, Sparkles, Zap } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import api from '../api';
import { useToastStore } from '../components/ErrorBoundary';
import { PageContainer } from '../components/PageContainer';

interface CodexStatus {
  configured: boolean;
  provider: string;
  model: string;
  base_url: string;
  reasoning_effort: string;
  message: string;
}

interface CodexResponse {
  response_id: string;
  model: string;
  output_text: string;
  reasoning_effort: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
}

const presetPrompts = [
  {
    label: 'Review strongest strategy',
    mode: 'strategy-review' as const,
    prompt: 'Review our strongest backtest strategy and tell me why it deserves trust, where it is fragile, and what validation should happen before live trading.',
  },
  {
    label: 'Explain dashboard KPIs',
    mode: 'dashboard' as const,
    prompt: 'Explain what the main dashboard metrics mean, what should concern me first, and which next action would reduce risk the most.',
  },
  {
    label: 'Debug runtime issue',
    mode: 'runtime-debug' as const,
    prompt: 'Help me debug a strategy runtime failure. Explain the likely causes, what logs or state to inspect next, and the safest recovery sequence.',
  },
];

export const CodexPage: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState<'general' | 'dashboard' | 'strategy-review' | 'runtime-debug'>('general');
  const [context, setContext] = useState('');
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const statusQuery = useQuery({
    queryKey: ['codex', 'status'],
    queryFn: async (): Promise<CodexStatus> => {
      const response = await api.getCodexStatus();
      return (response.data ?? {}) as CodexStatus;
    },
    staleTime: 30_000,
  });

  const promptMutation = useMutation({
    mutationFn: async (): Promise<CodexResponse> => {
      const response = await api.requestCodexResponse({
        prompt,
        context,
        mode,
      });
      return (response.data ?? {}) as CodexResponse;
    },
    onSuccess: () => {
      successToast('Codex replied', 'The assistant response is ready below.', { duration: 3000 });
    },
    onError: (error: unknown) => {
      errorToast(
        'Codex request failed',
        error instanceof Error ? error.message : 'Unable to get a response from Codex right now.'
      );
    },
  });

  const status = statusQuery.data;
  const canSubmit = prompt.trim().length > 0 && !promptMutation.isPending && !!status?.configured;

  const helperCopy = useMemo(() => {
    if (!status?.configured) {
      return 'Set OPENAI_API_KEY on the backend and reload this page to enable in-app Codex assistance.';
    }
    return 'Codex runs through the backend so your OpenAI key stays off the browser.';
  }, [status?.configured]);

  return (
    <PageContainer size="wide" className="space-y-6">
      <section
        className="relative overflow-hidden rounded-3xl border border-slate-700/60 px-6 py-6 sm:px-8"
        style={{
          background:
            'linear-gradient(135deg, rgba(15,23,42,.96) 0%, rgba(30,41,59,.94) 48%, rgba(29,78,216,.24) 100%)',
        }}
      >
        <div className="absolute -right-16 top-0 h-52 w-52 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="absolute -bottom-12 left-0 h-36 w-36 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-300">
              <Sparkles className="h-3.5 w-3.5" />
              Codex Workspace
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Get production-aware guidance for strategy quality, runtime issues, and what to do next.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              Ask for debugging help, KPI interpretation, or a strategy review. Responses are routed through your backend so the OpenAI key never lives in the frontend.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Provider</p>
              <p className="mt-1 text-sm font-semibold text-white">{status?.provider ?? 'openai'}</p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Model</p>
              <p className="mt-1 text-sm font-semibold text-white">{status?.model ?? 'gpt-5.4'}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Ask Codex</h2>
              <p className="mt-1 text-sm text-slate-400">
                Give the assistant enough context to stay accurate and actionable.
              </p>
            </div>
            <div
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
                status?.configured
                  ? 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                  : 'border border-amber-500/20 bg-amber-500/10 text-amber-300'
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${status?.configured ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              {status?.configured ? 'Connected' : 'Not configured'}
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {presetPrompts.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => {
                  setPrompt(preset.prompt);
                  setMode(preset.mode);
                }}
                className="rounded-full border border-slate-600/80 bg-slate-900/60 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-blue-500/40 hover:text-white"
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor="codex-mode">
                Focus
              </label>
              <select
                id="codex-mode"
                value={mode}
                onChange={(event) => setMode(event.target.value as typeof mode)}
                className="w-full rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm text-white outline-none transition focus:border-blue-500/60"
              >
                <option value="general">General guidance</option>
                <option value="dashboard">Dashboard interpretation</option>
                <option value="strategy-review">Strategy review</option>
                <option value="runtime-debug">Runtime debugging</option>
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor="codex-prompt">
                Prompt
              </label>
              <textarea
                id="codex-prompt"
                rows={7}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Ask for a strategy review, a backtest interpretation, or help debugging a runtime issue..."
                className="w-full rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-blue-500/60"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor="codex-context">
                Extra context
              </label>
              <textarea
                id="codex-context"
                rows={5}
                value={context}
                onChange={(event) => setContext(event.target.value)}
                placeholder="Paste relevant runtime errors, KPI summaries, strategy notes, or deployment context here."
                className="w-full rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-blue-500/60"
              />
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-400">{helperCopy}</p>
              <button
                type="button"
                disabled={!canSubmit}
                onClick={() => promptMutation.mutate()}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700"
              >
                {promptMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Asking Codex...
                  </>
                ) : (
                  <>
                    Ask Codex
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-xl bg-blue-500/10 p-2 text-blue-300">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Connection status</h2>
                <p className="text-sm text-slate-400">Backend-managed OpenAI configuration</p>
              </div>
            </div>

            {statusQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-300">
                <Loader2 className="h-4 w-4 animate-spin" />
                Checking Codex availability...
              </div>
            ) : statusQuery.isError ? (
              <div className="rounded-xl border border-red-700/60 bg-red-950/30 p-4 text-sm text-red-200">
                Unable to load Codex status right now.
              </div>
            ) : (
              <div className="space-y-3 text-sm">
                <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
                  <p className="font-medium text-white">{status?.message}</p>
                  <div className="mt-3 grid grid-cols-2 gap-3 text-slate-300">
                    <div>
                      <p className="text-slate-500">Reasoning</p>
                      <p>{status?.reasoning_effort ?? 'medium'}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Endpoint</p>
                      <p className="truncate">{status?.base_url ?? 'https://api.openai.com/v1'}</p>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
                  <div className="mb-3 flex items-center gap-2 text-slate-200">
                    <ShieldCheck className="h-4 w-4 text-emerald-300" />
                    Production-safe setup
                  </div>
                  <ul className="space-y-2 text-slate-400">
                    <li>OpenAI key stays on the Go backend, not in the browser.</li>
                    <li>Requests go through app auth and inherit the app trace ID.</li>
                    <li>Use `OPENAI_API_KEY` and optional `OPENAI_CODEX_MODEL` on the backend service.</li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-300">
                <Zap className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Latest response</h2>
                <p className="text-sm text-slate-400">High-signal output ready for action</p>
              </div>
            </div>

            {promptMutation.isPending ? (
              <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-slate-700/60 bg-slate-900/50 text-slate-300">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Codex is thinking...
                </div>
              </div>
            ) : promptMutation.data ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
                    <p className="text-slate-500">Model</p>
                    <p className="font-semibold text-white">{promptMutation.data.model}</p>
                  </div>
                  <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
                    <p className="text-slate-500">Reasoning</p>
                    <p className="font-semibold text-white">{promptMutation.data.reasoning_effort}</p>
                  </div>
                  <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
                    <p className="text-slate-500">Tokens</p>
                    <p className="font-semibold text-white">{promptMutation.data.total_tokens ?? 'N/A'}</p>
                  </div>
                  <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
                    <p className="text-slate-500">Response ID</p>
                    <p className="truncate font-semibold text-white">{promptMutation.data.response_id}</p>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-4">
                  <p className="whitespace-pre-wrap text-sm leading-7 text-slate-200">
                    {promptMutation.data.output_text}
                  </p>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-5 text-sm text-slate-400">
                Ask Codex a question and the response will appear here.
              </div>
            )}

            {promptMutation.isError && (
              <div className="mt-4 rounded-xl border border-red-700/60 bg-red-950/30 p-4 text-sm text-red-200">
                <div className="flex items-start gap-2">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <p>
                    {promptMutation.error instanceof Error
                      ? promptMutation.error.message
                      : 'Unable to load a Codex response right now.'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </PageContainer>
  );
};
