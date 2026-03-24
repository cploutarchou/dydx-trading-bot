package services

import (
	"fmt"
	"log"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// BotInstanceService handles bot instance business logic
type BotInstanceService struct {
	repo      *repository.BotInstanceRepository
	apiClient *BotAPIClient
}

// NewBotInstanceService creates a new bot instance service
func NewBotInstanceService(repo *repository.BotInstanceRepository, apiClient *BotAPIClient) *BotInstanceService {
	return &BotInstanceService{
		repo:      repo,
		apiClient: apiClient,
	}
}

// WithAuthToken returns a request-scoped service copy that forwards
// the provided token to the downstream bot API.
func (s *BotInstanceService) WithAuthToken(token string) *BotInstanceService {
	if s == nil {
		return nil
	}

	if s.apiClient == nil {
		return s
	}

	return &BotInstanceService{
		repo:      s.repo,
		apiClient: s.apiClient.WithToken(token),
	}
}

// CreateBotInstance creates a new bot instance
func (s *BotInstanceService) CreateBotInstance(instance *models.BotInstance) error {
	return s.repo.CreateBotInstance(instance)
}

// CreateBotInstanceWithConfig creates a new bot instance in the bot API and persists metadata in the DB.
func (s *BotInstanceService) CreateBotInstanceWithConfig(instance *models.BotInstance, payload map[string]interface{}) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	if _, err := s.apiClient.CreateBotInstance(payload); err != nil {
		return fmt.Errorf("failed to create bot instance in bot API: %w", err)
	}

	if err := s.repo.CreateBotInstance(instance); err != nil {
		// Best-effort rollback in bot API to avoid orphan runtime instances.
		_, _ = s.apiClient.DeleteBotInstance(instance.InstanceID)
		return err
	}

	return nil
}

// GetBotInstanceByID retrieves a bot instance by ID
func (s *BotInstanceService) GetBotInstanceByID(id int) (*models.BotInstance, error) {
	return s.repo.GetBotInstanceByID(id)
}

// GetBotInstanceByInstanceID retrieves a bot instance by instance_id
func (s *BotInstanceService) GetBotInstanceByInstanceID(instanceID string) (*models.BotInstance, error) {
	return s.repo.GetBotInstanceByInstanceID(instanceID)
}

// ListBotInstancesByUserID retrieves all bot instances for a user
func (s *BotInstanceService) ListBotInstancesByUserID(userID int, limit int, offset int) ([]models.BotInstance, error) {
	return s.repo.ListBotInstancesByUserID(userID, limit, offset)
}

// UpdateBotInstanceStatus updates the status of a bot instance
func (s *BotInstanceService) UpdateBotInstanceStatus(instanceID string, status string) error {
	return s.repo.UpdateBotInstanceStatus(instanceID, status)
}

// UpdateBotInstanceMetrics updates performance metrics
func (s *BotInstanceService) UpdateBotInstanceMetrics(instanceID string, totalTrades int, totalPnL *float64, currentBalance *float64) error {
	return s.repo.UpdateBotInstanceMetrics(instanceID, totalTrades, totalPnL, currentBalance)
}

// DeleteBotInstance deletes a bot instance
func (s *BotInstanceService) DeleteBotInstance(instanceID string) error {
	if s.apiClient != nil {
		if _, err := s.apiClient.DeleteBotInstance(instanceID); err != nil {
			return fmt.Errorf("failed to delete bot instance in bot API: %w", err)
		}
	}

	return s.repo.DeleteBotInstance(instanceID)
}

// StartBotInstance starts a bot instance via the bot API
func (s *BotInstanceService) StartBotInstance(instanceID string) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	_, err := s.apiClient.StartBotInstance(instanceID)
	if err != nil {
		log.Printf("Failed to start bot via API: %v", err)
		return err
	}

	log.Printf("Bot instance started via API: %s", instanceID)

	// Update status in database
	return s.repo.UpdateBotInstanceStatus(instanceID, "running")
}

// StopBotInstance stops a bot instance via the bot API
func (s *BotInstanceService) StopBotInstance(instanceID string) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	_, err := s.apiClient.StopBotInstance(instanceID)
	if err != nil {
		log.Printf("Failed to stop bot via API: %v", err)
		return err
	}

	log.Printf("Bot instance stopped via API: %s", instanceID)

	// Update status in database
	return s.repo.UpdateBotInstanceStatus(instanceID, "stopped")
}

// RestartBotInstance restarts a bot instance via the bot API
func (s *BotInstanceService) RestartBotInstance(instanceID string) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	_, err := s.apiClient.RestartBotInstance(instanceID)
	if err != nil {
		log.Printf("Failed to restart bot via API: %v", err)
		return err
	}

	log.Printf("Bot instance restarted via API: %s", instanceID)

	// Update status in database
	return s.repo.UpdateBotInstanceStatus(instanceID, "running")
}

// GetBotInstanceStats gets statistics for a bot instance
func (s *BotInstanceService) GetBotInstanceStats(instanceID string) (map[string]interface{}, error) {
	if s.apiClient == nil {
		return nil, fmt.Errorf("bot API client not configured")
	}

	return s.apiClient.GetBotInstanceStats(instanceID)
}

// GetBotInstanceTrades gets trades for a bot instance
func (s *BotInstanceService) GetBotInstanceTrades(instanceID string, limit int, offset int, winningOnly bool) (map[string]interface{}, error) {
	if s.apiClient == nil {
		return nil, fmt.Errorf("bot API client not configured")
	}

	return s.apiClient.GetBotInstanceTrades(instanceID, limit, offset, winningOnly)
}

// SyncBotInstanceFromAPI syncs bot instance data from the bot API
func (s *BotInstanceService) SyncBotInstanceFromAPI(instanceID string) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	result, err := s.apiClient.GetBotInstance(instanceID)
	if err != nil {
		return fmt.Errorf("failed to get bot instance from API: %w", err)
	}

	log.Printf("Successfully synced bot instance %s from API: %+v", instanceID, result)
	return nil
}
