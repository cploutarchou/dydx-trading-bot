package services

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"

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

// WithTraceID returns a request-scoped service copy that forwards the provided
// trace ID to the downstream bot API.
func (s *BotInstanceService) WithTraceID(traceID string) *BotInstanceService {
	if s == nil {
		return nil
	}

	if s.apiClient == nil {
		return s
	}

	return &BotInstanceService{
		repo:      s.repo,
		apiClient: s.apiClient.WithTraceID(traceID),
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

// RecreateBotInstanceWithConfig forcefully replaces a runtime instance both upstream and locally.
func (s *BotInstanceService) RecreateBotInstanceWithConfig(instance *models.BotInstance, payload map[string]interface{}) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	if _, err := s.apiClient.StopBotInstanceWithForce(instance.InstanceID, true); err != nil {
		var apiErr *BotAPIError
		if !errors.As(err, &apiErr) || apiErr.StatusCode != http.StatusNotFound {
			log.Printf("⚠️ best-effort stop before recreate failed for %s: %v", instance.InstanceID, err)
		}
	}

	if _, err := s.apiClient.DeleteBotInstance(instance.InstanceID); err != nil {
		var apiErr *BotAPIError
		if !errors.As(err, &apiErr) || apiErr.StatusCode != http.StatusNotFound {
			return fmt.Errorf("failed to delete bot instance in bot API: %w", err)
		}
	}

	if err := s.repo.DeleteBotInstance(instance.InstanceID); err != nil {
		return fmt.Errorf("failed to delete bot instance metadata: %w", err)
	}

	return s.CreateBotInstanceWithConfig(instance, payload)
}

func botAPIErrorStatus(err error) int {
	var apiErr *BotAPIError
	if errors.As(err, &apiErr) {
		return apiErr.StatusCode
	}
	return 0
}

func botAPIErrorMessage(err error) string {
	var apiErr *BotAPIError
	if errors.As(err, &apiErr) {
		return strings.TrimSpace(apiErr.Message)
	}
	return strings.TrimSpace(err.Error())
}

func shouldRecoverMissingRemoteInstance(err error) bool {
	if err == nil {
		return false
	}

	statusCode := botAPIErrorStatus(err)
	if statusCode == http.StatusNotFound {
		return true
	}

	message := strings.ToLower(botAPIErrorMessage(err))
	return statusCode == http.StatusBadRequest &&
		(strings.Contains(message, "not found") ||
			strings.Contains(message, "already stopped") ||
			strings.Contains(message, "failed to stop instance"))
}

func isRemoteRuntimeStopped(remote map[string]interface{}) bool {
	if remote == nil {
		return false
	}

	status := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", remote["status"])))
	return status == "" || status == "stopped" || status == "created" || status == "error" || status == "failed"
}

func stringField(payload map[string]interface{}, key string) string {
	if payload == nil {
		return ""
	}
	value, ok := payload[key]
	if !ok || value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprintf("%v", value))
}

func (s *BotInstanceService) buildRemoteBotCreatePayload(instance *models.BotInstance) (map[string]interface{}, error) {
	if instance == nil {
		return nil, fmt.Errorf("bot instance metadata not available")
	}
	if !instance.Config.Valid || strings.TrimSpace(instance.Config.String) == "" {
		return nil, fmt.Errorf("missing persisted bot config for %s", instance.InstanceID)
	}

	var payload map[string]interface{}
	if err := json.Unmarshal([]byte(instance.Config.String), &payload); err != nil {
		return nil, fmt.Errorf("failed to decode persisted bot config for %s: %w", instance.InstanceID, err)
	}
	if payload == nil {
		payload = map[string]interface{}{}
	}

	if stringField(payload, "instance_id") == "" {
		payload["instance_id"] = instance.InstanceID
	}
	if stringField(payload, "instance_name") == "" {
		payload["instance_name"] = instance.InstanceName
	}
	if stringField(payload, "strategy") == "" && strings.TrimSpace(instance.Strategy) != "" {
		payload["strategy"] = instance.Strategy
	}
	if stringField(payload, "name") == "" && strings.TrimSpace(instance.InstanceName) != "" {
		payload["name"] = instance.InstanceName
	}

	if _, ok := payload["trading_params"]; !ok && instance.TradingParams.Valid && strings.TrimSpace(instance.TradingParams.String) != "" {
		var tradingParams map[string]interface{}
		if err := json.Unmarshal([]byte(instance.TradingParams.String), &tradingParams); err == nil && tradingParams != nil {
			payload["trading_params"] = tradingParams
		}
	}

	return payload, nil
}

func (s *BotInstanceService) ensureRemoteBotInstance(instanceID string) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	if _, err := s.apiClient.GetBotInstance(instanceID); err == nil {
		return nil
	} else if !shouldRecoverMissingRemoteInstance(err) {
		return err
	}

	instance, err := s.repo.GetBotInstanceByInstanceID(instanceID)
	if err != nil {
		return fmt.Errorf("failed to load local bot metadata for %s: %w", instanceID, err)
	}

	payload, err := s.buildRemoteBotCreatePayload(instance)
	if err != nil {
		return err
	}

	if _, err := s.apiClient.CreateBotInstance(payload); err != nil {
		if statusCode := botAPIErrorStatus(err); statusCode == http.StatusBadRequest || statusCode == http.StatusConflict {
			message := strings.ToLower(botAPIErrorMessage(err))
			if strings.Contains(message, "already exists") {
				return nil
			}
		}
		return fmt.Errorf("failed to recreate upstream bot runtime for %s: %w", instanceID, err)
	}

	log.Printf("✅ recreated missing upstream bot runtime from stored config: %s", instanceID)
	return nil
}

