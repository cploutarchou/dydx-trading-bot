package models

import (
	"encoding/json"
	"time"
)

// ============ TradeLog Methods ============

// ToDict converts TradeLog to dictionary
func (t *TradeLog) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"id":              t.ID,
		"result_id_fk":    t.ResultIDFK,
		"trade_number":    t.TradeNumber,
		"entry_price_1":   t.EntryPrice1,
		"entry_price_2":   t.EntryPrice2,
		"exit_price_1":    t.ExitPrice1,
		"exit_price_2":    t.ExitPrice2,
		"quantity_1":      t.Quantity1,
		"quantity_2":      t.Quantity2,
		"side_1":          t.Side1,
		"side_2":          t.Side2,
		"pnl":             t.Pnl,
		"pnl_usd":         t.PnlUSD,
		"entry_zscore":    t.EntryZScore,
		"exit_zscore":     t.ExitZScore,
		"entry_timestamp": t.EntryTimestamp,
		"exit_timestamp":  t.ExitTimestamp,
		"created_at":      t.CreatedAt,
	}
}

// FromDict populates TradeLog from a dictionary
func (t *TradeLog) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		t.ID = int(id)
	}
	if resultIDFK, ok := data["result_id_fk"].(float64); ok {
		t.ResultIDFK = int(resultIDFK)
	}
	if tradeNumber, ok := data["trade_number"].(float64); ok {
		tn := int(tradeNumber)
		t.TradeNumber = &tn
	}
	if entryPrice1, ok := data["entry_price_1"].(float64); ok {
		t.EntryPrice1 = &entryPrice1
	}
	if entryPrice2, ok := data["entry_price_2"].(float64); ok {
		t.EntryPrice2 = &entryPrice2
	}
	if exitPrice1, ok := data["exit_price_1"].(float64); ok {
		t.ExitPrice1 = &exitPrice1
	}
	if exitPrice2, ok := data["exit_price_2"].(float64); ok {
		t.ExitPrice2 = &exitPrice2
	}
	if quantity1, ok := data["quantity_1"].(float64); ok {
		t.Quantity1 = &quantity1
	}
	if quantity2, ok := data["quantity_2"].(float64); ok {
		t.Quantity2 = &quantity2
	}
	if side1, ok := data["side_1"].(string); ok {
		t.Side1 = &side1
	}
	if side2, ok := data["side_2"].(string); ok {
		t.Side2 = &side2
	}
	if pnl, ok := data["pnl"].(float64); ok {
		t.Pnl = &pnl
	}
	if pnlUSD, ok := data["pnl_usd"].(float64); ok {
		t.PnlUSD = &pnlUSD
	}
	if entryZScore, ok := data["entry_zscore"].(float64); ok {
		t.EntryZScore = &entryZScore
	}
	if exitZScore, ok := data["exit_zscore"].(float64); ok {
		t.ExitZScore = &exitZScore
	}
	if entryTimestamp, ok := data["entry_timestamp"].(string); ok {
		if pt, err := time.Parse(time.RFC3339, entryTimestamp); err == nil {
			t.EntryTimestamp = &pt
		}
	}
	if exitTimestamp, ok := data["exit_timestamp"].(string); ok {
		if pt, err := time.Parse(time.RFC3339, exitTimestamp); err == nil {
			t.ExitTimestamp = &pt
		}
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if ct, err := time.Parse(time.RFC3339, createdAt); err == nil {
			t.CreatedAt = ct
		}
	}
}

// ToJSON converts TradeLog to JSON
func (t *TradeLog) ToJSON() ([]byte, error) {
	return json.Marshal(t.ToDict())
}

// FromJSON populates TradeLog from JSON
func (t *TradeLog) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	t.FromDict(dict)
	return nil
}
