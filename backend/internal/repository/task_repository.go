package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/google/uuid"
)

// TaskRepository provides database operations for task management tables.
// Part of Phase 4: NATS JetStream command/event bus foundation.
type TaskRepository struct {
	db *sql.DB
}

// NewTaskRepository creates a new TaskRepository.
func NewTaskRepository(db *sql.DB) *TaskRepository {
	return &TaskRepository{db: db}
}

// ==================== TaskCommand Operations ====================

// TaskCommandStatus constants for command lifecycle.
const (
	TaskCommandStatusPending   = "pending"
	TaskCommandStatusPublished = "published"
	TaskCommandStatusCompleted = "completed"
	TaskCommandStatusFailed    = "failed"
)

// CreateTaskCommand creates a new task command with idempotency key.
func (r *TaskRepository) CreateTaskCommand(ctx context.Context, commandType, ownerType, ownerID, idempotencyKey string, requestedByUserID *int, payloadJSON []byte) (*models.TaskCommand, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	id := uuid.New().String()
	now := time.Now().UTC()

	query := `INSERT INTO task_commands (id, command_type, owner_type, owner_id, idempotency_key, requested_by_user_id, payload_json, status, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id, command_type, owner_type, owner_id, idempotency_key, requested_by_user_id, payload_json, status, created_at`

	var taskCmd models.TaskCommand
	err := r.db.QueryRowContext(ctx, query,
		id, commandType, ownerType, ownerID, idempotencyKey, requestedByUserID, payloadJSON, TaskCommandStatusPending, now,
	).Scan(
		&taskCmd.ID, &taskCmd.CommandType, &taskCmd.OwnerType, &taskCmd.OwnerID, &taskCmd.IdempotencyKey,
		&taskCmd.RequestedByUserID, &taskCmd.PayloadJSON, &taskCmd.Status, &taskCmd.CreatedAt,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("failed to create task command: %w", err)
		}
		return nil, fmt.Errorf("create task command: %w", err)
	}

	return &taskCmd, nil
}

// GetTaskCommandByID retrieves a task command by its ID.
func (r *TaskRepository) GetTaskCommandByID(ctx context.Context, id string) (*models.TaskCommand, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, command_type, owner_type, owner_id, idempotency_key, requested_by_user_id, payload_json, status, created_at
		FROM task_commands WHERE id = $1`

	var taskCmd models.TaskCommand
	err := r.db.QueryRowContext(ctx, query, id).Scan(
		&taskCmd.ID, &taskCmd.CommandType, &taskCmd.OwnerType, &taskCmd.OwnerID, &taskCmd.IdempotencyKey,
		&taskCmd.RequestedByUserID, &taskCmd.PayloadJSON, &taskCmd.Status, &taskCmd.CreatedAt,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, sql.ErrNoRows
		}
		return nil, fmt.Errorf("get task command by id: %w", err)
	}

	return &taskCmd, nil
}

// GetTaskCommandByIdempotencyKey retrieves a task command by its idempotency key.
func (r *TaskRepository) GetTaskCommandByIdempotencyKey(ctx context.Context, idempotencyKey string) (*models.TaskCommand, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, command_type, owner_type, owner_id, idempotency_key, requested_by_user_id, payload_json, status, created_at
		FROM task_commands WHERE idempotency_key = $1`

	var taskCmd models.TaskCommand
	err := r.db.QueryRowContext(ctx, query, idempotencyKey).Scan(
		&taskCmd.ID, &taskCmd.CommandType, &taskCmd.OwnerType, &taskCmd.OwnerID, &taskCmd.IdempotencyKey,
		&taskCmd.RequestedByUserID, &taskCmd.PayloadJSON, &taskCmd.Status, &taskCmd.CreatedAt,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, sql.ErrNoRows
		}
		return nil, fmt.Errorf("get task command by idempotency key: %w", err)
	}

	return &taskCmd, nil
}

