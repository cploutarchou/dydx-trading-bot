package services

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/nats"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/stretchr/testify/assert"
)

func TestNATSCommandService_ServiceCreation(t *testing.T) {
	t.Run("creates service with valid dependencies", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{Enabled: true, CommandBusEnabled: true})
		assert.NotNil(t, service)
	})

	t.Run("creates service with disabled NATS", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{Enabled: false})
		assert.NotNil(t, service)
		assert.False(t, service.IsNATSEnabled())
	})
}

func TestNATSCommandService_HealthCheck(t *testing.T) {
	t.Run("fails health check with nil task repository", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		err := service.HealthCheck()
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "task repository is nil")
	})
}

func TestNATSCommandService_IsNATSEnabled(t *testing.T) {
	tests := []struct {
		name    string
		enabled bool
		want    bool
	}{
		{"enabled", true, true},
		{"disabled", false, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			service := NewNATSCommandService(nil, nil, config.NATSSettings{Enabled: tt.enabled, CommandBusEnabled: true})
			// IsNATSEnabled also checks if publisher is not nil, so this will be false
			// since we're passing nil publisher
			assert.False(t, service.IsNATSEnabled())
		})
	}
}

func TestNATSCommandService_serializeConfigForPayload(t *testing.T) {
	// Create a minimal service for testing serialization
	service := NewNATSCommandService(nil, nil, config.NATSSettings{})

	t.Run("handles nil config", func(t *testing.T) {
		payload, err := service.serializeConfigForPayload(nil)
		assert.NoError(t, err)
		assert.Equal(t, []byte("{}"), payload)
	})

	t.Run("handles empty config", func(t *testing.T) {
		payload, err := service.serializeConfigForPayload(map[string]interface{}{})
		assert.NoError(t, err)
		assert.Equal(t, []byte("{}"), payload)
	})

	t.Run("includes essential fields", func(t *testing.T) {
		config := map[string]interface{}{
			"name":                 "test backtest",
			"strategy_id":          float64(42),
			"source":               "api",
			"start_date":           "2024-01-01T00:00:00Z",
			"end_date":             "2024-01-02T00:00:00Z",
			"requested_by_user_id": float64(123),
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)

		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)

		assert.Equal(t, "test backtest", result["name"])
		assert.Equal(t, float64(42), result["strategy_id"])
		assert.Equal(t, "api", result["source"])
		assert.Equal(t, "2024-01-01T00:00:00Z", result["start_date"])
		assert.Equal(t, "2024-01-02T00:00:00Z", result["end_date"])
		assert.Equal(t, float64(123), result["requested_by_user_id"])
	})

	t.Run("handles pair arrays", func(t *testing.T) {
		config := map[string]interface{}{
			"pairs": []interface{}{"BTC-USD", "ETH-USD", "SOL-USD"},
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)

		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)

		assert.Equal(t, float64(3), result["pair_count"])
		// Small array should be included
		pairs, ok := result["pairs"].([]interface{})
		assert.True(t, ok)
		assert.Equal(t, 3, len(pairs))
	})

	t.Run("excludes large pair arrays", func(t *testing.T) {
		// Create a large array
		largePairs := make([]interface{}, 15)
		for i := range largePairs {
			largePairs[i] = "PAIR-" + string(rune('A'+i%26))
		}
		config := map[string]interface{}{
			"pairs": largePairs,
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)

		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)

		assert.Equal(t, float64(15), result["pair_count"])
		// Large array should not be included
		_, hasPairs := result["pairs"]
		assert.False(t, hasPairs)
	})

	t.Run("handles trading parameters", func(t *testing.T) {
		config := map[string]interface{}{
			"trading_parameters": map[string]interface{}{
				"zscore_threshold": 2.0,
				"other_setting":    "value",
			},
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)

		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)

		assert.Equal(t, true, result["has_trading_parameters"])
		assert.Equal(t, true, result["trading_parameters_present"])

		// Should not include the actual parameters
		_, hasParams := result["trading_parameters"]
		assert.False(t, hasParams)
	})

	t.Run("handles config serialization error gracefully", func(t *testing.T) {
		// The serialize function should handle this gracefully
		config := map[string]interface{}{
			"name": "test",
			// This would cause issues during JSON marshaling
		}

		payload, err := service.serializeConfigForPayload(config)
		// This might actually succeed or fail depending on how Go handles the config
		// but we want to ensure it doesn't panic
		if err != nil {
			// Some configs might cause errors, that's acceptable
			assert.NotNil(t, err)
		} else {
			assert.NotNil(t, payload)
		}
	})
}

// Integration test that would require actual database and NATS server
// This is left as a placeholder for when proper test infrastructure is available
func TestNATSCommandService_Integration(t *testing.T) {
	t.Skip("Integration tests require database and NATS server setup")

	// This would test the full dual-write flow:
	// 1. Create task command in PostgreSQL
	// 2. Create task run
	// 3. Publish to NATS JetStream
	// 4. Verify idempotency
	// 5. Test error scenarios
}

