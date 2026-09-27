package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"strings"
)

// Grok is called through the xAI Responses API (POST /v1/responses). xAI
// documents Chat Completions as its legacy endpoint.

const (
	xaiEffortLow    = "low"
	xaiEffortMedium = "medium"

	xaiIncompleteMaxOutputTokens = "max_output_tokens"

	// aiReplyCutOffMessage is returned when a reply stops at the output token
	// limit; a partial JSON reply is never parsed.
	aiReplyCutOffMessage = "The reply was cut off before it finished. Try a shorter or more specific question."
)

// aiReplyCutOffError is a reply that ended at the output token limit.
type aiReplyCutOffError struct {
	Provider string
}

func (e *aiReplyCutOffError) Error() string {
	return aiReplyCutOffMessage
}

// xaiIncompleteError is a Responses API reply with status "incomplete".
type xaiIncompleteError struct {
	Reason string
}

func (e *xaiIncompleteError) Error() string {
	reason := strings.TrimSpace(e.Reason)
	if reason == "" {
		reason = "unknown"
	}
	return fmt.Sprintf("Grok returned an incomplete reply (%s)", reason)
}

type xaiResponsesResponse struct {
	Status            string `json:"status"`
	IncompleteDetails *struct {
		Reason string `json:"reason"`
	} `json:"incomplete_details"`
	Output []struct {
		Type    string `json:"type"`
		Content []struct {
			Type    string `json:"type"`
			Text    string `json:"text"`
			Refusal string `json:"refusal"`
		} `json:"content"`
	} `json:"output"`
	Error json.RawMessage `json:"error"`
	Usage aiUsage         `json:"usage"`
}

// aiJSONExecutor posts one JSON request and decodes the 2xx body into target.
type aiJSONExecutor func(ctx context.Context, config aiProviderConfig, kind aiRequestKind, bearer string, payload any, target any, headers map[string]string) error

// xaiReasoningEffort is the reasoning effort of a kind: analysis kinds run at
// the analysis effort under the long chat deadlines, quick kinds at low. The
// policy lives in ai_model_policy.go.
func xaiReasoningEffort(kind aiRequestKind) string {
	return xaiReasoningEffortForKind(kind)
}

// xaiMaxOutputTokens bounds a Responses API reply; the limit includes the
// reasoning tokens. The policy lives in ai_model_policy.go.
func xaiMaxOutputTokens(kind aiRequestKind) int {
	return xaiMaxOutputTokensForKind(kind)
}

// buildXAIResponsesBody builds a stateless Responses API request: store is
// false so xAI keeps no conversation, and no sampling penalties or stop
// sequences are sent because reasoning models reject them.
func buildXAIResponsesBody(model string, system string, turns []AIChatTurn, maxOutputTokens int, effort string, format map[string]any) map[string]any {
	input := make([]map[string]string, 0, len(turns)+1)
	if strings.TrimSpace(system) != "" {
		input = append(input, map[string]string{"role": "system", "content": system})
	}
	for _, turn := range turns {
		input = append(input, map[string]string{"role": turn.Role, "content": turn.Content})
	}
	body := map[string]any{
		"model":             model,
		"input":             input,
		"store":             false,
		"max_output_tokens": maxOutputTokens,
		"reasoning":         map[string]string{"effort": effort},
	}
	if format != nil {
		body["text"] = map[string]any{"format": format}
	}
	return body
}

// xaiJSONSchemaFormat is the flat Responses API structured-output format.
func xaiJSONSchemaFormat(name string, schema map[string]any) map[string]any {
	return map[string]any{
		"type":   "json_schema",
		"name":   name,
		"schema": schema,
		"strict": true,
	}
}

// parseXAIResponsesOutput returns the reply text of a completed response.
func parseXAIResponsesOutput(response *xaiResponsesResponse) (string, error) {
	status := strings.ToLower(strings.TrimSpace(response.Status))
	if status == "incomplete" {
		reason := ""
		if response.IncompleteDetails != nil {
			reason = response.IncompleteDetails.Reason
		}
		return "", &xaiIncompleteError{Reason: reason}
	}
	if status != "completed" {
		if status == "" {
			status = "missing"
		}
		return "", &aiProviderCallError{Message: fmt.Sprintf("Grok returned a response with status %s", status)}
	}

	var text strings.Builder
	for _, item := range response.Output {
		if item.Type != "message" {
			continue
		}
		for _, part := range item.Content {
			switch part.Type {
			case "output_text":
				text.WriteString(part.Text)
			case "refusal":
				return "", &aiProviderCallError{Message: fmt.Sprintf("Grok declined to answer: %s", truncateAIText(part.Refusal, 240))}
			}
		}
	}
	content := strings.TrimSpace(text.String())
	if content == "" {
		return "", &aiProviderCallError{Message: "Grok returned an empty reply"}
	}
	return content, nil
}

// callXAIResponses sends one Responses API request. A reply cut off at the
// output limit is retried once at low effort; a second cut-off is an error.
func (s *AIMarketService) callXAIResponses(ctx context.Context, execute aiJSONExecutor, apiKey string, config aiProviderConfig, kind aiRequestKind, system string, turns []AIChatTurn, format map[string]any, maxOutputTokens int) (string, aiUsage, error) {
	if maxOutputTokens <= 0 {
		maxOutputTokens = xaiMaxOutputTokens(kind)
	}
	effort := xaiReasoningEffort(kind)

	text, usage, err := s.executeXAIResponses(ctx, execute, apiKey, config, kind, buildXAIResponsesBody(config.model, system, turns, maxOutputTokens, effort, format))
	var incomplete *xaiIncompleteError
	if errors.As(err, &incomplete) && incomplete.Reason == xaiIncompleteMaxOutputTokens && effort != xaiEffortLow && effort != "none" {
		text, usage, err = s.executeXAIResponses(ctx, execute, apiKey, config, kind, buildXAIResponsesBody(config.model, system, turns, maxOutputTokens, xaiEffortLow, format))
	}
	if errors.As(err, &incomplete) {
		if incomplete.Reason == xaiIncompleteMaxOutputTokens {
			return "", usage, &aiReplyCutOffError{Provider: config.provider}
		}
		return "", usage, err
	}
	return text, usage, err
}

