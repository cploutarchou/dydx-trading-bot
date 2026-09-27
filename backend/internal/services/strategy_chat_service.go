package services

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// StrategyChatDefaultProvider answers when a chat request names no provider.
const StrategyChatDefaultProvider = ExternalAPIProviderGrok

const (
	StrategyChatMaxContentRunes = 4000
	strategyChatHistoryMessages = 20
	strategyChatListMessages    = 200
	strategyChatMaxOutputTokens = 16000
	strategyChatSchemaName      = "strategy_chat_reply"
	strategyChatMaxNameRunes    = 100
)

// Error codes of the strategy chat HTTP contract.
const (
	StrategyChatCodeNotFound              = "NOT_FOUND"
	StrategyChatCodeInvalidRequest        = "INVALID_REQUEST"
	StrategyChatCodeInvalidProposalFields = "INVALID_PROPOSAL_FIELDS"
	StrategyChatCodeRunningAckRequired    = "STRATEGY_RUNNING_ACK_REQUIRED"
	StrategyChatCodeProposalNotPending    = "PROPOSAL_NOT_PENDING"
	StrategyChatCodeRateLimited           = "CHAT_RATE_LIMITED"
	StrategyChatCodeBusy                  = "CHAT_BUSY"
	StrategyChatCodeQuotaExceeded         = "STRATEGY_QUOTA_EXCEEDED"
	StrategyChatCodeProviderDisabled      = "AI_PROVIDER_DISABLED"
	StrategyChatCodeProviderNotConfigured = "AI_PROVIDER_NOT_CONFIGURED"
	StrategyChatCodeProviderError         = "AI_PROVIDER_ERROR"
	StrategyChatCodeTimeout               = "AI_TIMEOUT"
	StrategyChatCodeInternal              = "INTERNAL_ERROR"
)

// StrategyChatError is a chat failure with its HTTP status and contract code.
type StrategyChatError struct {
	Status  int
	Code    string
	Message string
}

func (e *StrategyChatError) Error() string {
	return e.Message
}

func newStrategyChatError(status int, code, message string) *StrategyChatError {
	return &StrategyChatError{Status: status, Code: code, Message: message}
}

func strategyChatInternalError(action string, err error) *StrategyChatError {
	log.Printf("strategy_chat %s failed: %v", action, err)
	return newStrategyChatError(http.StatusInternalServerError, StrategyChatCodeInternal, "Something went wrong. Try again.")
}

// StrategyChatAI is the provider call the chat depends on.
type StrategyChatAI interface {
	ChatCompletion(ctx context.Context, userID int, provider string, req AIChatCompletionRequest) (*AIChatCompletionResult, error)
}

// StrategyChatActor is the signed-in caller.
type StrategyChatActor struct {
	UserID  int
	IsAdmin bool
}

// StrategyChatSessionView is a session as the API returns it.
type StrategyChatSessionView struct {
	ID         int64  `json:"id"`
	StrategyID int    `json:"strategy_id"`
	Title      string `json:"title"`
	CreatedAt  string `json:"created_at"`
	UpdatedAt  string `json:"updated_at"`
}

// StrategyChatProposalResult records what applying or creating did.
// AppliedFields and UnchangedFields are pointers so that an empty list is
// stored and returned as [] for applied and created proposals (a plain slice
// with omitempty would drop it), and absent for dismissed ones.
type StrategyChatProposalResult struct {
	AppliedFields       *[]string `json:"applied_fields,omitempty"`
	UnchangedFields     *[]string `json:"unchanged_fields,omitempty"`
	VersionID           *int      `json:"version_id,omitempty"`
	NewStrategyID       *int      `json:"new_strategy_id,omitempty"`
	NewStrategyName     string    `json:"new_strategy_name,omitempty"`
	AcknowledgedRunning *bool     `json:"acknowledged_running,omitempty"`
	At                  string    `json:"at"`
}

// StrategyChatMessageView is a message as the API returns it.
type StrategyChatMessageView struct {
	ID             int64                       `json:"id"`
	SessionID      int64                       `json:"session_id"`
	Role           string                      `json:"role"`
	Content        string                      `json:"content"`
	Proposal       *StrategyChatProposal       `json:"proposal"`
	ProposalStatus *string                     `json:"proposal_status"`
	ProposalResult *StrategyChatProposalResult `json:"proposal_result"`
	Provider       string                      `json:"provider"`
	Model          string                      `json:"model"`
	CreatedAt      string                      `json:"created_at"`
	// EvidenceSummary says what data the assistant reply was based on. It is
	// set on the assistant message of the turn that produced it and null on
	// user messages and on messages loaded later.
	EvidenceSummary *AIEvidenceSummary `json:"evidence_summary"`
}

// StrategyChatState is the GET /chat payload.
type StrategyChatState struct {
	Session       *StrategyChatSessionView  `json:"session"`
	Messages      []StrategyChatMessageView `json:"messages"`
	RuntimeActive bool                      `json:"runtime_active"`
}

// StrategyChatTurn is a session with the messages a request added.
type StrategyChatTurn struct {
	Session  *StrategyChatSessionView  `json:"session"`
	Messages []StrategyChatMessageView `json:"messages"`
}

