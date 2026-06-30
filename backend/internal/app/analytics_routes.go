package app

import (
	"context"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

const (
	analyticsQueryTimeout = 5 * time.Second
	defaultHistoryHours   = 24
)

// registerAnalyticsRoutes exposes the backend-owned ClickHouse read models.
// All routes are admin-gated and fail closed: when ClickHouse is disabled the
// response reports enabled=false with empty data so dashboards can degrade
// gracefully instead of erroring, and a query failure surfaces an error without
// returning stale or partial rows.
func registerAnalyticsRoutes(
	router *gin.Engine,
	positionReader *services.LivePositionReader,
	tradeSummaryReader *services.LiveTradeSummaryReader,
	pairBreakdownReader *services.LivePairBreakdownReader,
	workerMetricsReader *services.LiveWorkerMetricsReader,
	apiRequestWriter *services.APIRequestWriter,
) {
	group := router.Group("/api/v1/analytics")
	group.Use(middleware.RequireAuth())

	group.GET("/position-history", func(c *gin.Context) {
		serveLivePositionHistory(c, positionReader)
	})
	group.GET("/trade-summary", func(c *gin.Context) {
		serveLiveTradeSummary(c, tradeSummaryReader)
	})
	group.GET("/pair-breakdown", func(c *gin.Context) {
		serveLivePairBreakdown(c, pairBreakdownReader)
	})

	// Worker metrics routes
	group.GET("/worker-metrics", func(c *gin.Context) {
		serveWorkerMetrics(c, workerMetricsReader)
	})
	group.GET("/worker-metrics/summary", func(c *gin.Context) {
		serveWorkerMetricsSummary(c, workerMetricsReader)
	})
	group.GET("/worker-metrics/throughput", func(c *gin.Context) {
		serveWorkerThroughput(c, workerMetricsReader)
	})
	group.GET("/worker-metrics/failures", func(c *gin.Context) {
		serveWorkerFailures(c, workerMetricsReader)
	})
	group.GET("/worker-metrics/heartbeat", func(c *gin.Context) {
		serveWorkerHeartbeat(c, workerMetricsReader)
	})

	// API request metrics routes
	group.GET("/api-requests/summary", func(c *gin.Context) {
		serveAPIRequestSummary(c, apiRequestWriter)
	})
	group.GET("/api-requests/latency", func(c *gin.Context) {
		serveAPIRequestLatency(c, apiRequestWriter)
	})
	group.GET("/api-requests/errors", func(c *gin.Context) {
		serveAPIRequestErrors(c, apiRequestWriter)
	})
	group.GET("/api-requests/slow", func(c *gin.Context) {
		serveAPIRequestSlow(c, apiRequestWriter)
	})
}

// serveLivePositionHistory is the testable core of the position-history route.
// It is kept separate from registration so it can be exercised with a synthetic
// gin.Context without standing up the full auth middleware.
func serveLivePositionHistory(c *gin.Context, positionReader *services.LivePositionReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	instanceID := strings.TrimSpace(c.Query("instance_id"))
	positionID := strings.TrimSpace(c.Query("position_id"))
	hours := parseHistoryHours(c.Query("hours"))

	if instanceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"success":  false,
			"message":  "instance_id query parameter is required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	// Fail closed when ClickHouse reads are not configured: return a stable,
	// enabled=false envelope with empty data so dashboards degrade gracefully.
	if positionReader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"enabled": false,
			"source":  "disabled",
			"data": gin.H{
				"snapshots": []interface{}{},
				"count":     0,
			},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	snapshots, err := positionReader.GetHistory(ctx, instanceID, positionID, hours)
	if err != nil {
		// Query failed: do not return partial data. Report enabled=true with the
		// failure reason so operators can see ClickHouse is configured but unhealthy.
		c.JSON(http.StatusOK, gin.H{
			"success": false,
			"enabled": true,
			"source":  "clickhouse",
			"message": "ClickHouse position history query failed",
			"error":   err.Error(),
			"data": gin.H{
				"snapshots": []interface{}{},
				"count":     0,
			},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"instance_id": instanceID,
			"position_id": positionID,
			"hours":       hours,
			"snapshots":   snapshots,
			"count":       len(snapshots),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

func parseHistoryHours(raw string) int {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return defaultHistoryHours
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil || parsed <= 0 {
		return defaultHistoryHours
	}
	return parsed
}

// serveLiveTradeSummary is the testable core of the trade-summary route. It
// mirrors serveLivePositionHistory: admin-gated, requires instance_id, fails
// closed with an enabled=false envelope when ClickHouse is off, and surfaces a
// success=false envelope on query failure instead of partial aggregates.
func serveLiveTradeSummary(c *gin.Context, tradeSummaryReader *services.LiveTradeSummaryReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	instanceID := strings.TrimSpace(c.Query("instance_id"))
	hours := parseHistoryHours(c.Query("hours"))

	if instanceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"success":  false,
			"message":  "instance_id query parameter is required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	// Fail closed when ClickHouse reads are not configured: return a stable,
	// enabled=false envelope with empty data so dashboards degrade gracefully.
	if tradeSummaryReader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     emptyTradeSummaryEnvelope(instanceID, hours),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	summary, err := tradeSummaryReader.GetSummary(ctx, instanceID, hours)
	if err != nil {
		// Query failed: do not return partial aggregates. Report enabled=true with
		// the failure reason so operators can see ClickHouse is configured but unhealthy.
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse trade summary query failed",
			"error":    err.Error(),
			"data":     emptyTradeSummaryEnvelope(instanceID, hours),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success":  true,
		"enabled":  true,
		"source":   "clickhouse",
		"data":     summary,
		"trace_id": middleware.GetTraceID(c),
	})
}

// emptyTradeSummaryEnvelope is the stable degraded payload shared by the disabled
// and query-failure paths so consumers always see the same shape.
func emptyTradeSummaryEnvelope(instanceID string, hours int) gin.H {
	return gin.H{
		"instance_id":      instanceID,
		"hours":            hours,
		"totals":           services.LiveTradeTotals{},
		"daily":            []interface{}{},
		"orders_by_status": []interface{}{},
	}
}

// serveLivePairBreakdown is the testable core of the pair-breakdown route. It
// mirrors the other analytics handlers: admin-gated, requires instance_id, fails
// closed with an enabled=false envelope when ClickHouse is off, and surfaces a
// success=false envelope on query failure instead of partial rows.
func serveLivePairBreakdown(c *gin.Context, pairBreakdownReader *services.LivePairBreakdownReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	instanceID := strings.TrimSpace(c.Query("instance_id"))
	hours := parseHistoryHours(c.Query("hours"))

	if instanceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"success":  false,
			"message":  "instance_id query parameter is required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	// Fail closed when ClickHouse reads are not configured: return a stable,
	// enabled=false envelope with empty data so dashboards degrade gracefully.
	if pairBreakdownReader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     emptyPairBreakdownEnvelope(instanceID, hours),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	breakdown, err := pairBreakdownReader.GetBreakdown(ctx, instanceID, hours)
	if err != nil {
		// Query failed: do not return partial rows. Report enabled=true with the
		// failure reason so operators can see ClickHouse is configured but unhealthy.
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse pair breakdown query failed",
			"error":    err.Error(),
			"data":     emptyPairBreakdownEnvelope(instanceID, hours),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success":  true,
		"enabled":  true,
		"source":   "clickhouse",
		"data":     breakdown,
		"trace_id": middleware.GetTraceID(c),
	})
}

// emptyPairBreakdownEnvelope is the stable degraded payload shared by the disabled
// and query-failure paths so consumers always see the same shape.
func emptyPairBreakdownEnvelope(instanceID string, hours int) gin.H {
	return gin.H{
		"instance_id": instanceID,
		"hours":       hours,
		"pairs":       []interface{}{},
	}
}

// Worker metrics handlers

// serveWorkerMetrics handles requests for raw worker metrics.
func serveWorkerMetrics(c *gin.Context, reader *services.LiveWorkerMetricsReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	// Parse query parameters
	workerID := strings.TrimSpace(c.Query("worker_id"))
	workerType := strings.TrimSpace(c.Query("worker_type"))
	queueName := strings.TrimSpace(c.Query("queue_name"))
	hours := parseHistoryHours(c.Query("hours"))
	limitStr := strings.TrimSpace(c.Query("limit"))
	limit := 1000
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	// Fail closed when ClickHouse reads are not configured
	if reader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"enabled": false,
			"source":  "disabled",
			"data": gin.H{
				"metrics": []interface{}{},
				"count":   0,
			},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	metrics, err := reader.GetMetrics(ctx, workerID, workerType, queueName, hours, limit)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success": false,
			"enabled": true,
			"source":  "clickhouse",
			"message": "ClickHouse worker metrics query failed",
			"error":   err.Error(),
			"data": gin.H{
				"metrics": []interface{}{},
				"count":   0,
			},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"worker_id":   workerID,
			"worker_type": workerType,
			"queue_name":  queueName,
			"hours":       hours,
			"metrics":     metrics,
			"count":       len(metrics),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// serveWorkerMetricsSummary handles requests for comprehensive worker metrics summary.
func serveWorkerMetricsSummary(c *gin.Context, reader *services.LiveWorkerMetricsReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	workerID := strings.TrimSpace(c.Query("worker_id"))
	workerType := strings.TrimSpace(c.Query("worker_type"))
	queueName := strings.TrimSpace(c.Query("queue_name"))
	hours := parseHistoryHours(c.Query("hours"))

	// Fail closed when ClickHouse reads are not configured
	if reader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     emptyWorkerMetricsSummaryEnvelope(),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	summary, err := reader.GetWorkerSummary(ctx, workerID, workerType, queueName, hours)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse worker metrics summary query failed",
			"error":    err.Error(),
			"data":     emptyWorkerMetricsSummaryEnvelope(),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success":  true,
		"enabled":  true,
		"source":   "clickhouse",
		"data":     summary,
		"trace_id": middleware.GetTraceID(c),
	})
}

// serveWorkerThroughput handles requests for worker throughput metrics.
func serveWorkerThroughput(c *gin.Context, reader *services.LiveWorkerMetricsReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	workerType := strings.TrimSpace(c.Query("worker_type"))
	queueName := strings.TrimSpace(c.Query("queue_name"))
	hours := parseHistoryHours(c.Query("hours"))

	// Fail closed when ClickHouse reads are not configured
	if reader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	throughput, err := reader.GetThroughputSummary(ctx, workerType, queueName, hours)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse worker throughput query failed",
			"error":    err.Error(),
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"worker_type": workerType,
			"queue_name":  queueName,
			"hours":       hours,
			"throughput":  throughput,
			"count":       len(throughput),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// serveWorkerFailures handles requests for worker failure metrics.
func serveWorkerFailures(c *gin.Context, reader *services.LiveWorkerMetricsReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	workerType := strings.TrimSpace(c.Query("worker_type"))
	queueName := strings.TrimSpace(c.Query("queue_name"))
	hours := parseHistoryHours(c.Query("hours"))

	// Fail closed when ClickHouse reads are not configured
	if reader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	failures, err := reader.GetFailureSummary(ctx, workerType, queueName, hours)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse worker failures query failed",
			"error":    err.Error(),
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"worker_type": workerType,
			"queue_name":  queueName,
			"hours":       hours,
			"failures":    failures,
			"count":       len(failures),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// serveWorkerHeartbeat handles requests for worker heartbeat status.
func serveWorkerHeartbeat(c *gin.Context, reader *services.LiveWorkerMetricsReader) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	workerType := strings.TrimSpace(c.Query("worker_type"))

	// Fail closed when ClickHouse reads are not configured
	if reader == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	heartbeats, err := reader.GetHeartbeatStatus(ctx, workerType)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse worker heartbeat query failed",
			"error":    err.Error(),
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"worker_type": workerType,
			"heartbeats":  heartbeats,
			"count":       len(heartbeats),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// API request handlers

// serveAPIRequestSummary handles requests for API request summary metrics.
func serveAPIRequestSummary(c *gin.Context, writer *services.APIRequestWriter) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	service := strings.TrimSpace(c.Query("service"))
	if service == "" {
		service = "backend"
	}
	hours := parseHistoryHours(c.Query("hours"))

	// Fail closed when ClickHouse reads are not configured
	if writer == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     emptyAPIRequestSummaryEnvelope(service, hours),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	summary, err := writer.GetSummary(ctx, service, hours)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse API request summary query failed",
			"error":    err.Error(),
			"data":     emptyAPIRequestSummaryEnvelope(service, hours),
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"service": service,
			"hours":   hours,
			"summary": summary,
			"count":   len(summary),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// serveAPIRequestLatency handles requests for API request latency distribution.
func serveAPIRequestLatency(c *gin.Context, writer *services.APIRequestWriter) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	service := strings.TrimSpace(c.Query("service"))
	if service == "" {
		service = "backend"
	}
	hours := parseHistoryHours(c.Query("hours"))

	// Fail closed when ClickHouse reads are not configured
	if writer == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	latency, err := writer.GetLatencyDistribution(ctx, service, hours)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse API request latency query failed",
			"error":    err.Error(),
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"service": service,
			"hours":   hours,
			"latency": latency,
			"count":   len(latency),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// serveAPIRequestErrors handles requests for API request error rate metrics.
func serveAPIRequestErrors(c *gin.Context, writer *services.APIRequestWriter) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	service := strings.TrimSpace(c.Query("service"))
	if service == "" {
		service = "backend"
	}
	hours := parseHistoryHours(c.Query("hours"))

	// Fail closed when ClickHouse reads are not configured
	if writer == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	errorRates, err := writer.GetErrorRate(ctx, service, hours)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse API request error rate query failed",
			"error":    err.Error(),
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"service":     service,
			"hours":       hours,
			"error_rates": errorRates,
			"count":       len(errorRates),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// serveAPIRequestSlow handles requests for slow API requests.
func serveAPIRequestSlow(c *gin.Context, writer *services.APIRequestWriter) {
	if !c.GetBool("is_admin") {
		c.JSON(http.StatusForbidden, gin.H{
			"success":  false,
			"message":  "Admin access required",
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	service := strings.TrimSpace(c.Query("service"))
	if service == "" {
		service = "backend"
	}

	thresholdMs := 1000 // Default 1 second
	if thresholdStr := strings.TrimSpace(c.Query("threshold_ms")); thresholdStr != "" {
		if threshold, err := strconv.Atoi(thresholdStr); err == nil && threshold > 0 {
			thresholdMs = threshold
		}
	}

	limit := 50
	if limitStr := strings.TrimSpace(c.Query("limit")); limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	// Fail closed when ClickHouse reads are not configured
	if writer == nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  true,
			"enabled":  false,
			"source":   "disabled",
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), analyticsQueryTimeout)
	defer cancel()

	slowRequests, err := writer.GetHighLatencyRequests(ctx, service, thresholdMs, limit)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"success":  false,
			"enabled":  true,
			"source":   "clickhouse",
			"message":  "ClickHouse slow requests query failed",
			"error":    err.Error(),
			"data":     []interface{}{},
			"trace_id": middleware.GetTraceID(c),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"enabled": true,
		"source":  "clickhouse",
		"data": gin.H{
			"service":       service,
			"threshold_ms":  thresholdMs,
			"limit":         limit,
			"slow_requests": slowRequests,
			"count":         len(slowRequests),
		},
		"trace_id": middleware.GetTraceID(c),
	})
}

// Helper functions for empty envelopes

func emptyWorkerMetricsSummaryEnvelope() gin.H {
	return gin.H{
		"worker_id":     "",
		"worker_type":   "",
		"queue_name":    "",
		"hours":         defaultHistoryHours,
		"throughput":    services.WorkerThroughputSummary{},
		"failures":      services.WorkerFailureSummary{},
		"heartbeat":     nil,
		"total_metrics": 0,
	}
}

func emptyAPIRequestSummaryEnvelope(service string, hours int) gin.H {
	return gin.H{
		"service": service,
		"hours":   hours,
		"summary": []interface{}{},
		"count":   0,
	}
}
