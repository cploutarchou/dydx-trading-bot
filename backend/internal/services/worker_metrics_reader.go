package services

import (
	"context"
	"errors"
	"fmt"
)

const (
	workerMetricsTable   = "worker_metrics"
	defaultWorkerHours   = 24
	maxWorkerMetricsRows = 1000
)

// WorkerMetric represents a single worker metric from ClickHouse.
type WorkerMetric struct {
	MetricTime  string  `json:"metric_time"`
	WorkerID    string  `json:"worker_id"`
	WorkerType  string  `json:"worker_type"`
	QueueName   string  `json:"queue_name"`
	MetricName  string  `json:"metric_name"`
	MetricValue float64 `json:"metric_value"`
}

// WorkerThroughputSummary provides aggregated worker throughput metrics.
type WorkerThroughputSummary struct {
	WorkerID       string  `json:"worker_id"`
	WorkerType     string  `json:"worker_type"`
	QueueName      string  `json:"queue_name"`
	TasksCompleted uint64  `json:"tasks_completed"`
	TasksSucceeded uint64  `json:"tasks_succeeded"`
	TasksFailed    uint64  `json:"tasks_failed"`
	AvgDurationMs  float64 `json:"avg_duration_ms"`
	TotalRetries   uint64  `json:"total_retries"`
}

// WorkerFailureSummary provides worker failure metrics.
type WorkerFailureSummary struct {
	WorkerID     string `json:"worker_id"`
	WorkerType   string `json:"worker_type"`
	QueueName    string `json:"queue_name"`
	FailureCount uint64 `json:"failure_count"`
	RetryCount   uint64 `json:"retry_count"`
	LastFailure  string `json:"last_failure"`
}

// WorkerHeartbeatStatus provides worker heartbeat monitoring data.
type WorkerHeartbeatStatus struct {
	WorkerID      string  `json:"worker_id"`
	WorkerType    string  `json:"worker_type"`
	QueueName     string  `json:"queue_name"`
	LastHeartbeat string  `json:"last_heartbeat"`
	HeartbeatAgeS float64 `json:"heartbeat_age_seconds"`
	IsHealthy     bool    `json:"is_healthy"`
}

// WorkerMetricsSummary is the combined envelope for worker metrics.
type WorkerMetricsSummary struct {
	WorkerID     string                  `json:"worker_id"`
	WorkerType   string                  `json:"worker_type"`
	QueueName    string                  `json:"queue_name"`
	Hours        int                     `json:"hours"`
	Throughput   WorkerThroughputSummary `json:"throughput"`
	Failures     WorkerFailureSummary    `json:"failures"`
	Heartbeat    *WorkerHeartbeatStatus  `json:"heartbeat,omitempty"`
	TotalMetrics uint64                  `json:"total_metrics"`
}

// LiveWorkerMetricsReader provides typed read access to worker_metrics ClickHouse table.
type LiveWorkerMetricsReader struct {
	reader *ClickHouseReader
}

// NewLiveWorkerMetricsReader creates a new worker metrics reader.
// Returns nil when ClickHouse reads are disabled.
func NewLiveWorkerMetricsReader(reader *ClickHouseReader) *LiveWorkerMetricsReader {
	if reader == nil {
		return nil
	}
	return &LiveWorkerMetricsReader{reader: reader}
}