// StrategyChatSendInput is one user message.
type StrategyChatSendInput struct {
	SessionID *int64
	Content   string
	Provider  string
	// BotToken is the caller's bot API token for deployments that forward
	// user tokens to the bot; it is never stored or sent to a provider.
	BotToken string
}

// StrategyChatApplyInput selects changes to apply; nil Fields means all.
type StrategyChatApplyInput struct {
	Fields             *[]string
	AcknowledgeRunning bool
}

// StrategyChatCreateInput names the new strategy and selects changes; nil
// Fields means all.
type StrategyChatCreateInput struct {
	Name   string
	Fields *[]string
}

// StrategyChatActionResult is the outcome of apply or create-strategy.
type StrategyChatActionResult struct {
	Strategy     *models.BacktestStrategy
	Message      StrategyChatMessageView
	AuditDetails map[string]any
}

// StrategyChatService runs the per-strategy assistant chat.
type StrategyChatService struct {
	repo       *repository.StrategyChatRepository
	strategies *StrategyService
	backtests  *repository.BacktestRepository
	users      *repository.UserRepository
	ai         StrategyChatAI
	// evidence builds the data block of a turn (runs, ledger, live runtime,
	// pair scan); nil means completed runs only.
	evidence *StrategyEvidenceBuilder
}

// NewStrategyChatService wires the chat service.
func NewStrategyChatService(
	repo *repository.StrategyChatRepository,
	strategies *StrategyService,
	backtests *repository.BacktestRepository,
	users *repository.UserRepository,
	ai StrategyChatAI,
) *StrategyChatService {
	return &StrategyChatService{
		repo:       repo,
		strategies: strategies,
		backtests:  backtests,
		users:      users,
		ai:         ai,
	}
}

// SetEvidenceBuilder wires the strategy evidence into chat turns.
func (s *StrategyChatService) SetEvidenceBuilder(builder *StrategyEvidenceBuilder) {
	s.evidence = builder
}

// AuthorizeStrategy returns the strategy when the caller owns it or is an
// admin. Missing, deleted and foreign strategies are all "not found".
func (s *StrategyChatService) AuthorizeStrategy(actor StrategyChatActor, strategyID int) (*models.BacktestStrategy, error) {
	if strategyID <= 0 || actor.UserID <= 0 {
		return nil, newStrategyChatError(http.StatusNotFound, StrategyChatCodeNotFound, "Strategy not found")
	}
	strategy, err := s.strategies.GetStrategy(strategyID)
	if err != nil {
		return nil, strategyChatInternalError("load strategy", err)
	}
	if strategy == nil || strategy.DeletedAt != nil || (strategy.UserID != actor.UserID && !actor.IsAdmin) {
		return nil, newStrategyChatError(http.StatusNotFound, StrategyChatCodeNotFound, "Strategy not found")
	}
	return strategy, nil
}

// GetChat returns the caller's current session for the strategy, its
// messages and whether the strategy is running (or its state is unknown).
func (s *StrategyChatService) GetChat(actor StrategyChatActor, strategyID int) (*StrategyChatState, error) {
	strategy, err := s.AuthorizeStrategy(actor, strategyID)
	if err != nil {
		return nil, err
	}
	session, err := s.repo.GetActiveSession(actor.UserID, strategy.ID)
	if err != nil {
		return nil, strategyChatInternalError("load session", err)
	}
	state := &StrategyChatState{Messages: make([]StrategyChatMessageView, 0)}
	if session != nil {
		state.Session = strategyChatSessionView(session)
		messages, err := s.repo.ListRecentMessages(session.ID, strategyChatListMessages)
		if err != nil {
			return nil, strategyChatInternalError("load messages", err)
		}
		for i := range messages {
			state.Messages = append(state.Messages, strategyChatMessageView(&messages[i]))
		}
	}
	state.RuntimeActive = strategyChatRuntimeActive(s.strategies.GetExecutionState(strategy.ID))
	return state, nil
}

// StartSession archives the current session and starts an empty one.
func (s *StrategyChatService) StartSession(actor StrategyChatActor, strategyID int) (*StrategyChatTurn, error) {
	strategy, err := s.AuthorizeStrategy(actor, strategyID)
	if err != nil {
		return nil, err
	}
	session, err := s.repo.StartSession(actor.UserID, strategy.ID)
	if err != nil {
		return nil, strategyChatInternalError("start session", err)
	}
	return &StrategyChatTurn{Session: strategyChatSessionView(session), Messages: make([]StrategyChatMessageView, 0)}, nil
}

// ValidateMessageInput checks the message text and provider before any
// provider or rate-limit work, and returns them normalized.
func (s *StrategyChatService) ValidateMessageInput(input StrategyChatSendInput) (string, string, error) {
	content := strings.TrimSpace(input.Content)
	length := len([]rune(content))
	if length == 0 {
		return "", "", newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidRequest, "Write a message first")
	}
	if length > StrategyChatMaxContentRunes {
		return "", "", newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidRequest,
			fmt.Sprintf("A message can be at most %d characters", StrategyChatMaxContentRunes))
	}
	provider := StrategyChatDefaultProvider
	if strings.TrimSpace(input.Provider) != "" {
		normalized, err := normalizeAIProvider(input.Provider)
		if err != nil {
			return "", "", newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidRequest, "Unsupported AI provider")
		}
		provider = normalized
	}
	return content, provider, nil
}

