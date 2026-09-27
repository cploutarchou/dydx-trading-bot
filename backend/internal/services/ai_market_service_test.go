package services

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return fn(req)
}

func newAIServiceWithTransport(fn roundTripFunc) *AIMarketService {
	return &AIMarketService{
		httpClient: &http.Client{Transport: fn},
	}
}

func aiJSONResponse(status int, body string) *http.Response {
	return &http.Response{
		StatusCode: status,
		Header:     make(http.Header),
		Body:       io.NopCloser(strings.NewReader(body)),
	}
}

func TestAIMarketServiceDeepSeekDefaultUsesV4Flash(t *testing.T) {
	t.Setenv("DEEPSEEK_MODEL", "")

	service := NewAIMarketService(nil)
	config := service.providerConfig(ExternalAPIProviderDeepSeek)
	if config.model != "deepseek-v4-flash" {
		t.Fatalf("expected DeepSeek default model deepseek-v4-flash, got %q", config.model)
	}
}

func TestAIMarketServiceDeepSeekMarketSelectionUsesJSONMode(t *testing.T) {
	t.Setenv("DEEPSEEK_MODEL", "")

	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		var payload map[string]any
		if err := json.NewDecoder(req.Body).Decode(&payload); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if payload["model"] != "deepseek-v4-flash" {
			t.Fatalf("expected deepseek-v4-flash model, got %#v", payload["model"])
		}
		responseFormat, ok := payload["response_format"].(map[string]any)
		if !ok || responseFormat["type"] != "json_object" {
			t.Fatalf("expected json_object response_format, got %#v", payload["response_format"])
		}
		thinking, ok := payload["thinking"].(map[string]any)
		if !ok || thinking["type"] != "disabled" {
			t.Fatalf("expected disabled thinking for market selection, got %#v", payload["thinking"])
		}
		if payload["max_tokens"] != float64(aiMarketSelectionMaxTokens) {
			t.Fatalf("expected max_tokens %d, got %#v", aiMarketSelectionMaxTokens, payload["max_tokens"])
		}

		return aiJSONResponse(http.StatusOK, `{
			"choices":[{"message":{"content":"{\"selected_markets\":[\"BTC-USD\",\"ETH-USD\"],\"rationale\":\"liquid majors\",\"confidence\":1.2}"}}],
			"usage":{"prompt_tokens":20,"completion_tokens":10,"total_tokens":30,"prompt_cache_hit_tokens":8,"prompt_cache_miss_tokens":12}
		}`), nil
	})

	result, err := service.callOpenAICompatible(
		context.Background(),
		"test-key",
		service.providerConfig(ExternalAPIProviderDeepSeek),
		"Rank BTC-USD, ETH-USD",
	)
	if err != nil {
		t.Fatalf("callOpenAICompatible returned error: %v", err)
	}
	if result.Confidence != 1 {
		t.Fatalf("expected confidence to be clamped to 1, got %f", result.Confidence)
	}
}

func TestAIMarketServiceRetriesRetryableProviderStatus(t *testing.T) {
	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		if attempts == 1 {
			return aiJSONResponse(http.StatusTooManyRequests, `{"error":"busy"}`), nil
		}
		return aiJSONResponse(http.StatusOK, `{
			"choices":[{"message":{"content":"{\"selected_markets\":[\"BTC-USD\",\"ETH-USD\"],\"rationale\":\"recovered\",\"confidence\":0.8}"}}],
			"usage":{"prompt_tokens":5,"completion_tokens":5,"total_tokens":10}
		}`), nil
	})

	_, err := service.callOpenAICompatible(
		context.Background(),
		"test-key",
		service.providerConfig(ExternalAPIProviderDeepSeek),
		"Rank BTC-USD, ETH-USD",
	)
	if err != nil {
		t.Fatalf("expected retry to recover, got error: %v", err)
	}
	if attempts != 2 {
		t.Fatalf("expected 2 attempts, got %d", attempts)
	}
}

