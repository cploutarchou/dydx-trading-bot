package services

import (
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
)

func jwtManager() *auth.Manager {
	refreshDays := 7
	if config.ConfigInstance != nil && config.ConfigInstance.Auth.RefreshTokenExpireDays > 0 {
		refreshDays = config.ConfigInstance.Auth.RefreshTokenExpireDays
	}

	return auth.NewManager(auth.JWTConfig{
		Secret:            auth.ResolveSharedJWTSecret(),
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

func GenerateAccessTokenWithRole(userID int, username string, isAdmin bool, role string) (string, error) {
	tokenString, _, err := jwtManager().CreateAccessTokenWithRole(userID, username, "", isAdmin, role, 30*time.Minute)
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

func GenerateRefreshTokenWithRole(userID int, username string, isAdmin bool, role string) (string, error) {
	tokenString, _, err := jwtManager().CreateRefreshTokenWithRole(userID, username, "", isAdmin, role)
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
