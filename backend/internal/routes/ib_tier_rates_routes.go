package routes

import (
	"database/sql"
	"net/http"
	"strconv"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/gin-gonic/gin"
)

type upsertIBTierRateRequest struct {
	CommissionRatePct float64 `json:"commission_rate_pct" binding:"required,min=0,max=100"`
	RebateRatePct     float64 `json:"rebate_rate_pct"     binding:"min=0,max=100"`
	Description       string  `json:"description"`
	IsActive          *bool   `json:"is_active"`
}

func RegisterIBTierRatesRoutes(router *gin.Engine, database *sql.DB) {
	grp := router.Group("/api/v1/admin/ib/tier-rates")
	grp.Use(middleware.RequireAuth())
	grp.Use(middleware.RequireMFA(database))
	grp.Use(middleware.RequirePermission(database, "crm.admin.manage"))
	{
		grp.GET("", listIBTierRatesHandler(database))
		grp.PUT("/:tier", upsertIBTierRateHandler(database))
		grp.DELETE("/:tier", deleteIBTierRateHandler(database))
	}
}

func listIBTierRatesHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		repo := repository.NewIBTierCommissionRateRepository(database)
		rates, err := repo.List()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to list tier commission rates",
			})
			return
		}
		if rates == nil {
			rates = []*models.IBTierCommissionRate{}
		}
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"data": gin.H{
				"rates": rates,
				"total": len(rates),
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func upsertIBTierRateHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		tierLevel, err := strconv.Atoi(c.Param("tier"))
		if err != nil || tierLevel < 1 || tierLevel > 50 {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "tier must be a positive integer between 1 and 50",
			})
			return
		}

		var req upsertIBTierRateRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "Invalid request: " + err.Error(),
			})
			return
		}

		isActive := true
		if req.IsActive != nil {
			isActive = *req.IsActive
		}

		actorID := c.GetInt("user_id")
		rate := &models.IBTierCommissionRate{
			TierLevel:         tierLevel,
			CommissionRatePct: req.CommissionRatePct,
			RebateRatePct:     req.RebateRatePct,
			Description:       req.Description,
			IsActive:          isActive,
			CreatedByUserID:   &actorID,
		}

		repo := repository.NewIBTierCommissionRateRepository(database)
		if err := repo.Upsert(rate); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to save tier commission rate: " + err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Tier commission rate saved",
			"data":      gin.H{"rate": rate},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}

func deleteIBTierRateHandler(database *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		tierLevel, err := strconv.Atoi(c.Param("tier"))
		if err != nil || tierLevel < 1 {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"message": "tier must be a positive integer",
			})
			return
		}

		repo := repository.NewIBTierCommissionRateRepository(database)
		if err := repo.DeleteByTier(tierLevel); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": "Failed to delete tier commission rate: " + err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success":   true,
			"message":   "Tier commission rate deleted",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		})
	}
}
