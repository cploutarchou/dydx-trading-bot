package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type BotTradeRepository struct {
	db *sql.DB
}

func NewBotTradeRepository(db *sql.DB) *BotTradeRepository {
	return &BotTradeRepository{db: db}
}

// CreateBotTrade creates a new bot trade record
func (r *BotTradeRepository) CreateBotTrade(trade *models.BotTrade) error {
	query := `
		INSERT INTO bot_trades (
			bot_instance_id, trade_id, market_1, market_2, entry_timestamp,
			entry_price_1, entry_price_2, entry_zscore, side_1, side_2,
			size_1, size_2, hedge_ratio, exit_timestamp, exit_price_1, 
			exit_price_2, exit_zscore, pnl, pnl_pct, duration_hours,
			strategy_zscore_threshold, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 
			$14, $15, $16, $17, $18, $19, $20, $21, $22, $23)
		RETURNING id, created_at, updated_at
	`

	err := r.db.QueryRow(
		query,
		trade.BotInstanceID, trade.TradeID, trade.Market1, trade.Market2,
		trade.EntryTimestamp, trade.EntryPrice1, trade.EntryPrice2, trade.EntryZScore,
		trade.Side1, trade.Side2, trade.Size1, trade.Size2, trade.HedgeRatio,
		trade.ExitTimestamp, trade.ExitPrice1, trade.ExitPrice2, trade.ExitZScore,
		trade.PnL, trade.PnLPct, trade.DurationHours, trade.StrategyZscoreThreshold,
		time.Now(), time.Now(),
	).Scan(&trade.ID, &trade.CreatedAt, &trade.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create bot trade: %w", err)
	}

	return nil
}

// GetBotTradeByTradeID retrieves a bot trade by trade_id
func (r *BotTradeRepository) GetBotTradeByTradeID(tradeID string) (*models.BotTrade, error) {
	trade := &models.BotTrade{}

	query := `
		SELECT id, bot_instance_id, trade_id, market_1, market_2, entry_timestamp,
			entry_price_1, entry_price_2, entry_zscore, side_1, side_2,
			size_1, size_2, hedge_ratio, exit_timestamp, exit_price_1,
			exit_price_2, exit_zscore, pnl, pnl_pct, duration_hours,
			strategy_zscore_threshold, created_at, updated_at
		FROM bot_trades
		WHERE trade_id = $1
	`

	err := r.db.QueryRow(query, tradeID).Scan(
		&trade.ID, &trade.BotInstanceID, &trade.TradeID, &trade.Market1, &trade.Market2,
		&trade.EntryTimestamp, &trade.EntryPrice1, &trade.EntryPrice2, &trade.EntryZScore,
		&trade.Side1, &trade.Side2, &trade.Size1, &trade.Size2, &trade.HedgeRatio,
		&trade.ExitTimestamp, &trade.ExitPrice1, &trade.ExitPrice2, &trade.ExitZScore,
		&trade.PnL, &trade.PnLPct, &trade.DurationHours, &trade.StrategyZscoreThreshold,
		&trade.CreatedAt, &trade.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("bot trade not found")
		}
		return nil, fmt.Errorf("failed to get bot trade: %w", err)
	}

	return trade, nil
}

