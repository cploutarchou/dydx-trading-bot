package services

import (
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

func intPtr(v int) *int { return &v }

func TestMergeRemoteRuntimeStateKeepsBotErrorWithRecordedPositions(t *testing.T) {
	stored := StrategyRuntimeState{
		InstanceID: "strategy-1-101",
		Status:     "running",
		BotStatus:  "running",
	}
	remote := map[string]interface{}{
		"instance_id":    "strategy-1-101",
		"status":         "error",
		"last_error":     "Runtime process for strategy-1-101 is no longer running",
		"open_positions": float64(16),
	}

	merged := mergeRemoteRuntimeState(stored, remote)

	if merged.Status != "error" || merged.BotStatus != "error" {
		t.Fatalf("recorded positions must not promote an errored runtime, got status=%q bot_status=%q", merged.Status, merged.BotStatus)
	}
	if merged.LastError == "" {
		t.Fatalf("the bot's error must be kept")
	}
	if merged.OpenPositions == nil || *merged.OpenPositions != 16 {
		t.Fatalf("recorded positions must still be reported, got %v", merged.OpenPositions)
	}
	if !merged.RuntimeConfirmed || merged.LastConfirmedAt == nil {
		t.Fatalf("a bot answer must mark the state confirmed")
	}
	if isBotStatusRunning(remote) {
		t.Fatalf("the remote payload must not be rewritten to running")
	}

	strategy := &models.BacktestStrategy{ID: 101, Name: "Runtime Strategy"}
	response := buildStrategyRuntimeResponse(strategy, &models.StrategyExecutionState{}, merged, false)
	if response["is_running"] != false {
		t.Fatalf("expected is_running=false, got %v", response["is_running"])
	}
	if response["exposure_unconfirmed"] != true {
		t.Fatalf("recorded positions on a non-running runtime must be flagged, got %v", response["exposure_unconfirmed"])
	}
	if response["runtime_confirmed"] != true {
		t.Fatalf("expected runtime_confirmed=true, got %v", response["runtime_confirmed"])
	}
}

func TestRuntimeResponseDoesNotFlagExposureWhileRunning(t *testing.T) {
	state := StrategyRuntimeState{Status: "running", BotStatus: "running", OpenPositions: intPtr(2), RuntimeConfirmed: true}
	response := buildStrategyRuntimeResponse(&models.BacktestStrategy{ID: 7}, &models.StrategyExecutionState{}, state, true)
	if response["exposure_unconfirmed"] != false {
		t.Fatalf("a running runtime's positions are live, got exposure_unconfirmed=%v", response["exposure_unconfirmed"])
	}
}

func TestShouldPersistRuntimeState(t *testing.T) {
	now := time.Date(2026, 9, 26, 15, 0, 0, 0, time.UTC)
	recent := now.Add(-time.Minute)
	old := now.Add(-runtimeConfirmationRefreshInterval)
	base := StrategyRuntimeState{
		InstanceID:      "strategy-1-101",
		Status:          "error",
		BotStatus:       "error",
		LastError:       "no longer running",
		OpenPositions:   intPtr(16),
		LastSyncedAt:    &recent,
		LastConfirmedAt: &recent,
	}

	tests := []struct {
		name          string
		mutate        func(next *StrategyRuntimeState)
		storedRunning bool
		nextRunning   bool
		want          bool
	}{
		{name: "identical poll writes nothing", mutate: func(*StrategyRuntimeState) {}, want: false},
		{name: "only volatile fields moved", mutate: func(n *StrategyRuntimeState) {
			later := now
			n.LastSyncedAt = &later
			n.LastConfirmedAt = &later
			n.UptimeSeconds = intPtr(5)
			n.RuntimeUpdatedAt = &later
		}, want: false},
		{name: "status changed", mutate: func(n *StrategyRuntimeState) { n.Status = "running"; n.BotStatus = "running" }, want: true},
		{name: "open positions changed", mutate: func(n *StrategyRuntimeState) { n.OpenPositions = intPtr(0) }, want: true},
		{name: "started_at set", mutate: func(n *StrategyRuntimeState) { n.StartedAt = &now }, want: true},
		{name: "running flag flipped", mutate: func(*StrategyRuntimeState) {}, storedRunning: false, nextRunning: true, want: true},
		{name: "confirmation refresh after the interval", mutate: func(n *StrategyRuntimeState) { n.LastConfirmedAt = &now }, want: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			next := base
			tt.mutate(&next)
			if got := shouldPersistRuntimeState(base, tt.storedRunning, next, tt.nextRunning, now); got != tt.want {
				t.Fatalf("expected %v, got %v", tt.want, got)
			}
		})
	}

	t.Run("stored confirmation older than the interval refreshes", func(t *testing.T) {
		stored := base
		stored.LastConfirmedAt = &old
		next := base
		next.LastConfirmedAt = &now
		if !shouldPersistRuntimeState(stored, false, next, false, now) {
			t.Fatalf("expected a refresh write after %s", runtimeConfirmationRefreshInterval)
		}
	})

	t.Run("stored confirmation missing is written once", func(t *testing.T) {
		stored := base
		stored.LastConfirmedAt = nil
		next := base
		if !shouldPersistRuntimeState(stored, false, next, false, now) {
			t.Fatalf("expected a write when the stored state has no confirmation time")
		}
	})
}

func TestIsActiveRuntimeStatus(t *testing.T) {
	for _, status := range []string{"running", "Starting", "degraded", "recovering", "safeguarded"} {
		if !isActiveRuntimeStatus(status) {
			t.Fatalf("%q must be active", status)
		}
	}
	for _, status := range []string{"", "stopped", "error", "missing", "unavailable", "paused"} {
		if isActiveRuntimeStatus(status) {
			t.Fatalf("%q must not be active", status)
		}
	}
}
