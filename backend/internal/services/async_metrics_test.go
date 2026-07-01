package services

import (
	"testing"
)

func TestAsyncMetrics_BasicOperations(t *testing.T) {
	// Get a fresh instance for testing
	m := &AsyncMetrics{}

	// Test initial state
	snapshot := m.Snapshot()
	if snapshot.NATS.PublishSuccesses != 0 {
		t.Errorf("Expected 0 NATS publish successes initially, got %d", snapshot.NATS.PublishSuccesses)
	}
	if snapshot.NATS.PublishFailures != 0 {
		t.Errorf("Expected 0 NATS publish failures initially, got %d", snapshot.NATS.PublishFailures)
	}

	// Test recording successes
	m.RecordNATSPublishSuccess()
	m.RecordNATSPublishSuccess()
	snapshot = m.Snapshot()
	if snapshot.NATS.PublishSuccesses != 2 {
		t.Errorf("Expected 2 NATS publish successes, got %d", snapshot.NATS.PublishSuccesses)
	}

	// Test recording failures
	m.RecordNATSPublishFailure()
	snapshot = m.Snapshot()
	if snapshot.NATS.PublishFailures != 1 {
		t.Errorf("Expected 1 NATS publish failure, got %d", snapshot.NATS.PublishFailures)
	}

	// Test ClickHouse metrics
	m.RecordClickHouseWriteSuccess()
	m.RecordClickHouseWriteFailure()
	snapshot = m.Snapshot()
	if snapshot.ClickHouse.WriteSuccesses != 1 {
		t.Errorf("Expected 1 ClickHouse write success, got %d", snapshot.ClickHouse.WriteSuccesses)
	}
	if snapshot.ClickHouse.WriteFailures != 1 {
		t.Errorf("Expected 1 ClickHouse write failure, got %d", snapshot.ClickHouse.WriteFailures)
	}

	// Test MinIO metrics
	m.RecordMinIOUploadSuccess()
	m.RecordMinIOUploadFailure()
	snapshot = m.Snapshot()
	if snapshot.MinIO.UploadSuccesses != 1 {
		t.Errorf("Expected 1 MinIO upload success, got %d", snapshot.MinIO.UploadSuccesses)
	}
	if snapshot.MinIO.UploadFailures != 1 {
		t.Errorf("Expected 1 MinIO upload failure, got %d", snapshot.MinIO.UploadFailures)
	}

	// Test task metrics
	m.RecordTaskRetry()
	m.RecordDeadLetter()
	snapshot = m.Snapshot()
	if snapshot.Tasks.RetryCounts != 1 {
		t.Errorf("Expected 1 task retry, got %d", snapshot.Tasks.RetryCounts)
	}
	if snapshot.Tasks.DeadLetters != 1 {
		t.Errorf("Expected 1 dead letter, got %d", snapshot.Tasks.DeadLetters)
	}

	// Test consumer lag
	m.SetNATSConsumerLag(100)
	snapshot = m.Snapshot()
	if snapshot.NATS.ConsumerLagMs != 100 {
		t.Errorf("Expected consumer lag of 100ms, got %d", snapshot.NATS.ConsumerLagMs)
	}

	// Test heartbeat
	m.RecordHeartbeat()
	snapshot = m.Snapshot()
	if snapshot.NATS.LastHeartbeat.IsZero() {
		t.Error("Expected last heartbeat to be set")
	}
}

func TestAsyncMetrics_Reset(t *testing.T) {
	m := &AsyncMetrics{}

	// Record some metrics
	m.RecordNATSPublishSuccess()
	m.RecordNATSPublishFailure()
	m.SetNATSConsumerLag(100)

	// Reset
	m.Reset()

	// Verify all are zero
	snapshot := m.Snapshot()
	if snapshot.NATS.PublishSuccesses != 0 {
		t.Errorf("Expected 0 NATS publish successes after reset, got %d", snapshot.NATS.PublishSuccesses)
	}
	if snapshot.NATS.PublishFailures != 0 {
		t.Errorf("Expected 0 NATS publish failures after reset, got %d", snapshot.NATS.PublishFailures)
	}
	if snapshot.NATS.ConsumerLagMs != 0 {
		t.Errorf("Expected 0 consumer lag after reset, got %d", snapshot.NATS.ConsumerLagMs)
	}
	if !snapshot.NATS.LastHeartbeat.IsZero() {
		t.Error("Expected last heartbeat to be zero after reset")
	}
}

func TestAsyncMetrics_Singleton(t *testing.T) {
	// Get the singleton instance twice
	m1 := GetAsyncMetrics()
	m2 := GetAsyncMetrics()

	// They should be the same instance
	if m1 != m2 {
		t.Error("GetAsyncMetrics should return the same singleton instance")
	}

	// Record via m1
	m1.RecordNATSPublishSuccess()

	// Verify via m2
	if m2.Snapshot().NATS.PublishSuccesses != 1 {
		t.Error("Singleton instance should share state")
	}
}
