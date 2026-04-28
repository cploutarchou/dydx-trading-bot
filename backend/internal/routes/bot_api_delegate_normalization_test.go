package routes

import "testing"

func TestNormalizeBotJobsPayload_AcceptsDBBackedFieldsAndCanonicalStatuses(t *testing.T) {
	payload := map[string]interface{}{
		"success": true,
		"data": map[string]interface{}{
			"jobs": []interface{}{
				map[string]interface{}{
					"job_id":              "job-1",
					"status":              "running",
					"progress_pct":        float64(47),
					"updated_at":          "2026-04-26T10:11:12Z",
					"process_id":          float64(12345),
					"execution_time_ms":   float64(9001),
					"cancellation_reason": nil,
					"metadata":            map[string]interface{}{"source": "db"},
					"error_message":       nil,
					"started_at":          "2026-04-26T10:10:00Z",
					"completed_at":        nil,
					"created_at":          "2026-04-26T10:09:00Z",
				},
			},
		},
	}

	normalized := normalizeBotJobsPayload(payload)
	data := normalized["data"].(map[string]interface{})
	jobs := data["jobs"].([]interface{})
	job := jobs[0].(map[string]interface{})

	if job["status"] != "running" {
		t.Fatalf("expected canonical running status, got %v", job["status"])
	}
	for _, key := range []string{
		"progress_pct",
		"updated_at",
		"process_id",
		"execution_time_ms",
		"cancellation_reason",
		"metadata",
		"error_message",
		"started_at",
		"completed_at",
		"created_at",
	} {
		if _, ok := job[key]; !ok {
			t.Fatalf("expected DB-backed job field %q to be preserved in %+v", key, job)
		}
	}
	if job["progress_percent"] != float64(47) || job["progress"] != float64(47) {
		t.Fatalf("expected progress aliases from progress_pct, got %+v", job)
	}
}

func TestNormalizeBotJobsPayload_LegacyQueuedAndRetryStatusesMapSafely(t *testing.T) {
	payload := map[string]interface{}{
		"jobs": []interface{}{
			map[string]interface{}{"status": "queued"},
			map[string]interface{}{"status": "retry"},
			map[string]interface{}{"status": "retrying"},
			map[string]interface{}{"status": "FAILED"},
			map[string]interface{}{"status": "canceled"},
		},
	}

	normalized := normalizeBotJobsPayload(payload)
	jobs := normalized["jobs"].([]interface{})
	want := []string{"pending", "pending", "running", "failed", "cancelled"}
	for i, expected := range want {
		job := jobs[i].(map[string]interface{})
		if job["status"] != expected {
			t.Fatalf("job %d expected status %q, got %v", i, expected, job["status"])
		}
	}
}

func TestNormalizeBacktestStatusPayload_HTTPStatusRemainsAuthoritativeWithoutWebsocketEvents(t *testing.T) {
	payload := map[string]interface{}{
		"data": map[string]interface{}{
			"run_id": "gap-run",
			"status": "running",
		},
	}

	normalized := normalizeBacktestStatusPayload(payload)
	data := normalized["data"].(map[string]interface{})
	if data["status"] != "running" {
		t.Fatalf("expected HTTP status to remain running, got %v", data["status"])
	}
	if data["progress_pct"] != float64(0) || data["progress_percent"] != float64(0) || data["progress"] != float64(0) {
		t.Fatalf("expected missing websocket/progress fields to default to zero aliases, got %+v", data)
	}
	if _, ok := data["current_task"]; !ok {
		t.Fatalf("expected current_task key to be present when websocket event is absent")
	}
	if _, ok := data["current_pair"]; !ok {
		t.Fatalf("expected current_pair key to be present when websocket event is absent")
	}
}

func TestNormalizeBacktestStatusPayload_LegacyPendingWithProgressBecomesRunning(t *testing.T) {
	payload := map[string]interface{}{
		"data": map[string]interface{}{
			"run_id":       "legacy-run",
			"status":       "pending",
			"progress_pct": float64(12.3),
			"current_pair": "BTC-USD/ETH-USD",
		},
	}

	normalized := normalizeBacktestStatusPayload(payload)
	data := normalized["data"].(map[string]interface{})
	if data["status"] != "running" {
		t.Fatalf("expected progress-bearing pending run to normalize to running, got %v", data["status"])
	}
	if data["progress_pct"] != float64(12.3) {
		t.Fatalf("expected progress to be preserved, got %+v", data)
	}
}

func TestNormalizeBacktestListPayload_CanonicalizesLegacyStatuses(t *testing.T) {
	payload := map[string]interface{}{
		"data": map[string]interface{}{
			"backtests": []interface{}{
				map[string]interface{}{"run_id": "queued", "status": "queued"},
				map[string]interface{}{"run_id": "busy", "status": "created", "total_trades": float64(3)},
				map[string]interface{}{"run_id": "old-stalled", "status": "stalled"},
				map[string]interface{}{"run_id": "old-timeout", "status": "timed_out"},
			},
		},
	}

	normalized := normalizeBacktestListPayload(payload)
	items := normalized["data"].(map[string]interface{})["backtests"].([]interface{})
	want := []string{"pending", "running", "stale", "timeout"}
	for i, expected := range want {
		run := items[i].(map[string]interface{})
		if run["status"] != expected {
			t.Fatalf("run %d expected %q, got %v", i, expected, run["status"])
		}
	}
}
