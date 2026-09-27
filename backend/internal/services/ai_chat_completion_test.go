package services

import (
	"bytes"
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

type fakeTimeoutError struct{}

func (fakeTimeoutError) Error() string   { return "client timeout" }
func (fakeTimeoutError) Timeout() bool   { return true }
func (fakeTimeoutError) Temporary() bool { return true }

func chatTurns() []AIChatTurn {
	return []AIChatTurn{
		{Role: "user", Content: "first"},
		{Role: "assistant", Content: "answer"},
		{Role: "user", Content: "second"},
	}
}

func TestOpenAIChatUsesJSONModeAndClampsTokens(t *testing.T) {
	t.Setenv("OPENAI_API_KEY", "test-openai-key")
	t.Setenv("OPENAI_MODEL", "")
	t.Setenv("OPENAI_BASE_URL", "")
	t.Setenv("AI_PROVIDER_OPENAI_ENABLED", "")

	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		if req.URL.String() != "https://api.openai.com/v1/chat/completions" {
			t.Fatalf("unexpected URL %s", req.URL)
		}
		payload := decodeAIRequest(t, req)
		format, _ := payload["response_format"].(map[string]any)
		if format["type"] != "json_object" {
			t.Fatalf("expected json_object, got %#v", payload["response_format"])
		}
		if payload["max_tokens"] != float64(4096) {
			t.Fatalf("expected max_tokens clamped to 4096, got %#v", payload["max_tokens"])
		}
		messages, _ := payload["messages"].([]any)
		roles := make([]string, 0, len(messages))
		for _, entry := range messages {
			roles = append(roles, entry.(map[string]any)["role"].(string))
		}
		if strings.Join(roles, ",") != "system,user,assistant,user" {
			t.Fatalf("expected the whole conversation, got %v", roles)
		}
		if _, ok := payload["thinking"]; ok {
			t.Fatalf("expected no DeepSeek options for OpenAI")
		}
		return aiJSONResponse(http.StatusOK, `{"choices":[{"message":{"content":"{\"reply\":\"hi\",\"proposal\":null}"},"finish_reason":"stop"}],"usage":{"prompt_tokens":9,"completion_tokens":4,"total_tokens":13}}`), nil
	})

	result, err := service.ChatCompletion(context.Background(), 3, "openai", AIChatCompletionRequest{
		System: "Reply in JSON.", Turns: chatTurns(), MaxOutputTokens: 16000,
	})
	if err != nil {
		t.Fatalf("ChatCompletion returned error: %v", err)
	}
	if result.InputTokens != 9 || result.OutputTokens != 4 || result.Model != "gpt-4o-mini" {
		t.Fatalf("unexpected result %+v", result)
	}
}

func TestOpenAIChatLengthFinishIsCutOff(t *testing.T) {
	t.Setenv("OPENAI_API_KEY", "test-openai-key")
	t.Setenv("AI_PROVIDER_OPENAI_ENABLED", "")
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusOK, `{"choices":[{"message":{"content":"{\"reply\":\"cut"},"finish_reason":"length"}]}`), nil
	})
	_, err := service.ChatCompletion(context.Background(), 3, "openai", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()})
	var cutOff *aiReplyCutOffError
	if !errors.As(err, &cutOff) {
		t.Fatalf("expected a cut-off error, got %v", err)
	}
}

func TestDeepSeekChatUsesJSONModeWithoutThinking(t *testing.T) {
	t.Setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
	t.Setenv("DEEPSEEK_MODEL", "")
	t.Setenv("AI_PROVIDER_DEEPSEEK_ENABLED", "")
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		payload := decodeAIRequest(t, req)
		if payload["model"] != "deepseek-v4-flash" {
			t.Fatalf("expected the chat model, not the reasoning model, got %#v", payload["model"])
		}
		thinking, _ := payload["thinking"].(map[string]any)
		if thinking["type"] != "disabled" {
			t.Fatalf("expected thinking disabled with JSON mode, got %#v", payload["thinking"])
		}
		if _, ok := payload["reasoning_effort"]; ok {
			t.Fatalf("expected no reasoning_effort for chat")
		}
		format, _ := payload["response_format"].(map[string]any)
		if format["type"] != "json_object" {
			t.Fatalf("expected json_object, got %#v", payload["response_format"])
		}
		return aiJSONResponse(http.StatusOK, `{"choices":[{"message":{"content":"{\"reply\":\"hi\",\"proposal\":null}"},"finish_reason":"stop"}]}`), nil
	})
	if _, err := service.ChatCompletion(context.Background(), 3, "deepseek", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()}); err != nil {
		t.Fatalf("ChatCompletion returned error: %v", err)
	}
}

