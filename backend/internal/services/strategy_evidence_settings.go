package services

import (
	"encoding/json"
	"math"
	"strings"
)

// evidenceSettingsFromConfig picks the allowlisted strategy settings out of a
// run's stored config snapshot (backtest_runs.config). The bot request nests
// them under trading_parameters; older rows may hold them at the top level.
// Anything else in the snapshot (markets, balances, metadata) is not copied.
func evidenceSettingsFromConfig(config string) map[string]any {
	config = strings.TrimSpace(config)
	if config == "" {
		return nil
	}
	var decoded map[string]any
	if err := json.Unmarshal([]byte(config), &decoded); err != nil {
		return nil
	}
	sources := make([]map[string]any, 0, 3)
	if params, ok := decoded["trading_parameters"].(map[string]any); ok {
		sources = append(sources, params)
	}
	if request, ok := decoded["request"].(map[string]any); ok {
		if params, ok := request["trading_parameters"].(map[string]any); ok {
			sources = append(sources, params)
		}
	}
	sources = append(sources, decoded)

	settings := make(map[string]any)
	for _, field := range strategyChatFields {
		for _, source := range sources {
			raw, ok := source[field.Key]
			if !ok {
				if field.Key == "candle_resolution" {
					raw, ok = source["resolution"]
				}
				if !ok {
					continue
				}
			}
			if value, ok := evidenceSettingValue(field, raw); ok {
				settings[field.Key] = value
			}
			break
		}
	}
	if len(settings) == 0 {
		return nil
	}
	return settings
}

// evidenceSettingValue coerces a snapshot value to the field's type; values
// of another type are dropped rather than guessed.
func evidenceSettingValue(field strategyChatField, raw any) (any, bool) {
	switch field.Kind {
	case strategyChatBool:
		value, ok := raw.(bool)
		return value, ok
	case strategyChatEnum:
		text, ok := raw.(string)
		if !ok {
			return nil, false
		}
		value, ok := strictCandleResolution(text)
		return value, ok
	default:
		number, ok := strategyChatNumber(raw)
		if !ok || math.IsNaN(number) || math.IsInf(number, 0) {
			return nil, false
		}
		if field.Kind == strategyChatInt {
			if number != math.Trunc(number) {
				return nil, false
			}
			return int(number), true
		}
		return number, true
	}
}
