package startup

import (
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/dydx-trading-bot/backend-go/config"
)

const defaultJWTPlaceholder = "your-super-secret-key-change-in-production"

func ValidateSecurityBaseline(cfg *config.Config) error {
	if cfg == nil {
		return fmt.Errorf("missing config")
	}
	// The baseline applies to production as before AND to any environment
	// label that is not explicitly development-ish: "staging"/"qa"/"uat"
	// previously slipped through and silently accepted placeholder
	// credentials and wildcard CORS.
	if !isProductionEnvironment() && isDevelopmentEnvironment() {
		return nil
	}

	if isPlaceholderSecret(cfg.Auth.JWTSecretKey) {
		return fmt.Errorf("production requires a non-placeholder JWT secret (JWT_SECRET_KEY/SECRET_KEY)")
	}

	origins := configuredCORSOrigins()
	if len(origins) == 0 {
		return fmt.Errorf("production requires explicit CORS_ALLOWED_ORIGINS or FRONTEND_URL")
	}

	for _, origin := range origins {
		if origin == "*" {
			return fmt.Errorf("production CORS origins must not include wildcard '*'")
		}
		if _, err := url.Parse(origin); err != nil {
			return fmt.Errorf("invalid CORS origin %q: %w", origin, err)
		}
	}

	return nil
}

func isDevelopmentEnvironment() bool {
	for _, key := range []string{"APP_ENV", "ENVIRONMENT"} {
		raw := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
		switch raw {
		case "", "dev", "development", "test", "testing", "local", "ci":
			return true
		}
	}
	return false
}

func isProductionEnvironment() bool {
	for _, key := range []string{"APP_ENV", "ENVIRONMENT", "GIN_MODE"} {
		raw := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
		switch raw {
		case "prod", "production", "release":
			return true
		}
	}
	return false
}

func isPlaceholderSecret(secret string) bool {
	normalized := strings.ToLower(strings.TrimSpace(secret))
	if normalized == "" {
		return true
	}
	for _, placeholder := range []string{
		defaultJWTPlaceholder,
		"changeme",
		"change-me",
		"change_me",
		"placeholder",
		"your-secret-key",
		"your-super-secret-key",
	} {
		if normalized == strings.ToLower(strings.TrimSpace(placeholder)) {
			return true
		}
	}
	return false
}

func configuredCORSOrigins() []string {
	origins := make([]string, 0)
	seen := make(map[string]struct{})
	for _, raw := range []string{os.Getenv("CORS_ALLOWED_ORIGINS"), os.Getenv("FRONTEND_URL")} {
		for _, part := range strings.Split(raw, ",") {
			origin := strings.TrimSpace(part)
			if origin == "" {
				continue
			}
			if _, exists := seen[origin]; exists {
				continue
			}
			seen[origin] = struct{}{}
			origins = append(origins, origin)
		}
	}
	return origins
}
