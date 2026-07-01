// Package services provides business logic and integration services.
//
// This file implements basic async infrastructure metrics tracking for Phase 4
// observability hardening. It provides simple counters for NATS publish failures,
// consumer lag tracking, and other async path health indicators that can be
// exposed via the existing /metrics endpoint.
package services

import (
	"sync"
	"time"
)

// AsyncMetrics tracks basic health metrics for async infrastructure components.
// It is intentionally simple to avoid overcomplicating the codebase while still
// providing observable signals for NATS, ClickHouse, and MinIO operations.
type AsyncMetrics struct {
	mu sync.RWMutex

	// NATS metrics
	natsPublishSuccesses uint64
	natsPublishFailures  uint64
	natsConsumerLagMs    uint64
	natsLastHeartbeat    time.Time

	// ClickHouse metrics
	clickhouseWriteSuccesses uint64
	clickhouseWriteFailures  uint64

	// MinIO metrics
	minioUploadSuccesses uint64
	minioUploadFailures  uint64

	// General task metrics
	taskRetryCounts uint64
	deadLetterCount uint64
}

// Global singleton instance for simplicity (can be replaced with DI if needed)
var (
	asyncMetricsInstance *AsyncMetrics
	asyncMetricsOnce     sync.Once
)

// GetAsyncMetrics returns the singleton AsyncMetrics instance.
func GetAsyncMetrics() *AsyncMetrics {
	asyncMetricsOnce.Do(func() {
		asyncMetricsInstance = &AsyncMetrics{}
	})
	return asyncMetricsInstance
}

// RecordNATSPublishSuccess increments the NATS publish success counter.
func (m *AsyncMetrics) RecordNATSPublishSuccess() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.natsPublishSuccesses++
}

// RecordNATSPublishFailure increments the NATS publish failure counter.
func (m *AsyncMetrics) RecordNATSPublishFailure() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.natsPublishFailures++
}

// SetNATSConsumerLag sets the current consumer lag in milliseconds.
func (m *AsyncMetrics) SetNATSConsumerLag(lagMs uint64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.natsConsumerLagMs = lagMs
}

// RecordHeartbeat updates the last heartbeat timestamp.
func (m *AsyncMetrics) RecordHeartbeat() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.natsLastHeartbeat = time.Now().UTC()
}

// RecordClickHouseWriteSuccess increments the ClickHouse write success counter.
func (m *AsyncMetrics) RecordClickHouseWriteSuccess() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.clickhouseWriteSuccesses++
}

// RecordClickHouseWriteFailure increments the ClickHouse write failure counter.
func (m *AsyncMetrics) RecordClickHouseWriteFailure() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.clickhouseWriteFailures++
}

// RecordMinIOUploadSuccess increments the MinIO upload success counter.
func (m *AsyncMetrics) RecordMinIOUploadSuccess() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.minioUploadSuccesses++
}

// RecordMinIOUploadFailure increments the MinIO upload failure counter.
func (m *AsyncMetrics) RecordMinIOUploadFailure() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.minioUploadFailures++
}

// RecordTaskRetry increments the task retry counter.
func (m *AsyncMetrics) RecordTaskRetry() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.taskRetryCounts++
}

// RecordDeadLetter increments the dead letter counter.
func (m *AsyncMetrics) RecordDeadLetter() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.deadLetterCount++
}

// Snapshot returns a copy of the current metrics for reporting.
type AsyncMetricsSnapshot struct {
	NATS struct {
		PublishSuccesses uint64    `json:"publish_successes"`
		PublishFailures  uint64    `json:"publish_failures"`
		ConsumerLagMs    uint64    `json:"consumer_lag_ms"`
		LastHeartbeat    time.Time `json:"last_heartbeat,omitempty"`
	} `json:"nats"`
	ClickHouse struct {
		WriteSuccesses uint64 `json:"write_successes"`
		WriteFailures  uint64 `json:"write_failures"`
	} `json:"clickhouse"`
	MinIO struct {
		UploadSuccesses uint64 `json:"upload_successes"`
		UploadFailures  uint64 `json:"upload_failures"`
	} `json:"minio"`
	Tasks struct {
		RetryCounts uint64 `json:"retry_counts"`
		DeadLetters uint64 `json:"dead_letters"`
	} `json:"tasks"`
}

// Snapshot returns a copy of the current metrics for reporting.
func (m *AsyncMetrics) Snapshot() AsyncMetricsSnapshot {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return AsyncMetricsSnapshot{
		NATS: struct {
			PublishSuccesses uint64    `json:"publish_successes"`
			PublishFailures  uint64    `json:"publish_failures"`
			ConsumerLagMs    uint64    `json:"consumer_lag_ms"`
			LastHeartbeat    time.Time `json:"last_heartbeat,omitempty"`
		}{
			PublishSuccesses: m.natsPublishSuccesses,
			PublishFailures:  m.natsPublishFailures,
			ConsumerLagMs:    m.natsConsumerLagMs,
			LastHeartbeat:    m.natsLastHeartbeat,
		},
		ClickHouse: struct {
			WriteSuccesses uint64 `json:"write_successes"`
			WriteFailures  uint64 `json:"write_failures"`
		}{
			WriteSuccesses: m.clickhouseWriteSuccesses,
			WriteFailures:  m.clickhouseWriteFailures,
		},
		MinIO: struct {
			UploadSuccesses uint64 `json:"upload_successes"`
			UploadFailures  uint64 `json:"upload_failures"`
		}{
			UploadSuccesses: m.minioUploadSuccesses,
			UploadFailures:  m.minioUploadFailures,
		},
		Tasks: struct {
			RetryCounts uint64 `json:"retry_counts"`
			DeadLetters uint64 `json:"dead_letters"`
		}{
			RetryCounts: m.taskRetryCounts,
			DeadLetters: m.deadLetterCount,
		},
	}
}

// Reset clears all metrics (useful for testing).
func (m *AsyncMetrics) Reset() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.natsPublishSuccesses = 0
	m.natsPublishFailures = 0
	m.natsConsumerLagMs = 0
	m.natsLastHeartbeat = time.Time{}
	m.clickhouseWriteSuccesses = 0
	m.clickhouseWriteFailures = 0
	m.minioUploadSuccesses = 0
	m.minioUploadFailures = 0
	m.taskRetryCounts = 0
	m.deadLetterCount = 0
}
