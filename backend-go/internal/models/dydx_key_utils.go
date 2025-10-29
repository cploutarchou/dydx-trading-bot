package models

import (
	"encoding/json"
	"time"
)

// ToDict DYDXKeyToDict converts DYDXKey to dictionary, optionally excluding encrypted_secret
func (d *DYDXKey) ToDict(includeSecret bool) map[string]interface{} {
	result := map[string]interface{}{
		"id":            d.ID,
		"user_id":       d.UserID,
		"network":       d.Network,
		"chain_address": d.ChainAddress,
		"is_active":     d.IsActive,
		"created_at":    d.CreatedAt,
		"updated_at":    d.UpdatedAt,
	}

	if includeSecret {
		result["encrypted_secret"] = d.EncryptedSecret
	}

	return result
}

// FromDict populates DYDXKey from a dictionary
func (d *DYDXKey) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		d.ID = int(id)
	}
	if userID, ok := data["user_id"].(float64); ok {
		d.UserID = int(userID)
	}
	if network, ok := data["network"].(string); ok {
		d.Network = network
	}
	if chainAddr, ok := data["chain_address"].(string); ok {
		d.ChainAddress = chainAddr
	}
	if secret, ok := data["encrypted_secret"].(string); ok {
		d.EncryptedSecret = secret
	}
	if active, ok := data["is_active"].(bool); ok {
		d.IsActive = active
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			d.CreatedAt = t
		}
	}
	if updatedAt, ok := data["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			d.UpdatedAt = t
		}
	}
}

// ToJSON converts DYDXKey to JSON, optionally excluding encrypted_secret
func (d *DYDXKey) ToJSON(includeSecret bool) ([]byte, error) {
	return json.Marshal(d.ToDict(includeSecret))
}

// FromJSON populates DYDXKey from JSON
func (d *DYDXKey) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	d.FromDict(dict)
	return nil
}

// ============ DYDXKeySettings Methods ============

// ToDict converts DYDXKeySettings to dictionary
func (d *DYDXKeySettings) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"id":                  d.ID,
		"user_id":             d.UserID,
		"default_network":     d.DefaultNetwork,
		"auto_switch_testnet": d.AutoSwitchTestnet,
		"created_at":          d.CreatedAt,
		"updated_at":          d.UpdatedAt,
	}
}

// FromDict populates DYDXKeySettings from a dictionary
func (d *DYDXKeySettings) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		d.ID = int(id)
	}
	if userID, ok := data["user_id"].(float64); ok {
		d.UserID = int(userID)
	}
	if network, ok := data["default_network"].(string); ok {
		d.DefaultNetwork = network
	}
	if autoSwitch, ok := data["auto_switch_testnet"].(bool); ok {
		d.AutoSwitchTestnet = autoSwitch
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			d.CreatedAt = t
		}
	}
	if updatedAt, ok := data["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			d.UpdatedAt = t
		}
	}
}

// ToJSON converts DYDXKeySettings to JSON
func (d *DYDXKeySettings) ToJSON() ([]byte, error) {
	return json.Marshal(d.ToDict())
}

// FromJSON populates DYDXKeySettings from JSON
func (d *DYDXKeySettings) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	d.FromDict(dict)
	return nil
}