// SendMessage runs one turn: it builds the strategy context, asks the
// provider, validates any proposal and stores both messages together. Nothing
// is stored when any step fails.
func (s *StrategyChatService) SendMessage(ctx context.Context, actor StrategyChatActor, strategyID int, input StrategyChatSendInput) (*StrategyChatTurn, error) {
	content, provider, err := s.ValidateMessageInput(input)
	if err != nil {
		return nil, err
	}
	strategy, err := s.AuthorizeStrategy(actor, strategyID)
	if err != nil {
		return nil, err
	}
	session, err := s.resolveSession(actor, strategy.ID, input.SessionID)
	if err != nil {
		return nil, err
	}

	history := make([]models.StrategyChatMessage, 0)
	if session.ID > 0 {
		history, err = s.repo.ListRecentMessages(session.ID, strategyChatHistoryMessages)
		if err != nil {
			return nil, strategyChatInternalError("load history", err)
		}
	}

	state, stateErr := s.strategies.GetExecutionState(strategy.ID)
	var evidence *StrategyEvidence
	if s.evidence != nil {
		evidence = s.evidence.Build(ctx, strategy, state, stateErr, EvidenceOptions{IncludeLive: true, BotToken: input.BotToken})
	} else {
		var runs []models.BacktestRun
		runsErr := fmt.Errorf("backtest repository is not configured")
		if s.backtests != nil {
			runs, runsErr = s.backtests.GetRunsByStrategyID(strategy.UserID, strategy.ID, strategyChatContextBacktests)
		}
		if runsErr != nil {
			log.Printf("strategy_chat backtest context unavailable strategy_id=%d: %v", strategy.ID, runsErr)
		}
		evidence = evidenceFromRuns(runs, runsErr)
	}
	system, err := buildStrategyChatSystemPrompt(buildStrategyChatContextWithEvidence(strategy, evidence, state, stateErr))
	if err != nil {
		return nil, strategyChatInternalError("build prompt", err)
	}

	turns := append(strategyChatHistoryTurns(history), AIChatTurn{Role: models.StrategyChatRoleUser, Content: content})
	result, err := s.ai.ChatCompletion(ctx, actor.UserID, provider, AIChatCompletionRequest{
		System:          system,
		Turns:           turns,
		SchemaName:      strategyChatSchemaName,
		Schema:          strategyChatReplySchema(),
		MaxOutputTokens: strategyChatMaxOutputTokens,
	})
	if err != nil {
		return nil, strategyChatAIError(ctx, actor, provider, err)
	}

	reply, err := parseStrategyChatModelReply(result.Content)
	if err != nil {
		log.Printf("strategy_chat unreadable reply provider=%s model=%s: %v", result.Provider, result.Model, err)
		return nil, newStrategyChatError(http.StatusBadGateway, StrategyChatCodeProviderError,
			fmt.Sprintf("%s returned a reply that could not be read. Try again.", providerDisplayName(provider)))
	}

	userMessage := &models.StrategyChatMessage{
		Role:     models.StrategyChatRoleUser,
		Content:  content,
		Provider: provider,
	}
	assistantMessage := &models.StrategyChatMessage{
		Role:         models.StrategyChatRoleAssistant,
		Content:      reply.Reply,
		Provider:     result.Provider,
		Model:        result.Model,
		InputTokens:  result.InputTokens,
		OutputTokens: result.OutputTokens,
	}
	if proposal := validateStrategyChatProposal(reply.Proposal, strategy); proposal != nil {
		encoded, err := json.Marshal(proposal)
		if err != nil {
			return nil, strategyChatInternalError("encode proposal", err)
		}
		assistantMessage.Proposal = sql.NullString{String: string(encoded), Valid: true}
		assistantMessage.ProposalStatus = sql.NullString{String: models.StrategyChatProposalPending, Valid: true}
	}

	if strings.TrimSpace(session.Title) == "" {
		session.Title = strategyChatTitle(content)
	}
	if err := s.repo.AppendTurn(session, userMessage, assistantMessage); err != nil {
		return nil, strategyChatInternalError("store turn", err)
	}
	assistantView := strategyChatMessageView(assistantMessage)
	summary := evidence.Summary
	assistantView.EvidenceSummary = &summary
	return &StrategyChatTurn{
		Session:  strategyChatSessionView(session),
		Messages: []StrategyChatMessageView{strategyChatMessageView(userMessage), assistantView},
	}, nil
}

// ValidateSendTarget checks, before any rate-limit or provider work, that the
// caller may chat about the strategy and that a given session_id is the
// caller's current session for it; a foreign or archived session is not found.
func (s *StrategyChatService) ValidateSendTarget(actor StrategyChatActor, strategyID int, sessionID *int64) error {
	strategy, err := s.AuthorizeStrategy(actor, strategyID)
	if err != nil {
		return err
	}
	_, err = s.resolveSession(actor, strategy.ID, sessionID)
	return err
}

