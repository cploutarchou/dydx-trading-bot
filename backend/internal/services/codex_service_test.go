package services

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCodexServiceStatusReflectsConfiguration(t *testing.T) {
	service := &CodexService{
		apiKey:          "",
		baseURL:         defaultCodexBaseURL,
		model:           "gpt-5.4",
		reasoningEffort: "medium",
	}

	status := service.Status()
	if status.Configured {
		t.Fatal("expected codex status to report not configured")
	}
	if !strings.Contains(status.Message, "OPENAI_API_KEY") {
		t.Fatalf("expected missing-key guidance, got %q", status.Message)
	}
}

func TestCodexServiceGenerateParsesOutputText(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer codex-test-key" {
			t.Fatalf("unexpected Authorization header: %q", got)
		}
		if got := r.Header.Get("X-Trace-Id"); got != "req-codex-test" {
			t.Fatalf("expected trace header to propagate, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"id":"resp_123",
			"model":"gpt-5.4",
			"output":[{"type":"message","content":[{"type":"output_text","text":"Focus on the lowest drawdown strategy first."}]}],
			"usage":{"input_tokens":123,"output_tokens":45,"total_tokens":168}
		}`))
	}))
	defer upstream.Close()

	service := &CodexService{
		apiKey:          "codex-test-key",
		baseURL:         upstream.URL,
		model:           "gpt-5.4",
		reasoningEffort: "medium",
		maxOutputTokens: 600,
		httpClient:      upstream.Client(),
	}

	result, err := service.Generate(context.Background(), "req-codex-test", CodexRequest{
		Prompt:  "Which strategy looks safest?",
		Context: "Best strategy has 12% drawdown. Safest strategy has 4% drawdown.",
		Mode:    "dashboard",
	})
	if err != nil {
		t.Fatalf("Generate returned error: %v", err)
	}

	if result.ResponseID != "resp_123" {
		t.Fatalf("unexpected response ID: %q", result.ResponseID)
	}
	if !strings.Contains(result.OutputText, "lowest drawdown") {
		t.Fatalf("unexpected output text: %q", result.OutputText)
	}
	if result.TotalTokens != 168 {
		t.Fatalf("unexpected token usage: %+v", result)
	}
}
