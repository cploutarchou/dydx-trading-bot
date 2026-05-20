package startup

import (
	"database/sql"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

func setupBootstrapAdminTestDB(t *testing.T) *sql.DB {
	t.Helper()

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT NOT NULL UNIQUE,
		email TEXT NOT NULL UNIQUE,
		role TEXT NOT NULL DEFAULT 'client',
		full_name TEXT,
		avatar TEXT,
		hashed_password TEXT NOT NULL,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		password_change_required BOOLEAN NOT NULL DEFAULT 0,
		failed_login_attempts INTEGER NOT NULL DEFAULT 0,
		locked_until DATETIME,
		last_login DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create users table: %v", err)
	}

	return dbConn
}

func TestEnsureBootstrapAdminCreatesDefaultAdmin(t *testing.T) {
	dbConn := setupBootstrapAdminTestDB(t)
	t.Cleanup(func() {
		_ = dbConn.Close()
	})

	t.Setenv("BOOTSTRAP_ADMIN_USERNAME", "")
	t.Setenv("BOOTSTRAP_ADMIN_EMAIL", "")
	t.Setenv("BOOTSTRAP_ADMIN_PASSWORD", "")

	if err := EnsureBootstrapAdmin(dbConn); err != nil {
		t.Fatalf("EnsureBootstrapAdmin: %v", err)
	}

	user, err := repository.NewUserRepository(dbConn).GetByUsername("admin")
	if err != nil {
		t.Fatalf("GetByUsername(admin): %v", err)
	}
	if user == nil {
		t.Fatal("expected bootstrap admin user")
	}
	if !user.IsAdmin || user.Role != "admin" || !user.IsActive {
		t.Fatalf("unexpected bootstrap admin flags: role=%s is_admin=%v is_active=%v", user.Role, user.IsAdmin, user.IsActive)
	}
	if !user.CheckPassword("admin123") {
		t.Fatal("expected bootstrap admin password to be admin123")
	}
}

func TestEnsureBootstrapAdminResetsExistingAdminPassword(t *testing.T) {
	dbConn := setupBootstrapAdminTestDB(t)
	t.Cleanup(func() {
		_ = dbConn.Close()
	})

	repo := repository.NewUserRepository(dbConn)
	existing := &models.User{
		Username:               "admin",
		Email:                  "admin@example.local",
		Role:                   "admin",
		FullName:               "Existing Admin",
		IsActive:               false,
		IsAdmin:                false,
		PasswordChangeRequired: true,
	}
	if err := existing.SetPassword("oldpass"); err != nil {
		t.Fatalf("SetPassword(oldpass): %v", err)
	}
	if err := repo.Create(existing); err != nil {
		t.Fatalf("Create(existing): %v", err)
	}
	if _, err := dbConn.Exec(`UPDATE users SET failed_login_attempts = 4 WHERE username = ?`, "admin"); err != nil {
		t.Fatalf("seed failed_login_attempts: %v", err)
	}

	if err := EnsureBootstrapAdmin(dbConn); err != nil {
		t.Fatalf("EnsureBootstrapAdmin: %v", err)
	}

	updated, err := repo.GetByUsername("admin")
	if err != nil {
		t.Fatalf("GetByUsername(admin): %v", err)
	}
	if updated == nil {
		t.Fatal("expected updated admin user")
	}
	if !updated.CheckPassword("admin123") {
		t.Fatal("expected existing admin password to be reset to admin123")
	}
	if updated.PasswordChangeRequired {
		t.Fatal("expected password_change_required=false for bootstrap admin")
	}
	if !updated.IsAdmin || updated.Role != "admin" || !updated.IsActive {
		t.Fatalf("unexpected updated admin flags: role=%s is_admin=%v is_active=%v", updated.Role, updated.IsAdmin, updated.IsActive)
	}
	var failedAttempts int
	if err := dbConn.QueryRow(`SELECT failed_login_attempts FROM users WHERE username = ?`, "admin").Scan(&failedAttempts); err != nil {
		t.Fatalf("query failed_login_attempts: %v", err)
	}
	if failedAttempts != 0 {
		t.Fatalf("failed_login_attempts=%d, want 0", failedAttempts)
	}
}