func (s *StrategyChatService) resolveSession(actor StrategyChatActor, strategyID int, sessionID *int64) (*models.StrategyChatSession, error) {
	if sessionID != nil {
		session, err := s.repo.GetSession(*sessionID)
		if err != nil {
			return nil, strategyChatInternalError("load session", err)
		}
		if session == nil || session.UserID != actor.UserID || session.StrategyID != strategyID || session.ArchivedAt != nil {
			return nil, newStrategyChatError(http.StatusNotFound, StrategyChatCodeNotFound, "Chat session not found")
		}
		return session, nil
	}
	session, err := s.repo.GetActiveSession(actor.UserID, strategyID)
	if err != nil {
		return nil, strategyChatInternalError("load session", err)
	}
	if session == nil {
		// Created together with the first turn, so a failed turn stores nothing.
		session = &models.StrategyChatSession{UserID: actor.UserID, StrategyID: strategyID}
	}
	return session, nil
}

// strategyChatAIError maps a provider failure onto the contract codes. The
// provider's own error text (which can name the account, the model or the
// configured endpoint) goes to the server log and, appended to the fixed
// message, to admins only; other users get a fixed message per status class.
func strategyChatAIError(ctx context.Context, actor StrategyChatActor, provider string, err error) error {
	name := providerDisplayName(provider)
	var accessErr *AIProviderAccessError
	if errors.As(err, &accessErr) {
		switch accessErr.Code {
		case http.StatusForbidden:
			return newStrategyChatError(http.StatusForbidden, StrategyChatCodeProviderDisabled, accessErr.Message)
		case http.StatusConflict:
			return newStrategyChatError(http.StatusConflict, StrategyChatCodeProviderNotConfigured, accessErr.Message)
		}
	}
	if errors.Is(err, context.DeadlineExceeded) || ctx.Err() != nil || isAIClientTimeout(err) {
		log.Printf("strategy_chat provider timeout provider=%s: %v", provider, err)
		return newStrategyChatError(http.StatusGatewayTimeout, StrategyChatCodeTimeout,
			fmt.Sprintf("%s did not answer in time. Try again.", name))
	}
	var cutOff *aiReplyCutOffError
	if errors.As(err, &cutOff) {
		return newStrategyChatError(http.StatusBadGateway, StrategyChatCodeProviderError, aiReplyCutOffMessage)
	}
	log.Printf("strategy_chat provider error provider=%s: %v", provider, err)
	var message string
	var callErr *aiProviderCallError
	switch {
	case errors.As(err, &callErr) && callErr.StatusCode == http.StatusTooManyRequests:
		message = fmt.Sprintf("%s rate limit reached. Try again in a minute.", name)
	case errors.As(err, &callErr) && callErr.StatusCode >= 500:
		message = fmt.Sprintf("%s is having trouble. Try again.", name)
	case errors.As(err, &callErr) && callErr.StatusCode >= 400:
		message = fmt.Sprintf("%s rejected the request or the model is not available. Ask an admin to check the AI provider settings.", name)
	case errors.As(err, &callErr):
		// No status: the request never got an answer (network, TLS, decoding).
		message = fmt.Sprintf("Could not reach %s. Try again.", name)
	default:
		message = fmt.Sprintf("%s could not answer. Try again.", name)
	}
	if actor.IsAdmin {
		message += " Provider detail: " + truncateAIText(err.Error(), 400)
	}
	return newStrategyChatError(http.StatusBadGateway, StrategyChatCodeProviderError, message)
}