// UpdateTaskCommandStatus updates the status of a task command.
func (r *TaskRepository) UpdateTaskCommandStatus(ctx context.Context, id, status string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_commands SET status = $2, updated_at = NOW() WHERE id = $1`
	result, err := r.db.ExecContext(ctx, query, id, status)
	if err != nil {
		return fmt.Errorf("update task command status: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// ==================== TaskRun Operations ====================

// TaskRunStatus constants for task execution lifecycle.
const (
	TaskRunStatusPending    = "pending"
	TaskRunStatusRunning    = "running"
	TaskRunStatusCompleted  = "completed"
	TaskRunStatusFailed     = "failed"
	TaskRunStatusCancelled  = "cancelled"
)

// CreateTaskRun creates a new task run linked to a command.
func (r *TaskRepository) CreateTaskRun(ctx context.Context, commandID, taskType string, maxRetries int) (*models.TaskRun, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	id := uuid.New().String()
	now := time.Now().UTC()

	query := `INSERT INTO task_runs (id, command_id, task_type, status, progress_pct, retry_count, max_retries, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
		RETURNING id, command_id, task_type, status, progress_pct, retry_count, max_retries, worker_backend, worker_owner, worker_task_id, started_at, finished_at, last_heartbeat_at, error_code, error_message, summary_json, created_at, updated_at`

	var taskRun models.TaskRun
	err := r.db.QueryRowContext(ctx, query,
		id, commandID, taskType, TaskRunStatusPending, 0.0, 0, maxRetries, now,
	).Scan(
		&taskRun.ID, &taskRun.CommandID, &taskRun.TaskType, &taskRun.Status, &taskRun.ProgressPct,
		&taskRun.RetryCount, &taskRun.MaxRetries, &taskRun.WorkerBackend, &taskRun.WorkerOwner,
		&taskRun.WorkerTaskID, &taskRun.StartedAt, &taskRun.FinishedAt, &taskRun.LastHeartbeatAt,
		&taskRun.ErrorCode, &taskRun.ErrorMessage, &taskRun.SummaryJSON, &taskRun.CreatedAt, &taskRun.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("failed to create task run: %w", err)
		}
		return nil, fmt.Errorf("create task run: %w", err)
	}

	return &taskRun, nil
}

// GetTaskRunByID retrieves a task run by its ID.
func (r *TaskRepository) GetTaskRunByID(ctx context.Context, id string) (*models.TaskRun, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, command_id, task_type, status, progress_pct, retry_count, max_retries, worker_backend, worker_owner, worker_task_id, started_at, finished_at, last_heartbeat_at, error_code, error_message, summary_json, created_at, updated_at
		FROM task_runs WHERE id = $1`

	var taskRun models.TaskRun
	err := r.db.QueryRowContext(ctx, query, id).Scan(
		&taskRun.ID, &taskRun.CommandID, &taskRun.TaskType, &taskRun.Status, &taskRun.ProgressPct,
		&taskRun.RetryCount, &taskRun.MaxRetries, &taskRun.WorkerBackend, &taskRun.WorkerOwner,
		&taskRun.WorkerTaskID, &taskRun.StartedAt, &taskRun.FinishedAt, &taskRun.LastHeartbeatAt,
		&taskRun.ErrorCode, &taskRun.ErrorMessage, &taskRun.SummaryJSON, &taskRun.CreatedAt, &taskRun.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, sql.ErrNoRows
		}
		return nil, fmt.Errorf("get task run by id: %w", err)
	}

	return &taskRun, nil
}