// The plain-text task path keeps DeepSeek's thinking mode for parameter
// suggestions; the model is DEEPSEEK_MODEL like every other DeepSeek call.
func TestAIMarketServiceDeepSeekStrategyTextTaskUsesThinking(t *testing.T) {
	t.Setenv("DEEPSEEK_MODEL", "")
	t.Setenv("DEEPSEEK_REASONING_EFFORT", "")

	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		var payload map[string]any
		if err := json.NewDecoder(req.Body).Decode(&payload); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if payload["model"] != "deepseek-v4-flash" {
			t.Fatalf("expected strategy suggestions to use DEEPSEEK_MODEL, got %#v", payload["model"])
		}
		thinking, ok := payload["thinking"].(map[string]any)
		if !ok || thinking["type"] != "enabled" {
			t.Fatalf("expected enabled thinking for strategy suggestions, got %#v", payload["thinking"])
		}
		if payload["reasoning_effort"] != "high" {
			t.Fatalf("expected reasoning_effort high, got %#v", payload["reasoning_effort"])
		}
		if payload["max_tokens"] != float64(4096) {
			t.Fatalf("expected max_tokens 4096, got %#v", payload["max_tokens"])
		}
		if _, ok := payload["temperature"]; ok {
			t.Fatalf("expected no temperature for DeepSeek thinking mode, got %#v", payload["temperature"])
		}
		return aiJSONResponse(http.StatusOK, `{
			"choices":[{"message":{"content":"1. zscore_threshold: Current '2.0' -> Suggested '2.4'. Rationale: reduce overtrading."}}],
			"usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30,"completion_tokens_details":{"reasoning_tokens":6}}
		}`), nil
	})

	content, err := service.callAIForTextTask(
		context.Background(),
		"test-key",
		ExternalAPIProviderDeepSeek,
		aiRequestKindStrategyParams,
		"system",
		"user",
	)
	if err != nil {
		t.Fatalf("callAIForTextTask returned error: %v", err)
	}
	if !strings.Contains(content, "zscore_threshold") {
		t.Fatalf("expected strategy suggestion content, got %q", content)
	}
}

func TestAIMarketServiceDeepSeekStrategyRetriesWithoutThinkingOnEmptyContent(t *testing.T) {
	t.Setenv("DEEPSEEK_MODEL", "")

	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		var payload map[string]any
		if err := json.NewDecoder(req.Body).Decode(&payload); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if attempts == 1 {
			thinking, ok := payload["thinking"].(map[string]any)
			if !ok || thinking["type"] != "enabled" {
				t.Fatalf("expected first attempt to use thinking, got %#v", payload["thinking"])
			}
			return aiJSONResponse(http.StatusOK, `{
				"choices":[{"message":{"content":""}}],
				"usage":{"prompt_tokens":850,"completion_tokens":4096,"total_tokens":4946,"completion_tokens_details":{"reasoning_tokens":4096}}
			}`), nil
		}

		thinking, ok := payload["thinking"].(map[string]any)
		if !ok || thinking["type"] != "disabled" {
			t.Fatalf("expected fallback attempt to disable thinking, got %#v", payload["thinking"])
		}
		if _, ok := payload["reasoning_effort"]; ok {
			t.Fatalf("expected fallback attempt to omit reasoning_effort, got %#v", payload["reasoning_effort"])
		}
		return aiJSONResponse(http.StatusOK, `{
			"choices":[{"message":{"content":"1. max_drawdown_pct: Current '10' -> Suggested '7'. Rationale: lower tail risk."}}],
			"usage":{"prompt_tokens":850,"completion_tokens":50,"total_tokens":900}
		}`), nil
	})

	content, err := service.callAIForTextTask(
		context.Background(),
		"test-key",
		ExternalAPIProviderDeepSeek,
		aiRequestKindStrategyParams,
		"system",
		"user",
	)
	if err != nil {
		t.Fatalf("callAIForTextTask returned error: %v", err)
	}
	if attempts != 2 {
		t.Fatalf("expected empty content fallback to make 2 attempts, got %d", attempts)
	}
	if !strings.Contains(content, "max_drawdown_pct") {
		t.Fatalf("expected fallback content, got %q", content)
	}
}

// TestRuntimeDigestHidesProviderDetailFromNonAdmins: a provider failure
// yields the fixed message of its class; the provider's text is for admins.
func TestRuntimeDigestHidesProviderDetailFromNonAdmins(t *testing.T) {
	grokChatEnv(t)
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusNotFound, `{"code":"not-found","error":"The model grok-9 does not exist or your team 1b2c3d4e-team-uuid does not have access to it"}`), nil
	})
	req := AIRuntimeDigestRequest{Provider: "grok", RunningBots: 1, TotalBots: 2, OpenPositions: 3, Network: "testnet"}

	result, err := service.RuntimeDigest(context.Background(), AIAnalysisActor{UserID: 7}, req)
	if err != nil {
		t.Fatalf("RuntimeDigest returned error: %v", err)
	}
	if result.UsedAI || result.Provider != "grok" || result.Content != "AI analysis unavailable: Grok rejected the request or the model is not available. Ask an admin to check the AI provider settings." {
		t.Fatalf("expected the fixed non-admin message, got %+v", result)
	}
	admin, err := service.RuntimeDigest(context.Background(), AIAnalysisActor{UserID: 2, IsAdmin: true}, req)
	if err != nil || admin.UsedAI || !strings.Contains(admin.Content, "Provider detail:") || !strings.Contains(admin.Content, "grok-9") {
		t.Fatalf("expected the provider detail for admins, got %+v %v", admin, err)
	}
}
