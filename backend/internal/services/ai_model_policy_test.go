package services

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"testing"
)

func modelPolicyEnv(t *testing.T) {
	t.Helper()
	for _, key := range []string{
		"XAI_MODEL", "XAI_ANALYSIS_MODEL", "XAI_REASONING_EFFORT", "XAI_ANALYSIS_REASONING_EFFORT",
		"DEEPSEEK_MODEL", "OPENAI_MODEL", "ANTHROPIC_MODEL",
	} {
		t.Setenv(key, "")
	}
}

func TestModelPolicyModelPerKind(t *testing.T) {
	modelPolicyEnv(t)
	service := NewAIMarketService(nil)

	cases := []struct {
		provider string
		kind     aiRequestKind
		model    string
	}{
		{ExternalAPIProviderGrok, aiRequestKindMarketSelection, "grok-4.3"},
		{ExternalAPIProviderGrok, aiRequestKindRuntimeDigest, "grok-4.3"},
		{ExternalAPIProviderGrok, aiRequestKindStrategyParams, "grok-4.7"},
		{ExternalAPIProviderGrok, aiRequestKindBacktestExplain, "grok-4.7"},
		{ExternalAPIProviderGrok, aiRequestKindStrategyChat, "grok-4.7"},
		{ExternalAPIProviderDeepSeek, aiRequestKindStrategyParams, "deepseek-v4-flash"},
		{ExternalAPIProviderDeepSeek, aiRequestKindStrategyChat, "deepseek-v4-flash"},
		{ExternalAPIProviderDeepSeek, aiRequestKindBacktestExplain, "deepseek-v4-flash"},
		{ExternalAPIProviderOpenAI, aiRequestKindStrategyParams, "gpt-4o-mini"},
		{ExternalAPIProviderClaude, aiRequestKindStrategyChat, "claude-haiku-4-5-20251001"},
	}
	for _, tc := range cases {
		if got := service.providerConfigForKind(tc.provider, tc.kind).model; got != tc.model {
			t.Fatalf("%s/%s: expected model %q, got %q", tc.provider, tc.kind, tc.model, got)
		}
	}

	t.Setenv("XAI_ANALYSIS_MODEL", "grok-4.7-custom")
	t.Setenv("XAI_MODEL", "grok-4.3-custom")
	if got := service.providerConfigForKind(ExternalAPIProviderGrok, aiRequestKindStrategyChat).model; got != "grok-4.7-custom" {
		t.Fatalf("expected XAI_ANALYSIS_MODEL to be honoured, got %q", got)
	}
	if got := service.providerConfigForKind(ExternalAPIProviderGrok, aiRequestKindMarketSelection).model; got != "grok-4.3-custom" {
		t.Fatalf("expected XAI_MODEL for quick kinds, got %q", got)
	}
	if got := service.providerConfigForKind(ExternalAPIProviderGrok, aiRequestKindStrategyChat).baseURL; got != "https://api.x.ai/v1/responses" {
		t.Fatalf("expected the endpoint unchanged, got %q", got)
	}
}

func TestModelPolicyEffortAndBudgetPerKind(t *testing.T) {
	modelPolicyEnv(t)

	cases := []struct {
		kind   aiRequestKind
		effort string
		tokens int
	}{
		{aiRequestKindMarketSelection, "low", 4000},
		{aiRequestKindRuntimeDigest, "low", 2000},
		{aiRequestKindBacktestExplain, "medium", 6000},
		{aiRequestKindStrategyParams, "medium", 10000},
		{aiRequestKindStrategyChat, "medium", 16000},
	}
	for _, tc := range cases {
		if got := xaiReasoningEffort(tc.kind); got != tc.effort {
			t.Fatalf("%s: expected effort %q, got %q", tc.kind, tc.effort, got)
		}
		if got := xaiMaxOutputTokens(tc.kind); got != tc.tokens {
			t.Fatalf("%s: expected %d output tokens, got %d", tc.kind, tc.tokens, got)
		}
	}

	// The quick-task override does not touch analysis kinds and vice versa.
	t.Setenv("XAI_REASONING_EFFORT", "none")
	t.Setenv("XAI_ANALYSIS_REASONING_EFFORT", "High")
	if got := xaiReasoningEffort(aiRequestKindMarketSelection); got != "none" {
		t.Fatalf("expected XAI_REASONING_EFFORT for market selection, got %q", got)
	}
	if got := xaiReasoningEffort(aiRequestKindStrategyParams); got != "high" {
		t.Fatalf("expected XAI_ANALYSIS_REASONING_EFFORT for suggestions, got %q", got)
	}
}

func TestModelPolicyAnalysisModelInStatus(t *testing.T) {
	modelPolicyEnv(t)
	service := NewAIMarketService(nil)
	if got := service.analysisModelForProvider(ExternalAPIProviderGrok); got != "grok-4.7" {
		t.Fatalf("expected grok-4.7 as the Grok analysis model, got %q", got)
	}
	// DeepSeek, OpenAI and Claude run every kind on their default model, so
	// no analysis model is shown.
	for _, provider := range []string{ExternalAPIProviderDeepSeek, ExternalAPIProviderOpenAI, ExternalAPIProviderClaude} {
		if got := service.analysisModelForProvider(provider); got != "" {
			t.Fatalf("expected no analysis model for %s, got %q", provider, got)
		}
	}
	encoded, err := json.Marshal(AIProviderStatus{
		Provider: ExternalAPIProviderGrok, Enabled: true, Available: true, AvailabilityStatus: "available",
		SharedKeyAvailable: true, ActiveKeySource: "shared",
		Model: service.providerConfig(ExternalAPIProviderGrok).model, AnalysisModel: service.analysisModelForProvider(ExternalAPIProviderGrok),
	})
	if err != nil || !strings.Contains(string(encoded), `"analysis_model":"grok-4.7"`) {
		t.Fatalf("expected analysis_model in the status JSON, got %s %v", encoded, err)
	}
	t.Logf("status provider JSON:\n%s", encoded)
}

// TestModelPolicyAnalysisKindsUseChatClientPolicy checks that a text task of
// an analysis kind goes through the chat client: a client timeout is not
// retried, while a quick kind still retries it.
func TestModelPolicyAnalysisKindsUseChatClientPolicy(t *testing.T) {
	grokChatEnv(t)
	attempts := 0
	timeoutTransport := roundTripFunc(func(req *http.Request) (*http.Response, error) {
		attempts++
		return nil, fakeTimeoutError{}
	})
	service := &AIMarketService{
		httpClient:     &http.Client{Transport: timeoutTransport},
		chatHTTPClient: &http.Client{Transport: timeoutTransport},
	}

	if _, err := service.callAIForTextTask(context.Background(), "test-xai-key", ExternalAPIProviderGrok, aiRequestKindBacktestExplain, "s", "u"); err == nil {
		t.Fatal("expected the timeout to surface")
	}
	if attempts != 1 {
		t.Fatalf("expected an analysis kind not to retry a client timeout, got %d attempts", attempts)
	}

	attempts = 0
	if _, err := service.callAIForTextTask(context.Background(), "test-xai-key", ExternalAPIProviderGrok, aiRequestKindRuntimeDigest, "s", "u"); err == nil {
		t.Fatal("expected the timeout to surface")
	}
	if attempts != defaultAIMarketMaxRetries {
		t.Fatalf("expected a quick kind to retry a client timeout %d times, got %d attempts", defaultAIMarketMaxRetries, attempts)
	}
}