// ApplyProposal applies the selected changes of a pending proposal to the
// strategy in one transaction: the proposal is claimed, the strategy row is
// re-read under a lock and the changes re-validated against it, the strategy
// as it was is saved as a version (so the existing revert endpoint can restore
// it), only the applied columns are written, and the result is stored. Any
// failure rolls everything back and the proposal stays pending. Nothing
// reaches a running bot: the change takes effect on the next stop and start.
func (s *StrategyChatService) ApplyProposal(actor StrategyChatActor, strategyID int, messageID int64, input StrategyChatApplyInput) (*StrategyChatActionResult, error) {
	strategy, err := s.AuthorizeStrategy(actor, strategyID)
	if err != nil {
		return nil, err
	}
	message, proposal, err := s.loadPendingProposal(actor, strategy.ID, messageID)
	if err != nil {
		return nil, err
	}
	selected, err := selectStrategyChatChanges(proposal, input.Fields, false)
	if err != nil {
		return nil, err
	}
	// Refuse bad requests before any lock is taken; the pass that counts runs
	// against the locked row below.
	if _, _, err := revalidateStrategyChatChanges(selected, strategy); err != nil {
		return nil, err
	}

	runtimeActive := strategyChatRuntimeActive(s.strategies.GetExecutionState(strategy.ID))
	if runtimeActive && !input.AcknowledgeRunning {
		return nil, newStrategyChatError(http.StatusConflict, StrategyChatCodeRunningAckRequired,
			"The strategy is running or its state is unknown. Confirm that the change only takes effect after you stop and start it.")
	}

	tx, err := s.repo.Begin()
	if err != nil {
		return nil, strategyChatInternalError("begin apply transaction", err)
	}
	defer rollbackStrategyChatTx(tx)
	chatTx := s.repo.WithTx(tx)
	strategyTx := s.strategies.WithTx(tx)

	if err := claimStrategyChatProposal(chatTx, message.ID, models.StrategyChatProposalApplied); err != nil {
		return nil, err
	}
	fresh, err := strategyTx.GetStrategyForUpdate(strategy.ID)
	if err != nil {
		return nil, strategyChatInternalError("lock strategy", err)
	}
	if fresh == nil || fresh.DeletedAt != nil {
		return nil, newStrategyChatError(http.StatusNotFound, StrategyChatCodeNotFound, "Strategy not found")
	}
	updates, unchangedFields, err := revalidateStrategyChatChanges(selected, fresh)
	if err != nil {
		return nil, err
	}
	if len(updates) == 0 {
		return nil, newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidProposalFields,
			"The selected changes already match the strategy")
	}

	before := *fresh
	version, err := strategyTx.SaveVersionSnapshot(&before, actor.UserID, "Before assistant change: "+proposal.Title)
	if err != nil {
		return nil, strategyChatInternalError("save version snapshot", err)
	}

	appliedFields, beforeValues, afterValues := applyStrategyChatUpdates(fresh, updates)
	if err := strategyTx.UpdateStrategyFields(fresh.ID, afterValues); err != nil {
		return nil, strategyChatInternalError("update strategy", err)
	}
	fresh.UpdatedAt = time.Now().UTC()

	result := StrategyChatProposalResult{
		AppliedFields:   &appliedFields,
		UnchangedFields: &unchangedFields,
		VersionID:       &version.ID,
		At:              time.Now().UTC().Format(time.RFC3339),
	}
	if runtimeActive {
		acknowledged := true
		result.AcknowledgedRunning = &acknowledged
	}
	view, err := storeStrategyChatProposalResult(chatTx, message, models.StrategyChatProposalApplied, result)
	if err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, strategyChatInternalError("commit apply transaction", err)
	}

	return &StrategyChatActionResult{
		Strategy: fresh,
		Message:  view,
		AuditDetails: map[string]any{
			"session_id":           message.SessionID,
			"message_id":           message.ID,
			"provider":             message.Provider,
			"model":                message.Model,
			"proposal_title":       proposal.Title,
			"proposal_kind":        proposal.Kind,
			"applied_fields":       appliedFields,
			"unchanged_fields":     unchangedFields,
			"before":               beforeValues,
			"after":                afterValues,
			"version_id":           version.ID,
			"runtime_active":       runtimeActive,
			"acknowledged_running": runtimeActive && input.AcknowledgeRunning,
		},
	}, nil
}

