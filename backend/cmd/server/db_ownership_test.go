package main

import (
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestValidateDatabaseOwnershipBlocksDedicatedSharedTarget_MySQL(t *testing.T) {
	t.Setenv("BOT_DB_CUTOVER_MODE", "dedicated")
	t.Setenv("BOT_DATABASE_URL", "mysql://bot_user:secret@shared-host:3306/shared_db")
	t.Setenv("DATABASE_URL", "mysql://backend_user:secret@shared-host:3306/shared_db")

	cfg := &config.Config{}
	cfg.Database.Host = "shared-host"
	cfg.Database.Port = 3306
	cfg.Database.Dbname = "shared_db"

	if err := validateDatabaseOwnership(cfg); err == nil {
		t.Fatal("expected dedicated ownership validation failure for shared backend/bot target (MySQL)")
	}
}

func TestValidateDatabaseOwnershipAllowsDedicatedSeparatedTarget_MySQL(t *testing.T) {
	t.Setenv("BOT_DB_CUTOVER_MODE", "dedicated")
	t.Setenv("BOT_DATABASE_URL", "mysql://bot_user:secret@bot-host:3307/bot_db")
	t.Setenv("DATABASE_URL", "mysql://backend_user:secret@backend-host:3306/backend_db")

	cfg := &config.Config{}
	cfg.Database.Host = "backend-host"
	cfg.Database.Port = 3306
	cfg.Database.Dbname = "backend_db"

	if err := validateDatabaseOwnership(cfg); err != nil {
		t.Fatalf("expected dedicated separated target to pass validation (MySQL): %v", err)
	}

	diagnostics := buildDatabaseOwnershipDiagnostics(cfg)
	if diagnostics.BlockingViolation {
		t.Fatalf("expected no blocking violation in diagnostics (MySQL): %+v", diagnostics)
	}
	if !diagnostics.Separated {
		t.Fatalf("expected separated=true in diagnostics (MySQL): %+v", diagnostics)
	}
}
