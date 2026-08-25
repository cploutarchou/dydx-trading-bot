package auth

import (
	"crypto/rand"
	"encoding/base64"
	"log"
	"os"
	"strings"
	"sync"

	"github.com/dydx-trading-bot/backend-go/config"
)

var (
	ephemeralSecretOnce sync.Once
	ephemeralSecret     string
)

// ResolveSharedJWTSecret returns the single JWT signing secret shared by the
// auth middleware and the token service, so tokens issued by one are verifiable
// by the other.
//
// Resolution order: JWT_SECRET_KEY / SECRET_KEY env, then the loaded config.
// Production fails fast when nothing is configured — a missing secret must
// never degrade to a known constant. Non-production falls back to a
// process-lifetime random secret (with a warning) so unconfigured development
// servers cannot mint tokens verifiable by any other deployment.
func ResolveSharedJWTSecret() string {
	if secret := strings.TrimSpace(os.Getenv("JWT_SECRET_KEY")); secret != "" {
		return secret
	}
	if secret := strings.TrimSpace(os.Getenv("SECRET_KEY")); secret != "" {
		return secret
	}
	if config.ConfigInstance != nil {
		if secret := strings.TrimSpace(config.ConfigInstance.Auth.JWTSecretKey); secret != "" {
			return secret
		}
	}

	if config.ResolveAppConfigEnvironment() == "production" {
		log.Fatal("JWT_SECRET_KEY (or SECRET_KEY) must be configured in production; refusing to start with an unverifiable signing secret")
	}

	ephemeralSecretOnce.Do(func() {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			log.Fatalf("failed to generate ephemeral JWT secret: %v", err)
		}
		ephemeralSecret = base64.RawURLEncoding.EncodeToString(buf)
		log.Printf("WARNING: JWT_SECRET_KEY is not configured; using a process-lifetime ephemeral signing secret. " +
			"Legacy bearer JWTs will not survive restarts (cookie sessions are unaffected). Set JWT_SECRET_KEY to stabilize.")
	})
	return ephemeralSecret
}
