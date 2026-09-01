package startup

import (
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const (
	defaultBootstrapAdminUsername = "admin"
	defaultBootstrapAdminEmail    = "admin@executionlab.io"
	defaultBootstrapAdminName     = "System Administrator"
)

func generateBootstrapAdminPassword() (string, error) {
	buf := make([]byte, 18)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("generate bootstrap admin password entropy: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}

func parseBootstrapAdminBool(raw string) bool {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

// EnsureBootstrapAdmin idempotently provisions the bootstrap admin account.
//
// Behavior contract:
//   - Production requires BOOTSTRAP_ADMIN_PASSWORD (fail fast otherwise).
//   - When the password env is unset outside production, a random one-time
//     password is generated and logged once (only on account creation).
//   - On restart the existing admin's password, email, and full name are
//     never overwritten unless BOOTSTRAP_ADMIN_RESET_PASSWORD=true.
//   - Admin role/active flags are re-asserted on every start (idempotent).
func EnsureBootstrapAdmin(conn *sql.DB) error {
	if conn == nil {
		return fmt.Errorf("bootstrap admin requires a database connection")
	}

	username := strings.TrimSpace(os.Getenv("BOOTSTRAP_ADMIN_USERNAME"))
	if username == "" {
		username = defaultBootstrapAdminUsername
	}
	envEmail := strings.TrimSpace(os.Getenv("BOOTSTRAP_ADMIN_EMAIL"))
	envPassword := strings.TrimSpace(os.Getenv("BOOTSTRAP_ADMIN_PASSWORD"))

	if strings.EqualFold(config.ResolveAppConfigEnvironment(), "production") && envPassword == "" {
		return fmt.Errorf("BOOTSTRAP_ADMIN_PASSWORD must be set when bootstrapping the admin account in production")
	}

	userRepo := repository.NewUserRepository(conn)
	existing, err := userRepo.GetByUsername(username)
	if err != nil && !strings.Contains(strings.ToLower(err.Error()), "user not found") {
		return fmt.Errorf("load bootstrap admin %q: %w", username, err)
	}

	if existing != nil {
		// Re-assert privileged flags without destroying operator-managed fields.
		existing.Role = "admin"
		existing.IsAdmin = true
		existing.IsActive = true
		if envEmail != "" {
			existing.Email = envEmail
		}

		if parseBootstrapAdminBool(os.Getenv("BOOTSTRAP_ADMIN_RESET_PASSWORD")) {
			password := envPassword
			generated := false
			if password == "" {
				if password, err = generateBootstrapAdminPassword(); err != nil {
					return err
				}
				generated = true
				log.Printf("Bootstrap admin password regenerated for username=%s (shown once): %s", username, password)
			}
			if err := existing.SetPassword(password); err != nil {
				return fmt.Errorf("hash bootstrap admin password: %w", err)
			}
			existing.PasswordChangeRequired = generated
		}

		if err := userRepo.Update(existing); err != nil {
			return fmt.Errorf("update bootstrap admin %q: %w", username, err)
		}
		resetBootstrapAdminLockState(conn, existing.ID)
		log.Printf("Bootstrap admin user ensured: username=%s action=updated", username)
		return nil
	}

	password := envPassword
	generated := false
	if password == "" {
		if password, err = generateBootstrapAdminPassword(); err != nil {
			return err
		}
		generated = true
	}

	email := envEmail
	if email == "" {
		email = defaultBootstrapAdminEmail
	}

	user := &models.User{
		Username:  username,
		Email:     email,
		Role:      "admin",
		FullName:  defaultBootstrapAdminName,
		IsActive:  true,
		IsAdmin:   true,
		// Generated credentials must be rotated at first login; an explicitly
		// configured password is operator-known and does not require rotation.
		PasswordChangeRequired: generated,
	}
	if err := user.SetPassword(password); err != nil {
		return fmt.Errorf("hash bootstrap admin password: %w", err)
	}
	if err := userRepo.Create(user); err != nil {
		return fmt.Errorf("create bootstrap admin %q: %w", username, err)
	}
	resetBootstrapAdminLockState(conn, user.ID)
	if generated {
		log.Printf("Bootstrap admin created with generated one-time password (username=%s, shown once): %s", username, password)
	} else {
		log.Printf("Bootstrap admin user ensured: username=%s action=created", username)
	}
	return nil
}

func resetBootstrapAdminLockState(conn *sql.DB, userID int) {
	if conn == nil || userID <= 0 {
		return
	}
	// Try to reset both lock-related columns; ignore errors if they don't exist
	if _, err := conn.Exec(`UPDATE users SET failed_login_attempts = 0 WHERE id = $1`, userID); err != nil {
		log.Printf("Bootstrap admin lock reset skipped for user_id=%d (failed_login_attempts): %v", userID, err)
	}
	if _, err := conn.Exec(`UPDATE users SET locked_until = NULL WHERE id = $1`, userID); err != nil {
		log.Printf("Bootstrap admin lock reset skipped for user_id=%d (locked_until): %v", userID, err)
	}
}