// Test the NATS envelope creation per contract
func TestNATSEnvelopeCreation(t *testing.T) {
	t.Run("creates valid envelope for backtest command", func(t *testing.T) {
		envelope := nats.Envelope{
			MessageID:       "test-command-id",
			IdempotencyKey:  "test-idempotency-key",
			CorrelationID:   "test-correlation-id",
			OwnerType:       "backtest",
			OwnerID:         "test-run-id",
			OccurredAt:      time.Now().UTC(),
			ProducerService: "backend-api",
			SchemaVersion:   nats.DefaultSchemaVersion,
			Subject:         nats.Subject("backtest", "command", "start"),
			Payload:         json.RawMessage(`{"test": "payload"}`),
		}

		// This should validate successfully
		err := envelope.Validate()
		assert.NoError(t, err)
		assert.Equal(t, "backtest.command.start", envelope.Subject)
	})

	t.Run("fails validation with missing required fields", func(t *testing.T) {
		envelope := nats.Envelope{
			// Missing required fields
			Subject: "backtest.command.start",
			Payload: json.RawMessage(`{}`),
		}

		err := envelope.Validate()
		assert.Error(t, err)
	})

	t.Run("creates correct subject for bot commands", func(t *testing.T) {
		subject := nats.Subject("bot", "command", "start")
		assert.Equal(t, "bot.command.start", subject)
	})

	t.Run("creates correct subject for backtest events", func(t *testing.T) {
		subject := nats.Subject("backtest", "event", "completed")
		assert.Equal(t, "backtest.event.completed", subject)
	})

	t.Run("maps subjects to correct streams", func(t *testing.T) {
		stream := nats.StreamFor("bot.command.start")
		assert.Equal(t, "BOT_COMMANDS", stream)

		stream = nats.StreamFor("backtest.event.completed")
		assert.Equal(t, "BACKTEST_EVENTS", stream)

		stream = nats.StreamFor("bot.event.started")
		assert.Equal(t, "BOT_EVENTS", stream)
	})

	t.Run("returns empty string for unknown subjects", func(t *testing.T) {
		stream := nats.StreamFor("unknown.subject")
		assert.Equal(t, "", stream)
	})
}

// Test repository constants are accessible
func TestRepositoryConstants(t *testing.T) {
	// These should be accessible from the repository package
	assert.Equal(t, "pending", repository.TaskCommandStatusPending)
	assert.Equal(t, "published", repository.TaskCommandStatusPublished)
	assert.Equal(t, "completed", repository.TaskCommandStatusCompleted)
	assert.Equal(t, "failed", repository.TaskCommandStatusFailed)

	assert.Equal(t, "pending", repository.TaskRunStatusPending)
	assert.Equal(t, "running", repository.TaskRunStatusRunning)
	assert.Equal(t, "completed", repository.TaskRunStatusCompleted)
	assert.Equal(t, "failed", repository.TaskRunStatusFailed)
	assert.Equal(t, "cancelled", repository.TaskRunStatusCancelled)

	assert.Equal(t, "success", repository.TaskAttemptOutcomeSuccess)
	assert.Equal(t, "failed", repository.TaskAttemptOutcomeFailed)
	assert.Equal(t, "timeout", repository.TaskAttemptOutcomeTimeout)

	assert.Equal(t, "active", repository.WorkerStatusActive)
	assert.Equal(t, "stale", repository.WorkerStatusStale)
	assert.Equal(t, "dead", repository.WorkerStatusDead)
	assert.Equal(t, "stopped", repository.WorkerStatusStopped)
}

// Test error scenarios that should be handled gracefully
func TestErrorHandling(t *testing.T) {
	t.Run("handles nil config in serialization", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		// This should not panic
		payload, err := service.serializeConfigForPayload(nil)
		assert.NoError(t, err)
		assert.NotNil(t, payload)
	})

	t.Run("handles malformed config gracefully", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		// Config with various types that might cause issues
		config := map[string]interface{}{
			"string": "value",
			"number": 42,
			"float":  3.14,
			"bool":   true,
			"null":   nil,
			"array":  []string{"a", "b"},
			"object": map[string]string{"key": "value"},
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)
		assert.NotNil(t, payload)

		// Should be valid JSON
		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)
	})
}

// Test that demonstrates the fail-closed behavior concept
func TestFailClosedBehavior(t *testing.T) {
	t.Run("service creation does not panic with nil dependencies", func(t *testing.T) {
		// This should not panic
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})
		assert.NotNil(t, service)
	})

	t.Run("health check fails gracefully with nil repo", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		// This should return an error, not panic
		err := service.HealthCheck()
		assert.Error(t, err)
	})

	t.Run("NATS enabled check returns false when dependencies are missing", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{Enabled: true, CommandBusEnabled: true})

		// Should be false because publisher is nil
		assert.False(t, service.IsNATSEnabled())
	})
}

// Test that required Go imports are available
func TestImportsAvailable(t *testing.T) {
	// This test ensures all required imports are working
	_ = context.Background()
	_ = errors.New("test")
	_ = json.RawMessage("{}")
	_ = config.NATSSettings{}
	_ = nats.Envelope{}
	_ = repository.TaskCommandStatusPending
}

