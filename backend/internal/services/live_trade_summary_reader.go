package services

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

const (
	defaultSummaryHours = 24
	maxSummaryHours     = 24 * 30
	tradeEventsTable    = "trade_events"
	orderEventsTable    = "order_events"
)

// LiveTradeTotals is the overall trade-event aggregate returned as a single row
// from trade_events. The mirrored columns are non-nullable (DEFAULT 0), so the
// read model uses plain numeric fields and never has to handle nulls.
type LiveTradeTotals struct {
	TradeEvents         uint64  `json:"trade_events"`
	TradesOpened        uint64  `json:"trades_opened"`
	TradesClosed        uint64  `json:"trades_closed"`
	TotalRealizedPnL    float64 `json:"total_realized_pnl"`
	TotalRealizedPnLPct float64 `json:"total_realized_pnl_pct"`
	WinningTrades       uint64  `json:"winning_trades"`
	LosingTrades        uint64  `json:"losing_trades"`
}

// LiveTradeDayAggregate is one per-day trade-event rollup. day is kept as a
// string because it is projected from toDate(event_time) on the ClickHouse side.
type LiveTradeDayAggregate struct {
	Day              string  `json:"day"`
	TradeEvents      uint64  `json:"trade_events"`
	ClosedTrades     uint64  `json:"closed_trades"`
	TotalRealizedPnL float64 `json:"total_realized_pnl"`
}

// LiveOrderStatusAggregate is a per-status order-event count rollup.
type LiveOrderStatusAggregate struct {
	Status string `json:"status"`
	Count  uint64 `json:"count"`
}

// LiveTradeSummary is the combined backend-owned aggregate read model over the
// bot-mirrored trade_events and order_events tables for a stable bot instance_id.
// It is the second backend-owned ClickHouse read model and is assembled from three
// independent aggregate queries so dashboards get rollups without reading raw rows.
type LiveTradeSummary struct {
	InstanceID     string                     `json:"instance_id"`
	Hours          int                        `json:"hours"`
	Totals         LiveTradeTotals            `json:"totals"`
	Daily          []LiveTradeDayAggregate    `json:"daily"`
	OrdersByStatus []LiveOrderStatusAggregate `json:"orders_by_status"`
	OrderEvents    uint64                     `json:"order_events"`
}

// LiveTradeSummaryReader builds aggregate read models over the live trade_events
// and order_events tables. It depends only on the shared ClickHouseReader and is
// nil when ClickHouse reads are disabled.
type LiveTradeSummaryReader struct {
	reader *ClickHouseReader
}

// NewLiveTradeSummaryReader returns nil when ClickHouse reads are disabled so
// route handlers can nil-check and fail closed to the existing delegated path.
func NewLiveTradeSummaryReader(reader *ClickHouseReader) *LiveTradeSummaryReader {
	if reader == nil {
		return nil
	}
	return &LiveTradeSummaryReader{reader: reader}
}

// GetSummary returns an aggregate summary of trade_events and order_events for a
// stable bot instance_id within the last hours hours. It keys exclusively by the
// backend-owned instance_id and runs three independent aggregate queries, failing
// closed (returning an error) if any query fails so dashboards never see partial
// data.
func (r *LiveTradeSummaryReader) GetSummary(ctx context.Context, instanceID string, hours int) (*LiveTradeSummary, error) {
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

	summary := &LiveTradeSummary{
		InstanceID:     instanceID,
		Hours:          hours,
		Daily:          []LiveTradeDayAggregate{},
		OrdersByStatus: []LiveOrderStatusAggregate{},
	}

	// Trade lifecycle rows are paired (an "opened" row with realized_pnl=0 and a
	// "closed" row carrying the realized PnL), so the totals are computed with
	// event_kind guards to avoid double counting trades or PnL.
	if err := r.loadTradeTotals(ctx, instanceID, hours, summary); err != nil {
		return nil, err
	}
	if err := r.loadDailyBreakdown(ctx, instanceID, hours, summary); err != nil {
		return nil, err
	}
	if err := r.loadOrderStatus(ctx, instanceID, hours, summary); err != nil {
		return nil, err
	}
	return summary, nil
}

