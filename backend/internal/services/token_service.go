package services

import (
	"fmt"
	"os"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// GenerateAccessToken generates a JWT access token
func GenerateAccessToken(userID int, username string, isAdmin bool) (string, error) {
	secretKey := os.Getenv("JWT_SECRET_KEY")
	if secretKey == "" {
		secretKey = "your-super-secret-key-change-in-production-min-32-chars"
	}

	expirationTime := time.Now().Add(30 * time.Minute)
	claims := jwt.MapClaims{
		"user_id":  userID,
		"username": username,
		"is_admin": isAdmin,
		"exp":      expirationTime.Unix(),
		"iat":      time.Now().Unix(),
		"type":     "access",
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(secretKey))
	if err != nil {
		return "", fmt.Errorf("failed to sign token: %w", err)
	}

	return tokenString, nil
}

// GenerateRefreshToken generates a JWT refresh token
func GenerateRefreshToken(userID int, username string) (string, error) {
	secretKey := os.Getenv("JWT_SECRET_KEY")
	if secretKey == "" {
		secretKey = "your-super-secret-key-change-in-production-min-32-chars"
	}

	expirationTime := time.Now().Add(7 * 24 * time.Hour)
	claims := jwt.MapClaims{
		"user_id":  userID,
		"username": username,
		"exp":      expirationTime.Unix(),
		"iat":      time.Now().Unix(),
		"type":     "refresh",
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(secretKey))
	if err != nil {
		return "", fmt.Errorf("failed to sign token: %w", err)
	}

	return tokenString, nil
}

// VerifyToken verifies a JWT token
func VerifyToken(tokenString string) (jwt.MapClaims, error) {
	secretKey := os.Getenv("JWT_SECRET_KEY")
	if secretKey == "" {
		secretKey = "your-super-secret-key-change-in-production-min-32-chars"
	}

	token, err := jwt.ParseWithClaims(tokenString, jwt.MapClaims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(secretKey), nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok || !token.Valid {
		return nil, fmt.Errorf("invalid token claims")
	}

	return claims, nil
}
