package startup

import (
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestValidateSecurityBaseline_AllowsNonProductionWithoutStrictSettings(t *testing.T) {
	t.Setenv("APP_ENV", "development")
	t.Setenv("CORS_ALLOWED_ORIGINS", "")

	cfg := &config.Config{}
	cfg.Auth.JWTSecretKey = "your-super-secret-key-change-in-production"

	if err := ValidateSecurityBaseline(cfg); err != nil {
		t.Fatalf("expected non-production baseline to allow startup, got error: %v", err)
	}
}

func TestValidateSecurityBaseline_BlocksProductionPlaceholderJWT(t *testing.T) {
	t.Setenv("APP_ENV", "production")
	t.Setenv("CORS_ALLOWED_ORIGINS", "https://app.executionlab.io")

	cfg := &config.Config{}
	cfg.Auth.JWTSecretKey = "your-super-secret-key-change-in-production"

	if err := ValidateSecurityBaseline(cfg); err == nil {
		t.Fatal("expected production baseline failure for placeholder JWT secret")
	}
}

func TestValidateSecurityBaseline_BlocksProductionMissingCORSAllowlist(t *testing.T) {
	t.Setenv("APP_ENV", "production")
	t.Setenv("CORS_ALLOWED_ORIGINS", "")
	t.Setenv("FRONTEND_URL", "")

	cfg := &config.Config{}
	cfg.Auth.JWTSecretKey = "super-long-real-secret-value"

	if err := ValidateSecurityBaseline(cfg); err == nil {
		t.Fatal("expected production baseline failure for missing CORS allowlist")
	}
}

func TestValidateSecurityBaseline_AllowsProductionWithStrictSettings(t *testing.T) {
	t.Setenv("APP_ENV", "production")
	t.Setenv("CORS_ALLOWED_ORIGINS", "https://app.executionlab.io,https://ops.executionlab.io")

	cfg := &config.Config{}
	cfg.Auth.JWTSecretKey = "super-long-real-secret-value"

	if err := ValidateSecurityBaseline(cfg); err != nil {
		t.Fatalf("expected production baseline success, got error: %v", err)
	}
}
