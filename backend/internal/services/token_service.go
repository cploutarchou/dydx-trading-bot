package services

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
)

const defaultJWTSecret = "your-super-secret-key-change-in-production"

func resolveJWTSecret() string {
	if secret := strings.TrimSpace(os.Getenv("JWT_SECRET_KEY")); secret != "" {
		return secret
	}
	if secret := strings.TrimSpace(os.Getenv("SECRET_KEY")); secret != "" {
		return secret
	}

	if config.ConfigInstance != nil {
		secret := strings.TrimSpace(config.ConfigInstance.Auth.JWTSecretKey)
		if secret != "" {
			return secret
		}
	}

	return defaultJWTSecret
}

func jwtManager() *auth.Manager {
	refreshDays := 7
	if config.ConfigInstance != nil && config.ConfigInstance.Auth.RefreshTokenExpireDays > 0 {
		refreshDays = config.ConfigInstance.Auth.RefreshTokenExpireDays
	}

	return auth.NewManager(auth.JWTConfig{
		Secret:            resolveJWTSecret(),
		ExpiryHours:       1,
		RefreshExpiryDays: refreshDays,
	})
}

// GenerateAccessToken generates a JWT access token
func GenerateAccessToken(userID int, username string, isAdmin bool) (string, error) {
	tokenString, _, err := jwtManager().CreateAccessToken(userID, username, "", isAdmin, 30*time.Minute)
	if err != nil {
		return "", fmt.Errorf("failed to create access token: %w", err)
	}

	return tokenString, nil
}

// GenerateRefreshToken generates a JWT refresh token
func GenerateRefreshToken(userID int, username string) (string, error) {
	tokenString, _, err := jwtManager().CreateRefreshToken(userID, username, "", false)
	if err != nil {
		return "", fmt.Errorf("failed to create refresh token: %w", err)
	}

	return tokenString, nil
}

// VerifyTokenClaims verifies a JWT token and returns typed claims.
func VerifyTokenClaims(tokenString string) (*auth.TokenClaims, error) {
	claims, err := jwtManager().VerifyToken(tokenString, "")
	if err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}
	return claims, nil
}

