package services

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"
)

const (
	defaultAIChatHTTPTimeout = 150 * time.Second
	aiChatMaxAttempts        = 2
	// aiChatMaxVisibleTokens caps the reply of providers whose limit counts
	// only visible output; every configured model already accepts 4096.
	aiChatMaxVisibleTokens = 4096
)

// AIChatTurn is one earlier message of a conversation.
type AIChatTurn struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// AIChatCompletionRequest is a multi-turn request whose reply is one JSON
// object. Schema is enforced by providers with structured outputs (Grok) and
// described in System for the others.
type AIChatCompletionRequest struct {
	System          string
	Turns           []AIChatTurn
	SchemaName      string
	Schema          map[string]any
	MaxOutputTokens int
	// kind selects the model, effort and output budget; the zero value is the
	// strategy chat. Parameter suggestions set it to run the same structured
	// call under their own budget.
	kind aiRequestKind
}

// requestKind is the request's kind, the strategy chat when unset.
func (r AIChatCompletionRequest) requestKind() aiRequestKind {
	if r.kind == "" {
		return aiRequestKindStrategyChat
	}
	return r.kind
}

// AIChatCompletionResult is the raw reply text (expected to be JSON).
type AIChatCompletionResult struct {
	Provider        string
	Model           string
	Content         string
	InputTokens     int
	OutputTokens    int
	ReasoningTokens int
}

// AIChatHTTPTimeout is the per-attempt timeout of chat provider calls,
// AI_CHAT_HTTP_TIMEOUT_SECONDS or 150 seconds.
func AIChatHTTPTimeout() time.Duration {
	raw := strings.TrimSpace(envWithDefault("AI_CHAT_HTTP_TIMEOUT_SECONDS", ""))
	if raw == "" {
		return defaultAIChatHTTPTimeout
	}
	seconds, err := strconv.Atoi(raw)
	if err != nil || seconds <= 0 {
		return defaultAIChatHTTPTimeout
	}
	return time.Duration(seconds) * time.Second
}

// AIChatMaxDuration bounds one chat call including its retry.
func AIChatMaxDuration() time.Duration {
	return time.Duration(aiChatMaxAttempts)*AIChatHTTPTimeout() + 15*time.Second
}

// ChatCompletion sends a multi-turn conversation to one provider and returns
// its reply. A provider failure is always an error, never a stand-in reply.
func (s *AIMarketService) ChatCompletion(ctx context.Context, userID int, provider string, req AIChatCompletionRequest) (*AIChatCompletionResult, error) {
	normalized, resolved, err := s.resolveUsableKey(userID, provider)
	if err != nil {
		return nil, err
	}
	if len(req.Turns) == 0 {
		return nil, fmt.Errorf("a chat request needs at least one message")
	}

	config := s.providerConfigForKind(normalized, req.requestKind())
	switch normalized {
	case ExternalAPIProviderGrok:
		return s.chatWithXAI(ctx, resolved.key, config, req)
	case ExternalAPIProviderOpenAI, ExternalAPIProviderDeepSeek:
		return s.chatWithOpenAICompatible(ctx, resolved.key, config, req)
	case ExternalAPIProviderClaude:
		return s.chatWithClaude(ctx, resolved.key, config, req)
	default:
		return nil, fmt.Errorf("unsupported AI provider: %s", provider)
	}
}

// executeChatJSON uses the chat client, tries at most twice and retries only
// rate limits, server errors and network failures. A client timeout is not
// retried: a second full wait would double an already long request.
func (s *AIMarketService) executeChatJSON(ctx context.Context, config aiProviderConfig, kind aiRequestKind, bearer string, payload any, target any, headers map[string]string) error {
	client := s.chatHTTPClient
	if client == nil {
		client = s.httpClient
	}
	return s.executeJSONWithPolicy(ctx, aiCallPolicy{
		client:            client,
		maxAttempts:       aiChatMaxAttempts,
		retryServerErrors: true,
		retryTimeouts:     false,
		describeErrors:    true,
	}, config, kind, bearer, payload, target, headers)
}

