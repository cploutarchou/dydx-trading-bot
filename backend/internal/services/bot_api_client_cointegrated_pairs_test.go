package services

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGetBotCointegratedPairs_PathAndEnvelope(t *testing.T) {
	var gotPath, gotAuth string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.EscapedPath()
		gotAuth = r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"strategy-1-2","analyzed_at":"2026-09-20T10:00:00+00:00","count":1,` +
			`"pairs":[{"base_market":"BTC-USD","quote_market":"ETH-USD","hedge_ratio":0.05,"half_life":12.5,"zero_crossings":40,"p_value":0.01,` +
			`"z_score_mean":0.02,"z_score_std":1.1,"confidence_score":0.8,"analysis_timestamp":"2026-09-20T10:00:00+00:00"}]}}`))
	}))
	defer srv.Close()

	client := NewBotAPIClient(srv.URL, "service-token")
	payload, err := client.GetBotCointegratedPairs("strategy-1-2/x")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if gotPath != "/api/v1/bots/strategy-1-2%2Fx/cointegrated-pairs" {
		t.Fatalf("unexpected path: %s", gotPath)
	}
	if gotAuth != "Bearer service-token" {
		t.Fatalf("expected the bearer token, got %q", gotAuth)
	}
	data, _ := payload["data"].(map[string]interface{})
	pairs, _ := data["pairs"].([]interface{})
	if len(pairs) != 1 || data["count"] != float64(1) {
		t.Fatalf("expected the envelope passed through, got %+v", payload)
	}
}

func TestGetBotCointegratedPairs_OldBotAnswers404(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"detail":"Not Found"}`))
	}))
	defer srv.Close()

	client := NewBotAPIClient(srv.URL, "")
	_, err := client.GetBotCointegratedPairs("strategy-1-2")
	var apiErr *BotAPIError
	if !errors.As(err, &apiErr) || apiErr.StatusCode != http.StatusNotFound {
		t.Fatalf("expected a 404 BotAPIError for an old bot, got %v", err)
	}
}
