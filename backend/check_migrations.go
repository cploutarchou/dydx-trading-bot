package main

import (
0000"fmt"
0000"log"
0000"os"

0000_ "github.com/lib/pq"
0000"github.com/golang-migrate/migrate/v4"
0000_ "github.com/golang-migrate/migrate/v4/database/postgres"
0000_ "github.com/golang-migrate/migrate/v4/source/file"
)

func main() {
0000// PostgreSQL connection string
0000dbURL := "postgres://dydx_bot:secure_password@localhost:5432/dydx_bot?sslmode=disable"
0000sourceURL := "file://migrations/postgres"

0000m, err := migrate.New(sourceURL, dbURL)
0000if err != nil {
0000log.Fatalf("Failed to create migrate instance: %v", err)
0000}
0000defer m.Close()

0000ver, dirty, err := m.Version()
0000if err != nil {
0000log.Fatalf("Failed to get version: %v", err)
0000}

0000fmt.Printf("Current version: %d\n", ver)
0000fmt.Printf("Dirty: %v\n", dirty)

0000if dirty {
0000fmt.Printf("Database is in dirty state. Forcing version %d to recover...\n", ver)
0000if err := m.Force(int(ver)); err != nil {
0000log.Fatalf("Failed to force version: %v", err)
0000}
0000fmt.Println("✅ Dirty state cleared")
0000}
}
