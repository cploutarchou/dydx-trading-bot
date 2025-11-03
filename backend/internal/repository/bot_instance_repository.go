package repository

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/lib/pq"
)

type BotInstanceRepository struct {
	db *sql.DB
}

func NewBotInstanceRepository(db *sql.DB) *BotInstanceRepository {
	return &BotInstanceRepository{db: db}
}

// CreateBotInstance creates a new bot instance
func (r *BotInstanceRepository) CreateBotInstance(instance *models.BotInstance) error {
	query := `
		INSERT INTO bot_instances (
			instance_id, instance_name, user_id, status, network, strategy, 
			config, trading_params, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id, created_at, updated_at
	`

	err := r.db.QueryRow(
		query,
		instance.InstanceID,
		instance.InstanceName,
		instance.UserID,
		instance.Status,
		instance.Network,
		instance.Strategy,
		instance.Config,
		instance.TradingParams,
		time.Now(),
		time.Now(),
	).Scan(&instance.ID, &instance.CreatedAt, &instance.UpdatedAt)

	if err != nil {
		if pqErr, ok := err.(*pq.Error); ok {
			if pqErr.Code == "23505" { // Unique constraint
				return fmt.Errorf("instance_id already exists: %s", instance.InstanceID)
			}
		}
		return fmt.Errorf("failed to create bot instance: %w", err)
	}

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
		WHERE id = $1
	`

	err := r.db.QueryRow(query, id).Scan(
		&instance.ID, &instance.InstanceID, &instance.InstanceName, &instance.UserID,
		&instance.Status, &instance.Network, &instance.Strategy,
		&instance.Config, &instance.TradingParams, &instance.TotalTrades, &instance.TotalPnL,
		&instance.CurrentBalance, &instance.StartingBalance, &instance.ProcessID, &instance.PID,
		&instance.Host, &instance.Port, &instance.ErrorMessage, &instance.LastErrorAt,
		&instance.StartedAt, &instance.StoppedAt, &instance.CreatedAt, &instance.UpdatedAt,
	)

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
		WHERE instance_id = $1
	`

	err := r.db.QueryRow(query, instanceID).Scan(
		&instance.ID, &instance.InstanceID, &instance.InstanceName, &instance.UserID,
		&instance.Status, &instance.Network, &instance.Strategy,
		&instance.Config, &instance.TradingParams, &instance.TotalTrades, &instance.TotalPnL,
		&instance.CurrentBalance, &instance.StartingBalance, &instance.ProcessID, &instance.PID,
		&instance.Host, &instance.Port, &instance.ErrorMessage, &instance.LastErrorAt,
		&instance.StartedAt, &instance.StoppedAt, &instance.CreatedAt, &instance.UpdatedAt,
	)

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
		WHERE user_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := r.db.Query(query, userID, limit, offset)
	if err != nil {
		log.Printf("Error querying bot instances: %v", err)
		return nil, fmt.Errorf("failed to list bot instances: %w", err)
	}
	defer rows.Close()

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

	return instances, nil
}

// UpdateBotInstanceStatus updates the status of a bot instance
func (r *BotInstanceRepository) UpdateBotInstanceStatus(instanceID string, status string) error {
	query := `
		UPDATE bot_instances
		SET status = $1, updated_at = $2
		WHERE instance_id = $3
	`

	result, err := r.db.Exec(query, status, time.Now(), instanceID)
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
		SET total_trades = $1, total_pnl = $2, current_balance = $3, updated_at = $4
		WHERE instance_id = $5
	`

	result, err := r.db.Exec(query, totalTrades, totalPnL, currentBalance, time.Now(), instanceID)
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
		SET process_id = $1, pid = $2, host = $3, port = $4, status = $5, started_at = $6, updated_at = $7
		WHERE instance_id = $8
	`

	result, err := r.db.Exec(
		query,
		processID, pid, host, port, status, time.Now(), time.Now(), instanceID,
	)
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
		SET error_message = $1, last_error_at = $2, status = 'error', updated_at = $3
		WHERE instance_id = $4
	`

	result, err := r.db.Exec(query, errorMessage, time.Now(), time.Now(), instanceID)
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
	query := `DELETE FROM bot_instances WHERE instance_id = $1`

	result, err := r.db.Exec(query, instanceID)
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
