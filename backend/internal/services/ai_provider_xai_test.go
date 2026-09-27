package services

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"testing"
)

func decodeAIRequest(t *testing.T, req *http.Request) map[string]any {
	t.Helper()
	var payload map[string]any
	if err := json.NewDecoder(req.Body).Decode(&payload); err != nil {
		t.Fatalf("decode request body: %v", err)
	}
	return payload
}

func xaiCompletedResponse(text string) string {
	encoded, _ := json.Marshal(text)
	return `{
		"id":"resp_1","object":"response","status":"completed","model":"grok-4.3",
		"output":[
			{"type":"reasoning","summary":[]},
			{"type":"message","role":"assistant","status":"completed","content":[{"type":"output_text","text":` + string(encoded) + `,"annotations":[]}]}
		],
		"incomplete_details":null,
		"usage":{"input_tokens":120,"input_tokens_details":{"cached_tokens":40},"output_tokens":30,"output_tokens_details":{"reasoning_tokens":200},"total_tokens":350}
	}`
}

const xaiIncompleteResponse = `{
	"id":"resp_2","object":"response","status":"incomplete","model":"grok-4.3",
	"output":[{"type":"message","role":"assistant","status":"incomplete","content":[{"type":"output_text","text":"{\"reply\":\"cut"}]}],
	"incomplete_details":{"reason":"max_output_tokens"},
	"usage":{"input_tokens":120,"output_tokens":16000,"output_tokens_details":{"reasoning_tokens":15900},"total_tokens":16120}
}`

// grokChatEnv makes the shared env key the only Grok credential, so
// ChatCompletion needs no database.
func grokChatEnv(t *testing.T) {
	t.Helper()
	t.Setenv("XAI_API_KEY", "test-xai-key")
	t.Setenv("XAI_MODEL", "")
	t.Setenv("XAI_ANALYSIS_MODEL", "")
	t.Setenv("XAI_BASE_URL", "")
	t.Setenv("XAI_REASONING_EFFORT", "")
	t.Setenv("XAI_ANALYSIS_REASONING_EFFORT", "")
	t.Setenv("AI_PROVIDER_GROK_ENABLED", "")
}

func TestGrokProviderDefaultsAndAliases(t *testing.T) {
	t.Setenv("XAI_MODEL", "")
	t.Setenv("XAI_BASE_URL", "")

	service := NewAIMarketService(nil)
	config := service.providerConfig(ExternalAPIProviderGrok)
	if config.provider != ExternalAPIProviderGrok || config.model != "grok-4.3" || config.baseURL != "https://api.x.ai/v1/responses" {
		t.Fatalf("unexpected Grok config: %+v", config)
	}
	for _, alias := range []string{"grok", "GROK", " xai ", "x.ai"} {
		normalized, err := normalizeAIProvider(alias)
		if err != nil || normalized != ExternalAPIProviderGrok {
			t.Fatalf("expected %q to normalize to grok, got %q (%v)", alias, normalized, err)
		}
	}
	if got := sharedAIKeyEnv(ExternalAPIProviderGrok); got != "XAI_API_KEY" {
		t.Fatalf("expected XAI_API_KEY, got %q", got)
	}
	if got := providerDisplayName(ExternalAPIProviderGrok); got != "Grok" {
		t.Fatalf("expected display name Grok, got %q", got)
	}
	found := false
	for _, provider := range SupportedAIProviders {
		found = found || provider == ExternalAPIProviderGrok
	}
	if !found {
		t.Fatalf("expected grok in SupportedAIProviders, got %v", SupportedAIProviders)
	}

	t.Setenv("AI_PROVIDER_GROK_ENABLED", "false")
	if service.providerEnabled(ExternalAPIProviderGrok) {
		t.Fatal("expected AI_PROVIDER_GROK_ENABLED=false to disable grok")
	}
}

func TestUnknownProviderNeverFallsThroughToOpenAI(t *testing.T) {
	t.Setenv("OPENAI_API_KEY", "must-not-be-used")
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		t.Fatalf("no request may be sent for an unknown provider, got %s", req.URL)
		return nil, nil
	})

	config := service.providerConfig("mystery")
	if config.baseURL != "" || config.model != "" {
		t.Fatalf("expected an empty config for an unknown provider, got %+v", config)
	}
	if service.providerEnabled("mystery") {
		t.Fatal("expected an unknown provider to be disabled")
	}
	if got := sharedAIKeyEnv("mystery"); got != "" {
		t.Fatalf("expected no shared key env for an unknown provider, got %q", got)
	}
	if got := providerDisplayName("mystery"); got != "" {
		t.Fatalf("expected no display name for an unknown provider, got %q", got)
	}
	if _, err := service.callAIForTextTask(context.Background(), "key", "mystery", aiRequestKindBacktestExplain, "s", "u"); err == nil {
		t.Fatal("expected callAIForTextTask to refuse an unknown provider")
	}
	if _, err := service.callProvider(context.Background(), "key", "mystery", "ai_recommended", []string{"BTC-USD", "ETH-USD"}, 2, "", AIMarketCriteria{}); err == nil {
		t.Fatal("expected callProvider to refuse an unknown provider")
	}
	if _, err := service.ChatCompletion(context.Background(), 1, "mystery", AIChatCompletionRequest{Turns: []AIChatTurn{{Role: "user", Content: "hi"}}}); err == nil {
		t.Fatal("expected ChatCompletion to refuse an unknown provider")
	}
}