// TestDeepSeekSuggestParamsChatUsesFlashWithoutThinking: the parameter
// suggestions read one JSON object back, so DeepSeek runs them on its chat
// model with thinking disabled, and the call is logged under its own kind.
func TestDeepSeekSuggestParamsChatUsesFlashWithoutThinking(t *testing.T) {
	t.Setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
	t.Setenv("DEEPSEEK_MODEL", "")
	t.Setenv("DEEPSEEK_BASE_URL", "")
	t.Setenv("AI_PROVIDER_DEEPSEEK_ENABLED", "")
	var logs bytes.Buffer
	log.SetOutput(&logs)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })

	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		payload := decodeAIRequest(t, req)
		if payload["model"] != "deepseek-v4-flash" {
			t.Fatalf("expected DEEPSEEK_MODEL for JSON-mode suggestions, got %#v", payload["model"])
		}
		thinking, _ := payload["thinking"].(map[string]any)
		if thinking["type"] != "disabled" {
			t.Fatalf("expected thinking disabled with JSON mode, got %#v", payload["thinking"])
		}
		if _, ok := payload["reasoning_effort"]; ok {
			t.Fatalf("expected no reasoning_effort in JSON mode, got %#v", payload["reasoning_effort"])
		}
		if payload["temperature"] != 0.3 {
			t.Fatalf("expected the chat temperature kept, got %#v", payload["temperature"])
		}
		format, _ := payload["response_format"].(map[string]any)
		if format["type"] != "json_object" {
			t.Fatalf("expected json_object, got %#v", payload["response_format"])
		}
		return aiJSONResponse(http.StatusOK, `{"choices":[{"message":{"content":"{\"summary\":\"s\",\"suggestions\":[],\"data_gaps\":[]}"},"finish_reason":"stop"}],"usage":{"prompt_tokens":9,"completion_tokens":4,"total_tokens":13}}`), nil
	})
	result, err := service.ChatCompletion(context.Background(), 3, "deepseek", AIChatCompletionRequest{
		System: "Return JSON.", Turns: []AIChatTurn{{Role: "user", Content: "review"}},
		MaxOutputTokens: xaiOutputTokensStrategyParams, kind: aiRequestKindStrategyParams,
	})
	if err != nil || result.Model != "deepseek-v4-flash" {
		t.Fatalf("unexpected result %+v %v", result, err)
	}
	if logged := logs.String(); !strings.Contains(logged, "kind=strategy_params") || strings.Contains(logged, "kind=strategy_chat") {
		t.Fatalf("expected the call logged as strategy_params, got:\n%s", logged)
	}
}

func TestClaudeChatUsesMessagesAPI(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
	t.Setenv("ANTHROPIC_BASE_URL", "")
	t.Setenv("ANTHROPIC_MODEL", "")
	t.Setenv("AI_PROVIDER_CLAUDE_ENABLED", "")
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		if req.Header.Get("x-api-key") != "test-anthropic-key" || req.Header.Get("Authorization") != "" {
			t.Fatalf("expected x-api-key auth only")
		}
		payload := decodeAIRequest(t, req)
		if payload["system"] != "Reply in JSON." {
			t.Fatalf("expected the system prompt in system, got %#v", payload["system"])
		}
		if payload["model"] != "claude-haiku-4-5-20251001" {
			t.Fatalf("expected the current default model, got %#v", payload["model"])
		}
		if _, ok := payload["temperature"]; ok {
			t.Fatalf("expected no temperature in a Messages API request, got %#v", payload["temperature"])
		}
		messages, _ := payload["messages"].([]any)
		if len(messages) != 3 || messages[0].(map[string]any)["role"] != "user" {
			t.Fatalf("expected the conversation without the system turn, got %#v", messages)
		}
		if _, ok := payload["response_format"]; ok {
			t.Fatalf("expected prompt-only JSON for Claude")
		}
		return aiJSONResponse(http.StatusOK, `{"content":[{"type":"text","text":"{\"reply\":\"hi\",\"proposal\":null}"}],"stop_reason":"end_turn","usage":{"input_tokens":11,"output_tokens":6}}`), nil
	})
	result, err := service.ChatCompletion(context.Background(), 3, "claude", AIChatCompletionRequest{System: "Reply in JSON.", Turns: chatTurns()})
	if err != nil {
		t.Fatalf("ChatCompletion returned error: %v", err)
	}
	if result.InputTokens != 11 || result.OutputTokens != 6 {
		t.Fatalf("expected Anthropic usage names mapped, got %+v", result)
	}

	cutOff := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusOK, `{"content":[{"type":"text","text":"{\"reply\""}],"stop_reason":"max_tokens"}`), nil
	})
	_, err = cutOff.ChatCompletion(context.Background(), 3, "claude", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()})
	var cutOffErr *aiReplyCutOffError
	if !errors.As(err, &cutOffErr) {
		t.Fatalf("expected a cut-off error, got %v", err)
	}
}