// CreateStrategyFromProposal creates a new strategy owned by the caller from
// the source strategy's settings plus the selected changes, in one transaction
// with the proposal claim and the quota check (the owner's user row is locked
// first, so two concurrent requests cannot both pass the count). The source is
// not modified.
func (s *StrategyChatService) CreateStrategyFromProposal(actor StrategyChatActor, strategyID int, messageID int64, input StrategyChatCreateInput) (*StrategyChatActionResult, error) {
	source, err := s.AuthorizeStrategy(actor, strategyID)
	if err != nil {
		return nil, err
	}
	message, proposal, err := s.loadPendingProposal(actor, source.ID, messageID)
	if err != nil {
		return nil, err
	}
	selected, err := selectStrategyChatChanges(proposal, input.Fields, true)
	if err != nil {
		return nil, err
	}
	if _, _, err := revalidateStrategyChatChanges(selected, source); err != nil {
		return nil, err
	}
	name, err := strategyChatNewStrategyName(input.Name, proposal.SuggestedName, source.Name)
	if err != nil {
		return nil, err
	}
	if s.users == nil {
		return nil, strategyChatInternalError("enforce strategy quota", errors.New("user repository is not configured"))
	}

	tx, err := s.repo.Begin()
	if err != nil {
		return nil, strategyChatInternalError("begin create transaction", err)
	}
	defer rollbackStrategyChatTx(tx)
	chatTx := s.repo.WithTx(tx)
	strategyTx := s.strategies.WithTx(tx)
	usersTx := s.users.WithTx(tx)

	if err := claimStrategyChatProposal(chatTx, message.ID, models.StrategyChatProposalCreated); err != nil {
		return nil, err
	}

	// Quota: the user row lock serializes concurrent creators; a failed lookup
	// is an error, never a default limit.
	if err := usersTx.LockUserForWrite(actor.UserID); err != nil {
		return nil, strategyChatInternalError("lock user", err)
	}
	user, err := usersTx.GetByID(actor.UserID)
	if err != nil || user == nil {
		if err == nil {
			err = errors.New("user not found")
		}
		return nil, strategyChatInternalError("load user quota", err)
	}
	maxStrategies := user.MaxStrategies
	if maxStrategies <= 0 {
		maxStrategies = 10
	}
	owned, err := strategyTx.CountStrategies(actor.UserID)
	if err != nil {
		return nil, strategyChatInternalError("enforce strategy quota", err)
	}
	if owned >= maxStrategies {
		return nil, newStrategyChatError(http.StatusTooManyRequests, StrategyChatCodeQuotaExceeded,
			fmt.Sprintf("Strategy limit reached for this account (%d/%d). Ask an admin to increase your strategy quota.", owned, maxStrategies))
	}

	fresh, err := strategyTx.GetStrategyForUpdate(source.ID)
	if err != nil {
		return nil, strategyChatInternalError("lock strategy", err)
	}
	if fresh == nil || fresh.DeletedAt != nil {
		return nil, newStrategyChatError(http.StatusNotFound, StrategyChatCodeNotFound, "Strategy not found")
	}
	updates, unchangedFields, err := revalidateStrategyChatChanges(selected, fresh)
	if err != nil {
		return nil, err
	}

	created, err := strategyTx.CreateStrategy(actor.UserID, name, fresh.Description, fresh.Category, false, false)
	if err != nil {
		return nil, strategyChatInternalError("create strategy", err)
	}
	copyStrategyChatSettings(created, fresh)
	appliedFields, beforeValues, afterValues := applyStrategyChatUpdates(created, updates)
	// The row is brand new and only this transaction can see it, so a full-row
	// write of the copied settings is safe here.
	if err := strategyTx.UpdateStrategy(created); err != nil {
		return nil, strategyChatInternalError("store new strategy", err)
	}

	newID := created.ID
	result := StrategyChatProposalResult{
		AppliedFields:   &appliedFields,
		UnchangedFields: &unchangedFields,
		NewStrategyID:   &newID,
		NewStrategyName: created.Name,
		At:              time.Now().UTC().Format(time.RFC3339),
	}
	view, err := storeStrategyChatProposalResult(chatTx, message, models.StrategyChatProposalCreated, result)
	if err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, strategyChatInternalError("commit create transaction", err)
	}

	return &StrategyChatActionResult{
		Strategy: created,
		Message:  view,
		AuditDetails: map[string]any{
			"session_id":         message.SessionID,
			"message_id":         message.ID,
			"provider":           message.Provider,
			"model":              message.Model,
			"proposal_title":     proposal.Title,
			"proposal_kind":      proposal.Kind,
			"source_strategy_id": fresh.ID,
			"new_strategy_id":    created.ID,
			"new_strategy_name":  created.Name,
			"applied_fields":     appliedFields,
			"unchanged_fields":   unchangedFields,
			"before":             beforeValues,
			"after":              afterValues,
		},
	}, nil
}

// DismissProposal closes a pending proposal without changing anything: one
// conditional update, no transaction needed.
func (s *StrategyChatService) DismissProposal(actor StrategyChatActor, strategyID int, messageID int64) (*StrategyChatMessageView, error) {
	strategy, err := s.AuthorizeStrategy(actor, strategyID)
	if err != nil {
		return nil, err
	}
	message, _, err := s.loadPendingProposal(actor, strategy.ID, messageID)
	if err != nil {
		return nil, err
	}
	result := StrategyChatProposalResult{At: time.Now().UTC().Format(time.RFC3339)}
	encoded, err := json.Marshal(result)
	if err != nil {
		return nil, strategyChatInternalError("encode proposal result", err)
	}
	changed, err := s.repo.TransitionProposal(message.ID, models.StrategyChatProposalPending, models.StrategyChatProposalDismissed,
		sql.NullString{String: string(encoded), Valid: true})
	if err != nil {
		return nil, strategyChatInternalError("dismiss proposal", err)
	}
	if !changed {
		return nil, strategyChatProposalNotPending()
	}
	view := strategyChatMessageViewWithResult(message, models.StrategyChatProposalDismissed, string(encoded))
	return &view, nil
}

func strategyChatProposalNotPending() *StrategyChatError {
	return newStrategyChatError(http.StatusConflict, StrategyChatCodeProposalNotPending, "This proposal was already applied, used or dismissed")
}

// loadPendingProposal returns the caller's assistant message and its proposal
// while the proposal is still pending.
func (s *StrategyChatService) loadPendingProposal(actor StrategyChatActor, strategyID int, messageID int64) (*models.StrategyChatMessage, *StrategyChatProposal, error) {
	notFound := newStrategyChatError(http.StatusNotFound, StrategyChatCodeNotFound, "Message not found")
	if messageID <= 0 {
		return nil, nil, notFound
	}
	message, err := s.repo.GetMessage(messageID)
	if err != nil {
		return nil, nil, strategyChatInternalError("load message", err)
	}
	if message == nil {
		return nil, nil, notFound
	}
	session, err := s.repo.GetSession(message.SessionID)
	if err != nil {
		return nil, nil, strategyChatInternalError("load session", err)
	}
	if session == nil || session.UserID != actor.UserID || session.StrategyID != strategyID {
		return nil, nil, notFound
	}
	proposal := decodeStrategyChatProposal(message.Proposal)
	if message.Role != models.StrategyChatRoleAssistant || proposal == nil ||
		!message.ProposalStatus.Valid || message.ProposalStatus.String != models.StrategyChatProposalPending {
		return nil, nil, strategyChatProposalNotPending()
	}
	return message, proposal, nil
}