func (s *AIMarketService) executeXAIResponses(ctx context.Context, execute aiJSONExecutor, apiKey string, config aiProviderConfig, kind aiRequestKind, body map[string]any) (string, aiUsage, error) {
	var response xaiResponsesResponse
	if err := execute(ctx, config, kind, apiKey, body, &response, nil); err != nil {
		return "", aiUsage{}, err
	}
	text, err := parseXAIResponsesOutput(&response)
	return text, response.Usage, err
}

// aiMarketSelectionSchema is the structured-output schema for market
// selection: at most limit tickers, a bounded list of pairs (both legs must
// be selected tickers; the server checks that) and a confidence in [0, 1].
func aiMarketSelectionSchema(limit int) map[string]any {
	if limit <= 0 {
		limit = defaultAIMarketLimit
	}
	return map[string]any{
		"type":                 "object",
		"additionalProperties": false,
		"required":             []string{"selected_markets", "pairs", "rationale", "confidence"},
		"properties": map[string]any{
			"selected_markets": map[string]any{
				"type":     "array",
				"items":    map[string]any{"type": "string"},
				"maxItems": limit,
			},
			"pairs": map[string]any{
				"type":     "array",
				"maxItems": aiMarketPairCap(limit),
				"items": map[string]any{
					"type":                 "object",
					"additionalProperties": false,
					"required":             []string{"market_1", "market_2", "reason"},
					"properties": map[string]any{
						"market_1": map[string]any{"type": "string"},
						"market_2": map[string]any{"type": "string"},
						"reason":   map[string]any{"type": "string"},
					},
				},
			},
			"rationale":  map[string]any{"type": "string"},
			"confidence": map[string]any{"type": "number", "minimum": 0, "maximum": 1},
		},
	}
}

func (s *AIMarketService) callXAIMarketSelection(ctx context.Context, apiKey string, config aiProviderConfig, prompt string, limit int) (*AIMarketSelectionResponse, error) {
	system := "You select dYdX perpetual markets for a crypto pairs-trading strategy from the market statistics you are given. Judge only by the numbers, never by ticker names or outside knowledge, and never claim profitability. Return only valid JSON matching the provided schema."
	text, _, err := s.callXAIResponses(
		ctx, s.executeJSON, apiKey, config, aiRequestKindMarketSelection,
		system, []AIChatTurn{{Role: "user", Content: prompt}},
		xaiJSONSchemaFormat("market_selection", aiMarketSelectionSchema(limit)), 0,
	)
	if err != nil {
		return nil, err
	}
	return parseAIMarketSelection(text)
}

func (s *AIMarketService) callXAIForText(ctx context.Context, apiKey string, config aiProviderConfig, kind aiRequestKind, systemPrompt string, userPrompt string) (string, error) {
	text, _, err := s.callXAIResponses(
		ctx, s.aiExecutorForKind(kind), apiKey, config, kind,
		systemPrompt, []AIChatTurn{{Role: "user", Content: userPrompt}},
		nil, 0,
	)
	return text, err
}

// aiProviderErrorDetail reads a provider error body in either documented xAI
// shape: {"code": "...", "error": "message"} or {"error": {"message": "..."}}.
func aiProviderErrorDetail(body []byte) string {
	if len(body) == 0 {
		return ""
	}
	var envelope struct {
		Error   json.RawMessage `json:"error"`
		Message string          `json:"message"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		return ""
	}
	var flat string
	if err := json.Unmarshal(envelope.Error, &flat); err == nil && strings.TrimSpace(flat) != "" {
		return truncateAIText(flat, 240)
	}
	var nested struct {
		Message string `json:"message"`
	}
	if err := json.Unmarshal(envelope.Error, &nested); err == nil && strings.TrimSpace(nested.Message) != "" {
		return truncateAIText(nested.Message, 240)
	}
	return truncateAIText(envelope.Message, 240)
}

// describeAIProviderError appends the provider's message to a rejected call.
// Key rejections keep the fixed message so a provider echo of the key never
// reaches a response or a log line.
func describeAIProviderError(err error, body []byte) {
	var callErr *aiProviderCallError
	if !errors.As(err, &callErr) || callErr.StatusCode < 400 {
		return
	}
	if callErr.StatusCode == http.StatusUnauthorized || callErr.StatusCode == http.StatusForbidden {
		return
	}
	if detail := aiProviderErrorDetail(body); detail != "" {
		callErr.Message = fmt.Sprintf("%s: %s", callErr.Message, detail)
	}
}

func isNetTimeout(err error) bool {
	var netErr net.Error
	return errors.As(err, &netErr) && netErr.Timeout()
}

func isAIClientTimeout(err error) bool {
	var callErr *aiProviderCallError
	return errors.As(err, &callErr) && callErr.Timeout
}

func truncateAIText(value string, limit int) string {
	value = strings.TrimSpace(value)
	runes := []rune(value)
	if limit <= 0 || len(runes) <= limit {
		return value
	}
	return strings.TrimSpace(string(runes[:limit])) + "..."
}
