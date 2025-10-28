package services

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type KeyManagementService struct {
	repo   *repository.KeyRepository
	secret string
}

func NewKeyManagementService(repo *repository.KeyRepository) *KeyManagementService {
	secret := os.Getenv("ENCRYPTION_KEY")
	if secret == "" {
		secret = "default-secret-key-change-in-production" // 32 chars min
	}
	// Pad to 32 bytes for AES-256
	if len(secret) < 32 {
		secret = fmt.Sprintf("%-32s", secret)
	} else if len(secret) > 32 {
		secret = secret[:32]
	}

	return &KeyManagementService{
		repo:   repo,
		secret: secret,
	}
}

func (s *KeyManagementService) encryptSecret(plaintext string) (string, error) {
	key := []byte(s.secret)
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", fmt.Errorf("failed to generate nonce: %w", err)
	}

	ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return base64.StdEncoding.EncodeToString(ciphertext), nil
}

func (s *KeyManagementService) decryptSecret(encryptedText string) (string, error) {
	key := []byte(s.secret)
	ciphertext, err := base64.StdEncoding.DecodeString(encryptedText)
	if err != nil {
		return "", fmt.Errorf("failed to decode ciphertext: %w", err)
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	nonceSize := gcm.NonceSize()
	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]

	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return "", fmt.Errorf("failed to decrypt: %w", err)
	}

	return string(plaintext), nil
}

func (s *KeyManagementService) CreateKey(userID int, network string, chainAddress string, secretPhrase string) (*models.DYDXKey, error) {
	// Validate inputs
	if network == "" {
		return nil, fmt.Errorf("network is required")
	}
	if chainAddress == "" {
		return nil, fmt.Errorf("chain_address is required")
	}
	if secretPhrase == "" {
		return nil, fmt.Errorf("secret_phrase is required")
	}

	network = strings.ToLower(network)
	if network != "testnet" && network != "mainnet" {
		return nil, fmt.Errorf("network must be 'testnet' or 'mainnet'")
	}

	// Encrypt secret phrase
	encrypted, err := s.encryptSecret(secretPhrase)
	if err != nil {
		return nil, fmt.Errorf("failed to encrypt secret: %w", err)
	}

	// Check if key already exists for this user/network
	existing, err := s.repo.GetKeyByUserAndNetwork(userID, network)
	if err != nil {
		return nil, fmt.Errorf("failed to check existing key: %w", err)
	}

	if existing != nil {
		// Update existing key
		existing.ChainAddress = chainAddress
		existing.EncryptedSecret = encrypted
		if err := s.repo.UpdateKey(existing); err != nil {
			return nil, fmt.Errorf("failed to update key: %w", err)
		}
		return existing, nil
	}

	// Create new key
	key := &models.DYDXKey{
		UserID:          userID,
		Network:         network,
		ChainAddress:    chainAddress,
		EncryptedSecret: encrypted,
		IsActive:        true,
		CreatedAt:       time.Now(),
		UpdatedAt:       time.Now(),
	}

	if err := s.repo.CreateKey(key); err != nil {
		return nil, fmt.Errorf("failed to create key: %w", err)
	}

	return key, nil
}

func (s *KeyManagementService) GetKeyInfo(userID int, network string) (map[string]interface{}, error) {
	key, err := s.repo.GetKeyByUserAndNetwork(userID, network)
	if err != nil {
		return nil, fmt.Errorf("failed to get key: %w", err)
	}

	if key == nil {
		return nil, nil
	}

	return map[string]interface{}{
		"id":            key.ID,
		"network":       key.Network,
		"chain_address": key.ChainAddress,
		"is_active":     key.IsActive,
		"created_at":    key.CreatedAt.Format(time.RFC3339),
		"updated_at":    key.UpdatedAt.Format(time.RFC3339),
	}, nil
}

func (s *KeyManagementService) GetKey(userID int, network string) (map[string]interface{}, error) {
	key, err := s.repo.GetKeyByUserAndNetwork(userID, network)
	if err != nil {
		return nil, fmt.Errorf("failed to get key: %w", err)
	}

	if key == nil {
		return nil, nil
	}

	// Decrypt secret
	decrypted, err := s.decryptSecret(key.EncryptedSecret)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt secret: %w", err)
	}

	return map[string]interface{}{
		"id":            key.ID,
		"network":       key.Network,
		"chain_address": key.ChainAddress,
		"secret_phrase": decrypted,
		"created_at":    key.CreatedAt.Format(time.RFC3339),
		"updated_at":    key.UpdatedAt.Format(time.RFC3339),
	}, nil
}

func (s *KeyManagementService) GetActiveKeys(userID int) ([]map[string]interface{}, error) {
	keys, err := s.repo.GetActiveKeysByUser(userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get keys: %w", err)
	}

	var result []map[string]interface{}
	for _, key := range keys {
		result = append(result, map[string]interface{}{
			"id":            key.ID,
			"network":       key.Network,
			"chain_address": key.ChainAddress,
			"is_active":     key.IsActive,
			"created_at":    key.CreatedAt.Format(time.RFC3339),
			"updated_at":    key.UpdatedAt.Format(time.RFC3339),
		})
	}

	return result, nil
}

func (s *KeyManagementService) DeleteKey(userID int, network string) error {
	return s.repo.DeleteKey(userID, network)
}