// claimStrategyChatProposal moves a pending proposal to its final status
// inside the caller's transaction, so a second request for the same proposal
// waits on the row and then finds it no longer pending. The status only
// becomes visible when the transaction commits.
func claimStrategyChatProposal(chatTx *repository.StrategyChatRepository, messageID int64, status string) error {
	claimed, err := chatTx.TransitionProposal(messageID, models.StrategyChatProposalPending, status, sql.NullString{})
	if err != nil {
		return strategyChatInternalError("claim proposal", err)
	}
	if !claimed {
		return strategyChatProposalNotPending()
	}
	return nil
}

// storeStrategyChatProposalResult writes the result of a claimed proposal in
// the caller's transaction and returns the message as the API will show it.
// A write that changes no row is an error, so the result is never lost.
func storeStrategyChatProposalResult(chatTx *repository.StrategyChatRepository, message *models.StrategyChatMessage, status string, result StrategyChatProposalResult) (StrategyChatMessageView, error) {
	encoded, err := json.Marshal(result)
	if err != nil {
		return StrategyChatMessageView{}, strategyChatInternalError("encode proposal result", err)
	}
	changed, err := chatTx.SetProposalResult(message.ID, status, string(encoded))
	if err != nil {
		return StrategyChatMessageView{}, strategyChatInternalError("store proposal result", err)
	}
	if !changed {
		return StrategyChatMessageView{}, strategyChatInternalError("store proposal result",
			fmt.Errorf("message %d is not in status %s", message.ID, status))
	}
	return strategyChatMessageViewWithResult(message, status, string(encoded)), nil
}

// strategyChatMessageViewWithResult is the stored message with the status and
// result this request wrote, without reading the row again.
func strategyChatMessageViewWithResult(message *models.StrategyChatMessage, status string, encodedResult string) StrategyChatMessageView {
	updated := *message
	updated.ProposalStatus = sql.NullString{String: status, Valid: true}
	updated.ProposalResult = sql.NullString{String: encodedResult, Valid: true}
	return strategyChatMessageView(&updated)
}

func rollbackStrategyChatTx(tx *sql.Tx) {
	if err := tx.Rollback(); err != nil && !errors.Is(err, sql.ErrTxDone) {
		log.Printf("strategy_chat failed to roll back transaction: %v", err)
	}
}

// selectStrategyChatChanges picks the proposal's changes named in fields (all
// when fields is nil), in proposal order. A name that is not part of the
// proposal is refused.
func selectStrategyChatChanges(proposal *StrategyChatProposal, fields *[]string, allowEmpty bool) ([]StrategyChatChange, error) {
	if fields == nil {
		return append([]StrategyChatChange(nil), proposal.Changes...), nil
	}
	if len(*fields) == 0 && !allowEmpty {
		return nil, newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidProposalFields, "Select at least one change")
	}
	inProposal := make(map[string]bool, len(proposal.Changes))
	for _, change := range proposal.Changes {
		inProposal[change.Field] = true
	}
	wanted := make(map[string]bool, len(*fields))
	unknown := make([]string, 0)
	for _, name := range *fields {
		field, ok := canonicalStrategyChatField(name)
		if !ok || !inProposal[field.Key] {
			unknown = append(unknown, truncateAIText(name, 64))
			continue
		}
		wanted[field.Key] = true
	}
	if len(unknown) > 0 {
		return nil, newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidProposalFields,
			"Not part of this proposal: "+strings.Join(unknown, ", "))
	}
	selected := make([]StrategyChatChange, 0, len(wanted))
	for _, change := range proposal.Changes {
		if wanted[change.Field] {
			selected = append(selected, change)
		}
	}
	return selected, nil
}

type strategyChatUpdate struct {
	field *strategyChatField
	value any
}

// revalidateStrategyChatChanges checks stored changes against the strategy as
// it is now. A change that already matches is skipped and reported in the
// second result; one that is no longer allowed refuses the whole request.
func revalidateStrategyChatChanges(changes []StrategyChatChange, strategy *models.BacktestStrategy) ([]strategyChatUpdate, []string, error) {
	updates := make([]strategyChatUpdate, 0, len(changes))
	unchanged := make([]string, 0)
	for _, change := range changes {
		field, ok := canonicalStrategyChatField(change.Field)
		if !ok {
			return nil, nil, newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidProposalFields,
				"Not an editable setting: "+truncateAIText(change.Field, 64))
		}
		value, reason := field.normalize(change.Proposed)
		current := field.get(strategy)
		if reason == "" && strategyChatValuesEqual(value, current) {
			unchanged = append(unchanged, field.Key)
			continue
		}
		if reason == "" {
			reason = field.checkAgainst(value, current)
		}
		if reason != "" {
			return nil, nil, newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidProposalFields,
				fmt.Sprintf("%s: %s", field.Key, reason))
		}
		updates = append(updates, strategyChatUpdate{field: field, value: value})
	}
	return updates, unchanged, nil
}

