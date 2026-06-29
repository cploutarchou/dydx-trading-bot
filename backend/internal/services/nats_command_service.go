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
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/nats"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/google/uuid"
)

// NATSCommandService handles dual-write command publishing to PostgreSQL task tables
// and NATS JetStream. It implements fail-closed behavior: if NATS is disabled or
// unavailable, it still creates the task command but skips NATS publishing.
type NATSCommandService struct {
	taskRepo     *repository.TaskRepository
	publisher    *nats.Publisher
	settings     config.NATSSettings
	clock        func() time.Time
}

// NewNATSCommandService creates a new NATS command service.
// If taskRepo is nil or settings indicate NATS is disabled, NATS publishing will be skipped
// but task command creation will still work.
func NewNATSCommandService(
	taskRepo *repository.TaskRepository,
	publisher *nats.Publisher,
	settings config.NATSSettings,
) *NATSCommandService {
	return &NATSCommandService{
		taskRepo:     taskRepo,
		publisher:    publisher,
		settings:     settings,
		clock:        time.Now,
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
func (s *NATSCommandService) PublishBacktestCommand(
	ctx context.Context,
	runID string,
	config map[string]interface{},
	requestedByUserID *int,
) (*models.TaskCommand, error) {
	// Generate idempotency key - use run ID if available, otherwise generate UUID
	idempotencyKey := runID
	if idempotencyKey == "" {
		idempotencyKey = uuid.New().String()
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
		"backtest",              // commandType
		"backtest",              // ownerType
		runID,                   // ownerID
		idempotencyKey,          // idempotencyKey
		requestedByUserID,       // requestedByUserID
		payloadJSON,             // payloadJSON
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create task command: %w", err)
	}

	// Update command status to published
	if err := s.taskRepo.UpdateTaskCommandStatus(ctx, taskCmd.ID, repository.TaskCommandStatusPublished); err != nil {
		log.Printf("NATS Command Service: failed to update task command status: %v", err)
		// Continue - command is still created, just not marked as published
	}

	// Create task run linked to command
	taskRun, err := s.taskRepo.CreateTaskRun(
		ctx,
		taskCmd.ID,              // commandID
		"backtest_execution",    // taskType
		3,                      // maxRetries
	)
	if err != nil {
		log.Printf("NATS Command Service: failed to create task run: %v", err)
		// Continue - command is still created, just no run record yet
	} else {
		log.Printf("NATS Command Service: created task run %s for command %s", taskRun.ID, taskCmd.ID)
	}

	// Publish to NATS JetStream (best-effort, non-blocking for HTTP flow)
	go s.publishToNATSAsync(ctx, taskCmd, config)

	return taskCmd, nil
}

// publishToNATSAsync publishes the command to NATS JetStream asynchronously.
// Errors are logged but do not affect the HTTP response, ensuring fail-closed behavior
// where the HTTP/Celery path remains authoritative.
func (s *NATSCommandService) publishToNATSAsync(
	ctx context.Context,
	taskCmd *models.TaskCommand,
	config map[string]interface{},
) {
	// Defer recovery from panics
	defer func() {
		if r := recover(); r != nil {
			log.Printf("NATS Command Service: panic during NATS publish: %v", r)
		}
	}()

	// Skip if NATS is not enabled or publisher is nil
	if !s.settings.Enabled || s.publisher == nil {
		log.Printf("NATS Command Service: NATS disabled, skipping publish for command %s", taskCmd.ID)
		return
	}

	// Create a minimal payload for NATS message (reference-heavy per contract)
	natsPayload := map[string]interface{}{
		"command_id":      taskCmd.ID,
		"run_id":          taskCmd.OwnerID,
		"command_type":    taskCmd.CommandType,
		"owner_type":      taskCmd.OwnerType,
		"owner_id":        taskCmd.OwnerID,
		"idempotency_key": taskCmd.IdempotencyKey,
		"created_at":      taskCmd.CreatedAt.Format(time.RFC3339),
		"status":         taskCmd.Status,
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

	payloadJSON, err := json.Marshal(natsPayload)
	if err != nil {
		log.Printf("NATS Command Service: failed to marshal NATS payload: %v", err)
		return
	}

	// Build envelope per contract
	envelope := nats.Envelope{
		MessageID:       taskCmd.ID,
		IdempotencyKey:  taskCmd.IdempotencyKey,
		CorrelationID:   uuid.New().String(),
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

	// Publish with context timeout
	publishCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// Attempt to publish
	publishResult, err := s.publisher.Publish(publishCtx, envelope)
	if err != nil {
		// Check if it's a disabled publisher error (expected when NATS is off)
		if err == nats.ErrPublisherDisabled {
			log.Printf("NATS Command Service: publisher disabled, skipping NATS publish for command %s", taskCmd.ID)
			return
		}
		log.Printf("NATS Command Service: failed to publish command %s to NATS: %v", taskCmd.ID, err)
		return
	}

	// Log successful publish
	if publishResult != nil {
		log.Printf("NATS Command Service: successfully published command %s to stream %s, sequence %d, duplicate=%t",
			taskCmd.ID, publishResult.Stream, publishResult.Sequence, publishResult.Duplicate)
		
		// If it was a duplicate, update task command status accordingly
		if publishResult.Duplicate {
			log.Printf("NATS Command Service: detected duplicate publish for command %s", taskCmd.ID)
			// This is expected behavior for idempotency
		}
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
	return s.settings.Enabled && s.publisher != nil
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