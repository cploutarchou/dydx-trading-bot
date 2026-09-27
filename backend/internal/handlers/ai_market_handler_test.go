package handlers

import (
	"testing"
	"time"
)

// The market-selection provider client allows 75 s per attempt; the handler
// deadline must leave room for one quick failure and a retry.
func TestAIMarketSelectDeadlineIsNinetySeconds(t *testing.T) {
	if aiMarketSelectDeadline != 90*time.Second {
		t.Fatalf("expected a 90 s market selection deadline, got %s", aiMarketSelectDeadline)
	}
}
