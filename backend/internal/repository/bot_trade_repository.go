package repository

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type BotTradeRepository struct {
	db       *sql.DB
	dbDriver string
}

func NewBotTradeRepository(db *sql.DB) *BotTradeRepository {
	driver := os.Getenv("DB_TYPE")
	if driver == "" {
		driver = os.Getenv("DB_DRIVER")
	}
	if driver == "" {
		driver = "postgres"
	}
	return &BotTradeRepository{db: db, dbDriver: driver}
}

func (r *BotTradeRepository) bindQuery(query string) string {
	if r == nil || !strings.Contains(strings.ToLower(r.dbDriver), "postgres") {
		return query
	}
	var b strings.Builder
	b.Grow(len(query) + 16)
	idx := 1
	for i := 0; i < len(query); i++ {
		if query[i] == '?' {
			b.WriteString(fmt.Sprintf("$%d", idx))
			idx++
			continue
		}
		b.WriteByte(query[i])
	}
	return b.String()
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
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
				?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			RETURNING id
		`

	now := time.Now()
	if err := r.db.QueryRow(
		r.bindQuery(query),
		trade.BotInstanceID, trade.TradeID, trade.Market1, trade.Market2,
		trade.EntryTimestamp, trade.EntryPrice1, trade.EntryPrice2, trade.EntryZScore,
		trade.Side1, trade.Side2, trade.Size1, trade.Size2, trade.HedgeRatio,
		trade.ExitTimestamp, trade.ExitPrice1, trade.ExitPrice2, trade.ExitZScore,
		trade.PnL, trade.PnLPct, trade.DurationHours, trade.StrategyZscoreThreshold,
		now, now,
	).Scan(&trade.ID); err != nil {
		return fmt.Errorf("failed to create bot trade: %w", err)
	}
	trade.CreatedAt = now
	trade.UpdatedAt = now

	return nil
}

func (r *BotTradeRepository) GetBotTradeByTradeID(tradeID string) (*models.BotTrade, error) {
	trade := &models.BotTrade{}

	query := `
		SELECT id, bot_instance_id, trade_id, market_1, market_2, entry_timestamp,
			entry_price_1, entry_price_2, entry_zscore, side_1, side_2,
			size_1, size_2, hedge_ratio, exit_timestamp, exit_price_1,
			exit_price_2, exit_zscore, pnl, pnl_pct, duration_hours,
			strategy_zscore_threshold, created_at, updated_at
		FROM bot_trades
		WHERE trade_id = ?
	`

	err := r.db.QueryRow(r.bindQuery(query), tradeID).Scan(
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
		WHERE bot_instance_id = ?
		ORDER BY entry_timestamp DESC
		LIMIT ? OFFSET ?
	`

	rows, err := r.db.Query(r.bindQuery(query), instanceID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list bot trades: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close bot trade rows: %v", closeErr)
		}
	}()

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

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed iterating bot trades: %w", err)
	}

	return trades, nil
}

// UpdateBotTrade updates bot trade exit information
func (r *BotTradeRepository) UpdateBotTrade(trade *models.BotTrade) error {
	query := `
		UPDATE bot_trades
		SET exit_timestamp = ?, exit_price_1 = ?, exit_price_2 = ?,
			exit_zscore = ?, pnl = ?, pnl_pct = ?, duration_hours = ?,
			updated_at = ?
		WHERE trade_id = ?
	`

	result, err := r.db.Exec(
		r.bindQuery(query),
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
	query := `DELETE FROM bot_trades WHERE trade_id = ?`

	result, err := r.db.Exec(r.bindQuery(query), tradeID)
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
		WHERE bot_instance_id = ? AND exit_timestamp IS NOT NULL
	`

	var totalTrades, winningTrades, losingTrades int
	var avgWin, avgLoss, totalPnL, avgPnL float64

	err := r.db.QueryRow(r.bindQuery(query), instanceID).Scan(
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
