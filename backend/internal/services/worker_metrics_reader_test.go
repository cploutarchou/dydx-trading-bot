package services

import (
	"context"
	"errors"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestNewLiveWorkerMetricsReaderNilWhenDisabled(t *testing.T) {
	if reader := NewLiveWorkerMetricsReader(nil); reader != nil {
		t.Fatalf("expected nil LiveWorkerMetricsReader, got %+v", reader)
	}
}

func TestNewLiveWorkerMetricsReaderNilWhenReaderNil(t *testing.T) {
	// NewClickHouseReader returns nil when disabled
	clickHouseReader := NewClickHouseReader(config.ClickHouseSettings{Enabled: false})
	if clickHouseReader != nil {
		t.Fatal("expected nil ClickHouseReader when disabled")
	}
	
	workerReader := NewLiveWorkerMetricsReader(clickHouseReader)
	if workerReader != nil {
		t.Fatalf("expected nil LiveWorkerMetricsReader, got %+v", workerReader)
	}
}

func TestLiveWorkerMetricsReaderGetMetricsNilReaderFailsClosed(t *testing.T) {
	var reader *LiveWorkerMetricsReader
	metrics, err := reader.GetMetrics(context.Background(), "", "", "", 24, 100)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if metrics != nil {
		t.Fatalf("expected nil metrics, got %+v", metrics)
	}
}

func TestLiveWorkerMetricsReaderGetThroughputSummaryNilReaderFailsClosed(t *testing.T) {
	var reader *LiveWorkerMetricsReader
	throughput, err := reader.GetThroughputSummary(context.Background(), "", "", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if throughput != nil {
		t.Fatalf("expected nil throughput, got %+v", throughput)
	}
}

func TestLiveWorkerMetricsReaderGetFailureSummaryNilReaderFailsClosed(t *testing.T) {
	var reader *LiveWorkerMetricsReader
	failures, err := reader.GetFailureSummary(context.Background(), "", "", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if failures != nil {
		t.Fatalf("expected nil failures, got %+v", failures)
	}
}

func TestLiveWorkerMetricsReaderGetHeartbeatStatusNilReaderFailsClosed(t *testing.T) {
	var reader *LiveWorkerMetricsReader
	heartbeats, err := reader.GetHeartbeatStatus(context.Background(), "")
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if heartbeats != nil {
		t.Fatalf("expected nil heartbeats, got %+v", heartbeats)
	}
}

func TestLiveWorkerMetricsReaderGetWorkerSummaryNilReaderFailsClosed(t *testing.T) {
	var reader *LiveWorkerMetricsReader
	summary, err := reader.GetWorkerSummary(context.Background(), "", "", "", 24)
	if !errors.Is(err, ErrClickHouseDisabled) {
		t.Fatalf("expected ErrClickHouseDisabled, got %v", err)
	}
	if summary != nil {
		t.Fatalf("expected nil summary, got %+v", summary)
	}
}

func TestLiveWorkerMetricsReaderWithEnabledReader(t *testing.T) {
	// Create a reader with enabled ClickHouse
	clickHouseReader := NewClickHouseReader(config.ClickHouseSettings{
		Enabled: true,
		URL:     "http://localhost:8123",
	})
	
	if clickHouseReader == nil {
		t.Fatal("expected non-nil ClickHouseReader")
	}
	
	reader := NewLiveWorkerMetricsReader(clickHouseReader)
	if reader == nil {
		t.Fatal("expected non-nil LiveWorkerMetricsReader")
	}
	
	// Test that the reader methods don't panic (they'll return errors due to no server)
	// This is just to ensure the structure is correct
	
	// Test GetMetrics
	_, err := reader.GetMetrics(context.Background(), "", "", "", 24, 100)
	if err == nil {
		t.Log("GetMetrics succeeded (unexpected with no server)")
	} else {
		t.Logf("GetMetrics returned error (expected): %v", err)
	}
	
	// Test GetThroughputSummary
	_, err = reader.GetThroughputSummary(context.Background(), "", "", 24)
	if err == nil {
		t.Log("GetThroughputSummary succeeded (unexpected with no server)")
	} else {
		t.Logf("GetThroughputSummary returned error (expected): %v", err)
	}
	
	// Test GetFailureSummary
	_, err = reader.GetFailureSummary(context.Background(), "", "", 24)
	if err == nil {
		t.Log("GetFailureSummary succeeded (unexpected with no server)")
	} else {
		t.Logf("GetFailureSummary returned error (expected): %v", err)
	}
	
	// Test GetHeartbeatStatus
	_, err = reader.GetHeartbeatStatus(context.Background(), "")
	if err == nil {
		t.Log("GetHeartbeatStatus succeeded (unexpected with no server)")
	} else {
		t.Logf("GetHeartbeatStatus returned error (expected): %v", err)
	}
	
	// Test GetWorkerSummary
	_, err = reader.GetWorkerSummary(context.Background(), "", "", "", 24)
	if err == nil {
		t.Log("GetWorkerSummary succeeded (unexpected with no server)")
	} else {
		t.Logf("GetWorkerSummary returned error (expected): %v", err)
	}
}

func TestWorkerMetricStruct(t *testing.T) {
	// Test that WorkerMetric struct can be properly instantiated
	metric := WorkerMetric{
		MetricTime:  "2026-01-01 00:00:00",
		WorkerID:    "worker-1",
		WorkerType:  "celery",
		QueueName:   "backtests",
		MetricName:  "tasks_completed",
		MetricValue: 100.0,
	}
	
	if metric.WorkerID != "worker-1" {
		t.Fatalf("expected WorkerID 'worker-1', got '%s'", metric.WorkerID)
	}
	if metric.WorkerType != "celery" {
		t.Fatalf("expected WorkerType 'celery', got '%s'", metric.WorkerType)
	}
	if metric.QueueName != "backtests" {
		t.Fatalf("expected QueueName 'backtests', got '%s'", metric.QueueName)
	}
	if metric.MetricName != "tasks_completed" {
		t.Fatalf("expected MetricName 'tasks_completed', got '%s'", metric.MetricName)
	}
	if metric.MetricValue != 100.0 {
		t.Fatalf("expected MetricValue 100.0, got %f", metric.MetricValue)
	}
}

func TestWorkerThroughputSummaryStruct(t *testing.T) {
	// Test that WorkerThroughputSummary struct can be properly instantiated
	throughput := WorkerThroughputSummary{
		WorkerID:      "worker-1",
		WorkerType:    "celery",
		QueueName:     "backtests",
		TasksCompleted: 100,
		TasksSucceeded: 95,
		TasksFailed:    5,
		AvgDurationMs:  150.5,
		TotalRetries:   3,
	}
	
	if throughput.WorkerID != "worker-1" {
		t.Fatalf("expected WorkerID 'worker-1', got '%s'", throughput.WorkerID)
	}
	if throughput.TasksCompleted != 100 {
		t.Fatalf("expected TasksCompleted 100, got %d", throughput.TasksCompleted)
	}
	if throughput.AvgDurationMs != 150.5 {
		t.Fatalf("expected AvgDurationMs 150.5, got %f", throughput.AvgDurationMs)
	}
}

func TestWorkerMetricsSummaryStruct(t *testing.T) {
	// Test that WorkerMetricsSummary struct can be properly instantiated
	summary := WorkerMetricsSummary{
		WorkerID:     "worker-1",
		WorkerType:   "celery",
		QueueName:    "backtests",
		Hours:        24,
		TotalMetrics: 1000,
	}
	
	if summary.WorkerID != "worker-1" {
		t.Fatalf("expected WorkerID 'worker-1', got '%s'", summary.WorkerID)
	}
	if summary.Hours != 24 {
		t.Fatalf("expected Hours 24, got %d", summary.Hours)
	}
	if summary.TotalMetrics != 1000 {
		t.Fatalf("expected TotalMetrics 1000, got %d", summary.TotalMetrics)
	}
}