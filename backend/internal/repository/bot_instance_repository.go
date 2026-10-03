package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type BotInstanceRepository struct {
	db       *sql.DB
	dbDriver string
}

func NewBotInstanceRepository(db *sql.DB) *BotInstanceRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}
	return &BotInstanceRepository{db: db, dbDriver: driver}
}

func (r *BotInstanceRepository) bindQuery(query string) string {
	return bindPlaceholders(r.dbDriver, query)
}

func isUndefinedColumnError(err error) bool {
	return db.IsUndefinedColumnError(err)
}

func normalizeBotStatus(status string) string {
	switch strings.ToUpper(strings.TrimSpace(status)) {
	case "CREATED", "STARTING", "RUNNING", "STOPPING", "STOPPED", "ERROR":
		return strings.ToUpper(strings.TrimSpace(status))
	case "PAUSED":
		// Current DB enum doesn't include PAUSED; map to STOPPED for compatibility.
		return "STOPPED"
	case "FAILED":
		return "ERROR"
	default:
		return "STOPPED"
	}
}

func configJSONValue(v sql.NullString) string {
	if !v.Valid || strings.TrimSpace(v.String) == "" || strings.TrimSpace(v.String) == "null" {
		return "{}"
	}
	return v.String
}

const selectBotInstancesCompatColumns = `
	SELECT id,
		instance_id,
		instance_id AS instance_name,
		0 AS user_id,
		CAST(status AS TEXT) AS status,
		network,
		strategy,
		CAST(config AS TEXT) AS config,
		NULL AS trading_params,
		0 AS total_trades,
		NULL AS total_pnl,
		NULL AS current_balance,
		NULL AS starting_balance,
		process_id,
		NULL AS pid,
		NULL AS host,
		NULL AS port,
		NULL AS error_message,
		NULL AS last_error_at,
		NULL AS started_at,
		NULL AS stopped_at,
		created_at,
		updated_at
	FROM bot_instances`

// CreateBotInstance creates a new bot instance
func (r *BotInstanceRepository) CreateBotInstance(instance *models.BotInstance) error {
	query := `
		INSERT INTO bot_instances (
			instance_id, instance_name, user_id, status, network, strategy,
			config, trading_params, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		RETURNING id
	`

	now := time.Now()
	if err := r.db.QueryRow(
		r.bindQuery(query),
		instance.InstanceID,
		instance.InstanceName,
		instance.UserID,
		normalizeBotStatus(instance.Status),
		instance.Network,
		instance.Strategy,
		instance.Config,
		instance.TradingParams,
		now,
		now,
	).Scan(&instance.ID); err != nil {
		if db.IsUndefinedColumnError(err) {
			fallbackQuery := `
				INSERT INTO bot_instances (
					instance_id, status, network, strategy, config, process_id, created_at, updated_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
				RETURNING id
			`

			fallbackNow := time.Now()
			if err = r.db.QueryRow(
				r.bindQuery(fallbackQuery),
				instance.InstanceID,
				normalizeBotStatus(instance.Status),
				instance.Network,
				instance.Strategy,
				configJSONValue(instance.Config),
				instance.ProcessID,
				fallbackNow,
				fallbackNow,
			).Scan(&instance.ID); err == nil {
				instance.CreatedAt = fallbackNow
				instance.UpdatedAt = fallbackNow
				return nil
			}
		}
		if err != nil {
			return db.WrapSQLError(err)
		}
	}
	instance.CreatedAt = now
	instance.UpdatedAt = now

	return nil
}

// GetBotInstanceByID retrieves a bot instance by ID
func (r *BotInstanceRepository) GetBotInstanceByID(id int) (*models.BotInstance, error) {
	instance := &models.BotInstance{}

	query := `
		SELECT id, instance_id, instance_name, user_id, status, network, strategy,
			config, trading_params, total_trades, total_pnl, current_balance,
			starting_balance, process_id, pid, host, port, error_message,
			last_error_at, started_at, stopped_at, created_at, updated_at
		FROM bot_instances
		WHERE id = ?
	`

	err := r.db.QueryRow(r.bindQuery(query), id).Scan(
		&instance.ID, &instance.InstanceID, &instance.InstanceName, &instance.UserID,
		&instance.Status, &instance.Network, &instance.Strategy,
		&instance.Config, &instance.TradingParams, &instance.TotalTrades, &instance.TotalPnL,
		&instance.CurrentBalance, &instance.StartingBalance, &instance.ProcessID, &instance.PID,
		&instance.Host, &instance.Port, &instance.ErrorMessage, &instance.LastErrorAt,
		&instance.StartedAt, &instance.StoppedAt, &instance.CreatedAt, &instance.UpdatedAt,
	)

	if err != nil && isUndefinedColumnError(err) {
		fallbackQuery := selectBotInstancesCompatColumns + ` WHERE id = ?`
		err = r.db.QueryRow(r.bindQuery(fallbackQuery), id).Scan(
			&instance.ID, &instance.InstanceID, &instance.InstanceName, &instance.UserID,
			&instance.Status, &instance.Network, &instance.Strategy,
			&instance.Config, &instance.TradingParams, &instance.TotalTrades, &instance.TotalPnL,
			&instance.CurrentBalance, &instance.StartingBalance, &instance.ProcessID, &instance.PID,
			&instance.Host, &instance.Port, &instance.ErrorMessage, &instance.LastErrorAt,
			&instance.StartedAt, &instance.StoppedAt, &instance.CreatedAt, &instance.UpdatedAt,
		)
	}

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("bot instance not found")
		}
		return nil, fmt.Errorf("failed to get bot instance: %w", err)
	}

	return instance, nil
}

