package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

const defaultCodexBaseURL = "https://api.openai.com/v1"

type CodexStatus struct {
	Configured      bool   `json:"configured"`
	Provider        string `json:"provider"`
	Model           string `json:"model"`
	BaseURL         string `json:"base_url"`
	ReasoningEffort string `json:"reasoning_effort"`
	Message         string `json:"message"`
}

type CodexRequest struct {
	Prompt  string `json:"prompt"`
	Context string `json:"context,omitempty"`
	Mode    string `json:"mode,omitempty"`
}

type CodexResult struct {
	ResponseID      string `json:"response_id"`
	Model           string `json:"model"`
	OutputText      string `json:"output_text"`
	ReasoningEffort string `json:"reasoning_effort"`
	InputTokens     int    `json:"input_tokens,omitempty"`
	OutputTokens    int    `json:"output_tokens,omitempty"`
	TotalTokens     int    `json:"total_tokens,omitempty"`
}

type CodexService struct {
	apiKey          string
	baseURL         string
	model           string
	reasoningEffort string
	maxOutputTokens int
	httpClient      *http.Client
}

type openAIResponsesRequest struct {
	Model           string               `json:"model"`
	Input           []openAIInputMessage `json:"input"`
	Reasoning       map[string]string    `json:"reasoning,omitempty"`
	MaxOutputTokens int                  `json:"max_output_tokens,omitempty"`
	Metadata        map[string]string    `json:"metadata,omitempty"`
}

type openAIInputMessage struct {
	Role    string               `json:"role"`
	Content []openAIInputContent `json:"content"`
}