func TestGrokChatCompletionRequestShapeAndUsage(t *testing.T) {
	grokChatEnv(t)

	schema := strategyChatReplySchema()
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		if req.URL.String() != "https://api.x.ai/v1/responses" {
			t.Fatalf("expected the Responses API URL, got %s", req.URL)
		}
		if got := req.Header.Get("Authorization"); got != "Bearer test-xai-key" {
			t.Fatalf("expected bearer auth, got %q", got)
		}
		payload := decodeAIRequest(t, req)
		// The chat is an analysis kind and runs on the analysis model.
		if payload["model"] != "grok-4.7" {
			t.Fatalf("expected grok-4.7, got %#v", payload["model"])
		}
		if payload["store"] != false {
			t.Fatalf("expected store=false, got %#v", payload["store"])
		}
		if payload["max_output_tokens"] != float64(16000) {
			t.Fatalf("expected max_output_tokens 16000, got %#v", payload["max_output_tokens"])
		}
		reasoning, _ := payload["reasoning"].(map[string]any)
		if reasoning["effort"] != "medium" {
			t.Fatalf("expected reasoning.effort medium, got %#v", payload["reasoning"])
		}
		for _, forbidden := range []string{"temperature", "messages", "presence_penalty", "frequency_penalty", "stop", "reasoning_effort", "max_tokens", "safety_identifier"} {
			if _, ok := payload[forbidden]; ok {
				t.Fatalf("expected no %s in a Responses request, got %#v", forbidden, payload[forbidden])
			}
		}
		text, _ := payload["text"].(map[string]any)
		format, _ := text["format"].(map[string]any)
		if format["type"] != "json_schema" || format["name"] != "strategy_chat_reply" || format["strict"] != true {
			t.Fatalf("expected a flat strict json_schema format, got %#v", text)
		}
		if _, nested := format["json_schema"]; nested {
			t.Fatalf("expected the flat Responses format, got nested json_schema: %#v", format)
		}
		sentSchema, _ := format["schema"].(map[string]any)
		if sentSchema["additionalProperties"] != false {
			t.Fatalf("expected a closed schema, got %#v", sentSchema)
		}
		input, _ := payload["input"].([]any)
		roles := make([]string, 0, len(input))
		for _, entry := range input {
			item, _ := entry.(map[string]any)
			roles = append(roles, item["role"].(string))
		}
		if strings.Join(roles, ",") != "system,user,assistant,user" {
			t.Fatalf("expected system,user,assistant,user input, got %v", roles)
		}
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse(`{"reply":"ok","proposal":null}`)), nil
	})

	result, err := service.ChatCompletion(context.Background(), 7, "grok", AIChatCompletionRequest{
		System: "Return JSON.",
		Turns: []AIChatTurn{
			{Role: "user", Content: "first"},
			{Role: "assistant", Content: "answer"},
			{Role: "user", Content: "second"},
		},
		SchemaName:      "strategy_chat_reply",
		Schema:          schema,
		MaxOutputTokens: 16000,
	})
	if err != nil {
		t.Fatalf("ChatCompletion returned error: %v", err)
	}
	if result.Content != `{"reply":"ok","proposal":null}` || result.Provider != "grok" || result.Model != "grok-4.7" {
		t.Fatalf("unexpected result: %+v", result)
	}
	if result.InputTokens != 120 || result.OutputTokens != 30 || result.ReasoningTokens != 200 {
		t.Fatalf("expected usage mapped from Responses fields, got %+v", result)
	}
}

