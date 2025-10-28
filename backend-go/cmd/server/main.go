package main

import (
	"fmt"
	"log"
	"os"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	_ "github.com/mattn/go-sqlite3"
)

func main() {
	// Load environment variables
	_ = godotenv.Load()

	// Get configuration from environment
	dbDriver := os.Getenv("DB_DRIVER")
	if dbDriver == "" {
		dbDriver = "sqlite"
	}

	dbDSN := os.Getenv("DB_DSN")
	if dbDSN == "" {
		if dbDriver == "sqlite" {
			dbDSN = "trading_bot.db"
		} else {
			dbDSN = "postgres://user:password@localhost/trading_bot"
		}
	}

	jwtSecret := os.Getenv("JWT_SECRET")
	if jwtSecret == "" {
		jwtSecret = "your-super-secret-key-change-in-production"
	}

	// Initialize database with automatic migrations
	database, err := db.New(db.Config{
		Driver:       dbDriver,
		DSN:          dbDSN,
		AutoMigrate:  true, // Automatically run pending migrations on startup
		MaxOpenConns: 25,
		MaxIdleConns: 5,
	})
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	// Create Gin router
	router := gin.Default()

	// Add middleware
	router.Use(middleware.CORSMiddleware())
	router.Use(middleware.LoggingMiddleware())

	// Health check
	router.GET("/health", func(c *gin.Context) {
		if err := database.Health(); err != nil {
			c.JSON(503, gin.H{"status": "unhealthy", "error": err})
			return
		}
		c.JSON(200, gin.H{"status": "healthy"})
	})

	// API v1 group
	//v1 := router.Group("/api/v1")
	{
		// Auth routes (will be implemented)
		// v1.POST("/auth/login", authHandlers.Login)
		// v1.POST("/auth/register", authHandlers.Register)
		// v1.POST("/auth/refresh", authHandlers.Refresh)

		// Protected routes (require JWT)
		// protected := v1.Group("")
		// protected.Use(middleware.AuthMiddleware(jwtSecret))
		// {
		//     // Backtest routes
		//     // protected.GET("/backtests", backtestHandlers.List)
		//     // etc
		// }
	}

	// Start server
	port := os.Getenv("API_PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 Backend server starting on port %s", port)
	if err := router.Run(fmt.Sprintf(":%s", port)); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
