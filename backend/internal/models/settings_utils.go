package models

import (
	"encoding/json"
	"time"
)

// ============ BotSetting Methods ============

// ToDict converts BotSetting to dictionary
func (b *BotSetting) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"id":            b.ID,
		"section":       b.Section,
		"key":           b.Key,
		"value":         b.Value,
		"value_type":    b.ValueType,
		"description":   b.Description,
		"default_value": b.DefaultValue,
		"is_active":     b.IsActive,
		"version":       b.Version,
		"created_at":    b.CreatedAt,
		"updated_at":    b.UpdatedAt,
	}
}

// FromDict populates BotSetting from a dictionary
func (b *BotSetting) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		b.ID = int(id)
	}
	if section, ok := data["section"].(string); ok {
		b.Section = section
	}
	if key, ok := data["key"].(string); ok {
		b.Key = key
	}
	if value, ok := data["value"].(string); ok {
		b.Value = value
	}
	if valueType, ok := data["value_type"].(string); ok {
		b.ValueType = valueType
	}
	if description, ok := data["description"].(string); ok {
		b.Description = description
	}
	if defaultValue, ok := data["default_value"].(string); ok {
		b.DefaultValue = defaultValue
	}
	if isActive, ok := data["is_active"].(bool); ok {
		b.IsActive = isActive
	}
	if version, ok := data["version"].(float64); ok {
		b.Version = int(version)
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			b.CreatedAt = t
		}
	}
	if updatedAt, ok := data["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			b.UpdatedAt = t
		}
	}
}

// ToJSON converts BotSetting to JSON
func (b *BotSetting) ToJSON() ([]byte, error) {
	return json.Marshal(b.ToDict())
}

// FromJSON populates BotSetting from JSON
func (b *BotSetting) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	b.FromDict(dict)
	return nil
}

// ============ RedisSetting Methods ============

// ToDict converts RedisSetting to dictionary
func (r *RedisSetting) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"id":         r.ID,
		"enabled":    r.Enabled,
		"host":       r.Host,
		"port":       r.Port,
		"db":         r.Db,
		"password":   r.Password,
		"ssl":        r.SSL,
		"created_at": r.CreatedAt,
		"updated_at": r.UpdatedAt,
	}
}

// FromDict populates RedisSetting from a dictionary
func (r *RedisSetting) FromDict(data map[string]interface{}) {
	if id, ok := data["id"].(float64); ok {
		r.ID = int(id)
	}
	if enabled, ok := data["enabled"].(bool); ok {
		r.Enabled = enabled
	}
	if host, ok := data["host"].(string); ok {
		r.Host = host
	}
	if port, ok := data["port"].(float64); ok {
		r.Port = int(port)
	}
	if db, ok := data["db"].(float64); ok {
		r.Db = int(db)
	}
	if password, ok := data["password"].(string); ok {
		r.Password = password
	}
	if ssl, ok := data["ssl"].(bool); ok {
		r.SSL = ssl
	}
	if createdAt, ok := data["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
			r.CreatedAt = t
		}
	}
	if updatedAt, ok := data["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, updatedAt); err == nil {
			r.UpdatedAt = t
		}
	}
}

// ToJSON converts RedisSetting to JSON
func (r *RedisSetting) ToJSON() ([]byte, error) {
	return json.Marshal(r.ToDict())
}

// FromJSON populates RedisSetting from JSON
func (r *RedisSetting) FromJSON(data []byte) error {
	var dict map[string]interface{}
	if err := json.Unmarshal(data, &dict); err != nil {
		return err
	}
	r.FromDict(dict)
	return nil
}