func TestGrokIncompleteReplyRetriesOnceAtLowEffort(t *testing.T) {
	grokChatEnv(t)

	efforts := make([]string, 0, 2)
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		payload := decodeAIRequest(t, req)
		reasoning, _ := payload["reasoning"].(map[string]any)
		efforts = append(efforts, reasoning["effort"].(string))
		if len(efforts) == 1 {
			return aiJSONResponse(http.StatusOK, xaiIncompleteResponse), nil
		}
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse(`{"reply":"short","proposal":null}`)), nil
	})

	result, err := service.ChatCompletion(context.Background(), 7, "grok", AIChatCompletionRequest{
		System: "Return JSON.", Turns: []AIChatTurn{{Role: "user", Content: "hi"}}, Schema: strategyChatReplySchema(),
	})
	if err != nil {
		t.Fatalf("expected the low-effort retry to succeed, got %v", err)
	}
	if strings.Join(efforts, ",") != "medium,low" {
		t.Fatalf("expected medium then low effort, got %v", efforts)
	}
	if !strings.Contains(result.Content, "short") {
		t.Fatalf("unexpected content %q", result.Content)
	}
}

func TestGrokIncompleteTwiceIsACleanCutOffError(t *testing.T) {
	grokChatEnv(t)

	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		return aiJSONResponse(http.StatusOK, xaiIncompleteResponse), nil
	})

	_, err := service.ChatCompletion(context.Background(), 7, "grok", AIChatCompletionRequest{
		System: "Return JSON.", Turns: []AIChatTurn{{Role: "user", Content: "hi"}},
	})
	var cutOff *aiReplyCutOffError
	if !errors.As(err, &cutOff) || err.Error() != aiReplyCutOffMessage {
		t.Fatalf("expected the cut-off error, got %v", err)
	}
	if attempts != 2 {
		t.Fatalf("expected exactly one retry, got %d attempts", attempts)
	}
}

func TestGrokIncompleteAtLowEffortIsNotRetried(t *testing.T) {
	grokChatEnv(t)
	t.Setenv("XAI_ANALYSIS_REASONING_EFFORT", "low")

	attempts := 0
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		attempts++
		return aiJSONResponse(http.StatusOK, xaiIncompleteResponse), nil
	})
	_, err := service.ChatCompletion(context.Background(), 7, "grok", AIChatCompletionRequest{
		System: "Return JSON.", Turns: []AIChatTurn{{Role: "user", Content: "hi"}},
	})
	var cutOff *aiReplyCutOffError
	if !errors.As(err, &cutOff) || attempts != 1 {
		t.Fatalf("expected one attempt and a cut-off error, got %d attempts and %v", attempts, err)
	}
}

func TestGrokRefusalAndMissingStatusAreErrors(t *testing.T) {
	cases := map[string]string{
		"refusal":        `{"status":"completed","output":[{"type":"message","content":[{"type":"refusal","refusal":"cannot help"}]}]}`,
		"failed status":  `{"status":"failed","output":[]}`,
		"missing status": `{"output":[{"type":"message","content":[{"type":"output_text","text":"hi"}]}]}`,
		"empty text":     `{"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"  "}]}]}`,
	}
	for name, body := range cases {
		t.Run(name, func(t *testing.T) {
			var response xaiResponsesResponse
			if err := json.Unmarshal([]byte(body), &response); err != nil {
				t.Fatalf("decode fixture: %v", err)
			}
			if _, err := parseXAIResponsesOutput(&response); err == nil {
				t.Fatalf("expected an error for %s", name)
			}
		})
	}
}

func TestGrokErrorBodiesInBothShapes(t *testing.T) {
	grokChatEnv(t)

	cases := []struct {
		status int
		body   string
		want   string
	}{
		{http.StatusNotFound, `{"code":"not-found","error":"The model grok-9 does not exist"}`, "The model grok-9 does not exist"},
		{http.StatusUnprocessableEntity, `{"error":{"type":"invalid_request_error","message":"schema is not supported"}}`, "schema is not supported"},
	}
	for _, tc := range cases {
		attempts := 0
		service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
			attempts++
			return aiJSONResponse(tc.status, tc.body), nil
		})
		_, err := service.ChatCompletion(context.Background(), 7, "grok", AIChatCompletionRequest{
			System: "Return JSON.", Turns: []AIChatTurn{{Role: "user", Content: "hi"}},
		})
		if err == nil || !strings.Contains(err.Error(), tc.want) {
			t.Fatalf("expected error containing %q, got %v", tc.want, err)
		}
		if attempts != 1 {
			t.Fatalf("expected a %d to be tried once, got %d attempts", tc.status, attempts)
		}
	}

	if detail := aiProviderErrorDetail([]byte(`not json`)); detail != "" {
		t.Fatalf("expected no detail from a non-JSON body, got %q", detail)
	}
}

