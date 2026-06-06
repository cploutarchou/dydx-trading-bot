package startup

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const (
	defaultBootstrapAdminUsername = "admin"
	defaultBootstrapAdminEmail    = "admin@executionlab.io"
	defaultBootstrapAdminPassword = "admin123"
	defaultBootstrapAdminName     = "System Administrator"
)

func EnsureBootstrapAdmin(conn *sql.DB) error {
	if conn == nil {
		return fmt.Errorf("bootstrap admin requires a database connection")
	}

	username := strings.TrimSpace(os.Getenv("BOOTSTRAP_ADMIN_USERNAME"))
	if username == "" {
		username = defaultBootstrapAdminUsername
	}

	email := strings.TrimSpace(os.Getenv("BOOTSTRAP_ADMIN_EMAIL"))
	if email == "" {
		email = defaultBootstrapAdminEmail
	}

	password := strings.TrimSpace(os.Getenv("BOOTSTRAP_ADMIN_PASSWORD"))
	if password == "" {
		password = defaultBootstrapAdminPassword
	}

	userRepo := repository.NewUserRepository(conn)
	existing, err := userRepo.GetByUsername(username)
	if err != nil && !strings.Contains(strings.ToLower(err.Error()), "user not found") {
		return fmt.Errorf("load bootstrap admin %q: %w", username, err)
	}

	if existing != nil {
		existing.Username = username
		existing.Email = email
		existing.Role = "admin"
		existing.FullName = defaultBootstrapAdminName
		existing.IsActive = true
		existing.IsAdmin = true
		existing.PasswordChangeRequired = false
		if err := existing.SetPassword(password); err != nil {
			return fmt.Errorf("hash bootstrap admin password: %w", err)
		}
		if err := userRepo.Update(existing); err != nil {
			return fmt.Errorf("update bootstrap admin %q: %w", username, err)
		}
		resetBootstrapAdminLockState(conn, existing.ID)
		log.Printf("Bootstrap admin user ensured: username=%s action=updated", username)
		return nil
	}

	user := &models.User{
		Username:               username,
		Email:                  email,
		Role:                   "admin",
		FullName:               defaultBootstrapAdminName,
		IsActive:               true,
		IsAdmin:                true,
		PasswordChangeRequired: false,
	}
	if err := user.SetPassword(password); err != nil {
		return fmt.Errorf("hash bootstrap admin password: %w", err)
	}
	if err := userRepo.Create(user); err != nil {
		return fmt.Errorf("create bootstrap admin %q: %w", username, err)
	}
	resetBootstrapAdminLockState(conn, user.ID)
	log.Printf("Bootstrap admin user ensured: username=%s action=created", username)
	return nil
}

func resetBootstrapAdminLockState(conn *sql.DB, userID int) {
	if conn == nil || userID <= 0 {
		return
	}
	if _, err := conn.Exec(
		`UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?`,
		userID,
	); err != nil {
		log.Printf("Bootstrap admin lock reset skipped for user_id=%d: %v", userID, err)
	}
}
