package repository

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type BotPositionRepository struct {
	db *sql.DB
}

func NewBotPositionRepository(db *sql.DB) *BotPositionRepository {
	return &BotPositionRepository{db: db}
}

// CreateBotPosition creates a new bot position record
func (r *BotPositionRepository) CreateBotPosition(position *models.BotPosition) error {
	query := `
		INSERT INTO bot_positions (
			bot_instance_id, position_id, market_1, market_2, status, is_active,
			entry_timestamp, entry_price_1, entry_price_2, entry_zscore,
			side_1, side_2, size_1, size_2, hedge_ratio,
			current_price_1, current_price_2, current_zscore, unrealized_pnl,
			unrealized_pnl_pct, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
			$15, $16, $17, $18, $19, $20, $21, $22)
		RETURNING id, created_at, updated_at
	`

	err := r.db.QueryRow(
		query,
		position.BotInstanceID, position.PositionID, position.Market1, position.Market2,
		position.Status, position.IsActive, position.EntryTimestamp, position.EntryPrice1,
		position.EntryPrice2, position.EntryZScore, position.Side1, position.Side2,
		position.Size1, position.Size2, position.HedgeRatio, position.CurrentPrice1,
		position.CurrentPrice2, position.CurrentZScore, position.UnrealizedPnL,
		position.UnrealizedPnLPct, time.Now(), time.Now(),
	).Scan(&position.ID, &position.CreatedAt, &position.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create bot position: %w", err)
	}

	return nil
}

// GetBotPositionByPositionID retrieves a bot position by position_id
func (r *BotPositionRepository) GetBotPositionByPositionID(positionID string) (*models.BotPosition, error) {
	position := &models.BotPosition{}

	query := `
		SELECT id, bot_instance_id, position_id, market_1, market_2, status, is_active,
			entry_timestamp, entry_price_1, entry_price_2, entry_zscore,
			side_1, side_2, size_1, size_2, hedge_ratio,
			current_price_1, current_price_2, current_zscore, unrealized_pnl,
			unrealized_pnl_pct, exit_timestamp, exit_price_1, exit_price_2,
			exit_zscore, realized_pnl, realized_pnl_pct, duration_hours,
			created_at, updated_at
		FROM bot_positions
		WHERE position_id = $1
	`

	err := r.db.QueryRow(query, positionID).Scan(
		&position.ID, &position.BotInstanceID, &position.PositionID, &position.Market1,
		&position.Market2, &position.Status, &position.IsActive, &position.EntryTimestamp,
		&position.EntryPrice1, &position.EntryPrice2, &position.EntryZScore,
		&position.Side1, &position.Side2, &position.Size1, &position.Size2, &position.HedgeRatio,
		&position.CurrentPrice1, &position.CurrentPrice2, &position.CurrentZScore,
		&position.UnrealizedPnL, &position.UnrealizedPnLPct, &position.ExitTimestamp,
		&position.ExitPrice1, &position.ExitPrice2, &position.ExitZScore,
		&position.RealizedPnL, &position.RealizedPnLPct, &position.DurationHours,
		&position.CreatedAt, &position.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("bot position not found")
		}
		return nil, fmt.Errorf("failed to get bot position: %w", err)
	}

	return position, nil
}

// ListBotPositionsByInstanceID retrieves all positions for a bot instance
func (r *BotPositionRepository) ListBotPositionsByInstanceID(instanceID int, status string, limit int, offset int) ([]models.BotPosition, error) {
	query := `
		SELECT id, bot_instance_id, position_id, market_1, market_2, status, is_active,
			entry_timestamp, entry_price_1, entry_price_2, entry_zscore,
			side_1, side_2, size_1, size_2, hedge_ratio,
			current_price_1, current_price_2, current_zscore, unrealized_pnl,
			unrealized_pnl_pct, exit_timestamp, exit_price_1, exit_price_2,
			exit_zscore, realized_pnl, realized_pnl_pct, duration_hours,
			created_at, updated_at
		FROM bot_positions
		WHERE bot_instance_id = $1
	`

	args := []interface{}{instanceID}

	if status != "" {
		query += ` AND status = $2`
		args = append(args, status)
	}

	query += ` ORDER BY entry_timestamp DESC LIMIT $` + fmt.Sprintf("%d", len(args)+1) + ` OFFSET $` + fmt.Sprintf("%d", len(args)+2)
	args = append(args, limit, offset)

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list bot positions: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close bot position rows: %v", closeErr)
		}
	}()

	var positions []models.BotPosition
	for rows.Next() {
		var position models.BotPosition
		err := rows.Scan(
			&position.ID, &position.BotInstanceID, &position.PositionID, &position.Market1,
			&position.Market2, &position.Status, &position.IsActive, &position.EntryTimestamp,
			&position.EntryPrice1, &position.EntryPrice2, &position.EntryZScore,
			&position.Side1, &position.Side2, &position.Size1, &position.Size2, &position.HedgeRatio,
			&position.CurrentPrice1, &position.CurrentPrice2, &position.CurrentZScore,
			&position.UnrealizedPnL, &position.UnrealizedPnLPct, &position.ExitTimestamp,
			&position.ExitPrice1, &position.ExitPrice2, &position.ExitZScore,
			&position.RealizedPnL, &position.RealizedPnLPct, &position.DurationHours,
			&position.CreatedAt, &position.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bot position: %w", err)
		}
		positions = append(positions, position)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed iterating bot positions: %w", err)
	}

	return positions, nil
}