// applyStrategyChatUpdates sets each field on the struct and reports the
// fields with their values before and after.
func applyStrategyChatUpdates(strategy *models.BacktestStrategy, updates []strategyChatUpdate) ([]string, map[string]any, map[string]any) {
	fields := make([]string, 0, len(updates))
	before := make(map[string]any, len(updates))
	after := make(map[string]any, len(updates))
	for _, update := range updates {
		before[update.field.Key] = update.field.get(strategy)
		update.field.set(strategy, update.value)
		after[update.field.Key] = update.field.get(strategy)
		fields = append(fields, update.field.Key)
	}
	return fields, before, after
}

// copyStrategyChatSettings copies the source's non-identity settings one by
// one. Owner, id, visibility, default flag, abort-on-start and bookkeeping are
// never copied.
func copyStrategyChatSettings(target *models.BacktestStrategy, source *models.BacktestStrategy) {
	target.Description = source.Description
	target.Category = source.Category
	target.RuntimeStrategy = source.RuntimeStrategy
	target.RuntimeNetwork = source.RuntimeNetwork
	target.RuntimeSubaccount = source.RuntimeSubaccount
	target.PairSelectionMode = source.PairSelectionMode
	target.SetSelectedMarketList(source.SelectedMarketList())
	target.ZscoreThreshold = source.ZscoreThreshold
	target.StatsWindow = source.StatsWindow
	target.MaxHalfLife = source.MaxHalfLife
	target.UsdPerTrade = source.UsdPerTrade
	target.UsdMinCollateral = source.UsdMinCollateral
	target.CloseAtZscoreCross = source.CloseAtZscoreCross
	target.FindCointegratedPairs = source.FindCointegratedPairs
	target.ManageExits = source.ManageExits
	target.PlaceTrades = source.PlaceTrades
	target.MaxPositions = source.MaxPositions
	target.MaxDrawdownPct = source.MaxDrawdownPct
	target.StopLossPct = source.StopLossPct
	target.TakeProfitPct = source.TakeProfitPct
	target.TrailingStopPct = source.TrailingStopPct
	target.RebalanceIntervalHours = source.RebalanceIntervalHours
	target.PositionTimeoutHours = source.PositionTimeoutHours
	target.TransactionFee = source.TransactionFee
	target.Slippage = source.Slippage
	target.StartingBalance = source.StartingBalance
	target.CandleResolution = source.CandleResolution
	target.MaxHistoryDays = source.MaxHistoryDays
	target.BenchmarkSymbol = source.BenchmarkSymbol
	target.RiskFreeRate = source.RiskFreeRate
	target.InitialAmount = source.InitialAmount

	target.IsPublic = false
	target.IsDefault = false
	target.AbortAllPositions = false
}

// strategyChatNewStrategyName is the caller's name, else the suggested one,
// else "<source> (variant)".
func strategyChatNewStrategyName(requested, suggested, sourceName string) (string, error) {
	if name := strings.TrimSpace(requested); name != "" {
		if len([]rune(name)) > strategyChatMaxNameRunes {
			return "", newStrategyChatError(http.StatusBadRequest, StrategyChatCodeInvalidRequest,
				fmt.Sprintf("A strategy name can be at most %d characters", strategyChatMaxNameRunes))
		}
		return name, nil
	}
	name := strings.TrimSpace(suggested)
	if name == "" {
		name = strings.TrimSpace(sourceName) + " (variant)"
	}
	if runes := []rune(name); len(runes) > strategyChatMaxNameRunes {
		name = strings.TrimSpace(string(runes[:strategyChatMaxNameRunes]))
	}
	return name, nil
}

func strategyChatTitle(content string) string {
	line := strings.TrimSpace(strings.SplitN(strings.TrimSpace(content), "\n", 2)[0])
	return truncateAIText(line, 60)
}

func strategyChatSessionView(session *models.StrategyChatSession) *StrategyChatSessionView {
	if session == nil {
		return nil
	}
	return &StrategyChatSessionView{
		ID:         session.ID,
		StrategyID: session.StrategyID,
		Title:      session.Title,
		CreatedAt:  session.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt:  session.UpdatedAt.UTC().Format(time.RFC3339),
	}
}

func strategyChatMessageView(message *models.StrategyChatMessage) StrategyChatMessageView {
	view := StrategyChatMessageView{
		ID:        message.ID,
		SessionID: message.SessionID,
		Role:      message.Role,
		Content:   message.Content,
		Proposal:  decodeStrategyChatProposal(message.Proposal),
		Provider:  message.Provider,
		Model:     message.Model,
		CreatedAt: message.CreatedAt.UTC().Format(time.RFC3339),
	}
	if view.Proposal != nil && message.ProposalStatus.Valid && message.ProposalStatus.String != "" {
		status := message.ProposalStatus.String
		view.ProposalStatus = &status
	}
	if message.ProposalResult.Valid && strings.TrimSpace(message.ProposalResult.String) != "" {
		var result StrategyChatProposalResult
		if err := json.Unmarshal([]byte(message.ProposalResult.String), &result); err == nil {
			view.ProposalResult = &result
		}
	}
	return view
}
