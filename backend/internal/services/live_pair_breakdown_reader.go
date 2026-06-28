package services

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

// LivePairBreakdown is one per-pair trade-performance aggregate projected from
// the bot-mirrored trade_events table. Pairs are the trading unit for this bot
// (pair1 + pair2 legs), so the breakdown groups closed trade lifecycle rows by
// the pair rather than by individual market. The aggregated columns are
// non-nullable (DEFAULT 0), so the read model uses plain numeric fields.
type LivePairBreakdown struct {
	Pair1             string  `json:"pair1"`
	Pair2             string  `json:"pair2"`
	TradesClosed      uint64  `json:"trades_closed"`
	TotalRealizedPnL  float64 `json:"total_realized_pnl"`
	AvgRealizedPnLPct float64 `json:"avg_realized_pnl_pct"`
	WinningTrades     uint64  `json:"winning_trades"`
	LosingTrades      uint64  `json:"losing_trades"`
	BestRealizedPnL   float64 `json:"best_realized_pnl"`
	WorstRealizedPnL  float64 `json:"worst_realized_pnl"`
}

// LivePairBreakdownSummary is the combined envelope for the per-pair breakdown
// read model over trade_events for a stable bot instance_id.
type LivePairBreakdownSummary struct {
	InstanceID string              `json:"instance_id"`
	Hours      int                 `json:"hours"`
	Pairs      []LivePairBreakdown `json:"pairs"`
}

// LivePairBreakdownReader builds per-pair aggregate read models over the live
// trade_events table. It is the third backend-owned ClickHouse read model and
// depends only on the shared ClickHouseReader.
type LivePairBreakdownReader struct {
	reader *ClickHouseReader
}

// NewLivePairBreakdownReader returns nil when ClickHouse reads are disabled so
// route handlers can nil-check and fail closed to the existing delegated path.
func NewLivePairBreakdownReader(reader *ClickHouseReader) *LivePairBreakdownReader {
	if reader == nil {
		return nil
	}
	return &LivePairBreakdownReader{reader: reader}
}

// GetBreakdown returns a per-pair trade-performance aggregate for a stable bot
// instance_id within the last hours hours. It keys exclusively by the
// backend-owned instance_id and aggregates only the closed trade lifecycle rows
// (event_kind = 'closed'), which are the rows that carry realized PnL, so each
// closed trade is counted exactly once per pair.
func (r *LivePairBreakdownReader) GetBreakdown(ctx context.Context, instanceID string, hours int) (*LivePairBreakdownSummary, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}
	instanceID = strings.TrimSpace(instanceID)
	if instanceID == "" {
		return nil, errors.New("instance_id is required")
	}
	if hours <= 0 {
		hours = defaultSummaryHours
	}
	if hours > maxSummaryHours {
		hours = maxSummaryHours
	}

	// Values are bound server-side via ClickHouse {name:Type} placeholders and the
	// matching param_name HTTP query arguments emitted by ClickHouseReader.Query.
	// They are never string-interpolated into the query text.
	query := fmt.Sprintf(`
SELECT
    pair1,
    pair2,
    count() AS trades_closed,
    sum(realized_pnl) AS total_realized_pnl,
    avg(realized_pnl_pct) AS avg_realized_pnl_pct,
    countIf(realized_pnl > 0) AS winning_trades,
    countIf(realized_pnl < 0) AS losing_trades,
    max(realized_pnl) AS best_realized_pnl,
    min(realized_pnl) AS worst_realized_pnl
FROM %s
WHERE instance_id = {instance_id:String}
  AND event_kind = 'closed'
  AND event_time >= now() - toIntervalHour({hours:UInt32})
GROUP BY pair1, pair2
ORDER BY total_realized_pnl DESC`, tradeEventsTable)

	rows, err := r.reader.Query(ctx, query, map[string]string{
		"instance_id": instanceID,
		"hours":       fmt.Sprintf("%d", hours),
	})
	if err != nil {
		return nil, err
	}
	pairs, err := DecodeRows[LivePairBreakdown](rows)
	if err != nil {
		return nil, err
	}
	if pairs == nil {
		pairs = []LivePairBreakdown{}
	}
	return &LivePairBreakdownSummary{
		InstanceID: instanceID,
		Hours:      hours,
		Pairs:      pairs,
	}, nil
}