// GetMetrics returns raw worker metrics for a specific worker or across all workers.
func (r *LiveWorkerMetricsReader) GetMetrics(
	ctx context.Context,
	workerID string,
	workerType string,
	queueName string,
	hours int,
	limit int,
) ([]WorkerMetric, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}
	if hours <= 0 {
		hours = defaultWorkerHours
	}
	if limit <= 0 {
		limit = maxWorkerMetricsRows
	}

	params := map[string]string{
		"hours": fmt.Sprintf("%d", hours),
		"limit": fmt.Sprintf("%d", limit),
	}

	// Base query with filtering
	query := fmt.Sprintf(`
SELECT
    toString(metric_time) AS metric_time,
    worker_id,
    worker_type,
    queue_name,
    metric_name,
    metric_value
FROM %s
WHERE metric_time >= now() - toIntervalHour({hours:UInt32})`, workerMetricsTable)

	if workerID != "" {
		params["worker_id"] = workerID
		query += "\n  AND worker_id = {worker_id:String}"
	}
	if workerType != "" {
		params["worker_type"] = workerType
		query += "\n  AND worker_type = {worker_type:String}"
	}
	if queueName != "" {
		params["queue_name"] = queueName
		query += "\n  AND queue_name = {queue_name:String}"
	}

	query += "\nORDER BY metric_time DESC\nLIMIT {limit:UInt32}"

	rows, err := r.reader.Query(ctx, query, params)
	if err != nil {
		return nil, err
	}

	return DecodeRows[WorkerMetric](rows)
}

// GetThroughputSummary returns aggregated throughput metrics for workers.
func (r *LiveWorkerMetricsReader) GetThroughputSummary(
	ctx context.Context,
	workerType string,
	queueName string,
	hours int,
) ([]WorkerThroughputSummary, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}
	if hours <= 0 {
		hours = defaultWorkerHours
	}

	params := map[string]string{
		"hours": fmt.Sprintf("%d", hours),
	}

	query := fmt.Sprintf(`
SELECT
    worker_id,
    worker_type,
    queue_name,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_completed') AS tasks_completed,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_succeeded') AS tasks_succeeded,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_failed') AS tasks_failed,
    avg(metric_value) FILTER(WHERE metric_name LIKE '%%.task_duration_ms') AS avg_duration_ms,
    sum(metric_value) FILTER(WHERE metric_name = 'task_retry_count') AS total_retries
FROM %s
WHERE metric_time >= now() - toIntervalHour({hours:UInt32})`, workerMetricsTable)

	if workerType != "" {
		params["worker_type"] = workerType
		query += "\n  AND worker_type = {worker_type:String}"
	}
	if queueName != "" {
		params["queue_name"] = queueName
		query += "\n  AND queue_name = {queue_name:String}"
	}

	query += "\nGROUP BY worker_id, worker_type, queue_name\nORDER BY tasks_completed DESC"

	rows, err := r.reader.Query(ctx, query, params)
	if err != nil {
		return nil, err
	}

	return DecodeRows[WorkerThroughputSummary](rows)
}

// GetFailureSummary returns aggregated failure metrics for workers.
func (r *LiveWorkerMetricsReader) GetFailureSummary(
	ctx context.Context,
	workerType string,
	queueName string,
	hours int,
) ([]WorkerFailureSummary, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}
	if hours <= 0 {
		hours = defaultWorkerHours
	}

	params := map[string]string{
		"hours": fmt.Sprintf("%d", hours),
	}

	query := fmt.Sprintf(`
SELECT
    worker_id,
    worker_type,
    queue_name,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_failed') AS failure_count,
    sum(metric_value) FILTER(WHERE metric_name = 'task_retry_count') AS retry_count,
    toString(max(metric_time) FILTER(WHERE metric_name = 'tasks_failed')) AS last_failure
FROM %s
WHERE metric_time >= now() - toIntervalHour({hours:UInt32})
  AND (
    metric_name = 'tasks_failed' OR
    metric_name = 'task_retry_count'
  )`, workerMetricsTable)

	if workerType != "" {
		params["worker_type"] = workerType
		query += "\n  AND worker_type = {worker_type:String}"
	}
	if queueName != "" {
		params["queue_name"] = queueName
		query += "\n  AND queue_name = {queue_name:String}"
	}

	query += "\nGROUP BY worker_id, worker_type, queue_name\nORDER BY failure_count DESC"

	rows, err := r.reader.Query(ctx, query, params)
	if err != nil {
		return nil, err
	}

	return DecodeRows[WorkerFailureSummary](rows)
}