// StartBotInstance starts a bot instance via the bot API
func (s *BotInstanceService) StartBotInstance(instanceID string) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	_, err := s.apiClient.StartBotInstance(instanceID)
	if err != nil {
		if shouldRecoverMissingRemoteInstance(err) {
			log.Printf("⚠️ upstream bot runtime missing during start for %s; attempting recovery from stored config", instanceID)
			if recoverErr := s.ensureRemoteBotInstance(instanceID); recoverErr != nil {
				log.Printf("Failed to recover missing upstream bot runtime for %s: %v", instanceID, recoverErr)
				return recoverErr
			}
			if _, err = s.apiClient.StartBotInstance(instanceID); err != nil {
				log.Printf("Failed to start bot via API after recovery: %v", err)
				_ = s.repo.UpdateBotInstanceError(instanceID, botAPIErrorMessage(err))
				return err
			}
		} else {
			log.Printf("Failed to start bot via API: %v", err)
			_ = s.repo.UpdateBotInstanceError(instanceID, botAPIErrorMessage(err))
			return err
		}
	}

	log.Printf("Bot instance started via API: %s", instanceID)

	// Update status in database
	return s.repo.UpdateBotInstanceStatus(instanceID, "running")
}

// StopBotInstance stops a bot instance via the bot API
func (s *BotInstanceService) StopBotInstance(instanceID string) error {
	return s.StopBotInstanceWithForce(instanceID, false)
}

// StopBotInstanceWithForce stops a bot instance via the bot API with optional force flag.
func (s *BotInstanceService) StopBotInstanceWithForce(instanceID string, force bool) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	_, err := s.apiClient.StopBotInstanceWithForce(instanceID, force)
	if err != nil {
		log.Printf("Failed to stop bot via API: %v", err)
		return err
	}

	log.Printf("Bot instance stopped via API: %s (force=%t)", instanceID, force)

	// Update status in database
	return s.repo.UpdateBotInstanceStatus(instanceID, "stopped")
}

// RestartBotInstance restarts a bot instance via the bot API
func (s *BotInstanceService) RestartBotInstance(instanceID string) error {
	if s.apiClient == nil {
		return fmt.Errorf("bot API client not configured")
	}

	remoteInstance, remoteErr := s.apiClient.GetBotInstance(instanceID)
	if remoteErr != nil {
		if shouldRecoverMissingRemoteInstance(remoteErr) {
			log.Printf("⚠️ upstream bot runtime missing during restart for %s; falling back to start recovery", instanceID)
			return s.StartBotInstance(instanceID)
		}
		log.Printf("Failed to inspect bot runtime before restart: %v", remoteErr)
		return remoteErr
	}

	if isRemoteRuntimeStopped(remoteInstance) {
		log.Printf("ℹ️ bot runtime %s is not currently running upstream; using start instead of restart", instanceID)
		return s.StartBotInstance(instanceID)
	}

	_, err := s.apiClient.RestartBotInstance(instanceID)
	if err != nil {
		if shouldRecoverMissingRemoteInstance(err) {
			log.Printf("⚠️ restart degraded for %s; falling back to start recovery", instanceID)
			return s.StartBotInstance(instanceID)
		}
		log.Printf("Failed to restart bot via API: %v", err)
		_ = s.repo.UpdateBotInstanceError(instanceID, botAPIErrorMessage(err))
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

	result, err := s.apiClient.GetBotInstanceStats(instanceID)
	if err != nil {
		if botAPIErrorStatus(err) == http.StatusNotFound {
			log.Printf("⚠️ upstream bot stats missing for %s; marking local bot instance as error", instanceID)
			_ = s.repo.UpdateBotInstanceError(instanceID, "runtime instance missing from bot API")
		}
		return nil, err
	}

	return result, nil
}

// GetRemoteBotInstance retrieves a bot instance directly from the upstream bot API.
func (s *BotInstanceService) GetRemoteBotInstance(instanceID string) (map[string]interface{}, error) {
	if s.apiClient == nil {
		return nil, fmt.Errorf("bot API client not configured")
	}

	return s.apiClient.GetBotInstance(instanceID)
}

// GetRuntimePreflight evaluates runtime readiness using the upstream bot API.
func (s *BotInstanceService) GetRuntimePreflight(payload map[string]interface{}) (map[string]interface{}, error) {
	if s.apiClient == nil {
		return nil, fmt.Errorf("bot API client not configured")
	}
	return s.apiClient.GetRuntimePreflight(payload)
}

// GetBotInstanceTrades gets trades for a bot instance using upstream status and pagination filtering.
func (s *BotInstanceService) GetBotInstanceTrades(instanceID string, status *string, limit *int, offset *int) (map[string]interface{}, error) {
	if s.apiClient == nil {
		return nil, fmt.Errorf("bot API client not configured")
	}

	return s.apiClient.GetBotInstanceTrades(instanceID, status, limit, offset)
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