func (s *AIMarketService) chatWithXAI(ctx context.Context, apiKey string, config aiProviderConfig, req AIChatCompletionRequest) (*AIChatCompletionResult, error) {
	var format map[string]any
	if req.Schema != nil {
		name := strings.TrimSpace(req.SchemaName)
		if name == "" {
			name = "reply"
		}
		format = xaiJSONSchemaFormat(name, req.Schema)
	}
	text, usage, err := s.callXAIResponses(ctx, s.executeChatJSON, apiKey, config, req.requestKind(), req.System, req.Turns, format, req.MaxOutputTokens)
	if err != nil {
		return nil, err
	}
	return newAIChatCompletionResult(config, text, usage), nil
}

func (s *AIMarketService) chatWithOpenAICompatible(ctx context.Context, apiKey string, config aiProviderConfig, req AIChatCompletionRequest) (*AIChatCompletionResult, error) {
	messages := make([]map[string]string, 0, len(req.Turns)+1)
	messages = append(messages, map[string]string{"role": "system", "content": req.System})
	for _, turn := range req.Turns {
		messages = append(messages, map[string]string{"role": turn.Role, "content": turn.Content})
	}
	body := map[string]any{
		"model":       config.model,
		"messages":    messages,
		"temperature": 0.3,
		"max_tokens":  aiChatVisibleTokenLimit(req.MaxOutputTokens),
		// JSON mode; the system prompt carries the word JSON and the shape.
		"response_format": map[string]string{"type": "json_object"},
	}
	kind := req.requestKind()
	applyDeepSeekOptions(body, config, kind)

	var response struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
			FinishReason string `json:"finish_reason"`
		} `json:"choices"`
		Usage aiUsage `json:"usage"`
	}
	if err := s.executeChatJSON(ctx, config, kind, apiKey, body, &response, nil); err != nil {
		return nil, err
	}
	if len(response.Choices) == 0 {
		return nil, &aiProviderCallError{Message: fmt.Sprintf("%s returned no response", providerDisplayName(config.provider))}
	}
	if response.Choices[0].FinishReason == "length" {
		return nil, &aiReplyCutOffError{Provider: config.provider}
	}
	content := strings.TrimSpace(response.Choices[0].Message.Content)
	if content == "" {
		return nil, &aiProviderCallError{Message: fmt.Sprintf("%s returned an empty reply", providerDisplayName(config.provider))}
	}
	return newAIChatCompletionResult(config, content, response.Usage), nil
}

func (s *AIMarketService) chatWithClaude(ctx context.Context, apiKey string, config aiProviderConfig, req AIChatCompletionRequest) (*AIChatCompletionResult, error) {
	messages := make([]map[string]string, 0, len(req.Turns))
	for _, turn := range req.Turns {
		messages = append(messages, map[string]string{"role": turn.Role, "content": turn.Content})
	}
	// No temperature: the provider's newer models reject a non-default value.
	body := map[string]any{
		"model":      config.model,
		"max_tokens": aiChatVisibleTokenLimit(req.MaxOutputTokens),
		"system":     req.System,
		"messages":   messages,
	}

	var response struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
		StopReason string  `json:"stop_reason"`
		Usage      aiUsage `json:"usage"`
	}
	headers := map[string]string{
		"x-api-key":         apiKey,
		"anthropic-version": "2023-06-01",
	}
	if err := s.executeChatJSON(ctx, config, req.requestKind(), "", body, &response, headers); err != nil {
		return nil, err
	}
	if response.StopReason == "max_tokens" {
		return nil, &aiReplyCutOffError{Provider: config.provider}
	}
	var text strings.Builder
	for _, part := range response.Content {
		if part.Type == "" || part.Type == "text" {
			text.WriteString(part.Text)
		}
	}
	content := strings.TrimSpace(text.String())
	if content == "" {
		return nil, &aiProviderCallError{Message: "Claude returned an empty reply"}
	}
	return newAIChatCompletionResult(config, content, response.Usage), nil
}

func aiChatVisibleTokenLimit(requested int) int {
	if requested <= 0 || requested > aiChatMaxVisibleTokens {
		return aiChatMaxVisibleTokens
	}
	return requested
}

func newAIChatCompletionResult(config aiProviderConfig, content string, usage aiUsage) *AIChatCompletionResult {
	counts := usage.counts()
	return &AIChatCompletionResult{
		Provider:        config.provider,
		Model:           config.model,
		Content:         content,
		InputTokens:     counts.prompt,
		OutputTokens:    counts.completion,
		ReasoningTokens: counts.reasoning,
	}
}
