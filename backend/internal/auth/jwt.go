package auth

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
)

// JWTConfig holds JWT configuration
type JWTConfig struct {
	Secret            string
	ExpiryHours       int
	RefreshExpiryDays int
}

// TokenClaims represents JWT claims
type TokenClaims struct {
	UserID   int    `json:"user_id"`
	Username string `json:"username"`
	Email    string `json:"email"`
	IsAdmin  bool   `json:"is_admin"`
	Role     string `json:"role"`
	Type     string `json:"type"`
	jwt.RegisteredClaims
}

// TokenResponse represents a token response
type TokenResponse struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	ExpiresAt    time.Time `json:"expires_at"`
	TokenType    string    `json:"token_type"`
}

// Manager handles JWT token operations
type Manager struct {
	config JWTConfig
}

// NewManager creates a new JWT manager
func NewManager(cfg JWTConfig) *Manager {
	return &Manager{config: cfg}
}

// CreateAccessToken creates a JWT access token
func (m *Manager) CreateAccessToken(userID int, username, email string, isAdmin bool, expiresDelta ...time.Duration) (string, time.Time, error) {
	role := "client"
	if isAdmin {
		role = "admin"
	}
	return m.CreateAccessTokenWithRole(userID, username, email, isAdmin, role, expiresDelta...)
}

func (m *Manager) CreateAccessTokenWithRole(userID int, username, email string, isAdmin bool, role string, expiresDelta ...time.Duration) (string, time.Time, error) {
	var expiresAt time.Time
	if len(expiresDelta) > 0 {
		expiresAt = time.Now().Add(expiresDelta[0])
	} else if m.config.ExpiryHours > 0 {
		expiresAt = time.Now().Add(time.Hour * time.Duration(m.config.ExpiryHours))
	} else {
		expiresAt = time.Now().Add(time.Hour * 24) // default 24h
	}

	claims := TokenClaims{
		UserID:   userID,
		Username: username,
		Email:    email,
		IsAdmin:  isAdmin,
		Role:     role,
		Type:     "access",
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expiresAt),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			NotBefore: jwt.NewNumericDate(time.Now()),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(m.config.Secret))
	if err != nil {
		return "", time.Time{}, fmt.Errorf("failed to sign access token: %w", err)
	}

	return tokenString, expiresAt, nil
}

// CreateRefreshToken creates a JWT refresh token
func (m *Manager) CreateRefreshToken(userID int, username, email string, isAdmin bool) (string, time.Time, error) {
	role := "client"
	if isAdmin {
		role = "admin"
	}
	return m.CreateRefreshTokenWithRole(userID, username, email, isAdmin, role)
}

func (m *Manager) CreateRefreshTokenWithRole(userID int, username, email string, isAdmin bool, role string) (string, time.Time, error) {
	var expiresAt time.Time
	if m.config.RefreshExpiryDays > 0 {
		expiresAt = time.Now().Add(time.Hour * 24 * time.Duration(m.config.RefreshExpiryDays))
	} else {
		expiresAt = time.Now().Add(time.Hour * 24 * 7) // default 7 days
	}

	claims := TokenClaims{
		UserID:   userID,
		Username: username,
		Email:    email,
		IsAdmin:  isAdmin,
		Role:     role,
		Type:     "refresh",
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expiresAt),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			NotBefore: jwt.NewNumericDate(time.Now()),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(m.config.Secret))
	if err != nil {
		return "", time.Time{}, fmt.Errorf("failed to sign refresh token: %w", err)
	}

	return tokenString, expiresAt, nil
}

// DecodeToken decodes and validates a JWT token and returns claims
func (m *Manager) DecodeToken(tokenString string) (*TokenClaims, error) {
	claims := &TokenClaims{}
	_, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(m.config.Secret), nil
	}, jwt.WithLeeway(60*time.Second))
	if err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	return claims, nil
}

// VerifyToken verifies token validity and expected type (access or refresh)
func (m *Manager) VerifyToken(tokenString string, expectedType string) (*TokenClaims, error) {
	claims, err := m.DecodeToken(tokenString)
	if err != nil {
		return nil, err
	}
	if expectedType != "" && claims.Type != expectedType {
		return nil, fmt.Errorf("token type mismatch: expected %s got %s", expectedType, claims.Type)
	}
	return claims, nil
}

// ExtractSubject returns the username (subject) from a token if valid
func (m *Manager) ExtractSubject(tokenString string) (string, error) {
	claims, err := m.DecodeToken(tokenString)
	if err != nil {
		return "", err
	}
	return claims.Username, nil
}

// HashPassword hashes a password using bcrypt
func HashPassword(password string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return "", fmt.Errorf("failed to hash password: %w", err)
	}
	return string(hash), nil
}

// VerifyPassword verifies a password against its hash
func VerifyPassword(hash, password string) error {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
}