// loadTradeTotals runs the single-row trade_events aggregate. The query has no
// GROUP BY, so ClickHouse always returns exactly one row (zeroed when no rows
// match), but the result is still decoded defensively.
func (r *LiveTradeSummaryReader) loadTradeTotals(ctx context.Context, instanceID string, hours int, summary *LiveTradeSummary) error {
	// Values are bound server-side via ClickHouse {name:Type} placeholders and the
	// matching param_name HTTP query arguments emitted by ClickHouseReader.Query.
	// They are never string-interpolated into the query text.
	query := fmt.Sprintf(`
SELECT
    count() AS trade_events,
    countIf(event_kind = 'opened') AS trades_opened,
    countIf(event_kind = 'closed') AS trades_closed,
    sum(realized_pnl) AS total_realized_pnl,
    sum(realized_pnl_pct) AS total_realized_pnl_pct,
    countIf(event_kind = 'closed' AND realized_pnl > 0) AS winning_trades,
    countIf(event_kind = 'closed' AND realized_pnl < 0) AS losing_trades
FROM %s
WHERE instance_id = {instance_id:String}
  AND event_time >= now() - toIntervalHour({hours:UInt32})`, tradeEventsTable)

	rows, err := r.reader.Query(ctx, query, r.paramsFor(instanceID, hours))
	if err != nil {
		return err
	}
	totals, err := DecodeRows[LiveTradeTotals](rows)
	if err != nil {
		return err
	}
	if len(totals) > 0 {
		summary.Totals = totals[0]
	}
	return nil
}

// loadDailyBreakdown runs the per-day trade_events rollup grouped by event day.
func (r *LiveTradeSummaryReader) loadDailyBreakdown(ctx context.Context, instanceID string, hours int, summary *LiveTradeSummary) error {
	query := fmt.Sprintf(`
SELECT
    toString(toDate(event_time)) AS day,
    count() AS trade_events,
    countIf(event_kind = 'closed') AS closed_trades,
    sum(realized_pnl) AS total_realized_pnl
FROM %s
WHERE instance_id = {instance_id:String}
  AND event_time >= now() - toIntervalHour({hours:UInt32})
GROUP BY day
ORDER BY day ASC`, tradeEventsTable)

	rows, err := r.reader.Query(ctx, query, r.paramsFor(instanceID, hours))
	if err != nil {
		return err
	}
	daily, err := DecodeRows[LiveTradeDayAggregate](rows)
	if err != nil {
		return err
	}
	if daily == nil {
		daily = []LiveTradeDayAggregate{}
	}
	summary.Daily = daily
	return nil
}

// loadOrderStatus runs the order_events status rollup and derives the total
// order-event count from the per-status breakdown so the envelope stays
// internally consistent with a single query.
func (r *LiveTradeSummaryReader) loadOrderStatus(ctx context.Context, instanceID string, hours int, summary *LiveTradeSummary) error {
	query := fmt.Sprintf(`
SELECT
    status,
    count() AS count
FROM %s
WHERE instance_id = {instance_id:String}
  AND event_time >= now() - toIntervalHour({hours:UInt32})
GROUP BY status
ORDER BY count DESC`, orderEventsTable)

	rows, err := r.reader.Query(ctx, query, r.paramsFor(instanceID, hours))
	if err != nil {
		return err
	}
	byStatus, err := DecodeRows[LiveOrderStatusAggregate](rows)
	if err != nil {
		return err
	}
	if byStatus == nil {
		byStatus = []LiveOrderStatusAggregate{}
	}
	summary.OrdersByStatus = byStatus
	var total uint64
	for _, entry := range byStatus {
		total += entry.Count
	}
	summary.OrderEvents = total
	return nil
}

func (r *LiveTradeSummaryReader) paramsFor(instanceID string, hours int) map[string]string {
	return map[string]string{
		"instance_id": instanceID,
		"hours":       fmt.Sprintf("%d", hours),
	}
}