// GetTaskRunsByCommandID retrieves all task runs for a given command.
func (r *TaskRepository) GetTaskRunsByCommandID(ctx context.Context, commandID string) ([]*models.TaskRun, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, command_id, task_type, status, progress_pct, retry_count, max_retries, worker_backend, worker_owner, worker_task_id, started_at, finished_at, last_heartbeat_at, error_code, error_message, summary_json, created_at, updated_at
		FROM task_runs WHERE command_id = $1 ORDER BY created_at DESC`

	rows, err := r.db.QueryContext(ctx, query, commandID)
	if err != nil {
		return nil, fmt.Errorf("query task runs by command id: %w", err)
	}
	defer rows.Close()

	var taskRuns []*models.TaskRun
	for rows.Next() {
		var taskRun models.TaskRun
		err := rows.Scan(
			&taskRun.ID, &taskRun.CommandID, &taskRun.TaskType, &taskRun.Status, &taskRun.ProgressPct,
			&taskRun.RetryCount, &taskRun.MaxRetries, &taskRun.WorkerBackend, &taskRun.WorkerOwner,
			&taskRun.WorkerTaskID, &taskRun.StartedAt, &taskRun.FinishedAt, &taskRun.LastHeartbeatAt,
			&taskRun.ErrorCode, &taskRun.ErrorMessage, &taskRun.SummaryJSON, &taskRun.CreatedAt, &taskRun.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("scan task run: %w", err)
		}
		taskRuns = append(taskRuns, &taskRun)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration: %w", err)
	}

	return taskRuns, nil
}

// GetTaskRunsByStatus retrieves task runs filtered by task type and status.
func (r *TaskRepository) GetTaskRunsByStatus(ctx context.Context, taskType, status string, limit int) ([]*models.TaskRun, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, command_id, task_type, status, progress_pct, retry_count, max_retries, worker_backend, worker_owner, worker_task_id, started_at, finished_at, last_heartbeat_at, error_code, error_message, summary_json, created_at, updated_at
		FROM task_runs WHERE task_type = $1 AND status = $2 ORDER BY updated_at DESC LIMIT $3`

	rows, err := r.db.QueryContext(ctx, query, taskType, status, limit)
	if err != nil {
		return nil, fmt.Errorf("query task runs by status: %w", err)
	}
	defer rows.Close()

	var taskRuns []*models.TaskRun
	for rows.Next() {
		var taskRun models.TaskRun
		err := rows.Scan(
			&taskRun.ID, &taskRun.CommandID, &taskRun.TaskType, &taskRun.Status, &taskRun.ProgressPct,
			&taskRun.RetryCount, &taskRun.MaxRetries, &taskRun.WorkerBackend, &taskRun.WorkerOwner,
			&taskRun.WorkerTaskID, &taskRun.StartedAt, &taskRun.FinishedAt, &taskRun.LastHeartbeatAt,
			&taskRun.ErrorCode, &taskRun.ErrorMessage, &taskRun.SummaryJSON, &taskRun.CreatedAt, &taskRun.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("scan task run: %w", err)
		}
		taskRuns = append(taskRuns, &taskRun)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration: %w", err)
	}

	return taskRuns, nil
}

