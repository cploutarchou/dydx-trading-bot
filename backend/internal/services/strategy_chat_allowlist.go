package services

import (
	"fmt"
	"math"
	"strconv"
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// The strategy chat allowlist is the single source of truth for what the
// assistant may change: the prompt, the reply schema, proposal validation,
// apply and create-strategy all read strategyChatFields.

const (
	StrategyChatRiskNormal      = "normal"
	StrategyChatRiskMoney       = "money"
	StrategyChatRiskRiskControl = "risk_control"

	StrategyChatKindUpdate      = "update"
	StrategyChatKindNewStrategy = "new_strategy"

	strategyChatMaxChanges = 8
)

type strategyChatValueKind string

const (
	strategyChatFloat strategyChatValueKind = "float"
	strategyChatInt   strategyChatValueKind = "int"
	strategyChatEnum  strategyChatValueKind = "enum"
	strategyChatBool  strategyChatValueKind = "bool"
)

// StrategyChatChange is one validated change of a proposal.
type StrategyChatChange struct {
	Field        string `json:"field"`
	Label        string `json:"label"`
	Unit         string `json:"unit"`
	Current      any    `json:"current"`
	Proposed     any    `json:"proposed"`
	Reason       string `json:"reason"`
	Risk         string `json:"risk"`
	BacktestOnly bool   `json:"backtest_only"`
}

// StrategyChatDroppedChange is a proposed change the server refused, and why.
type StrategyChatDroppedChange struct {
	Field  string `json:"field"`
	Value  any    `json:"value"`
	Reason string `json:"reason"`
}

// StrategyChatProposal is a server-validated proposal as stored and returned.
type StrategyChatProposal struct {
	Kind          string                      `json:"kind"`
	Title         string                      `json:"title"`
	Summary       string                      `json:"summary"`
	SuggestedName string                      `json:"suggested_name"`
	Changes       []StrategyChatChange        `json:"changes"`
	Dropped       []StrategyChatDroppedChange `json:"dropped"`
}

type strategyChatField struct {
	Key          string
	Label        string
	Unit         string
	Risk         string
	BacktestOnly bool
	Kind         strategyChatValueKind
	Min          float64
	Max          float64
	ExclusiveMin bool
	// NoSwitchOff forbids proposing 0 (off) while the limit is on.
	NoSwitchOff bool
	Options     []string
	// Hint is extra meaning spelled out for the model, such as units.
	Hint string
	get  func(*models.BacktestStrategy) any
	set  func(*models.BacktestStrategy, any)
}

var strategyChatCandleResolutions = []string{"1MIN", "5MINS", "15MINS", "30MINS", "1HOUR", "4HOURS", "1DAY"}

var strategyChatFields = []strategyChatField{
	{
		Key: "zscore_threshold", Label: "Z-score entry threshold", Risk: StrategyChatRiskNormal,
		Kind: strategyChatFloat, Min: 0.1, Max: 10,
		get: func(s *models.BacktestStrategy) any { return s.ZscoreThreshold },
		set: func(s *models.BacktestStrategy, v any) { s.ZscoreThreshold = v.(float64) },
	},
	{
		Key: "stats_window", Label: "Statistics window", Unit: "bars", Risk: StrategyChatRiskNormal,
		Kind: strategyChatInt, Min: 2, Max: 2000,
		get: func(s *models.BacktestStrategy) any { return s.StatsWindow },
		set: func(s *models.BacktestStrategy, v any) { s.StatsWindow = v.(int) },
	},
	{
		Key: "max_half_life", Label: "Maximum half-life", Unit: "bars", Risk: StrategyChatRiskNormal,
		Kind: strategyChatInt, Min: 1, Max: 10000,
		get: func(s *models.BacktestStrategy) any { return strategyChatWholeNumber(s.MaxHalfLife) },
		set: func(s *models.BacktestStrategy, v any) { s.MaxHalfLife = float64(v.(int)) },
	},
	{
		Key: "usd_per_trade", Label: "Size per trade", Unit: "USD", Risk: StrategyChatRiskMoney,
		Kind: strategyChatFloat, Min: 1, Max: 1_000_000,
		get: func(s *models.BacktestStrategy) any { return s.UsdPerTrade },
		set: func(s *models.BacktestStrategy, v any) { s.UsdPerTrade = v.(float64) },
	},
	{
		Key: "usd_min_collateral", Label: "Minimum free collateral", Unit: "USD", Risk: StrategyChatRiskMoney,
		Kind: strategyChatFloat, Min: 1, Max: 10_000_000,
		get: func(s *models.BacktestStrategy) any { return s.UsdMinCollateral },
		set: func(s *models.BacktestStrategy, v any) { s.UsdMinCollateral = v.(float64) },
	},
	{
		Key: "max_positions", Label: "Maximum open pairs", Risk: StrategyChatRiskMoney,
		Kind: strategyChatInt, Min: 1, Max: 100,
		get: func(s *models.BacktestStrategy) any { return s.MaxPositions },
		set: func(s *models.BacktestStrategy, v any) { s.MaxPositions = v.(int) },
	},
	// The risk-control bounds stay well below the values at which the limit
	// never triggers in practice (a 100% drawdown or stop, a one-year
	// timeout), so a proposal cannot switch a limit off through its maximum.
	{
		Key: "max_drawdown_pct", Label: "Maximum drawdown", Unit: "%", Risk: StrategyChatRiskRiskControl,
		Kind: strategyChatFloat, Min: 0, Max: 50, NoSwitchOff: true,
		Hint: "0 means off",
		get:  func(s *models.BacktestStrategy) any { return s.MaxDrawdownPct },
		set:  func(s *models.BacktestStrategy, v any) { s.MaxDrawdownPct = v.(float64) },
	},
	{
		Key: "stop_loss_pct", Label: "Stop loss", Unit: "%", Risk: StrategyChatRiskRiskControl,
		Kind: strategyChatFloat, Min: 0.1, Max: 25,
		get: func(s *models.BacktestStrategy) any { return s.StopLossPct },
		set: func(s *models.BacktestStrategy, v any) { s.StopLossPct = v.(float64) },
	},
	{
		Key: "take_profit_pct", Label: "Take profit", Unit: "%", Risk: StrategyChatRiskNormal,
		Kind: strategyChatFloat, Min: 0.1, Max: 1000,
		get: func(s *models.BacktestStrategy) any { return s.TakeProfitPct },
		set: func(s *models.BacktestStrategy, v any) { s.TakeProfitPct = v.(float64) },
	},
	{
		Key: "trailing_stop_pct", Label: "Trailing stop", Unit: "%", Risk: StrategyChatRiskRiskControl,
		Kind: strategyChatFloat, Min: 0, Max: 25, NoSwitchOff: true,
		Hint: "0 means off",
		get:  func(s *models.BacktestStrategy) any { return s.TrailingStopPct },
		set:  func(s *models.BacktestStrategy, v any) { s.TrailingStopPct = v.(float64) },
	},
	{
		Key: "rebalance_interval_hours", Label: "Rebalance interval", Unit: "hours", Risk: StrategyChatRiskNormal,
		Kind: strategyChatInt, Min: 1, Max: 8760,
		get: func(s *models.BacktestStrategy) any { return s.RebalanceIntervalHours },
		set: func(s *models.BacktestStrategy, v any) { s.RebalanceIntervalHours = v.(int) },
	},
	{
		Key: "position_timeout_hours", Label: "Position timeout", Unit: "hours", Risk: StrategyChatRiskRiskControl,
		Kind: strategyChatInt, Min: 1, Max: 720,
		get: func(s *models.BacktestStrategy) any { return s.PositionTimeoutHours },
		set: func(s *models.BacktestStrategy, v any) { s.PositionTimeoutHours = v.(int) },
	},
	{
		Key: "transaction_fee", Label: "Backtest fee rate (fraction)", Risk: StrategyChatRiskNormal, BacktestOnly: true,
		Kind: strategyChatFloat, Min: 0, Max: 0.1, ExclusiveMin: true,
		Hint: "a fraction per fill, 0.0005 means 0.05%",
		get:  func(s *models.BacktestStrategy) any { return s.TransactionFee },
		set:  func(s *models.BacktestStrategy, v any) { s.TransactionFee = v.(float64) },
	},
	{
		Key: "slippage", Label: "Backtest slippage (fraction)", Risk: StrategyChatRiskNormal, BacktestOnly: true,
		Kind: strategyChatFloat, Min: 0, Max: 0.1, ExclusiveMin: true,
		Hint: "a fraction per fill, 0.001 means 0.1%",
		get:  func(s *models.BacktestStrategy) any { return s.Slippage },
		set:  func(s *models.BacktestStrategy, v any) { s.Slippage = v.(float64) },
	},
	{
		Key: "max_history_days", Label: "Backtest history", Unit: "days", Risk: StrategyChatRiskNormal, BacktestOnly: true,
		Kind: strategyChatInt, Min: 1, Max: 3650,
		get: func(s *models.BacktestStrategy) any { return s.MaxHistoryDays },
		set: func(s *models.BacktestStrategy, v any) { s.MaxHistoryDays = v.(int) },
	},
	{
		Key: "risk_free_rate", Label: "Risk-free rate (fraction)", Risk: StrategyChatRiskNormal, BacktestOnly: true,
		Kind: strategyChatFloat, Min: 0, Max: 1, ExclusiveMin: true,
		Hint: "a yearly fraction, 0.02 means 2%",
		get:  func(s *models.BacktestStrategy) any { return s.RiskFreeRate },
		set:  func(s *models.BacktestStrategy, v any) { s.RiskFreeRate = v.(float64) },
	},
	{
		Key: "candle_resolution", Label: "Candle resolution", Risk: StrategyChatRiskNormal,
		Kind: strategyChatEnum, Options: strategyChatCandleResolutions,
		get: func(s *models.BacktestStrategy) any { return s.CandleResolution },
		set: func(s *models.BacktestStrategy, v any) { s.CandleResolution = v.(string) },
	},
	{
		Key: "close_at_zscore_cross", Label: "Close when the z-score crosses zero", Risk: StrategyChatRiskNormal,
		Kind: strategyChatBool,
		get:  func(s *models.BacktestStrategy) any { return s.CloseAtZscoreCross },
		set:  func(s *models.BacktestStrategy, v any) { s.CloseAtZscoreCross = v.(bool) },
	},
}

var strategyChatFieldIndex = func() map[string]*strategyChatField {
	index := make(map[string]*strategyChatField, len(strategyChatFields))
	for i := range strategyChatFields {
		index[strategyChatFields[i].Key] = &strategyChatFields[i]
	}
	return index
}()

// strategyChatFieldAliases maps accepted alternative names to allowlist keys.
var strategyChatFieldAliases = map[string]string{
	"resolution": "candle_resolution",
}

// strategyChatLockedFields are real strategy settings the assistant may never
// change; they get a clearer drop reason than an unknown name.
var strategyChatLockedFields = map[string]bool{
	"id": true, "user_id": true, "name": true, "description": true, "category": true,
	"runtime_network": true, "runtime_subaccount": true, "runtime_strategy": true,
	"place_trades": true, "abort_all_positions": true, "is_public": true, "is_default": true,
	"find_cointegrated_pairs": true, "manage_exits": true, "selected_markets": true,
	"pair_selection_mode": true, "starting_balance": true, "initial_amount": true,
	"benchmark_symbol": true, "capital_allocation_usd": true,
}

// canonicalStrategyChatField resolves a field name or alias to its allowlist
// entry.
func canonicalStrategyChatField(name string) (*strategyChatField, bool) {
	key := strings.ToLower(strings.TrimSpace(name))
	if alias, ok := strategyChatFieldAliases[key]; ok {
		key = alias
	}
	field, ok := strategyChatFieldIndex[key]
	return field, ok
}

// normalize converts a proposed value to the field's Go type (float64, int,
// string or bool) and checks its bounds; it returns a reason when it refuses.
func (f *strategyChatField) normalize(raw any) (any, string) {
	switch f.Kind {
	case strategyChatBool:
		switch value := raw.(type) {
		case bool:
			return value, ""
		case string:
			switch strings.ToLower(strings.TrimSpace(value)) {
			case "true":
				return true, ""
			case "false":
				return false, ""
			}
		}
		return nil, "Expected true or false"
	case strategyChatEnum:
		text, ok := raw.(string)
		if !ok {
			return nil, "Expected one of " + strings.Join(f.Options, ", ")
		}
		if value, ok := strictCandleResolution(text); ok {
			return value, ""
		}
		return nil, "Expected one of " + strings.Join(f.Options, ", ")
	}

	number, ok := strategyChatNumber(raw)
	if !ok {
		return nil, "Expected a number"
	}
	if math.IsNaN(number) || math.IsInf(number, 0) {
		return nil, "Expected a finite number"
	}
	if (f.ExclusiveMin && number <= f.Min) || (!f.ExclusiveMin && number < f.Min) || number > f.Max {
		return nil, "Outside the allowed range " + f.rangeText()
	}
	if f.Kind == strategyChatInt {
		if number != math.Trunc(number) {
			return nil, "Expected a whole number"
		}
		return int(number), ""
	}
	return number, ""
}

func (f *strategyChatField) rangeText() string {
	lower := "from " + strategyChatFormatNumber(f.Min)
	if f.ExclusiveMin {
		lower = "above " + strategyChatFormatNumber(f.Min)
	}
	return lower + " to " + strategyChatFormatNumber(f.Max)
}

// strategyChatMaxLoosening is how much larger than the current value a
// risk-control limit may be proposed while it is on: a bigger jump would
// switch the limit off in all but name.
const strategyChatMaxLoosening = 4

// checkAgainst refuses a normalized value that equals the current one,
// switches a risk limit off, or loosens a risk limit more than four-fold.
func (f *strategyChatField) checkAgainst(value any, current any) string {
	if strategyChatValuesEqual(value, current) {
		return "Same as the current value"
	}
	proposed, _ := strategyChatNumber(value)
	existing, _ := strategyChatNumber(current)
	if f.NoSwitchOff && existing > 0 && proposed == 0 {
		return "Switching this risk limit off is not allowed"
	}
	if f.Risk == StrategyChatRiskRiskControl && existing > 0 && proposed > strategyChatMaxLoosening*existing {
		return "Loosens this risk limit more than four-fold; propose a smaller step"
	}
	return ""
}

func strategyChatNumber(raw any) (float64, bool) {
	switch value := raw.(type) {
	case float64:
		return value, true
	case float32:
		return float64(value), true
	case int:
		return float64(value), true
	case int64:
		return float64(value), true
	case string:
		parsed, err := strconv.ParseFloat(strings.TrimSpace(value), 64)
		if err != nil {
			return 0, false
		}
		return parsed, true
	default:
		return 0, false
	}
}

func strategyChatValuesEqual(left any, right any) bool {
	leftNumber, leftIsNumber := strategyChatNumber(left)
	rightNumber, rightIsNumber := strategyChatNumber(right)
	_, leftIsString := left.(string)
	_, rightIsString := right.(string)
	if leftIsNumber && rightIsNumber && !leftIsString && !rightIsString {
		return math.Abs(leftNumber-rightNumber) <= 1e-9*math.Max(1, math.Abs(rightNumber))
	}
	return fmt.Sprint(left) == fmt.Sprint(right)
}

// strategyChatWholeNumber reports a float setting that holds a whole number as
// an int, the way the allowlist declares it.
func strategyChatWholeNumber(value float64) any {
	if value == math.Trunc(value) && math.Abs(value) < 1e15 {
		return int(value)
	}
	return value
}

func strategyChatFormatNumber(value float64) string {
	return strconv.FormatFloat(value, 'f', -1, 64)
}

// strictCandleResolution maps the resolution spellings the strategy editor
// accepts onto the stored values and, unlike the editor, refuses anything
// else instead of defaulting to 1HOUR.
func strictCandleResolution(value string) (string, bool) {
	switch strings.ToUpper(strings.TrimSpace(value)) {
	case "M1", "1M", "1MIN", "1MINUTE", "1MINUTES":
		return "1MIN", true
	case "M5", "5M", "5MIN", "5MINS", "5MINUTE", "5MINUTES":
		return "5MINS", true
	case "M15", "15M", "15MIN", "15MINS", "15MINUTE", "15MINUTES":
		return "15MINS", true
	case "M30", "30M", "30MIN", "30MINS", "30MINUTE", "30MINUTES":
		return "30MINS", true
	case "H1", "1H", "1HR", "1HOUR", "1HOURS":
		return "1HOUR", true
	case "H4", "4H", "4HR", "4HOUR", "4HOURS":
		return "4HOURS", true
	case "D1", "1D", "1DAY", "1DAYS":
		return "1DAY", true
	default:
		return "", false
	}
}

// strategyChatModelChange and strategyChatModelProposal are the model's reply
// before validation. Nothing in them is trusted.
type strategyChatModelChange struct {
	Field  string `json:"field"`
	Value  any    `json:"value"`
	Reason string `json:"reason"`
}

type strategyChatModelProposal struct {
	Kind          string                    `json:"kind"`
	Title         string                    `json:"title"`
	Summary       string                    `json:"summary"`
	SuggestedName string                    `json:"suggested_name"`
	Changes       []strategyChatModelChange `json:"changes"`
}

type strategyChatModelReply struct {
	Reply    string                     `json:"reply"`
	Proposal *strategyChatModelProposal `json:"proposal"`
}

// validateStrategyChatProposal keeps only allowlisted, in-bounds changes that
// differ from the strategy's current values (at most 8), and records every
// refused change with its reason. Current values come from the strategy, never
// from the model.
func validateStrategyChatProposal(raw *strategyChatModelProposal, strategy *models.BacktestStrategy) *StrategyChatProposal {
	if raw == nil {
		return nil
	}
	proposal := &StrategyChatProposal{
		Kind:          StrategyChatKindUpdate,
		Title:         truncateAIText(raw.Title, 120),
		Summary:       truncateAIText(raw.Summary, 1000),
		SuggestedName: truncateAIText(raw.SuggestedName, 100),
		Changes:       make([]StrategyChatChange, 0),
		Dropped:       make([]StrategyChatDroppedChange, 0),
	}
	if strings.EqualFold(strings.TrimSpace(raw.Kind), StrategyChatKindNewStrategy) {
		proposal.Kind = StrategyChatKindNewStrategy
	}
	if proposal.Title == "" {
		proposal.Title = "Suggested changes"
		if proposal.Kind == StrategyChatKindNewStrategy {
			proposal.Title = "Suggested new strategy"
		}
	}

	seen := make(map[string]bool, len(raw.Changes))
	for _, change := range raw.Changes {
		drop := func(reason string) {
			proposal.Dropped = append(proposal.Dropped, StrategyChatDroppedChange{
				Field:  truncateAIText(change.Field, 64),
				Value:  strategyChatSafeValue(change.Value),
				Reason: reason,
			})
		}

		field, ok := canonicalStrategyChatField(change.Field)
		if !ok {
			if strategyChatLockedFields[strings.ToLower(strings.TrimSpace(change.Field))] {
				drop("The assistant cannot change this setting")
			} else {
				drop("Unknown setting")
			}
			continue
		}
		if seen[field.Key] {
			drop("Duplicate change for this setting")
			continue
		}
		seen[field.Key] = true

		value, reason := field.normalize(change.Value)
		current := field.get(strategy)
		if reason == "" {
			reason = field.checkAgainst(value, current)
		}
		if reason == "" && len(proposal.Changes) >= strategyChatMaxChanges {
			reason = fmt.Sprintf("More than %d changes were proposed", strategyChatMaxChanges)
		}
		if reason != "" {
			drop(reason)
			continue
		}
		proposal.Changes = append(proposal.Changes, StrategyChatChange{
			Field:        field.Key,
			Label:        field.Label,
			Unit:         field.Unit,
			Current:      current,
			Proposed:     value,
			Reason:       truncateAIText(change.Reason, 500),
			Risk:         field.Risk,
			BacktestOnly: field.BacktestOnly,
		})
	}
	return proposal
}

// strategyChatSafeValue keeps a refused value only when it is a short scalar.
func strategyChatSafeValue(value any) any {
	switch typed := value.(type) {
	case bool, float64, int:
		return typed
	case string:
		return truncateAIText(typed, 64)
	default:
		return nil
	}
}

// strategyChatReplySchema is the strict structured-output schema of a reply:
// every object closed and fully required, unions as anyOf.
func strategyChatReplySchema() map[string]any {
	fields := make([]string, 0, len(strategyChatFields))
	for _, field := range strategyChatFields {
		fields = append(fields, field.Key)
	}
	change := map[string]any{
		"type":                 "object",
		"additionalProperties": false,
		"required":             []string{"field", "value", "reason"},
		"properties": map[string]any{
			"field": map[string]any{"type": "string", "enum": fields},
			"value": map[string]any{"anyOf": []any{
				map[string]any{"type": "number"},
				map[string]any{"type": "string"},
				map[string]any{"type": "boolean"},
			}},
			"reason": map[string]any{"type": "string"},
		},
	}
	proposal := map[string]any{
		"type":                 "object",
		"additionalProperties": false,
		"required":             []string{"kind", "title", "summary", "suggested_name", "changes"},
		"properties": map[string]any{
			"kind":           map[string]any{"type": "string", "enum": []string{StrategyChatKindUpdate, StrategyChatKindNewStrategy}},
			"title":          map[string]any{"type": "string"},
			"summary":        map[string]any{"type": "string"},
			"suggested_name": map[string]any{"type": "string"},
			"changes": map[string]any{
				"type":     "array",
				"maxItems": strategyChatMaxChanges,
				"items":    change,
			},
		},
	}
	return map[string]any{
		"type":                 "object",
		"additionalProperties": false,
		"required":             []string{"reply", "proposal"},
		"properties": map[string]any{
			"reply":    map[string]any{"type": "string"},
			"proposal": map[string]any{"anyOf": []any{map[string]any{"type": "null"}, proposal}},
		},
	}
}

// strategyChatFieldPromptLines lists every allowlisted field with its bounds
// for the system prompt.
func strategyChatFieldPromptLines() []string {
	lines := make([]string, 0, len(strategyChatFields))
	for _, field := range strategyChatFields {
		label := field.Label
		if field.Unit != "" {
			label = fmt.Sprintf("%s (%s)", label, field.Unit)
		}
		var rule string
		switch field.Kind {
		case strategyChatBool:
			rule = "true or false"
		case strategyChatEnum:
			rule = "one of " + strings.Join(field.Options, ", ")
		case strategyChatInt:
			rule = "whole number " + field.rangeText()
		default:
			rule = "number " + field.rangeText()
		}
		notes := make([]string, 0, 3)
		if field.Hint != "" {
			notes = append(notes, field.Hint)
		}
		if field.NoSwitchOff {
			notes = append(notes, "never propose 0 while it is on")
		}
		if field.Risk == StrategyChatRiskRiskControl {
			notes = append(notes, "at most four times the current value")
		}
		if field.BacktestOnly {
			notes = append(notes, "backtest only")
		}
		line := fmt.Sprintf("- %s: %s; %s", field.Key, label, rule)
		if len(notes) > 0 {
			line += "; " + strings.Join(notes, "; ")
		}
		lines = append(lines, line)
	}
	return lines
}