// ListBotTradesByInstanceID retrieves all trades for a bot instance
func (r *BotTradeRepository) ListBotTradesByInstanceID(instanceID int, limit int, offset int) ([]models.BotTrade, error) {
	query := `
		SELECT id, bot_instance_id, trade_id, market_1, market_2, entry_timestamp,
			entry_price_1, entry_price_2, entry_zscore, side_1, side_2,
			size_1, size_2, hedge_ratio, exit_timestamp, exit_price_1,
			exit_price_2, exit_zscore, pnl, pnl_pct, duration_hours,
			strategy_zscore_threshold, created_at, updated_at
		FROM bot_trades
		WHERE bot_instance_id = $1
		ORDER BY entry_timestamp DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := r.db.Query(query, instanceID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list bot trades: %w", err)
	}
	defer rows.Close()

	var trades []models.BotTrade
	for rows.Next() {
		var trade models.BotTrade
		err := rows.Scan(
			&trade.ID, &trade.BotInstanceID, &trade.TradeID, &trade.Market1, &trade.Market2,
			&trade.EntryTimestamp, &trade.EntryPrice1, &trade.EntryPrice2, &trade.EntryZScore,
			&trade.Side1, &trade.Side2, &trade.Size1, &trade.Size2, &trade.HedgeRatio,
			&trade.ExitTimestamp, &trade.ExitPrice1, &trade.ExitPrice2, &trade.ExitZScore,
			&trade.PnL, &trade.PnLPct, &trade.DurationHours, &trade.StrategyZscoreThreshold,
			&trade.CreatedAt, &trade.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bot trade: %w", err)
		}
		trades = append(trades, trade)
	}

	return trades, nil
}

// UpdateBotTrade updates bot trade exit information
func (r *BotTradeRepository) UpdateBotTrade(trade *models.BotTrade) error {
	query := `
		UPDATE bot_trades
		SET exit_timestamp = $1, exit_price_1 = $2, exit_price_2 = $3,
			exit_zscore = $4, pnl = $5, pnl_pct = $6, duration_hours = $7,
			updated_at = $8
		WHERE trade_id = $9
	`

	result, err := r.db.Exec(
		query,
		trade.ExitTimestamp, trade.ExitPrice1, trade.ExitPrice2, trade.ExitZScore,
		trade.PnL, trade.PnLPct, trade.DurationHours, time.Now(), trade.TradeID,
	)
	if err != nil {
		return fmt.Errorf("failed to update bot trade: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot trade not found: %s", trade.TradeID)
	}

	return nil
}

// DeleteBotTrade deletes a bot trade
func (r *BotTradeRepository) DeleteBotTrade(tradeID string) error {
	query := `DELETE FROM bot_trades WHERE trade_id = $1`

	result, err := r.db.Exec(query, tradeID)
	if err != nil {
		return fmt.Errorf("failed to delete bot trade: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("bot trade not found: %s", tradeID)
	}

	return nil
}

// GetBotTradeStats retrieves statistics for trades of an instance
func (r *BotTradeRepository) GetBotTradeStats(instanceID int) (map[string]interface{}, error) {
	query := `
		SELECT 
			COUNT(*) as total_trades,
			COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
			COUNT(CASE WHEN pnl <= 0 THEN 1 END) as losing_trades,
			COALESCE(AVG(CASE WHEN pnl > 0 THEN pnl END), 0) as avg_win,
			COALESCE(AVG(CASE WHEN pnl <= 0 THEN pnl END), 0) as avg_loss,
			COALESCE(SUM(pnl), 0) as total_pnl,
			COALESCE(AVG(pnl), 0) as avg_pnl
		FROM bot_trades
		WHERE bot_instance_id = $1 AND exit_timestamp IS NOT NULL
	`

	var totalTrades, winningTrades, losingTrades int
	var avgWin, avgLoss, totalPnL, avgPnL float64

	err := r.db.QueryRow(query, instanceID).Scan(
		&totalTrades, &winningTrades, &losingTrades, &avgWin, &avgLoss, &totalPnL, &avgPnL,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to get bot trade stats: %w", err)
	}

	stats := map[string]interface{}{
		"total_trades":   totalTrades,
		"winning_trades": winningTrades,
		"losing_trades":  losingTrades,
		"avg_win":        avgWin,
		"avg_loss":       avgLoss,
		"total_pnl":      totalPnL,
		"avg_pnl":        avgPnL,
	}

	if totalTrades > 0 {
		stats["win_rate"] = float64(winningTrades) / float64(totalTrades)
	} else {
		stats["win_rate"] = 0.0
	}

	return stats, nil
}
