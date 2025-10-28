package main

import (
	"fmt"
	"github.com/dydx-trading-bot/backend-go/config"
	database2 "github.com/golang-migrate/migrate/v4/database"
	"log"
	"os"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/routes"
	"github.com/gin-gonic/gin"
	"github.com/golang-migrate/migrate/v4"
	"github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/database/sqlite3"
	_ "github.com/golang-migrate/migrate/v4/source/file"
	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
	_ "github.com/mattn/go-sqlite3"
)

func main() {
	// Load environment variables
	_ = godotenv.Load()

	config.LoadConfig()
	log.Printf("Loaded config: %+v", config.ConfigInstance)

	if config.ConfigInstance.Database.Type == "postgresql" {
		config.ConfigInstance.Database.Type = "postgres"
	}

	// Initialize database with automatic migrations
	database, err := db.New(db.Config{
		Driver:       config.ConfigInstance.Database.Type,
		DSN:          config.ConfigInstance.Database.DSN(),
		AutoMigrate:  true, // Automatically run pending migrations on startup
		MaxOpenConns: 25,
		MaxIdleConns: 5,
	})
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	if database == nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}

	if err = runMigrations(database, config.ConfigInstance.Database.Type); err != nil {
		log.Fatalf("Failed to run migrations: %v", err)
	}

	// Initialize auth middleware with config
	middleware.InitAuthMiddleware(config.ConfigInstance)

	// Create Gin router
	router := gin.Default()

	// Add middleware
	router.Use(middleware.ErrorHandlingMiddleware())
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

	// Register routes
	routes.RegisterBacktestRoutes(router, database)
	routes.RegisterKeyRoutes(router, database)

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

func runMigrations(database *db.Database, dbDriver string) error {
	var driverInstance database2.Driver
	var err error

	if dbDriver == "sqlite3" || dbDriver == "sqlite" {
		driverInstance, err = sqlite3.WithInstance(database.DB, &sqlite3.Config{})
		if err != nil {
			return fmt.Errorf("failed to create sqlite3 driver: %w", err)
		}
	} else if dbDriver == "postgres" {
		driverInstance, err = postgres.WithInstance(database.DB, &postgres.Config{})
		if err != nil {
			return fmt.Errorf("failed to create postgres driver: %w", err)
		}
	} else {
		return fmt.Errorf("unsupported driver: %s", dbDriver)
	}

	m, err := migrate.NewWithDatabaseInstance("file://migrations", dbDriver, driverInstance)
	if err != nil {
		return fmt.Errorf("failed to create migrate instance: %w", err)
	}
	defer m.Close()

	if err := m.Up(); err != nil && err != migrate.ErrNoChange {
		return fmt.Errorf("failed to run migrations: %w", err)
	}

	log.Println("Migrations completed successfully")
	return nil
}