// UpdateTaskRunStatus updates the status of a task run.
func (r *TaskRepository) UpdateTaskRunStatus(ctx context.Context, id, status string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_runs SET status = $2, updated_at = NOW() WHERE id = $1`
	result, err := r.db.ExecContext(ctx, query, id, status)
	if err != nil {
		return fmt.Errorf("update task run status: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// UpdateTaskRunProgress updates the progress of a task run.
func (r *TaskRepository) UpdateTaskRunProgress(ctx context.Context, id string, progressPct float64) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_runs SET progress_pct = $2, updated_at = NOW() WHERE id = $1`
	result, err := r.db.ExecContext(ctx, query, id, progressPct)
	if err != nil {
		return fmt.Errorf("update task run progress: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// UpdateTaskRunHeartbeat updates the heartbeat timestamp for a task run.
func (r *TaskRepository) UpdateTaskRunHeartbeat(ctx context.Context, id string, workerBackend, workerOwner, workerTaskID string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_runs SET last_heartbeat_at = NOW(), worker_backend = $2, worker_owner = $3, worker_task_id = $4, updated_at = NOW() WHERE id = $1`
	result, err := r.db.ExecContext(ctx, query, id, workerBackend, workerOwner, workerTaskID)
	if err != nil {
		return fmt.Errorf("update task run heartbeat: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// UpdateTaskRunWorkerAssignment updates worker assignment for a task run.
func (r *TaskRepository) UpdateTaskRunWorkerAssignment(ctx context.Context, id, workerBackend, workerOwner, workerTaskID string, startedAt time.Time) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_runs SET worker_backend = $2, worker_owner = $3, worker_task_id = $4, started_at = $5, status = $6, updated_at = NOW() WHERE id = $1`
	result, err := r.db.ExecContext(ctx, query, id, workerBackend, workerOwner, workerTaskID, startedAt, TaskRunStatusRunning)
	if err != nil {
		return fmt.Errorf("update task run worker assignment: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// UpdateTaskRunCompletion updates task run with completion details.
func (r *TaskRepository) UpdateTaskRunCompletion(ctx context.Context, id string, finishedAt time.Time, summaryJSON []byte, errorCode, errorMessage *string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_runs SET finished_at = $2, status = $3, summary_json = $4, error_code = $5, error_message = $6, updated_at = NOW() WHERE id = $1`
	status := TaskRunStatusCompleted
	if errorCode != nil && *errorCode != "" {
		status = TaskRunStatusFailed
	}

	result, err := r.db.ExecContext(ctx, query, id, finishedAt, status, summaryJSON, errorCode, errorMessage)
	if err != nil {
		return fmt.Errorf("update task run completion: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// IncrementTaskRunRetry updates retry count and status for a task run.
func (r *TaskRepository) IncrementTaskRunRetry(ctx context.Context, id, errorCode, errorMessage string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_runs SET retry_count = retry_count + 1, status = $2, error_code = $3, error_message = $4, updated_at = NOW() WHERE id = $1`
	result, err := r.db.ExecContext(ctx, query, id, TaskRunStatusPending, errorCode, errorMessage)
	if err != nil {
		return fmt.Errorf("increment task run retry: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// ==================== TaskAttempt Operations ====================

// TaskAttemptOutcome constants.
const (
	TaskAttemptOutcomeSuccess = "success"
	TaskAttemptOutcomeFailed  = "failed"
	TaskAttemptOutcomeTimeout = "timeout"
)

// CreateTaskAttempt creates a new task attempt record.
func (r *TaskRepository) CreateTaskAttempt(ctx context.Context, taskRunID string, attemptNumber int, workerID, consumerName *string) (*models.TaskAttempt, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	id := uuid.New().String()
	now := time.Now().UTC()

	query := `INSERT INTO task_attempts (id, task_run_id, attempt_number, worker_id, consumer_name, started_at, outcome)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, task_run_id, attempt_number, worker_id, consumer_name, started_at, finished_at, outcome, error_code, error_message`

	var taskAttempt models.TaskAttempt
	err := r.db.QueryRowContext(ctx, query,
		id, taskRunID, attemptNumber, workerID, consumerName, now, TaskAttemptOutcomeSuccess,
	).Scan(
		&taskAttempt.ID, &taskAttempt.TaskRunID, &taskAttempt.AttemptNumber, &taskAttempt.WorkerID,
		&taskAttempt.ConsumerName, &taskAttempt.StartedAt, &taskAttempt.FinishedAt,
		&taskAttempt.Outcome, &taskAttempt.ErrorCode, &taskAttempt.ErrorMessage,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("failed to create task attempt: %w", err)
		}
		return nil, fmt.Errorf("create task attempt: %w", err)
	}

	return &taskAttempt, nil
}

// GetTaskAttemptsByTaskRunID retrieves all attempts for a given task run.
func (r *TaskRepository) GetTaskAttemptsByTaskRunID(ctx context.Context, taskRunID string) ([]*models.TaskAttempt, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, task_run_id, attempt_number, worker_id, consumer_name, started_at, finished_at, outcome, error_code, error_message
		FROM task_attempts WHERE task_run_id = $1 ORDER BY attempt_number ASC`

	rows, err := r.db.QueryContext(ctx, query, taskRunID)
	if err != nil {
		return nil, fmt.Errorf("query task attempts by task run id: %w", err)
	}
	defer rows.Close()

	var attempts []*models.TaskAttempt
	for rows.Next() {
		var attempt models.TaskAttempt
		err := rows.Scan(
			&attempt.ID, &attempt.TaskRunID, &attempt.AttemptNumber, &attempt.WorkerID,
			&attempt.ConsumerName, &attempt.StartedAt, &attempt.FinishedAt,
			&attempt.Outcome, &attempt.ErrorCode, &attempt.ErrorMessage,
		)
		if err != nil {
			return nil, fmt.Errorf("scan task attempt: %w", err)
		}
		attempts = append(attempts, &attempt)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration: %w", err)
	}

	return attempts, nil
}

// UpdateTaskAttemptCompletion updates an attempt with completion details.
func (r *TaskRepository) UpdateTaskAttemptCompletion(ctx context.Context, id string, finishedAt *time.Time, outcome, errorCode, errorMessage string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE task_attempts SET finished_at = $2, outcome = $3, error_code = $4, error_message = $5 WHERE id = $1`
	result, err := r.db.ExecContext(ctx, query, id, finishedAt, outcome, errorCode, errorMessage)
	if err != nil {
		return fmt.Errorf("update task attempt completion: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// ==================== WorkerHeartbeat Operations ====================

// WorkerStatus constants.
const (
	WorkerStatusActive  = "active"
	WorkerStatusStale   = "stale"
	WorkerStatusDead    = "dead"
	WorkerStatusStopped = "stopped"
)

// CreateOrUpdateWorkerHeartbeat creates or updates a worker heartbeat.
func (r *TaskRepository) CreateOrUpdateWorkerHeartbeat(ctx context.Context, workerID, workerType, hostname string, leaseExpiresAt time.Time) (*models.WorkerHeartbeat, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	now := time.Now().UTC()

	// Try to update existing heartbeat first
	updateQuery := `UPDATE worker_heartbeats SET worker_type = $2, hostname = $3, lease_expires_at = $4, last_seen_at = $5, status = $6, metadata_json = metadata_json
		WHERE worker_id = $1 RETURNING id, worker_id, worker_type, hostname, lease_expires_at, last_seen_at, status, metadata_json`

	var heartbeat models.WorkerHeartbeat
	err := r.db.QueryRowContext(ctx, updateQuery,
		workerID, workerType, hostname, leaseExpiresAt, now, WorkerStatusActive,
	).Scan(
		&heartbeat.ID, &heartbeat.WorkerID, &heartbeat.WorkerType, &heartbeat.Hostname,
		&heartbeat.LeaseExpiresAt, &heartbeat.LastSeenAt, &heartbeat.Status, &heartbeat.MetadataJSON,
	)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, fmt.Errorf("update worker heartbeat: %w", err)
	}

	if errors.Is(err, sql.ErrNoRows) {
		// Insert new heartbeat
		id := uuid.New().String()
		insertQuery := `INSERT INTO worker_heartbeats (id, worker_id, worker_type, hostname, lease_expires_at, last_seen_at, status)
			VALUES ($1, $2, $3, $4, $5, $6, $7)
			RETURNING id, worker_id, worker_type, hostname, lease_expires_at, last_seen_at, status, metadata_json`

		err = r.db.QueryRowContext(ctx, insertQuery,
			id, workerID, workerType, hostname, leaseExpiresAt, now, WorkerStatusActive,
		).Scan(
			&heartbeat.ID, &heartbeat.WorkerID, &heartbeat.WorkerType, &heartbeat.Hostname,
			&heartbeat.LeaseExpiresAt, &heartbeat.LastSeenAt, &heartbeat.Status, &heartbeat.MetadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("insert worker heartbeat: %w", err)
		}
	}

	return &heartbeat, nil
}

// GetWorkerHeartbeat retrieves a worker heartbeat by worker ID.
func (r *TaskRepository) GetWorkerHeartbeat(ctx context.Context, workerID string) (*models.WorkerHeartbeat, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, worker_id, worker_type, hostname, lease_expires_at, last_seen_at, status, metadata_json
		FROM worker_heartbeats WHERE worker_id = $1`

	var heartbeat models.WorkerHeartbeat
	err := r.db.QueryRowContext(ctx, query, workerID).Scan(
		&heartbeat.ID, &heartbeat.WorkerID, &heartbeat.WorkerType, &heartbeat.Hostname,
		&heartbeat.LeaseExpiresAt, &heartbeat.LastSeenAt, &heartbeat.Status, &heartbeat.MetadataJSON,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, sql.ErrNoRows
		}
		return nil, fmt.Errorf("get worker heartbeat: %w", err)
	}

	return &heartbeat, nil
}

// GetStaleWorkerHeartbeats retrieves worker heartbeats that have expired leases.
func (r *TaskRepository) GetStaleWorkerHeartbeats(ctx context.Context, now time.Time) ([]*models.WorkerHeartbeat, error) {
	if r.db == nil {
		return nil, errors.New("task repository: nil db")
	}

	query := `SELECT id, worker_id, worker_type, hostname, lease_expires_at, last_seen_at, status, metadata_json
		FROM worker_heartbeats WHERE lease_expires_at < $1 AND status = $2 ORDER BY lease_expires_at ASC`

	rows, err := r.db.QueryContext(ctx, query, now, WorkerStatusActive)
	if err != nil {
		return nil, fmt.Errorf("query stale worker heartbeats: %w", err)
	}
	defer rows.Close()

	var heartbeats []*models.WorkerHeartbeat
	for rows.Next() {
		var heartbeat models.WorkerHeartbeat
		err := rows.Scan(
			&heartbeat.ID, &heartbeat.WorkerID, &heartbeat.WorkerType, &heartbeat.Hostname,
			&heartbeat.LeaseExpiresAt, &heartbeat.LastSeenAt, &heartbeat.Status, &heartbeat.MetadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("scan worker heartbeat: %w", err)
		}
		heartbeats = append(heartbeats, &heartbeat)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration: %w", err)
	}

	return heartbeats, nil
}

// UpdateWorkerHeartbeatStatus updates the status of a worker heartbeat.
func (r *TaskRepository) UpdateWorkerHeartbeatStatus(ctx context.Context, workerID, status string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `UPDATE worker_heartbeats SET status = $2, last_seen_at = NOW() WHERE worker_id = $1`
	result, err := r.db.ExecContext(ctx, query, workerID, status)
	if err != nil {
		return fmt.Errorf("update worker heartbeat status: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// UpdateWorkerHeartbeatWithMetadata updates worker heartbeat with metadata.
func (r *TaskRepository) UpdateWorkerHeartbeatWithMetadata(ctx context.Context, workerID string, metadata map[string]interface{}) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return fmt.Errorf("marshal metadata: %w", err)
	}

	query := `UPDATE worker_heartbeats SET last_seen_at = NOW(), status = $2, metadata_json = $3 WHERE worker_id = $1`
	result, err := r.db.ExecContext(ctx, query, workerID, WorkerStatusActive, metadataJSON)
	if err != nil {
		return fmt.Errorf("update worker heartbeat metadata: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

// DeleteWorkerHeartbeat removes a worker heartbeat record.
func (r *TaskRepository) DeleteWorkerHeartbeat(ctx context.Context, workerID string) error {
	if r.db == nil {
		return errors.New("task repository: nil db")
	}

	query := `DELETE FROM worker_heartbeats WHERE worker_id = $1`
	result, err := r.db.ExecContext(ctx, query, workerID)
	if err != nil {
		return fmt.Errorf("delete worker heartbeat: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("check rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}
