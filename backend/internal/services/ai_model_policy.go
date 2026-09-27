package services

import "strings"

// Model policy per request kind. Quick tasks (market selection, runtime
// digest) run on the provider's default model with low reasoning effort;
// analysis tasks (parameter suggestions, backtest explanations, the strategy
// chat) run on the analysis model with the analysis effort, under the longer
// chat HTTP client and handler deadlines.

const (
	defaultXAIModel                  = "grok-4.3"
	defaultXAIAnalysisModel          = "grok-4.7"
	defaultXAIAnalysisReasoningLevel = xaiEffortMedium

	// Responses API output budgets per kind; the limit includes reasoning
	// tokens, so analysis kinds get room for the reasoning they are asked for.
	xaiOutputTokensStrategyChat    = 16000
	xaiOutputTokensStrategyParams  = 10000
	xaiOutputTokensBacktestExplain = 6000
	xaiOutputTokensMarketSelection = 4000
	xaiOutputTokensRuntimeDigest   = 2000
)

// aiAnalysisKind reports whether a kind is an analysis task.
func aiAnalysisKind(kind aiRequestKind) bool {
	switch kind {
	case aiRequestKindStrategyParams, aiRequestKindBacktestExplain, aiRequestKindStrategyChat:
		return true
	default:
		return false
	}
}

// providerConfigForKind is providerConfig with the model swapped for the
// kind: Grok analysis kinds use XAI_ANALYSIS_MODEL, everything else is the
// provider's default model. DeepSeek parameter suggestions run on
// DEEPSEEK_MODEL too: they read one JSON object back (JSON mode, thinking
// disabled), which is not a job for the reasoning model.
func (s *AIMarketService) providerConfigForKind(provider string, kind aiRequestKind) aiProviderConfig {
	config := s.providerConfig(provider)
	if provider == ExternalAPIProviderGrok && aiAnalysisKind(kind) {
		config.model = envWithDefault("XAI_ANALYSIS_MODEL", defaultXAIAnalysisModel)
	}
	return config
}

// analysisModelForProvider is the model a provider uses for the analysis
// kinds when it differs from its default model, otherwise empty.
func (s *AIMarketService) analysisModelForProvider(provider string) string {
	analysis := s.providerConfigForKind(provider, aiRequestKindStrategyChat).model
	if analysis == s.providerConfig(provider).model {
		return ""
	}
	return analysis
}

// xaiReasoningEffortForKind is the Responses API reasoning effort: analysis
// kinds use XAI_ANALYSIS_REASONING_EFFORT (default medium), quick kinds use
// XAI_REASONING_EFFORT (default low).
func xaiReasoningEffortForKind(kind aiRequestKind) string {
	if aiAnalysisKind(kind) {
		return strings.ToLower(strings.TrimSpace(envWithDefault("XAI_ANALYSIS_REASONING_EFFORT", defaultXAIAnalysisReasoningLevel)))
	}
	return strings.ToLower(strings.TrimSpace(envWithDefault("XAI_REASONING_EFFORT", xaiEffortLow)))
}

// xaiMaxOutputTokensForKind is the Responses API output budget per kind.
func xaiMaxOutputTokensForKind(kind aiRequestKind) int {
	switch kind {
	case aiRequestKindStrategyChat:
		return xaiOutputTokensStrategyChat
	case aiRequestKindStrategyParams:
		return xaiOutputTokensStrategyParams
	case aiRequestKindBacktestExplain:
		return xaiOutputTokensBacktestExplain
	case aiRequestKindRuntimeDigest:
		return xaiOutputTokensRuntimeDigest
	default:
		return xaiOutputTokensMarketSelection
	}
}

// aiExecutorForKind picks the HTTP policy for a kind: analysis kinds use the
// chat client (long per-attempt timeout, at most two attempts, retry only
// rate limits, server errors and network failures); quick kinds keep the
// market-filter client with its timeout retries.
func (s *AIMarketService) aiExecutorForKind(kind aiRequestKind) aiJSONExecutor {
	if aiAnalysisKind(kind) {
		return s.executeChatJSON
	}
	return s.executeJSON
}
