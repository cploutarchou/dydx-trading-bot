package routes

import "testing"

// TestExtractBacktestRunID verifies the dual-write correlation reads the real
// run_id from the bot API response (top-level or data envelope) and returns ""
// when absent, so the route never fabricates a run identifier.
func TestExtractBacktestRunID(t *testing.T) {
	tests := []struct {
		name   string
		result map[string]interface{}
		want   string
	}{
		{
			name:   "top level run_id",
			result: map[string]interface{}{"run_id": "run-abc"},
			want:   "run-abc",
		},
		{
			name:   "nested under data envelope",
			result: map[string]interface{}{"data": map[string]interface{}{"run_id": "run-def"}},
			want:   "run-def",
		},
		{
			name:   "top level takes precedence over nested",
			result: map[string]interface{}{"run_id": "run-top", "data": map[string]interface{}{"run_id": "run-nested"}},
			want:   "run-top",
		},
		{
			name:   "missing run_id returns empty",
			result: map[string]interface{}{"other": "value"},
			want:   "",
		},
		{
			name:   "blank run_id returns empty",
			result: map[string]interface{}{"run_id": "  "},
			want:   "",
		},
		{
			name:   "nil result returns empty",
			result: nil,
			want:   "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := extractBacktestRunID(tt.result); got != tt.want {
				t.Fatalf("extractBacktestRunID() = %q, want %q", got, tt.want)
			}
		})
	}
}