type openAIInputContent struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type openAIResponsesResponse struct {
	ID         string `json:"id"`
	Model      string `json:"model"`
	OutputText string `json:"output_text"`
	Output     []struct {
		Type    string `json:"type"`
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
	} `json:"output"`
	Usage struct {
		InputTokens  int `json:"input_tokens"`
		OutputTokens int `json:"output_tokens"`
		TotalTokens  int `json:"total_tokens"`
	} `json:"usage"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

func NewCodexServiceFromEnv() *CodexService {
	baseURL := strings.TrimRight(strings.TrimSpace(os.Getenv("OPENAI_CODEX_BASE_URL")), "/")
	if baseURL == "" {
		baseURL = defaultCodexBaseURL
	}

	model := strings.TrimSpace(os.Getenv("OPENAI_CODEX_MODEL"))
	if model == "" {
		model = "gpt-5.4"
	}

	reasoningEffort := strings.TrimSpace(os.Getenv("OPENAI_CODEX_REASONING_EFFORT"))
	if reasoningEffort == "" {
		reasoningEffort = "medium"
	}

	maxOutputTokens := 1800
	if raw := strings.TrimSpace(os.Getenv("OPENAI_CODEX_MAX_OUTPUT_TOKENS")); raw != "" {
		if parsed, err := strconv.Atoi(raw); err == nil && parsed > 0 {
			maxOutputTokens = parsed
		}
	}

	return &CodexService{
		apiKey:          strings.TrimSpace(os.Getenv("OPENAI_API_KEY")),
		baseURL:         baseURL,
		model:           model,
		reasoningEffort: reasoningEffort,
		maxOutputTokens: maxOutputTokens,
		httpClient: &http.Client{
			Timeout: 45 * time.Second,
		},
	}
}

func (s *CodexService) Status() CodexStatus {
	configured := strings.TrimSpace(s.apiKey) != ""
	message := "Codex is ready for authenticated workspace assistance."
	if !configured {
		message = "Codex is not configured yet. Set OPENAI_API_KEY on the backend to enable it."
	}

	return CodexStatus{
		Configured:      configured,
		Provider:        "openai",
		Model:           s.model,
		BaseURL:         s.baseURL,
		ReasoningEffort: s.reasoningEffort,
		Message:         message,
	}
}

func (s *CodexService) Generate(ctx context.Context, traceID string, request CodexRequest) (*CodexResult, error) {
	if !s.Status().Configured {
		return nil, fmt.Errorf("codex is not configured: missing OPENAI_API_KEY")
	}

	prompt := strings.TrimSpace(request.Prompt)
	if prompt == "" {
		return nil, fmt.Errorf("prompt is required")
	}

	payload := openAIResponsesRequest{
		Model: s.model,
		Input: []openAIInputMessage{
			{
				Role: "system",
				Content: []openAIInputContent{
					{
						Type: "input_text",
						Text: buildCodexSystemPrompt(request.Mode),
					},
				},
			},
			{
				Role: "user",
				Content: []openAIInputContent{
					{
						Type: "input_text",
						Text: buildCodexUserPrompt(request),
					},
				},
			},
		},
		Reasoning: map[string]string{
			"effort": s.reasoningEffort,
		},
		MaxOutputTokens: s.maxOutputTokens,
		Metadata: map[string]string{
			"trace_id": traceID,
			"surface":  "dydx-trading-bot-dashboard",
		},
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal codex request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.baseURL+"/responses", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create codex request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+s.apiKey)
	req.Header.Set("Content-Type", "application/json")
	if strings.TrimSpace(traceID) != "" {
		req.Header.Set("X-Trace-Id", traceID)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to reach codex upstream: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read codex response: %w", err)
	}

	var apiResponse openAIResponsesResponse
	if err := json.Unmarshal(responseBody, &apiResponse); err != nil {
		return nil, fmt.Errorf("failed to decode codex response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		upstreamMessage := strings.TrimSpace(extractCodexErrorMessage(apiResponse, responseBody))
		if upstreamMessage == "" {
			upstreamMessage = fmt.Sprintf("codex upstream returned status %d", resp.StatusCode)
		}
		log.Printf("❌ Codex upstream error trace_id=%s status=%d body=%s", traceID, resp.StatusCode, strings.TrimSpace(string(responseBody)))
		return nil, fmt.Errorf("%s", upstreamMessage)
	}

	outputText := strings.TrimSpace(extractCodexOutputText(apiResponse))
	if outputText == "" {
		return nil, fmt.Errorf("codex returned an empty response")
	}

	return &CodexResult{
		ResponseID:      apiResponse.ID,
		Model:           firstNonEmpty(apiResponse.Model, s.model),
		OutputText:      outputText,
		ReasoningEffort: s.reasoningEffort,
		InputTokens:     apiResponse.Usage.InputTokens,
		OutputTokens:    apiResponse.Usage.OutputTokens,
		TotalTokens:     apiResponse.Usage.TotalTokens,
	}, nil
}

func buildCodexSystemPrompt(mode string) string {
	base := `You are Codex inside a production dYdX trading bot workspace.

Help the user with accurate, high-signal guidance about trading strategies, runtime issues, backtest interpretation, and application behavior.
Be concrete and practical.
Do not invent unavailable metrics, logs, or code paths.
If information is missing, say what is missing and recommend the safest next step.
Prefer risk-aware guidance over aggressive optimization.`

	switch strings.ToLower(strings.TrimSpace(mode)) {
	case "strategy-review":
		return base + "\n\nFocus on strategy quality, risk, and backtest interpretation."
	case "runtime-debug":
		return base + "\n\nFocus on debugging runtime failures, state mismatches, and deployment reliability."
	case "dashboard":
		return base + "\n\nFocus on explaining KPIs, rankings, and what the user should do next."
	default:
		return base
	}
}

func buildCodexUserPrompt(request CodexRequest) string {
	var builder strings.Builder
	builder.WriteString("User request:\n")
	builder.WriteString(strings.TrimSpace(request.Prompt))

	if contextText := strings.TrimSpace(request.Context); contextText != "" {
		builder.WriteString("\n\nApplication context:\n")
		builder.WriteString(contextText)
	}

	return builder.String()
}

func extractCodexOutputText(response openAIResponsesResponse) string {
	if strings.TrimSpace(response.OutputText) != "" {
		return response.OutputText
	}

	var segments []string
	for _, output := range response.Output {
		for _, content := range output.Content {
			if strings.TrimSpace(content.Text) != "" {
				segments = append(segments, content.Text)
			}
		}
	}

	return strings.TrimSpace(strings.Join(segments, "\n\n"))
}

func extractCodexErrorMessage(response openAIResponsesResponse, rawBody []byte) string {
	if response.Error != nil && strings.TrimSpace(response.Error.Message) != "" {
		return response.Error.Message
	}

	var fallback struct {
		Error *struct {
			Message string `json:"message"`
		} `json:"error"`
	}
	if err := json.Unmarshal(rawBody, &fallback); err == nil && fallback.Error != nil {
		return strings.TrimSpace(fallback.Error.Message)
	}

	return ""
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			return trimmed
		}
	}
	return ""
}