// UpdateBotPosition updates bot position details
func (r *BotPositionRepository) UpdateBotPosition(position *models.BotPosition) error {
	query := `
		UPDATE bot_positions
		SET current_price_1 = $1, current_price_2 = $2, current_zscore = $3,
			unrealized_pnl = $4, unrealized_pnl_pct = $5, updated_at = $6
		WHERE position_id = $7
	`

	result, err := r.db.Exec(
		query,
		position.CurrentPrice1, position.CurrentPrice2, position.CurrentZScore,
		position.UnrealizedPnL, position.UnrealizedPnLPct, time.Now(), position.PositionID,
	)
	if err != nil {
		return fmt.Errorf("failed to update bot position: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot position not found: %s", position.PositionID)
	}

	return nil
}

// CloseBotPosition closes a position by updating exit information
func (r *BotPositionRepository) CloseBotPosition(position *models.BotPosition) error {
	query := `
		UPDATE bot_positions
		SET status = 'closed', is_active = 0, exit_timestamp = $1, exit_price_1 = $2,
			exit_price_2 = $3, exit_zscore = $4, realized_pnl = $5, realized_pnl_pct = $6,
			duration_hours = $7, updated_at = $8
		WHERE position_id = $9
	`

	result, err := r.db.Exec(
		query,
		position.ExitTimestamp, position.ExitPrice1, position.ExitPrice2, position.ExitZScore,
		position.RealizedPnL, position.RealizedPnLPct, position.DurationHours, time.Now(),
		position.PositionID,
	)
	if err != nil {
		return fmt.Errorf("failed to close bot position: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot position not found: %s", position.PositionID)
	}

	return nil
}

// DeleteBotPosition deletes a bot position
func (r *BotPositionRepository) DeleteBotPosition(positionID string) error {
	query := `DELETE FROM bot_positions WHERE position_id = $1`

	result, err := r.db.Exec(query, positionID)
	if err != nil {
		return fmt.Errorf("failed to delete bot position: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot position not found: %s", positionID)
	}

	return nil
}

// GetOpenPositionsByInstanceID retrieves all open positions for an instance
func (r *BotPositionRepository) GetOpenPositionsByInstanceID(instanceID int) ([]models.BotPosition, error) {
	query := `
		SELECT id, bot_instance_id, position_id, market_1, market_2, status, is_active,
			entry_timestamp, entry_price_1, entry_price_2, entry_zscore,
			side_1, side_2, size_1, size_2, hedge_ratio,
			current_price_1, current_price_2, current_zscore, unrealized_pnl,
			unrealized_pnl_pct, exit_timestamp, exit_price_1, exit_price_2,
			exit_zscore, realized_pnl, realized_pnl_pct, duration_hours,
			created_at, updated_at
		FROM bot_positions
		WHERE bot_instance_id = $1 AND status = 'open'
		ORDER BY entry_timestamp DESC
	`

	rows, err := r.db.Query(query, instanceID)
	if err != nil {
		return nil, fmt.Errorf("failed to list open bot positions: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close open bot position rows: %v", closeErr)
		}
	}()

	var positions []models.BotPosition
	for rows.Next() {
		var position models.BotPosition
		err := rows.Scan(
			&position.ID, &position.BotInstanceID, &position.PositionID, &position.Market1,
			&position.Market2, &position.Status, &position.IsActive, &position.EntryTimestamp,
			&position.EntryPrice1, &position.EntryPrice2, &position.EntryZScore,
			&position.Side1, &position.Side2, &position.Size1, &position.Size2, &position.HedgeRatio,
			&position.CurrentPrice1, &position.CurrentPrice2, &position.CurrentZScore,
			&position.UnrealizedPnL, &position.UnrealizedPnLPct, &position.ExitTimestamp,
			&position.ExitPrice1, &position.ExitPrice2, &position.ExitZScore,
			&position.RealizedPnL, &position.RealizedPnLPct, &position.DurationHours,
			&position.CreatedAt, &position.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bot position: %w", err)
		}
		positions = append(positions, position)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed iterating open bot positions: %w", err)
	}

	return positions, nil
}
