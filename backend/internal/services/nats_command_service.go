// Package services provides business logic and integration services.
//
// This file implements the NATS command service for Phase 4 NATS JetStream integration.
// It provides dual-write functionality: creating task commands in PostgreSQL and
// publishing to NATS JetStream, while keeping the HTTP/Celery path authoritative.
package services

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/nats"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/google/uuid"
)

// TaskCommandStore is the subset of task-table operations the command service
// depends on. *repository.TaskRepository satisfies it; tests may substitute a
// fake to assert state transitions without a database.
type TaskCommandStore interface {
	CreateTaskCommand(ctx context.Context, commandType, ownerType, ownerID, idempotencyKey string, requestedByUserID *int, payloadJSON []byte) (*models.TaskCommand, error)
	UpdateTaskCommandStatus(ctx context.Context, id, status string) error
	CreateTaskRun(ctx context.Context, commandID, taskType string, maxRetries int) (*models.TaskRun, error)
	ListTaskCommandsPendingSince(ctx context.Context, cutoff time.Time, limit int) ([]*models.TaskCommand, error)
}

// NATSPublisherClient is the subset of the NATS publisher used for command
// transport. *nats.Publisher satisfies it; a nil publisher means NATS disabled.
type NATSPublisherClient interface {
	Publish(ctx context.Context, env nats.Envelope) (*nats.PublishResult, error)
}

// NATSCommandService handles dual-write command publishing to PostgreSQL task tables
// and NATS JetStream. It implements fail-closed behavior: if NATS is disabled or
// unavailable, it still creates the task command but skips NATS publishing.
type NATSCommandService struct {
	taskRepo  TaskCommandStore
	publisher NATSPublisherClient
	settings  config.NATSSettings
	clock     func() time.Time
	metrics   *AsyncMetrics

	// publishSlots bounds concurrent async publish goroutines: an unreachable
	// NATS must not accumulate one 10s goroutine per request.
	publishSlots chan struct{}
	slotOnce     sync.Once
}

// publishLimiter lazily initializes the bounded-publish channel so instances
// constructed without it (tests, alternate constructors) still publish.
func (s *NATSCommandService) publishLimiter() chan struct{} {
	s.slotOnce.Do(func() {
		if s.publishSlots == nil {
			s.publishSlots = make(chan struct{}, 16)
		}
	})
	return s.publishSlots
}

// NewNATSCommandService creates a new NATS command service.
// If taskRepo is nil or settings indicate NATS is disabled, NATS publishing will be skipped
// but task command creation will still work.
//
// The concrete *repository.TaskRepository / *nats.Publisher arguments are
// converted to nil interface values when nil so the service's nil checks (used
// for fail-closed decisions and health) behave correctly.
func NewNATSCommandService(
	taskRepo *repository.TaskRepository,
	publisher *nats.Publisher,
	settings config.NATSSettings,
) *NATSCommandService {
	var store TaskCommandStore
	if taskRepo != nil {
		store = taskRepo
	}
	var pub NATSPublisherClient
	if publisher != nil {
		pub = publisher
	}
	return &NATSCommandService{
		taskRepo:  store,
		publisher: pub,
		settings:  settings,
		clock:     time.Now,
		metrics:   GetAsyncMetrics(),
		// 16 concurrent publishes; a full channel drops the publish and leaves the
		// command "pending" (the documented truthful-status failure semantic).
		publishSlots: make(chan struct{}, 16),
	}
}