// GetBotInstanceByInstanceID retrieves a bot instance by instance_id
func (r *BotInstanceRepository) GetBotInstanceByInstanceID(instanceID string) (*models.BotInstance, error) {
	instance := &models.BotInstance{}

	query := `
		SELECT id, instance_id, instance_name, user_id, status, network, strategy,
			config, trading_params, total_trades, total_pnl, current_balance,
			starting_balance, process_id, pid, host, port, error_message,
			last_error_at, started_at, stopped_at, created_at, updated_at
		FROM bot_instances
		WHERE instance_id = ?
	`

	err := r.db.QueryRow(r.bindQuery(query), instanceID).Scan(
		&instance.ID, &instance.InstanceID, &instance.InstanceName, &instance.UserID,
		&instance.Status, &instance.Network, &instance.Strategy,
		&instance.Config, &instance.TradingParams, &instance.TotalTrades, &instance.TotalPnL,
		&instance.CurrentBalance, &instance.StartingBalance, &instance.ProcessID, &instance.PID,
		&instance.Host, &instance.Port, &instance.ErrorMessage, &instance.LastErrorAt,
		&instance.StartedAt, &instance.StoppedAt, &instance.CreatedAt, &instance.UpdatedAt,
	)

	if err != nil && isUndefinedColumnError(err) {
		fallbackQuery := selectBotInstancesCompatColumns + ` WHERE instance_id = ?`
		err = r.db.QueryRow(r.bindQuery(fallbackQuery), instanceID).Scan(
			&instance.ID, &instance.InstanceID, &instance.InstanceName, &instance.UserID,
			&instance.Status, &instance.Network, &instance.Strategy,
			&instance.Config, &instance.TradingParams, &instance.TotalTrades, &instance.TotalPnL,
			&instance.CurrentBalance, &instance.StartingBalance, &instance.ProcessID, &instance.PID,
			&instance.Host, &instance.Port, &instance.ErrorMessage, &instance.LastErrorAt,
			&instance.StartedAt, &instance.StoppedAt, &instance.CreatedAt, &instance.UpdatedAt,
		)
	}

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("bot instance not found")
		}
		return nil, fmt.Errorf("failed to get bot instance: %w", err)
	}

	return instance, nil
}

// ListBotInstancesByUserID retrieves all bot instances for a user
func (r *BotInstanceRepository) ListBotInstancesByUserID(userID int, limit int, offset int) ([]models.BotInstance, error) {
	query := `
		SELECT id, instance_id, instance_name, user_id, status, network, strategy,
			config, trading_params, total_trades, total_pnl, current_balance,
			starting_balance, process_id, pid, host, port, error_message,
			last_error_at, started_at, stopped_at, created_at, updated_at
		FROM bot_instances
		WHERE user_id = ?
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`

	rows, err := r.db.Query(r.bindQuery(query), userID, limit, offset)
	if err != nil {
		if isUndefinedColumnError(err) {
			log.Printf("Error querying bot instances: schema missing user_id column; refusing unsafe compatibility fallback")
			return nil, fmt.Errorf("failed to list bot instances: current schema missing user_id; run migrations before listing user-scoped bot instances")
		} else {
			log.Printf("Error querying bot instances: %v", err)
			return nil, fmt.Errorf("failed to list bot instances: %w", err)
		}
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("Error closing bot instance rows: %v", closeErr)
		}
	}()

	var instances []models.BotInstance
	for rows.Next() {
		var instance models.BotInstance
		err := rows.Scan(
			&instance.ID, &instance.InstanceID, &instance.InstanceName, &instance.UserID,
			&instance.Status, &instance.Network, &instance.Strategy,
			&instance.Config, &instance.TradingParams, &instance.TotalTrades, &instance.TotalPnL,
			&instance.CurrentBalance, &instance.StartingBalance, &instance.ProcessID, &instance.PID,
			&instance.Host, &instance.Port, &instance.ErrorMessage, &instance.LastErrorAt,
			&instance.StartedAt, &instance.StoppedAt, &instance.CreatedAt, &instance.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bot instance: %w", err)
		}
		instances = append(instances, instance)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed iterating bot instances: %w", err)
	}

	return instances, nil
}

