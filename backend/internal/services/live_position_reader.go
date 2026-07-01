package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

// DecodeRows decodes ClickHouse JSONEachRow raw rows into typed read models.
// It is generic so each read model can define its own struct without re-implementing
// JSONEachRow parsing.
func DecodeRows[T any](rows []json.RawMessage) ([]T, error) {
	if len(rows) == 0 {
		return nil, nil
	}
	out := make([]T, 0, len(rows))
	for index, raw := range rows {
		var item T
		if err := json.Unmarshal(raw, &item); err != nil {
			return nil, fmt.Errorf("decode row %d: %w", index, err)
		}
		out = append(out, item)
	}
	return out, nil
}

const (
	defaultPositionHistoryHours = 24
	maxPositionHistoryHours     = 24 * 30
	maxPositionHistoryRows      = 1000
	positionSnapshotsTable      = "position_snapshots"
)

// LivePositionSnapshot is the backend-owned read model over the bot-mirrored
// position_snapshots ClickHouse table. Nullable analytical columns use pointers
// so missing values survive the JSONEachRow round trip. snapshot_time is kept as
// a string because ClickHouse DateTime64 JSONEachRow output is not RFC3339.
type LivePositionSnapshot struct {
	SnapshotTime     string   `json:"snapshot_time"`
	PositionID       string   `json:"position_id"`
	InstanceID       string   `json:"instance_id"`
	BotID            string   `json:"bot_id"`
	Pair1            string   `json:"pair1"`
	Pair2            string   `json:"pair2"`
	Side1            string   `json:"side1"`
	Side2            string   `json:"side2"`
	Status           string   `json:"status"`
	EventKind        string   `json:"event_kind"`
	EntryPrice1      float64  `json:"entry_price1"`
	EntryPrice2      float64  `json:"entry_price2"`
	CurrentPrice1    *float64 `json:"current_price1,omitempty"`
	CurrentPrice2    *float64 `json:"current_price2,omitempty"`
	EntrySize1       float64  `json:"entry_size1"`
	EntrySize2       float64  `json:"entry_size2"`
	UnrealizedPnL    float64  `json:"unrealized_pnl"`
	UnrealizedPnLPct float64  `json:"unrealized_pnl_pct"`
	RealizedPnL      float64  `json:"realized_pnl"`
	RealizedPnLPct   float64  `json:"realized_pnl_pct"`
	ZScoreCurrent    *float64 `json:"z_score_current,omitempty"`
}

// LivePositionReader builds typed read models over the live position_snapshots
// table. It is the first backend-owned ClickHouse read model and depends only on
// the shared ClickHouseReader.
type LivePositionReader struct {
	reader *ClickHouseReader
}

// NewLivePositionReader returns nil when ClickHouse reads are disabled so route
// handlers can nil-check and fall back to the existing delegated read path.
func NewLivePositionReader(reader *ClickHouseReader) *LivePositionReader {
	if reader == nil {
		return nil
	}
	return &LivePositionReader{reader: reader}
}

// GetHistory returns position_snapshots rows for a stable bot instance_id,
// optionally narrowed to a single position_id, within the last hours hours. It
// keys exclusively by the backend-owned instance_id so the read model never
// depends on an unsafe cross-DB numeric bot id.
func (r *LivePositionReader) GetHistory(ctx context.Context, instanceID, positionID string, hours int) ([]LivePositionSnapshot, error) {
	if r == nil {
		return nil, ErrClickHouseDisabled
	}
	instanceID = strings.TrimSpace(instanceID)
	if instanceID == "" {
		return nil, errors.New("instance_id is required")
	}
	positionID = strings.TrimSpace(positionID)
	if hours <= 0 {
		hours = defaultPositionHistoryHours
	}
	if hours > maxPositionHistoryHours {
		hours = maxPositionHistoryHours
	}

	params := map[string]string{
		"instance_id": instanceID,
		"hours":       fmt.Sprintf("%d", hours),
		"limit":       fmt.Sprintf("%d", maxPositionHistoryRows),
	}

	// Values are bound server-side via ClickHouse {name:Type} placeholders and the
	// matching param_name HTTP query arguments emitted by ClickHouseReader.Query.
	// They are never string-interpolated into the query text.
	query := fmt.Sprintf(`
SELECT
    toString(snapshot_time) AS snapshot_time,
    position_id,
    instance_id,
    bot_id,
    pair1,
    pair2,
    side1,
    side2,
    status,
    event_kind,
    entry_price1,
    entry_price2,
    current_price1,
    current_price2,
    entry_size1,
    entry_size2,
    unrealized_pnl,
    unrealized_pnl_pct,
    realized_pnl,
    realized_pnl_pct,
    z_score_current
FROM %s
WHERE instance_id = {instance_id:String}
  AND snapshot_time >= now() - toIntervalHour({hours:UInt32})`, positionSnapshotsTable)

	if positionID != "" {
		params["position_id"] = positionID
		query += "\n  AND position_id = {position_id:String}"
	}
	query += "\nORDER BY snapshot_time ASC\nLIMIT {limit:UInt32}"

	rows, err := r.reader.Query(ctx, query, params)
	if err != nil {
		return nil, err
	}
	return DecodeRows[LivePositionSnapshot](rows)
}