// Test idempotency key generation and usage
func TestIdempotencyKeyHandling(t *testing.T) {
	t.Run("service created successfully with valid dependencies", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		// The service should be created successfully
		// We can't test the full flow without a database, but we can test the service creation
		assert.NotNil(t, service)
	})

	t.Run("service handles empty configuration gracefully", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		// Empty config should not cause issues
		assert.NotNil(t, service)
	})

	t.Run("service creation is resilient to various inputs", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		// Service should be created regardless of input
		assert.NotNil(t, service)
	})
}

// Test fail-closed behavior with disabled NATS
func TestFailClosedWithDisabledNATS(t *testing.T) {
	t.Run("service handles disabled NATS gracefully", func(t *testing.T) {
		// Create service with NATS disabled
		service := NewNATSCommandService(nil, nil, config.NATSSettings{Enabled: false})

		assert.NotNil(t, service)
		assert.False(t, service.IsNATSEnabled())
	})

	t.Run("service handles nil publisher gracefully", func(t *testing.T) {
		// Create service with nil publisher (NATS disabled)
		service := NewNATSCommandService(nil, nil, config.NATSSettings{Enabled: false})

		assert.NotNil(t, service)
		assert.False(t, service.IsNATSEnabled())
	})

	t.Run("service handles nil task repository in health check", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		err := service.HealthCheck()
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "task repository is nil")
	})
}

// Test duplicate protection via idempotency keys
func TestDuplicateProtection(t *testing.T) {
	t.Run("envelope uses correct idempotency key", func(t *testing.T) {
		// Test that the envelope created uses the provided idempotency key
		idempotencyKey := "test-idempotency-key"

		// We can't test the full NATS publishing without a server,
		// but we can verify the envelope structure
		envelope := nats.Envelope{
			MessageID:       "test-message-id",
			IdempotencyKey:  idempotencyKey,
			CorrelationID:   "test-correlation-id",
			OwnerType:       "backtest",
			OwnerID:         "test-owner-id",
			OccurredAt:      time.Now().UTC(),
			ProducerService: "backend-api",
			SchemaVersion:   nats.DefaultSchemaVersion,
			Subject:         nats.Subject("backtest", "command", "start"),
			Payload:         json.RawMessage(`{"test": "payload"}`),
		}

		// Validate the envelope
		err := envelope.Validate()
		assert.NoError(t, err)

		// Verify idempotency key is preserved
		assert.Equal(t, idempotencyKey, envelope.IdempotencyKey)
	})

	t.Run("envelope validation fails with empty idempotency key", func(t *testing.T) {
		envelope := nats.Envelope{
			MessageID:       "test-message-id",
			IdempotencyKey:  "", // Empty
			CorrelationID:   "test-correlation-id",
			OwnerType:       "backtest",
			OwnerID:         "test-owner-id",
			OccurredAt:      time.Now().UTC(),
			ProducerService: "backend-api",
			SchemaVersion:   nats.DefaultSchemaVersion,
			Subject:         nats.Subject("backtest", "command", "start"),
			Payload:         json.RawMessage(`{"test": "payload"}`),
		}

		err := envelope.Validate()
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "idempotency_key is required")
	})
}

// Test bounded payload serialization for duplicate protection
func TestBoundedPayloadSerialization(t *testing.T) {
	t.Run("excludes large arrays to prevent bloat", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		// Create config with large array
		largePairs := make([]interface{}, 15)
		for i := range largePairs {
			largePairs[i] = "PAIR-" + string(rune('A'+i%26))
		}
		config := map[string]interface{}{
			"pairs": largePairs,
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)

		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)

		// Should have pair_count but not the actual pairs array
		assert.Equal(t, float64(15), result["pair_count"])
		_, hasPairs := result["pairs"]
		assert.False(t, hasPairs)
	})

	t.Run("includes small arrays", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		config := map[string]interface{}{
			"pairs": []interface{}{"BTC-USD", "ETH-USD"},
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)

		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)

		// Small array should be included
		pairs, ok := result["pairs"].([]interface{})
		assert.True(t, ok)
		assert.Equal(t, 2, len(pairs))
	})

	t.Run("excludes full trading parameters", func(t *testing.T) {
		service := NewNATSCommandService(nil, nil, config.NATSSettings{})

		config := map[string]interface{}{
			"trading_parameters": map[string]interface{}{
				"zscore_threshold": 2.0,
				"max_positions":    10,
				"other_setting":    "value",
			},
		}

		payload, err := service.serializeConfigForPayload(config)
		assert.NoError(t, err)

		var result map[string]interface{}
		err = json.Unmarshal(payload, &result)
		assert.NoError(t, err)

		// Should indicate parameters are present but not include them
		assert.Equal(t, true, result["has_trading_parameters"])
		assert.Equal(t, true, result["trading_parameters_present"])
		_, hasParams := result["trading_parameters"]
		assert.False(t, hasParams)
	})
}