func (r *BotInstanceRepository) CountBotInstancesByUserID(userID int) (int, error) {
	var count int
	err := r.db.QueryRow(r.bindQuery(`SELECT COUNT(*) FROM bot_instances WHERE user_id = ?`), userID).Scan(&count)
	if err != nil {
		if isUndefinedColumnError(err) {
			return 0, fmt.Errorf("failed to count bot instances: current schema missing user_id; run migrations before enforcing user-scoped bot quotas")
		}
		return 0, fmt.Errorf("failed to count bot instances: %w", err)
	}
	return count, nil
}

// UpdateBotInstanceStatus updates the status of a bot instance
func (r *BotInstanceRepository) UpdateBotInstanceStatus(instanceID string, status string) error {
	query := `
		UPDATE bot_instances
		SET status = ?, updated_at = ?
		WHERE instance_id = ?
	`

	result, err := r.db.Exec(r.bindQuery(query), normalizeBotStatus(status), time.Now(), instanceID)
	if err != nil && isUndefinedColumnError(err) {
		fallbackQuery := `
			UPDATE bot_instances
			SET status = ?
			WHERE instance_id = ?
		`
		result, err = r.db.Exec(r.bindQuery(fallbackQuery), normalizeBotStatus(status), instanceID)
	}
	if err != nil {
		return fmt.Errorf("failed to update bot instance status: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot instance not found: %s", instanceID)
	}

	return nil
}

// UpdateBotInstanceMetrics updates performance metrics
func (r *BotInstanceRepository) UpdateBotInstanceMetrics(instanceID string, totalTrades int, totalPnL *float64, currentBalance *float64) error {
	query := `
		UPDATE bot_instances
		SET total_trades = ?, total_pnl = ?, current_balance = ?, updated_at = ?
		WHERE instance_id = ?
	`

	result, err := r.db.Exec(r.bindQuery(query), totalTrades, totalPnL, currentBalance, time.Now(), instanceID)
	if err != nil && isUndefinedColumnError(err) {
		fallbackQuery := `
			UPDATE bot_instances
			SET updated_at = ?
			WHERE instance_id = ?
		`
		result, err = r.db.Exec(r.bindQuery(fallbackQuery), time.Now(), instanceID)
	}
	if err != nil {
		return fmt.Errorf("failed to update bot instance metrics: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot instance not found: %s", instanceID)
	}

	return nil
}

// UpdateBotInstanceProcess updates process information
func (r *BotInstanceRepository) UpdateBotInstanceProcess(instanceID string, processID *int, pid *string, host *string, port *int, status string) error {
	query := `
		UPDATE bot_instances
		SET process_id = ?, pid = ?, host = ?, port = ?, status = ?, started_at = ?, updated_at = ?
		WHERE instance_id = ?
	`

	normalizedStatus := normalizeBotStatus(status)
	result, err := r.db.Exec(
		r.bindQuery(query),
		processID, pid, host, port, normalizedStatus, time.Now(), time.Now(), instanceID,
	)
	if err != nil && isUndefinedColumnError(err) {
		fallbackQuery := `
			UPDATE bot_instances
			SET process_id = ?, status = ?, updated_at = ?
			WHERE instance_id = ?
		`
		result, err = r.db.Exec(
			r.bindQuery(fallbackQuery),
			processID, normalizedStatus, time.Now(), instanceID,
		)
		if err != nil && isUndefinedColumnError(err) {
			minimalFallbackQuery := `
				UPDATE bot_instances
				SET status = ?
				WHERE instance_id = ?
			`
			result, err = r.db.Exec(r.bindQuery(minimalFallbackQuery), normalizedStatus, instanceID)
		}
	}
	if err != nil {
		return fmt.Errorf("failed to update bot instance process: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot instance not found: %s", instanceID)
	}

	return nil
}

// UpdateBotInstanceError records an error
func (r *BotInstanceRepository) UpdateBotInstanceError(instanceID string, errorMessage string) error {
	query := `
		UPDATE bot_instances
		SET error_message = ?, last_error_at = ?, status = ?, updated_at = ?
		WHERE instance_id = ?
	`

	normalizedStatus := normalizeBotStatus("ERROR")
	result, err := r.db.Exec(r.bindQuery(query), errorMessage, time.Now(), normalizedStatus, time.Now(), instanceID)
	if err != nil && isUndefinedColumnError(err) {
		fallbackQuery := `
			UPDATE bot_instances
			SET status = ?, updated_at = ?
			WHERE instance_id = ?
		`
		result, err = r.db.Exec(r.bindQuery(fallbackQuery), normalizedStatus, time.Now(), instanceID)
	}
	if err != nil {
		return fmt.Errorf("failed to update bot instance error: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot instance not found: %s", instanceID)
	}

	return nil
}

// DeleteBotInstance deletes a bot instance (cascades to trades, positions, alerts)
func (r *BotInstanceRepository) DeleteBotInstance(instanceID string) error {
	query := `DELETE FROM bot_instances WHERE instance_id = ?`

	result, err := r.db.Exec(r.bindQuery(query), instanceID)
	if err != nil {
		return fmt.Errorf("failed to delete bot instance: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot instance not found: %s", instanceID)
	}

	return nil
}
