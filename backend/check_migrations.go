package main

import (
	"fmt"
	"log"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
	_ "github.com/lib/pq"
)

func main() {
	// PostgresSQL connection string
	dbURL := "postgres://dydx_bot:secure_password@localhost:5432/dydx_bot?sslmode=disable"
	sourceURL := "file://migrations/postgres"

	m, err := migrate.New(sourceURL, dbURL)
	if err != nil {
		log.Fatalf("Failed to create migrate instance: %v", err)
	}
	defer m.Close()

	ver, dirty, err := m.Version()
	if err != nil {
		log.Fatalf("Failed to get version: %v", err)
	}

	fmt.Printf("Current version: %d\n", ver)
	fmt.Printf("Dirty: %v\n", dirty)

	if dirty {
		fmt.Printf("Database is in dirty state. Forcing version %d to recover...\n", ver)
		if err := m.Force(int(ver)); err != nil {
			log.Fatalf("Failed to force version: %v", err)
		}
		fmt.Println("✅ Dirty state cleared")
	}
}