// PublishBacktestCommand creates a task command for a backtest and optionally publishes
// to NATS JetStream. This is a dual-write operation:
// 1. Creates a task command in PostgreSQL (authoritative)
// 2. Publishes to NATS JetStream (best-effort, non-blocking for HTTP flow)
//
// Returns the created task command and any error from the PostgreSQL write.
// NATS publishing errors are logged but do not cause this function to return an error,
// ensuring the HTTP/Celery path remains authoritative.
//
// The correlationID should be the request trace ID for end-to-end correlation across
// frontend, backend, and bot services.
func (s *NATSCommandService) PublishBacktestCommand(
	ctx context.Context,
	runID string,
	config map[string]interface{},
	requestedByUserID *int,
	idempotencyKey string,
	correlationID string,
) (*models.TaskCommand, error) {
	// The checked-in runtime executes backtests through Celery. Merely enabling
	// NATS for durable events must not create an executable command mirror: a NATS
	// worker started later could otherwise replay the same authoritative run.
	if !s.settings.CommandBusEnabled {
		return nil, nil
	}
	if s.taskRepo == nil {
		return nil, fmt.Errorf("task repository is nil")
	}
	// Use provided idempotency key, or generate one if empty
	if idempotencyKey == "" {
		idempotencyKey = runID
		if idempotencyKey == "" {
			idempotencyKey = uuid.New().String()
		}
	}

	// Use provided correlation ID, or generate one if empty
	if correlationID == "" {
		correlationID = uuid.New().String()
	}

	// Serialize config to bounded JSON payload
	payloadJSON, err := s.serializeConfigForPayload(config)
	if err != nil {
		log.Printf("NATS Command Service: failed to serialize config for task command: %v", err)
		// Continue with empty payload rather than failing the command creation
		payloadJSON = []byte("{}")
	}

	// Create task command in PostgreSQL (authoritative)
	taskCmd, err := s.taskRepo.CreateTaskCommand(
		ctx,
		"backtest",        // commandType
		"backtest",        // ownerType
		runID,             // ownerID
		idempotencyKey,    // idempotencyKey
		requestedByUserID, // requestedByUserID
		payloadJSON,       // payloadJSON
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create task command: %w", err)
	}

	// Status stays "pending" here. It is only advanced to "published" after the
	// JetStream publish is acknowledged (see publishToNATSAsync). Marking it
	// published before transport success would report a false command state when
	// NATS is disabled or unreachable.
	// Create task run linked to command
	taskRun, err := s.taskRepo.CreateTaskRun(
		ctx,
		taskCmd.ID,           // commandID
		"backtest_execution", // taskType
		3,                    // maxRetries
	)
	if err != nil {
		log.Printf("NATS Command Service: failed to create task run: %v", err)
		// Continue - command is still created, just no run record yet
	} else {
		log.Printf("NATS Command Service: created task run %s for command %s", taskRun.ID, taskCmd.ID)
	}

	// Publish to NATS JetStream (best-effort, non-blocking for HTTP flow). Uses a
	// detached context so the publish attempt is not cancelled when the HTTP
	// response returns; the command status transition happens inside.
	// Bound concurrent publish attempts; when saturated, skip the publish and
	// leave the command "pending" for the reconciler/fallback path.
	slots := s.publishLimiter()
	select {
	case slots <- struct{}{}:
		go func() {
			defer func() { <-slots }()
			s.publishToNATSAsync(taskCmd, config, idempotencyKey, correlationID)
		}()
	default:
		log.Printf("NATS Command Service: publish concurrency limit reached; command %s left pending", taskCmd.ID)
	}

	return taskCmd, nil
}

