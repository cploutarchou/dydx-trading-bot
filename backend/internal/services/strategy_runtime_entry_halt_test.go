package services

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// entryHaltRuntimeService wires a StrategyRuntimeService to a fake bot API. Only
// the bot delegation is exercised, so no database is attached.
func entryHaltRuntimeService(t *testing.T, handler http.HandlerFunc) *StrategyRuntimeService {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)
	botService := NewBotInstanceService(nil, NewBotAPIClient(server.URL, "service-token"))
	return NewStrategyRuntimeService(nil, nil, nil, botService, nil)
}

func TestGetRuntimeEntryHaltAsksTheBotForTheStrategysRuntime(t *testing.T) {
	var requestedPath string
	service := entryHaltRuntimeService(t, func(w http.ResponseWriter, r *http.Request) {
		requestedPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"halted":true,"unverified":false,"halt":{"id":3,"network":"testnet","subaccount_number":0,"reason":"emergency close failed"}}}`))
	})

	state, err := service.GetRuntimeEntryHalt(&models.BacktestStrategy{ID: 2, UserID: 85})
	if err != nil {
		t.Fatalf("GetRuntimeEntryHalt: %v", err)
	}
	if requestedPath != "/api/v1/bots/strategy-85-2/entry-halt" {
		t.Fatalf("asked the bot for %q", requestedPath)
	}
	if state["halted"] != true {
		t.Fatalf("halted = %v, want true", state["halted"])
	}
	halt, _ := state["halt"].(map[string]interface{})
	if halt["reason"] != "emergency close failed" {
		t.Fatalf("halt = %v", state["halt"])
	}
}

func TestGetRuntimeEntryHaltForARuntimeTheBotDoesNotKnow(t *testing.T) {
	service := entryHaltRuntimeService(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"success":false,"message":"Bot instance 'strategy-85-2' not found"}`))
	})

	state, err := service.GetRuntimeEntryHalt(&models.BacktestStrategy{ID: 2, UserID: 85})
	if err != nil {
		t.Fatalf("GetRuntimeEntryHalt: %v", err)
	}
	if state["halted"] != false || state["unverified"] != false || state["halt"] != nil {
		t.Fatalf("state = %v", state)
	}
}

// An unreachable or failing bot is not "no halt": the caller gets an error and
// shows nothing rather than an all-clear.
func TestGetRuntimeEntryHaltDoesNotTurnABotFailureIntoAnAllClear(t *testing.T) {
	service := entryHaltRuntimeService(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"success":false,"message":"Internal server error"}`))
	})

	state, err := service.GetRuntimeEntryHalt(&models.BacktestStrategy{ID: 2, UserID: 85})
	if err == nil {
		t.Fatalf("expected an error, got state %v", state)
	}
}

func TestClearRuntimeEntryHaltSendsTheAcknowledgementAndTheOperator(t *testing.T) {
	var (
		requestedPath string
		payload       map[string]interface{}
	)
	service := entryHaltRuntimeService(t, func(w http.ResponseWriter, r *http.Request) {
		defer func() { _ = r.Body.Close() }()
		requestedPath = r.Method + " " + r.URL.Path
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Errorf("decode clear payload: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"Entry halt cleared","data":{"halted":false,"cleared":1}}`))
	})

	result, err := service.ClearRuntimeEntryHalt(&models.BacktestStrategy{ID: 2, UserID: 85}, "chris", "no AVAX position on chain")
	if err != nil {
		t.Fatalf("ClearRuntimeEntryHalt: %v", err)
	}
	if requestedPath != "POST /api/v1/bots/strategy-85-2/entry-halt/clear" {
		t.Fatalf("request = %q", requestedPath)
	}
	if payload["acknowledged"] != true || payload["cleared_by"] != "chris" || payload["note"] != "no AVAX position on chain" {
		t.Fatalf("payload = %v", payload)
	}
	if result["cleared"] != float64(1) || result["halted"] != false {
		t.Fatalf("result = %v", result)
	}
}

func TestClearRuntimeEntryHaltForARuntimeTheBotDoesNotKnow(t *testing.T) {
	service := entryHaltRuntimeService(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"success":false,"message":"Bot instance 'strategy-85-2' not found"}`))
	})

	_, err := service.ClearRuntimeEntryHalt(&models.BacktestStrategy{ID: 2, UserID: 85}, "chris", "")
	if !errors.Is(err, ErrStrategyRuntimeNotFound) {
		t.Fatalf("err = %v, want ErrStrategyRuntimeNotFound", err)
	}
}
