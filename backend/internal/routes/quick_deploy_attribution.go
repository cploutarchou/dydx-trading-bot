package routes

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strings"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// quickDeployInstanceStore is the slice of the bot instance repository the
// quick-deploy attribution needs.
type quickDeployInstanceStore interface {
	CreateBotInstance(instance *models.BotInstance) error
	CountBotInstancesByUserID(userID int) (int, error)
	DeleteBotInstance(instanceID string) error
}

// quickDeployUpstream removes a runtime that could not be attributed.
type quickDeployUpstream interface {
	DeleteBotInstance(instanceID string) (map[string]interface{}, error)
}

var errQuickDeployQuotaExceeded = errors.New("bot instance limit reached")

// quickDeployedInstanceID reads the instance id the bot API generated.
func quickDeployedInstanceID(result map[string]interface{}) string {
	if data, ok := result["data"].(map[string]interface{}); ok {
		if id, ok := data["instance_id"].(string); ok && strings.TrimSpace(id) != "" {
			return strings.TrimSpace(id)
		}
	}
	if id, ok := result["instance_id"].(string); ok {
		return strings.TrimSpace(id)
	}
	return ""
}

// recordQuickDeployedInstance gives a quick-deployed runtime an owner.
//
// Without a bot_instances row the runtime is invisible to the per-user quota
// (unlimited quick-deploys) and to the ownership checks (its creator cannot
// stop it). The row never contains credentials: only trading parameters are
// stored. When the row cannot be written, or writing it shows the quota was
// exceeded by a concurrent request, the upstream runtime is deleted again so
// no unowned live bot is left behind.
func recordQuickDeployedInstance(
	store quickDeployInstanceStore,
	upstream quickDeployUpstream,
	userID int,
	maxInstances int,
	instanceName string,
	autoStart bool,
	config map[string]interface{},
	result map[string]interface{},
) (string, error) {
	instanceID := quickDeployedInstanceID(result)
	if instanceID == "" {
		return "", errors.New("bot API did not return an instance id; the runtime cannot be attributed")
	}

	network := "testnet"
	if credentials, ok := config["credentials"].(map[string]interface{}); ok {
		if chainID, _ := credentials["chain_id"].(string); strings.EqualFold(strings.TrimSpace(chainID), "dydx-mainnet-1") {
			network = "mainnet"
		}
	}
	status := "stopped"
	if autoStart {
		status = "running"
	}
	tradingParams := sql.NullString{}
	if raw, ok := config["trading_params"]; ok && raw != nil {
		if encoded, err := json.Marshal(raw); err == nil {
			tradingParams = sql.NullString{String: string(encoded), Valid: true}
		}
	}

	instance := &models.BotInstance{
		InstanceID:    instanceID,
		InstanceName:  instanceName,
		UserID:        userID,
		Status:        status,
		Network:       network,
		Strategy:      "default",
		TradingParams: tradingParams,
	}
	if err := store.CreateBotInstance(instance); err != nil {
		rollbackQuickDeploy(upstream, instanceID)
		return "", fmt.Errorf("record bot instance ownership: %w", err)
	}

	// The quota was checked before the upstream call; two concurrent requests
	// can both pass that check. Re-count now that the row exists and undo this
	// deploy when the account is over its limit.
	if count, err := store.CountBotInstancesByUserID(userID); err == nil && count > maxInstances {
		rollbackQuickDeploy(upstream, instanceID)
		if delErr := store.DeleteBotInstance(instanceID); delErr != nil {
			return "", fmt.Errorf("%w; failed to remove the over-quota row: %v", errQuickDeployQuotaExceeded, delErr)
		}
		return "", errQuickDeployQuotaExceeded
	}

	return instanceID, nil
}

func rollbackQuickDeploy(upstream quickDeployUpstream, instanceID string) {
	if upstream == nil {
		return
	}
	if _, err := upstream.DeleteBotInstance(instanceID); err != nil {
		// Surfaced to the caller through the primary error; logged for operators.
		logQuickDeployRollbackFailure(instanceID, err)
	}
}

func logQuickDeployRollbackFailure(instanceID string, err error) {
	log.Printf("quick-deploy: failed to roll back upstream instance %s: %v (manual cleanup required)", instanceID, err)
}
