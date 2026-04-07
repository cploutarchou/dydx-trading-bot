package routes

import (
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

// RegisterStrategyRoutes registers strategy API routes
func RegisterStrategyRoutes(router *gin.Engine, database *db.Database) {
	strategyRepo := repository.NewStrategyRepository(database.DB)
	keyRepo := repository.NewKeyRepository(database.DB)
	botInstanceRepo := repository.NewBotInstanceRepository(database.DB)
	settingsRepo := repository.NewSettingsRepository(database.DB)
	credentialRepo := repository.NewExternalAPICredentialRepository(database.DB)
	strategyService := services.NewStrategyService(strategyRepo)
	keyService := services.NewKeyManagementService(keyRepo)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	telegramService := services.NewTelegramService(credentialService, settingsRepo)

	botAPIURL := os.Getenv("BOT_API_URL")
	if botAPIURL == "" {
		botAPIURL = "http://127.0.0.1:8889"
	}
	botAPIClient := services.NewBotAPIClient(botAPIURL, os.Getenv("BOT_API_TOKEN"))
	botInstanceService := services.NewBotInstanceService(botInstanceRepo, botAPIClient)
	runtimeService := services.NewStrategyRuntimeService(strategyService, keyService, telegramService, botInstanceService, botInstanceRepo)
	strategyHandler := handlers.NewStrategyHandler(strategyService, runtimeService)

	v1 := router.Group("/api/v1")
	{
		strategies := v1.Group("/strategies")
		{
			// Require authentication for all strategy routes
			strategies.Use(middleware.RequireAuth())

			// CRUD operations
			strategies.POST("", strategyHandler.CreateStrategy)
			strategies.GET("", strategyHandler.ListStrategies)
			strategies.GET("/:id", strategyHandler.GetStrategy)
			strategies.PUT("/:id", strategyHandler.UpdateStrategy)
			strategies.DELETE("/:id", strategyHandler.DeleteStrategy)
			strategies.GET("/:id/versions", strategyHandler.GetVersionHistory)
			strategies.POST("/:id/versions/:version_id/revert", strategyHandler.RevertVersion)
			strategies.GET("/:id/runtime", strategyHandler.GetStrategyRuntime)
			strategies.POST("/:id/start", strategyHandler.StartStrategyRuntime)
			strategies.POST("/:id/stop", strategyHandler.StopStrategyRuntime)
		}

		backtests := v1.Group("/backtests")
		{
			backtests.Use(middleware.RequireAuth())

			backtests.POST("/:run_id/create-strategy", func(c *gin.Context) {
				var req struct {
					Name        string                 `json:"name" binding:"required"`
					Description string                 `json:"description"`
					Config      map[string]interface{} `json:"config"`
				}
				if err := c.ShouldBindJSON(&req); err != nil {
					c.JSON(http.StatusBadRequest, handlers.APIResponse{
						Success:   false,
						Timestamp: time.Now().UTC().Format(time.RFC3339),
						Error:     "Invalid request payload",
					})
					return
				}

				userIDValue, exists := c.Get("user_id")
				if !exists {
					c.JSON(http.StatusUnauthorized, handlers.APIResponse{
						Success:   false,
						Timestamp: time.Now().UTC().Format(time.RFC3339),
						Error:     "Unauthorized",
					})
					return
				}
				userID, ok := userIDValue.(int)
				if !ok || userID <= 0 {
					c.JSON(http.StatusUnauthorized, handlers.APIResponse{
						Success:   false,
						Timestamp: time.Now().UTC().Format(time.RFC3339),
						Error:     "Unauthorized",
					})
					return
				}

				runID := strings.TrimSpace(c.Param("run_id"))
				if runID == "" {
					c.JSON(http.StatusBadRequest, handlers.APIResponse{
						Success:   false,
						Timestamp: time.Now().UTC().Format(time.RFC3339),
						Error:     "run_id is required",
					})
					return
				}

				requestClient := botAPIClient.WithTraceID(middleware.GetTraceID(c))
				if !services.UseConfiguredBotAPIServiceToken() {
					if token := extractBotAuthToken(c); token != "" {
						requestClient = requestClient.WithToken(token)
					}
				}

				details, err := requestClient.GetBacktestDetails(runID)
				if err != nil {
					respondBotAPIError(c, err)
					return
				}

				detailData := unwrapEnvelopePayload(normalizeBacktestDetailsPayload(details))
				config := req.Config
				if len(config) == 0 {
					config = asMap(detailData["strategy_snapshot"])
				}
				if len(config) == 0 {
					if requestPayload := asMap(detailData["request"]); requestPayload != nil {
						config = map[string]interface{}{}
						if params := asMap(requestPayload["trading_parameters"]); params != nil {
							for key, value := range params {
								config[key] = value
							}
						}
						if value, ok := requestPayload["pair_selection_mode"]; ok {
							config["pair_selection_mode"] = value
						}
						if value, ok := requestPayload["initial_balance"]; ok {
							config["starting_balance"] = value
							if _, exists := config["initial_amount"]; !exists {
								config["initial_amount"] = value
							}
						}
					}
				}

				strategy, err := strategyService.CreateStrategy(userID, req.Name, req.Description, "backtest", false, false)
				if err != nil {
					c.JSON(http.StatusInternalServerError, handlers.APIResponse{
						Success:   false,
						Timestamp: time.Now().UTC().Format(time.RFC3339),
						Error:     err.Error(),
					})
					return
				}

				if len(config) > 0 {
					strategy.FromDict(config)
				}
				strategy.Name = req.Name
				strategy.Description = req.Description
				if strings.TrimSpace(strategy.RuntimeStrategy) == "" {
					strategy.RuntimeStrategy = "cointegration"
				}
				if strings.TrimSpace(strategy.PairSelectionMode) == "" {
					strategy.PairSelectionMode = "liquidity"
				}

				if err := strategyService.UpdateStrategy(strategy); err != nil {
					_ = strategyService.DeleteStrategy(strategy.ID)
					c.JSON(http.StatusInternalServerError, handlers.APIResponse{
						Success:   false,
						Timestamp: time.Now().UTC().Format(time.RFC3339),
						Error:     err.Error(),
					})
					return
				}

				data := strategy.ToDict()
				data["source_backtest_run_id"] = runID

				c.JSON(http.StatusCreated, handlers.APIResponse{
					Success:   true,
					Data:      data,
					Timestamp: time.Now().UTC().Format(time.RFC3339),
				})
			})
		}
	}
}