func TestGrokKeyRejectionKeepsFixedMessage(t *testing.T) {
	grokChatEnv(t)
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusUnauthorized, `{"code":"unauthorized","error":"Incorrect API key provided: te***ey"}`), nil
	})
	_, err := service.ChatCompletion(context.Background(), 7, "grok", AIChatCompletionRequest{
		System: "Return JSON.", Turns: []AIChatTurn{{Role: "user", Content: "hi"}},
	})
	if err == nil || strings.Contains(err.Error(), "te***ey") || !strings.Contains(err.Error(), "rejected the configured API key") {
		t.Fatalf("expected the fixed key-rejection message, got %v", err)
	}
}

func TestGrokMarketSelectionUsesStrictSchemaAndLowEffort(t *testing.T) {
	grokChatEnv(t)
	service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
		payload := decodeAIRequest(t, req)
		if payload["max_output_tokens"] != float64(4000) {
			t.Fatalf("expected max_output_tokens 4000, got %#v", payload["max_output_tokens"])
		}
		reasoning, _ := payload["reasoning"].(map[string]any)
		if reasoning["effort"] != "low" {
			t.Fatalf("expected low effort for market selection, got %#v", payload["reasoning"])
		}
		text, _ := payload["text"].(map[string]any)
		format, _ := text["format"].(map[string]any)
		schema, _ := format["schema"].(map[string]any)
		required, _ := schema["required"].([]any)
		if format["type"] != "json_schema" || len(required) != 4 || schema["additionalProperties"] != false {
			t.Fatalf("expected the market selection schema, got %#v", format)
		}
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse(`{"selected_markets":["BTC-USD","ETH-USD"],"rationale":"liquid","confidence":0.7}`)), nil
	})

	result, err := service.callProvider(context.Background(), "test-xai-key", ExternalAPIProviderGrok, "ai_recommended", []string{"BTC-USD", "ETH-USD"}, 2, "", AIMarketCriteria{})
	if err != nil {
		t.Fatalf("callProvider returned error: %v", err)
	}
	if len(result.SelectedMarkets) != 2 || result.Confidence != 0.7 {
		t.Fatalf("unexpected selection %+v", result)
	}
}

func TestGrokTextTasksUsePlainTextAndTaskBudgets(t *testing.T) {
	grokChatEnv(t)
	cases := []struct {
		kind   aiRequestKind
		tokens float64
		effort string
	}{
		{aiRequestKindRuntimeDigest, 2000, "low"},
		// Explanations and suggestions are analysis kinds: analysis effort
		// and a budget with room for reasoning under the 150/170 s deadlines.
		{aiRequestKindBacktestExplain, 6000, "medium"},
		{aiRequestKindStrategyParams, 10000, "medium"},
	}
	for _, tc := range cases {
		service := newAIServiceWithTransport(func(req *http.Request) (*http.Response, error) {
			payload := decodeAIRequest(t, req)
			if payload["max_output_tokens"] != tc.tokens {
				t.Fatalf("%s: expected max_output_tokens %v, got %#v", tc.kind, tc.tokens, payload["max_output_tokens"])
			}
			reasoning, _ := payload["reasoning"].(map[string]any)
			if reasoning["effort"] != tc.effort {
				t.Fatalf("%s: expected effort %s, got %#v", tc.kind, tc.effort, payload["reasoning"])
			}
			if _, ok := payload["text"]; ok {
				t.Fatalf("%s: expected no structured format for a text task", tc.kind)
			}
			return aiJSONResponse(http.StatusOK, xaiCompletedResponse("Healthy. Keep monitoring.")), nil
		})
		content, err := service.callAIForTextTask(context.Background(), "test-xai-key", ExternalAPIProviderGrok, tc.kind, "system", "user")
		if err != nil || content != "Healthy. Keep monitoring." {
			t.Fatalf("%s: unexpected result %q, %v", tc.kind, content, err)
		}
	}
}

func TestAIUsageCountsMapsResponsesAndChatNames(t *testing.T) {
	var responses aiUsage
	if err := json.Unmarshal([]byte(`{"input_tokens":10,"input_tokens_details":{"cached_tokens":4},"output_tokens":5,"output_tokens_details":{"reasoning_tokens":7},"total_tokens":22}`), &responses); err != nil {
		t.Fatalf("decode: %v", err)
	}
	counts := responses.counts()
	if counts.prompt != 10 || counts.completion != 5 || counts.cacheHit != 4 || counts.reasoning != 7 || counts.total != 22 {
		t.Fatalf("unexpected Responses usage mapping: %+v", counts)
	}

	var chat aiUsage
	if err := json.Unmarshal([]byte(`{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5,"completion_tokens_details":{"reasoning_tokens":1}}`), &chat); err != nil {
		t.Fatalf("decode: %v", err)
	}
	counts = chat.counts()
	if counts.prompt != 3 || counts.completion != 2 || counts.total != 5 || counts.reasoning != 1 {
		t.Fatalf("unexpected Chat Completions usage mapping: %+v", counts)
	}
}
