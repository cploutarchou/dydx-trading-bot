package services

import (
	"fmt"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

const ExternalAPIProviderCodexIO = "codex_io"
const SharedCredentialUserID = 0

type ExternalAPICredentialInfo struct {
	Provider  string    `json:"provider"`
	Label     string    `json:"label"`
	IsActive  bool      `json:"is_active"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

type ExternalAPICredentialService struct {
	repo   *repository.ExternalAPICredentialRepository
	secret string
}

func NewExternalAPICredentialService(repo *repository.ExternalAPICredentialRepository) *ExternalAPICredentialService {
	return &ExternalAPICredentialService{
		repo:   repo,
		secret: loadEncryptionSecret(),
	}
}

func (s *ExternalAPICredentialService) Save(userID int, provider string, apiKey string, label string) (*ExternalAPICredentialInfo, error) {
	if userID < 0 {
		return nil, fmt.Errorf("user id is required")
	}
	provider = strings.TrimSpace(strings.ToLower(provider))
	if provider == "" {
		return nil, fmt.Errorf("provider is required")
	}
	apiKey = strings.TrimSpace(apiKey)
	if apiKey == "" {
		return nil, fmt.Errorf("api key is required")
	}

	encryptedKey, err := encryptString(s.secret, apiKey)
	if err != nil {
		return nil, fmt.Errorf("failed to encrypt api key: %w", err)
	}

	credential := &models.ExternalAPICredential{
		UserID:          userID,
		Provider:        provider,
		Label:           strings.TrimSpace(label),
		EncryptedAPIKey: encryptedKey,
		IsActive:        true,
	}
	if err := s.repo.Upsert(credential); err != nil {
		return nil, fmt.Errorf("failed to save api key: %w", err)
	}

	return &ExternalAPICredentialInfo{
		Provider:  credential.Provider,
		Label:     credential.Label,
		IsActive:  credential.IsActive,
		CreatedAt: credential.CreatedAt,
		UpdatedAt: credential.UpdatedAt,
	}, nil
}

func (s *ExternalAPICredentialService) SaveShared(provider string, apiKey string, label string) (*ExternalAPICredentialInfo, error) {
	return s.Save(SharedCredentialUserID, provider, apiKey, label)
}

func (s *ExternalAPICredentialService) Delete(userID int, provider string) error {
	if userID < 0 {
		return fmt.Errorf("user id is required")
	}
	provider = strings.TrimSpace(strings.ToLower(provider))
	if provider == "" {
		return fmt.Errorf("provider is required")
	}
	return s.repo.Deactivate(userID, provider)
}

func (s *ExternalAPICredentialService) DeleteShared(provider string) error {
	return s.Delete(SharedCredentialUserID, provider)
}

func (s *ExternalAPICredentialService) Get(userID int, provider string) (*ExternalAPICredentialInfo, error) {
	credential, err := s.repo.GetByUserAndProvider(userID, strings.TrimSpace(strings.ToLower(provider)))
	if err != nil {
		return nil, err
	}
	if credential == nil {
		return nil, nil
	}

	return &ExternalAPICredentialInfo{
		Provider:  credential.Provider,
		Label:     credential.Label,
		IsActive:  credential.IsActive,
		CreatedAt: credential.CreatedAt,
		UpdatedAt: credential.UpdatedAt,
	}, nil
}

func (s *ExternalAPICredentialService) GetShared(provider string) (*ExternalAPICredentialInfo, error) {
	return s.Get(SharedCredentialUserID, provider)
}

func (s *ExternalAPICredentialService) ResolveKey(userID int, provider string) (string, bool, error) {
	credential, err := s.repo.GetByUserAndProvider(userID, strings.TrimSpace(strings.ToLower(provider)))
	if err != nil {
		return "", false, err
	}
	if credential == nil || !credential.IsActive || strings.TrimSpace(credential.EncryptedAPIKey) == "" {
		return "", false, nil
	}

	key, err := decryptString(s.secret, credential.EncryptedAPIKey)
	if err != nil {
		return "", false, fmt.Errorf("failed to decrypt api key: %w", err)
	}

	return strings.TrimSpace(key), true, nil
}

func (s *ExternalAPICredentialService) ResolveSharedKey(provider string) (string, bool, error) {
	return s.ResolveKey(SharedCredentialUserID, provider)
}
