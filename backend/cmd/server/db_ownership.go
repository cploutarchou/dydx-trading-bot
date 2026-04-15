package main

import (
	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/startup"
)

type databaseOwnershipDiagnostics = startup.DatabaseOwnershipDiagnostics

func buildDatabaseOwnershipDiagnostics(cfg *config.Config) databaseOwnershipDiagnostics {
	return startup.BuildDatabaseOwnershipDiagnostics(cfg)
}

func validateDatabaseOwnership(cfg *config.Config) error {
	return startup.ValidateDatabaseOwnership(cfg)
}