// publishToNATSAsync publishes the command to NATS JetStream asynchronously.
// Errors are logged but do not affect the HTTP response, ensuring fail-closed behavior
// where the HTTP/Celery path remains authoritative. The command status is advanced
// to "published" ONLY after JetStream acknowledges the publish; on any failure or
// when NATS is disabled the status remains "pending" so command state is truthful.
func (s *NATSCommandService) publishToNATSAsync(
	taskCmd *models.TaskCommand,
	config map[string]interface{},
	idempotencyKey string,
	correlationID string,
) {
	// Defer recovery from panics
	defer func() {
		if r := recover(); r != nil {
			log.Printf("NATS Command Service: panic during NATS publish: %v", r)
		}
	}()

	// Skip if NATS is not enabled or publisher is nil
	if !s.settings.Enabled || !s.settings.CommandBusEnabled || s.publisher == nil {
		log.Printf("NATS Command Service: NATS disabled, skipping publish for command %s", taskCmd.ID)
		return
	}

	payloadJSON, err := buildCommandPayload(taskCmd, config)
	if err != nil {
		log.Printf("NATS Command Service: failed to marshal NATS payload: %v", err)
		return
	}

	// Build envelope per contract
	envelope := nats.Envelope{
		MessageID:       taskCmd.ID,
		IdempotencyKey:  idempotencyKey,
		CorrelationID:   correlationID,
		OwnerType:       taskCmd.OwnerType,
		OwnerID:         taskCmd.OwnerID,
		OccurredAt:      s.clock().UTC(),
		ProducerService: "backend-api",
		SchemaVersion:   nats.DefaultSchemaVersion,
		Subject:         nats.Subject("backtest", "command", "start"),
		Payload:         json.RawMessage(payloadJSON),
	}

	// Validate envelope
	if err := envelope.Validate(); err != nil {
		log.Printf("NATS Command Service: invalid envelope: %v", err)
		return
	}

	// Publish with a detached timeout context so the attempt is not cancelled
	// when the originating HTTP request returns.
	publishCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Attempt to publish
	publishResult, err := s.publisher.Publish(publishCtx, envelope)
	if err != nil {
		// Check if it's a disabled publisher error (expected when NATS is off)
		if err == nats.ErrPublisherDisabled {
			log.Printf("NATS Command Service: publisher disabled, skipping NATS publish for command %s", taskCmd.ID)
			return
		}
		// Transport failed: leave command status as "pending" (fail-closed). Do
		// not mark it published — the command was not durably delivered.
		log.Printf("NATS Command Service: failed to publish command %s to NATS (left pending): %v", taskCmd.ID, err)
		if s.metrics != nil {
			s.metrics.RecordNATSPublishFailure()
		}
		return
	}

	// Log successful publish
	if publishResult != nil {
		log.Printf("NATS Command Service: successfully published command %s to stream %s, sequence %d, duplicate=%t",
			taskCmd.ID, publishResult.Stream, publishResult.Sequence, publishResult.Duplicate)
		if s.metrics != nil {
			s.metrics.RecordNATSPublishSuccess()
		}

		if publishResult.Duplicate {
			log.Printf("NATS Command Service: detected duplicate publish for command %s", taskCmd.ID)
			// This is expected behavior for idempotency
		}
	}

	// Transport succeeded: NOW advance command status to "published". A failure
	// here only means the status lags the (successful) transport; it is logged
	// but cannot make the system less correct than before.
	markCtx, markCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer markCancel()
	if err := s.taskRepo.UpdateTaskCommandStatus(markCtx, taskCmd.ID, repository.TaskCommandStatusPublished); err != nil {
		log.Printf("NATS Command Service: published command %s but failed to mark status published: %v", taskCmd.ID, err)
	}
}

// serializeConfigForPayload creates a bounded JSON payload from the config.
// This ensures large config objects don't bloat the task_commands.payload_json field.
func (s *NATSCommandService) serializeConfigForPayload(config map[string]interface{}) ([]byte, error) {
	if config == nil {
		return []byte("{}"), nil
	}

	// Create a bounded config that only includes essential fields
	boundedConfig := make(map[string]interface{})

	// Include essential identification fields
	if val, ok := config["name"].(string); ok && val != "" {
		boundedConfig["name"] = val
	}
	if val, ok := config["strategy_id"].(float64); ok && val > 0 {
		boundedConfig["strategy_id"] = int(val)
	}
	if val, ok := config["source"].(string); ok && val != "" {
		boundedConfig["source"] = val
	}

	// Include timing fields if present
	if val, ok := config["start_date"].(string); ok && val != "" {
		boundedConfig["start_date"] = val
	}
	if val, ok := config["end_date"].(string); ok && val != "" {
		boundedConfig["end_date"] = val
	}

	// Include trading parameters reference (not full parameters)
	if params, ok := config["trading_parameters"].(map[string]interface{}); ok {
		boundedConfig["has_trading_parameters"] = true
		// Include a checksum or reference instead of full parameters
		if len(params) > 0 {
			boundedConfig["trading_parameters_present"] = true
		}
	}

	// Include pair information
	if pairs, ok := config["pairs"].([]interface{}); ok && len(pairs) > 0 {
		boundedConfig["pair_count"] = len(pairs)
		if len(pairs) <= 10 { // Only include actual pairs if reasonable count
			boundedConfig["pairs"] = pairs
		}
	}

	// Include user information
	if val, ok := config["requested_by_user_id"].(float64); ok && val > 0 {
		boundedConfig["requested_by_user_id"] = int(val)
	}

	return json.Marshal(boundedConfig)
}

// IsNATSEnabled returns whether NATS publishing is enabled.
func (s *NATSCommandService) IsNATSEnabled() bool {
	return s.settings.Enabled && s.settings.CommandBusEnabled && s.publisher != nil
}

// HealthCheck returns an error if the service is not healthy.
// For now, this just checks if the task repository is available.
// NATS connectivity is checked lazily during publish.
func (s *NATSCommandService) HealthCheck() error {
	if s.taskRepo == nil {
		return fmt.Errorf("task repository is nil")
	}
	return nil
}