// GetHeartbeatStatus returns current heartbeat status for all workers.
func (r *LiveWorkerMetricsReader) GetHeartbeatStatus(
	ctx context.Context,
	workerType string,
) ([]WorkerHeartbeatStatus, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}

	params := map[string]string{}

	query := fmt.Sprintf(`
SELECT
    worker_id,
    worker_type,
    queue_name,
    toString(max(metric_time)) AS last_heartbeat,
    max(metric_value) FILTER(WHERE metric_name = 'heartbeat_age_seconds') AS heartbeat_age_seconds,
    (max(metric_time) >= now() - toIntervalSecond(30)) AS is_healthy
FROM %s
WHERE metric_name IN ('heartbeat_age_seconds', 'tasks_completed')`, workerMetricsTable)

	if workerType != "" {
		params["worker_type"] = workerType
		query += "\n  AND worker_type = {worker_type:String}"
	}

	query += "\nGROUP BY worker_id, worker_type, queue_name\nORDER BY is_healthy ASC, heartbeat_age_seconds DESC"

	rows, err := r.reader.Query(ctx, query, params)
	if err != nil {
		return nil, err
	}

	return DecodeRows[WorkerHeartbeatStatus](rows)
}

// GetWorkerSummary returns a comprehensive summary for a specific worker.
func (r *LiveWorkerMetricsReader) GetWorkerSummary(
	ctx context.Context,
	workerID string,
	workerType string,
	queueName string,
	hours int,
) (*WorkerMetricsSummary, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}
	if hours <= 0 {
		hours = defaultWorkerHours
	}

	summary := &WorkerMetricsSummary{
		WorkerID:   workerID,
		WorkerType: workerType,
		QueueName:  queueName,
		Hours:      hours,
	}

	// Get total metrics count
	countParams := map[string]string{
		"hours":       fmt.Sprintf("%d", hours),
		"worker_id":   workerID,
		"worker_type": workerType,
		"queue_name":  queueName,
	}

	countQuery := fmt.Sprintf(`
SELECT count() AS total_metrics
FROM %s
WHERE metric_time >= now() - toIntervalHour({hours:UInt32})`, workerMetricsTable)

	if workerID != "" {
		countQuery += "\n  AND worker_id = {worker_id:String}"
	}
	if workerType != "" {
		countQuery += "\n  AND worker_type = {worker_type:String}"
	}
	if queueName != "" {
		countQuery += "\n  AND queue_name = {queue_name:String}"
	}

	countRows, err := r.reader.Query(ctx, countQuery, countParams)
	if err != nil {
		return nil, err
	}

	type CountResult struct {
		TotalMetrics uint64 `json:"total_metrics"`
	}
	counts, err := DecodeRows[CountResult](countRows)
	if err != nil {
		return nil, err
	}
	if len(counts) > 0 {
		summary.TotalMetrics = counts[0].TotalMetrics
	}

	// Get throughput summary
	throughputParams := map[string]string{
		"hours":       fmt.Sprintf("%d", hours),
		"worker_id":   workerID,
		"worker_type": workerType,
		"queue_name":  queueName,
	}

	throughputQuery := fmt.Sprintf(`
SELECT
    worker_id,
    worker_type,
    queue_name,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_completed') AS tasks_completed,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_succeeded') AS tasks_succeeded,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_failed') AS tasks_failed,
    avg(metric_value) FILTER(WHERE metric_name LIKE '%%.task_duration_ms') AS avg_duration_ms,
    sum(metric_value) FILTER(WHERE metric_name = 'task_retry_count') AS total_retries
FROM %s
WHERE metric_time >= now() - toIntervalHour({hours:UInt32})`, workerMetricsTable)

	if workerID != "" {
		throughputQuery += "\n  AND worker_id = {worker_id:String}"
	}
	if workerType != "" {
		throughputQuery += "\n  AND worker_type = {worker_type:String}"
	}
	if queueName != "" {
		throughputQuery += "\n  AND queue_name = {queue_name:String}"
	}

	throughputQuery += "\nGROUP BY worker_id, worker_type, queue_name"

	throughputRows, err := r.reader.Query(ctx, throughputQuery, throughputParams)
	if err != nil {
		return nil, err
	}

	throughputs, err := DecodeRows[WorkerThroughputSummary](throughputRows)
	if err != nil {
		return nil, err
	}
	if len(throughputs) > 0 {
		summary.Throughput = throughputs[0]
	}

	// Get failure summary
	failureParams := map[string]string{
		"hours":       fmt.Sprintf("%d", hours),
		"worker_id":   workerID,
		"worker_type": workerType,
		"queue_name":  queueName,
	}

	failureQuery := fmt.Sprintf(`
SELECT
    worker_id,
    worker_type,
    queue_name,
    sum(metric_value) FILTER(WHERE metric_name = 'tasks_failed') AS failure_count,
    sum(metric_value) FILTER(WHERE metric_name = 'task_retry_count') AS retry_count,
    toString(max(metric_time) FILTER(WHERE metric_name = 'tasks_failed')) AS last_failure
FROM %s
WHERE metric_time >= now() - toIntervalHour({hours:UInt32})
  AND (
    metric_name = 'tasks_failed' OR
    metric_name = 'task_retry_count'
  )`, workerMetricsTable)

	if workerID != "" {
		failureQuery += "\n  AND worker_id = {worker_id:String}"
	}
	if workerType != "" {
		failureQuery += "\n  AND worker_type = {worker_type:String}"
	}
	if queueName != "" {
		failureQuery += "\n  AND queue_name = {queue_name:String}"
	}

	failureQuery += "\nGROUP BY worker_id, worker_type, queue_name"

	failureRows, err := r.reader.Query(ctx, failureQuery, failureParams)
	if err != nil {
		return nil, err
	}

	failures, err := DecodeRows[WorkerFailureSummary](failureRows)
	if err != nil {
		return nil, err
	}
	if len(failures) > 0 {
		summary.Failures = failures[0]
	}

	// Get heartbeat status
	heartbeatParams := map[string]string{
		"worker_id":   workerID,
		"worker_type": workerType,
		"queue_name":  queueName,
	}

	heartbeatQuery := fmt.Sprintf(`
SELECT
    worker_id,
    worker_type,
    queue_name,
    toString(max(metric_time)) AS last_heartbeat,
    max(metric_value) FILTER(WHERE metric_name = 'heartbeat_age_seconds') AS heartbeat_age_seconds,
    (max(metric_time) >= now() - toIntervalSecond(30)) AS is_healthy
FROM %s
WHERE metric_name IN ('heartbeat_age_seconds', 'tasks_completed')`, workerMetricsTable)

	if workerID != "" {
		heartbeatQuery += "\n  AND worker_id = {worker_id:String}"
	}
	if workerType != "" {
		heartbeatQuery += "\n  AND worker_type = {worker_type:String}"
	}
	if queueName != "" {
		heartbeatQuery += "\n  AND queue_name = {queue_name:String}"
	}

	heartbeatQuery += "\nGROUP BY worker_id, worker_type, queue_name"

	heartbeatRows, err := r.reader.Query(ctx, heartbeatQuery, heartbeatParams)
	if err != nil {
		return nil, err
	}

	heartbeats, err := DecodeRows[WorkerHeartbeatStatus](heartbeatRows)
	if err != nil {
		return nil, err
	}
	if len(heartbeats) > 0 {
		summary.Heartbeat = &heartbeats[0]
	}

	return summary, nil
}

// Check if the interface is properly implemented
var _ = errors.New("worker metrics disabled")