// The older Messages API calls (market selection, text tasks) use the same
// default model and send no temperature either, so ANTHROPIC_MODEL may name a
// model that rejects a non-default temperature.
func TestMessagesAPIMarketAndTextRequestsCarryNoTemperature(t *testing.T) {
	t.Setenv("ANTHROPIC_MODEL", "")
	t.Setenv("ANTHROPIC_BASE_URL", "")
	if got := NewAIMarketService(nil).providerConfig(ExternalAPIProviderClaude).model; got != "claude-haiku-4-5-20251001" {
		t.Fatalf("expected the default model claude-haiku-4-5-20251001, got %q", got)
	}
	requests := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		requests++
		payload := decodeAIRequest(t, req)
		if payload["model"] != "claude-haiku-4-5-20251001" {
			t.Fatalf("expected the default model, got %#v", payload["model"])
		}
		if _, ok := payload["temperature"]; ok {
			t.Fatalf("expected no temperature in a Messages API request, got %#v", payload["temperature"])
		}
		if requests == 1 {
			return aiJSONResponse(http.StatusOK, `{"content":[{"type":"text","text":"{\"selected_markets\":[\"BTC-USD\",\"ETH-USD\"],\"rationale\":\"liquid\",\"confidence\":0.6}"}]}`), nil
		}
		return aiJSONResponse(http.StatusOK, `{"content":[{"type":"text","text":"Keep the window."}]}`), nil
	})
	if _, err := service.callProvider(context.Background(), "key", ExternalAPIProviderClaude, "ai_recommended", []string{"BTC-USD", "ETH-USD"}, 2, "", AIMarketCriteria{}); err != nil {
		t.Fatalf("callProvider returned error: %v", err)
	}
	if _, err := service.callAIForTextTask(context.Background(), "key", ExternalAPIProviderClaude, aiRequestKindStrategyParams, "system", "user"); err != nil {
		t.Fatalf("callAIForTextTask returned error: %v", err)
	}
	if requests != 2 {
		t.Fatalf("expected two Messages API requests, got %d", requests)
	}
}

func TestChatRetriesServerErrorsAtMostTwice(t *testing.T) {
	grokChatEnv(t)
	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		return aiJSONResponse(http.StatusBadGateway, `{"error":{"message":"upstream"}}`), nil
	})
	_, err := service.ChatCompletion(context.Background(), 3, "grok", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()})
	if err == nil {
		t.Fatal("expected a provider error")
	}
	if attempts != aiChatMaxAttempts {
		t.Fatalf("expected %d attempts, got %d", aiChatMaxAttempts, attempts)
	}
}

func TestChatDoesNotRetryBadRequests(t *testing.T) {
	grokChatEnv(t)
	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		return aiJSONResponse(http.StatusBadRequest, `{"code":"invalid","error":"bad"}`), nil
	})
	if _, err := service.ChatCompletion(context.Background(), 3, "grok", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()}); err == nil {
		t.Fatal("expected an error")
	}
	if attempts != 1 {
		t.Fatalf("expected a 400 to be tried once, got %d", attempts)
	}
}

func TestChatDoesNotRetryClientTimeouts(t *testing.T) {
	grokChatEnv(t)
	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		return nil, fakeTimeoutError{}
	})
	_, err := service.ChatCompletion(context.Background(), 3, "grok", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()})
	if !isAIClientTimeout(err) {
		t.Fatalf("expected a client timeout error, got %v", err)
	}
	if attempts != 1 {
		t.Fatalf("expected a timeout not to be retried, got %d attempts", attempts)
	}
}

func TestChatHTTPTimeoutComesFromEnv(t *testing.T) {
	t.Setenv("AI_CHAT_HTTP_TIMEOUT_SECONDS", "")
	if AIChatHTTPTimeout() != 150*time.Second {
		t.Fatalf("expected the 150s default, got %s", AIChatHTTPTimeout())
	}
	t.Setenv("AI_CHAT_HTTP_TIMEOUT_SECONDS", "42")
	if AIChatHTTPTimeout() != 42*time.Second {
		t.Fatalf("expected 42s, got %s", AIChatHTTPTimeout())
	}
	if NewAIMarketService(nil).chatHTTPClient.Timeout != 42*time.Second {
		t.Fatal("expected the chat client to use the configured timeout")
	}
	t.Setenv("AI_CHAT_HTTP_TIMEOUT_SECONDS", "nonsense")
	if AIChatHTTPTimeout() != 150*time.Second {
		t.Fatalf("expected an invalid value to fall back to 150s, got %s", AIChatHTTPTimeout())
	}
}

func TestChatProviderAccessErrors(t *testing.T) {
	t.Setenv("XAI_API_KEY", "")
	t.Setenv("AI_PROVIDER_GROK_ENABLED", "")
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		t.Fatal("no request may be sent without a key")
		return nil, nil
	})
	_, err := service.ChatCompletion(context.Background(), 3, "grok", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()})
	var accessErr *AIProviderAccessError
	if !errors.As(err, &accessErr) || accessErr.Code != http.StatusConflict {
		t.Fatalf("expected a 409 not-configured error, got %v", err)
	}

	t.Setenv("AI_PROVIDER_GROK_ENABLED", "off")
	_, err = service.ChatCompletion(context.Background(), 3, "grok", AIChatCompletionRequest{System: "JSON", Turns: chatTurns()})
	if !errors.As(err, &accessErr) || accessErr.Code != http.StatusForbidden {
		t.Fatalf("expected a 403 disabled error, got %v", err)
	}
}