// buildCommandPayload builds the reference-heavy message body the backtest
// consumer reads (command_id, run_id, owner, idempotency key). The first
// publish and the reconciler must send the same shape: the consumer resolves
// the run from these fields, not from the stored config.
func buildCommandPayload(taskCmd *models.TaskCommand, config map[string]interface{}) ([]byte, error) {
	natsPayload := map[string]interface{}{
		"command_id":      taskCmd.ID,
		"run_id":          taskCmd.OwnerID,
		"command_type":    taskCmd.CommandType,
		"owner_type":      taskCmd.OwnerType,
		"owner_id":        taskCmd.OwnerID,
		"idempotency_key": taskCmd.IdempotencyKey,
		"created_at":      taskCmd.CreatedAt.Format(time.RFC3339),
		"status":          taskCmd.Status,
	}

	// Add minimal config references (not full config to keep payload small)
	if config != nil {
		if name, ok := config["name"].(string); ok && name != "" {
			natsPayload["name"] = name
		}
		if strategyID, ok := config["strategy_id"].(float64); ok && strategyID > 0 {
			natsPayload["strategy_id"] = int(strategyID)
		}
	}

	return json.Marshal(natsPayload)
}

// ReconcilePendingCommands re-publishes task commands stuck in "pending"
// (publish lost to a NATS outage or a process restart mid-publish). The
// JetStream Msg-Id equals the idempotency key, so re-publishing an already
// delivered command is deduplicated server-side.
func (s *NATSCommandService) ReconcilePendingCommands(ctx context.Context, olderThan time.Duration, limit int) (int, error) {
	if s == nil || s.taskRepo == nil {
		return 0, nil
	}
	if !s.settings.Enabled || !s.settings.CommandBusEnabled || s.publisher == nil {
		return 0, nil
	}
	if olderThan <= 0 {
		olderThan = 2 * time.Minute
	}

	cutoff := s.clock().UTC().Add(-olderThan)
	commands, err := s.taskRepo.ListTaskCommandsPendingSince(ctx, cutoff, limit)
	if err != nil {
		return 0, fmt.Errorf("list pending commands: %w", err)
	}

	requeued := 0
	for _, taskCmd := range commands {
		if ctx.Err() != nil {
			break
		}

		// The stored payload is the serialized run config; rebuild the same
		// message body the first publish sends. A config that no longer parses
		// only loses the optional name/strategy references.
		var config map[string]interface{}
		if len(taskCmd.PayloadJSON) > 0 {
			if err := json.Unmarshal(taskCmd.PayloadJSON, &config); err != nil {
				log.Printf("NATS reconciler: stored config for command %s is not a JSON object: %v", taskCmd.ID, err)
				config = nil
			}
		}
		payloadJSON, err := buildCommandPayload(taskCmd, config)
		if err != nil {
			log.Printf("NATS reconciler: failed to build payload for command %s: %v", taskCmd.ID, err)
			continue
		}

		envelope := nats.Envelope{
			MessageID:      taskCmd.ID,
			IdempotencyKey: taskCmd.IdempotencyKey,
			// The original request trace id is not persisted; the command id
			// keeps the re-publish traceable to its task_commands row.
			CorrelationID:   taskCmd.ID,
			OwnerType:       taskCmd.OwnerType,
			OwnerID:         taskCmd.OwnerID,
			OccurredAt:      s.clock().UTC(),
			ProducerService: "backend-api-reconciler",
			SchemaVersion:   nats.DefaultSchemaVersion,
			Subject:         nats.Subject("backtest", "command", "start"),
			Payload:         json.RawMessage(payloadJSON),
		}
		if err := envelope.Validate(); err != nil {
			log.Printf("NATS reconciler: skipping invalid command %s: %v", taskCmd.ID, err)
			continue
		}

		if _, pubErr := s.publisher.Publish(ctx, envelope); pubErr != nil {
			log.Printf("NATS reconciler: re-publish failed for command %s: %v", taskCmd.ID, pubErr)
			continue
		}
		if err := s.taskRepo.UpdateTaskCommandStatus(ctx, taskCmd.ID, repository.TaskCommandStatusPublished); err != nil {
			log.Printf("NATS reconciler: failed to mark command %s published: %v", taskCmd.ID, err)
			continue
		}
		requeued++
	}
	if requeued > 0 {
		log.Printf("NATS reconciler: re-published %d pending command(s)", requeued)
	}
	return requeued, nil
}
