package routes

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type fakeQuickDeployStore struct {
	created   []*models.BotInstance
	deleted   []string
	createErr error
	count     int
}

func (f *fakeQuickDeployStore) CreateBotInstance(instance *models.BotInstance) error {
	if f.createErr != nil {
		return f.createErr
	}
	f.created = append(f.created, instance)
	f.count++
	return nil
}

func (f *fakeQuickDeployStore) CountBotInstancesByUserID(int) (int, error) { return f.count, nil }

func (f *fakeQuickDeployStore) DeleteBotInstance(instanceID string) error {
	f.deleted = append(f.deleted, instanceID)
	f.count--
	return nil
}

type fakeQuickDeployUpstream struct{ deleted []string }

func (f *fakeQuickDeployUpstream) DeleteBotInstance(instanceID string) (map[string]interface{}, error) {
	f.deleted = append(f.deleted, instanceID)
	return map[string]interface{}{}, nil
}

func quickDeployFixture() (map[string]interface{}, map[string]interface{}) {
	config := map[string]interface{}{
		"credentials":    map[string]interface{}{"chain_id": "dydx-mainnet-1", "address": "dydx1abc", "mnemonic": "never store these words"},
		"trading_params": map[string]interface{}{"usd_per_trade": 10.0},
	}
	result := map[string]interface{}{"success": true, "data": map[string]interface{}{"instance_id": "desk-20260920-101500"}}
	return config, result
}

func TestRecordQuickDeployedInstance_WritesOwnedRowWithoutCredentials(t *testing.T) {
	store, upstream := &fakeQuickDeployStore{}, &fakeQuickDeployUpstream{}
	config, result := quickDeployFixture()

	instanceID, err := recordQuickDeployedInstance(store, upstream, 7, 3, "desk", true, config, result)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if instanceID != "desk-20260920-101500" || len(store.created) != 1 {
		t.Fatalf("instanceID=%q created=%d", instanceID, len(store.created))
	}
	row := store.created[0]
	if row.UserID != 7 || row.Network != "mainnet" || row.Status != "running" || row.InstanceName != "desk" {
		t.Fatalf("unexpected row: %+v", row)
	}
	encoded, _ := json.Marshal(row)
	if strings.Contains(string(encoded), "never store these words") || row.Config.Valid {
		t.Fatalf("credentials must never be persisted in the ownership row: %s", encoded)
	}
	if !row.TradingParams.Valid || !strings.Contains(row.TradingParams.String, "usd_per_trade") {
		t.Fatalf("trading params not stored: %+v", row.TradingParams)
	}
	if len(upstream.deleted) != 0 {
		t.Fatalf("a successful deploy must not be rolled back: %v", upstream.deleted)
	}
}

func TestRecordQuickDeployedInstance_RollsBackUpstreamWhenTheRowCannotBeWritten(t *testing.T) {
	store := &fakeQuickDeployStore{createErr: errors.New("unique violation")}
	upstream := &fakeQuickDeployUpstream{}
	config, result := quickDeployFixture()

	if _, err := recordQuickDeployedInstance(store, upstream, 7, 3, "desk", true, config, result); err == nil {
		t.Fatal("expected an error")
	}
	if len(upstream.deleted) != 1 || upstream.deleted[0] != "desk-20260920-101500" {
		t.Fatalf("the unowned runtime must be deleted upstream, got %v", upstream.deleted)
	}
}

func TestRecordQuickDeployedInstance_UndoesADeployThatExceedsTheQuota(t *testing.T) {
	// A concurrent request already used the last slot after the pre-check.
	store := &fakeQuickDeployStore{count: 3}
	upstream := &fakeQuickDeployUpstream{}
	config, result := quickDeployFixture()

	_, err := recordQuickDeployedInstance(store, upstream, 7, 3, "desk", true, config, result)
	if !errors.Is(err, errQuickDeployQuotaExceeded) {
		t.Fatalf("err = %v, want quota exceeded", err)
	}
	if len(upstream.deleted) != 1 || len(store.deleted) != 1 || store.count != 3 {
		t.Fatalf("upstream=%v rows deleted=%v count=%d", upstream.deleted, store.deleted, store.count)
	}
}

func TestRecordQuickDeployedInstance_RequiresAnInstanceID(t *testing.T) {
	store, upstream := &fakeQuickDeployStore{}, &fakeQuickDeployUpstream{}
	config, _ := quickDeployFixture()

	if _, err := recordQuickDeployedInstance(store, upstream, 7, 3, "desk", false, config, map[string]interface{}{"success": true}); err == nil {
		t.Fatal("expected an error when the bot API returns no instance id")
	}
	if len(store.created) != 0 {
		t.Fatal("no row may be written without an instance id")
	}
}

func TestRecordQuickDeployedInstance_TestnetAndStoppedDefaults(t *testing.T) {
	store, upstream := &fakeQuickDeployStore{}, &fakeQuickDeployUpstream{}
	config := map[string]interface{}{"credentials": map[string]interface{}{"chain_id": "dydx-testnet-4"}}
	result := map[string]interface{}{"instance_id": "paper-1"}

	if _, err := recordQuickDeployedInstance(store, upstream, 9, 10, "paper", false, config, result); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if row := store.created[0]; row.Network != "testnet" || row.Status != "stopped" {
		t.Fatalf("unexpected row: %+v", row)
	}
}
