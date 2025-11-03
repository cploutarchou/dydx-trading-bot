package routes

import (
	"strconv"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// RegisterBotAPIDelegateRoutes registers all delegated bot API endpoints
// These routes proxy to the Python bot API (localhost:8000) and sync with the Go database
func RegisterBotAPIDelegateRoutes(router *gin.Engine, apiClient *services.BotAPIClient) {
	// Backtest proxy endpoints
	backtestGroup := router.Group("/api/v1/backtests")
	backtestGroup.Use(middleware.RequireAuth())
	{
		// Create backtest
		backtestGroup.POST("", func(c *gin.Context) {
			var config map[string]interface{}
			if err := c.BindJSON(&config); err != nil {
				c.JSON(400, gin.H{"error": "Invalid request body"})
				return
			}
			result, err := apiClient.CreateBacktest(config)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// List backtests with filters
		backtestGroup.GET("", func(c *gin.Context) {
			limit := 50
			offset := 0
			var status, days *string

			if l := c.Query("limit"); l != "" {
				var i int
				if _, err := parseIntQuery(l, &i); err == nil && i > 0 {
					limit = i
				}
			}
			if o := c.Query("offset"); o != "" {
				var i int
				if _, err := parseIntQuery(o, &i); err == nil && i >= 0 {
					offset = i
				}
			}
			if s := c.Query("status"); s != "" {
				status = &s
			}
			if d := c.Query("days"); d != "" {
				days = &d
			}

			result, err := apiClient.ListBacktestsWithFilters(limit, offset, status, parseIntPtr(days))
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get backtest summary stats
		backtestGroup.GET("/stats/summary", func(c *gin.Context) {
			days := 30
			if d := c.Query("days"); d != "" {
				if v, err := parseIntQuery(d, &days); err == nil {
					days = v
				}
			}
			result, err := apiClient.GetBacktestSummaryStats(days)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Compare backtests
		backtestGroup.POST("/compare", func(c *gin.Context) {
			var config map[string]interface{}
			if err := c.BindJSON(&config); err != nil {
				c.JSON(400, gin.H{"error": "Invalid request body"})
				return
			}
			result, err := apiClient.CompareBacktests(config)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get backtest by ID
		backtestGroup.GET("/:run_id", func(c *gin.Context) {
			runID := c.Param("run_id")
			result, err := apiClient.GetBacktestDetails(runID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Delete backtest
		backtestGroup.DELETE("/:run_id", func(c *gin.Context) {
			runID := c.Param("run_id")
			result, err := apiClient.DeleteBacktest(runID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get backtest status
		backtestGroup.GET("/:run_id/status", func(c *gin.Context) {
			runID := c.Param("run_id")
			result, err := apiClient.GetBacktestStatus(runID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get backtest trades
		backtestGroup.GET("/:run_id/trades", func(c *gin.Context) {
			runID := c.Param("run_id")
			limit := 100
			offset := 0
			winningOnly := false

			if l := c.Query("limit"); l != "" {
				if v, err := parseIntQuery(l, &limit); err == nil {
					limit = v
				}
			}
			if o := c.Query("offset"); o != "" {
				if v, err := parseIntQuery(o, &offset); err == nil {
					offset = v
				}
			}
			if c.Query("winning_only") == "true" {
				winningOnly = true
			}

			result, err := apiClient.GetBacktestTradesWithFilters(runID, limit, offset, winningOnly)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Cancel backtest
		backtestGroup.POST("/:run_id/cancel", func(c *gin.Context) {
			runID := c.Param("run_id")
			result, err := apiClient.CancelBacktest(runID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get backtest analytics
		backtestGroup.GET("/:run_id/analytics", func(c *gin.Context) {
			runID := c.Param("run_id")
			result, err := apiClient.GetBacktestAnalytics(runID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get position snapshots
		backtestGroup.GET("/:run_id/position-snapshots", func(c *gin.Context) {
			runID := c.Param("run_id")
			limit := 100
			offset := 0
			var marketPair *string

			if l := c.Query("limit"); l != "" {
				if v, err := parseIntQuery(l, &limit); err == nil {
					limit = v
				}
			}
			if o := c.Query("offset"); o != "" {
				if v, err := parseIntQuery(o, &offset); err == nil {
					offset = v
				}
			}
			if m := c.Query("market_pair"); m != "" {
				marketPair = &m
			}

			result, err := apiClient.GetPositionSnapshots(runID, limit, offset, marketPair)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get dYdX validation
		backtestGroup.GET("/:run_id/dydx-validation", func(c *gin.Context) {
			runID := c.Param("run_id")
			result, err := apiClient.ValidateAgainstdYdXData(runID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get performance metrics
		backtestGroup.GET("/:run_id/performance-metrics", func(c *gin.Context) {
			runID := c.Param("run_id")
			benchmark := c.DefaultQuery("benchmark", "BTC-USD")
			result, err := apiClient.GetAdvancedPerformanceMetrics(runID, benchmark)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get live progress
		backtestGroup.GET("/:run_id/live-progress", func(c *gin.Context) {
			runID := c.Param("run_id")
			result, err := apiClient.GetLiveProgress(runID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})
	}

	// Bot real-time data endpoints
	botGroup := router.Group("/api/v1/bots")
	botGroup.Use(middleware.RequireAuth())
	{
		// Get current positions
		botGroup.GET("/:instance_id/positions/current", func(c *gin.Context) {
			botID := c.Param("instance_id")
			result, err := apiClient.GetCurrentPositions(botID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get specific position
		botGroup.GET("/:instance_id/positions/:position_id", func(c *gin.Context) {
			botID := c.Param("instance_id")
			positionID := c.Param("position_id")
			result, err := apiClient.GetPosition(botID, positionID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get position history
		botGroup.GET("/:instance_id/position-history/:position_id", func(c *gin.Context) {
			botID := c.Param("instance_id")
			positionID := c.Param("position_id")
			hours := 24
			if h := c.Query("hours"); h != "" {
				if v, err := parseIntQuery(h, &hours); err == nil {
					hours = v
				}
			}
			result, err := apiClient.GetPositionHistory(botID, positionID, hours)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get market data
		botGroup.GET("/:instance_id/market-data", func(c *gin.Context) {
			botID := c.Param("instance_id")
			result, err := apiClient.GetMarketData(botID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get realtime stats
		botGroup.GET("/:instance_id/realtime-stats", func(c *gin.Context) {
			botID := c.Param("instance_id")
			result, err := apiClient.GetRealtimeStats(botID)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get alerts
		botGroup.GET("/:instance_id/alerts", func(c *gin.Context) {
			botID := c.Param("instance_id")
			limit := 50
			if l := c.Query("limit"); l != "" {
				if v, err := parseIntQuery(l, &limit); err == nil {
					limit = v
				}
			}
			result, err := apiClient.GetAlerts(botID, limit)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get bot history
		botGroup.GET("/:instance_id/history", func(c *gin.Context) {
			instanceID := c.Param("instance_id")
			days := 7
			if d := c.Query("days"); d != "" {
				if v, err := parseIntQuery(d, &days); err == nil {
					days = v
				}
			}
			result, err := apiClient.GetBotHistory(instanceID, days)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Get bot jobs
		botGroup.GET("/:instance_id/jobs", func(c *gin.Context) {
			instanceID := c.Param("instance_id")
			days := 7
			if d := c.Query("days"); d != "" {
				if v, err := parseIntQuery(d, &days); err == nil {
					days = v
				}
			}
			result, err := apiClient.GetBotJobs(instanceID, days)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})

		// Quick deploy bot
		botGroup.POST("/quick-deploy", func(c *gin.Context) {
			instanceName := c.Query("instance_name")
			autoStart := c.DefaultQuery("auto_start", "true") == "true"

			var config map[string]interface{}
			if err := c.BindJSON(&config); err != nil {
				c.JSON(400, gin.H{"error": "Invalid request body"})
				return
			}

			result, err := apiClient.QuickDeployBot(instanceName, autoStart, config)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(200, result)
		})
	}

	// System status endpoint
	router.GET("/api/v1/system/status", middleware.RequireAuth(), func(c *gin.Context) {
		result, err := apiClient.SystemStatus()
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		c.JSON(200, result)
	})
}

// Helper functions
func parseIntQuery(s string, target *int) (int, error) {
	i, err := strconv.Atoi(s)
	if err == nil {
		*target = i
	}
	return i, err
}

func parseIntPtr(s *string) *int {
	if s == nil {
		return nil
	}
	if i, err := strconv.Atoi(*s); err == nil {
		return &i
	}
	return nil
}
