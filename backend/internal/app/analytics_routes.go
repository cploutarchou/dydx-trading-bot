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
func registerAnalyticsRoutes(router *gin.Engine, positionReader *services.LivePositionReader, tradeSummaryReader *services.LiveTradeSummaryReader, pairBreakdownReader *services.LivePairBreakdownReader) {
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
