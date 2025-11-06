package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/dydx-trading-bot/backend-go/config"
)

func main() {
	config.LoadConfig()
	cfg := config.ConfigInstance
	migPath := cfg.Database.MigrationsPath()

	fmt.Printf("Database Type: %s\n", cfg.Database.Type)
	fmt.Printf("Migrations Path: %s\n", migPath)

	// Check if path is absolute
	if filepath.IsAbs(migPath) {
		fmt.Printf("Is Absolute: Yes\n")
	} else {
		fmt.Printf("Is Absolute: No\n")
		abs, _ := filepath.Abs(migPath)
		fmt.Printf("Would resolve to: %s\n", abs)
	}

	// Check if files exist
	files, _ := os.ReadDir(migPath)
	fmt.Printf("Number of files in migrations dir: %d\n", len(files))
}
