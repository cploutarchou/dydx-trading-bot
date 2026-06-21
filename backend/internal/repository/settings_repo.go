package repository

import (
	"database/sql"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// SettingsRepository handles database operations for bot and redis settings
type SettingsRepository struct {
	db *sql.DB
}

type settingScanner interface {
	Scan(dest ...interface{}) error
}

// NewSettingsRepository creates a new settings repository
func NewSettingsRepository(db *sql.DB) *SettingsRepository {
	return &SettingsRepository{db: db}
}

func scanBotSetting(scanner settingScanner) (*models.BotSetting, error) {
	var (
		section      sql.NullString
		key          sql.NullString
		value        sql.NullString
		valueType    sql.NullString
		description  sql.NullString
		defaultValue sql.NullString
		isActive     sql.NullBool
		version      sql.NullInt64
		createdAt    sql.NullTime
		updatedAt    sql.NullTime
	)

	setting := &models.BotSetting{}
	err := scanner.Scan(
		&setting.ID,
		&section,
		&key,
		&value,
		&valueType,
		&description,
		&defaultValue,
		&isActive,
		&version,
		&createdAt,
		&updatedAt,
	)
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	setting.Section = "general"
	if section.Valid && section.String != "" {
		setting.Section = section.String
	}
	if key.Valid {
		setting.Key = key.String
	}
	if value.Valid {
		setting.Value = value.String
	}
	setting.ValueType = "string"
	if valueType.Valid && valueType.String != "" {
		setting.ValueType = valueType.String
	}
	if description.Valid {
		setting.Description = description.String
	}
	if defaultValue.Valid {
		setting.DefaultValue = defaultValue.String
	}
	setting.IsActive = true
	if isActive.Valid {
		setting.IsActive = isActive.Bool
	}
	setting.Version = 1
	if version.Valid && version.Int64 > 0 {
		setting.Version = int(version.Int64)
	}
	setting.CreatedAt = now
	if createdAt.Valid {
		setting.CreatedAt = createdAt.Time
	}
	setting.UpdatedAt = setting.CreatedAt
	if updatedAt.Valid {
		setting.UpdatedAt = updatedAt.Time
	}

	return setting, nil
}

// ============ BotSetting Operations ============

// CreateBotSetting creates a new bot setting
func (r *SettingsRepository) CreateBotSetting(setting *models.BotSetting) error {
	query := "INSERT INTO bot_settings (section, \"key\", value, value_type, description, default_value, is_active, version, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id"

	now := time.Now()
	err := r.db.QueryRow(
		query,
		setting.Section,
		setting.Key,
		setting.Value,
		setting.ValueType,
		setting.Description,
		setting.DefaultValue,
		setting.IsActive,
		setting.Version,
		now,
		now,
	).Scan(&setting.ID)
	if err != nil {
		return fmt.Errorf("failed to create bot setting: %w", err)
	}
	setting.CreatedAt = now
	setting.UpdatedAt = now

	return nil
}

// GetBotSettingByID retrieves a bot setting by ID
func (r *SettingsRepository) GetBotSettingByID(id int) (*models.BotSetting, error) {
	query := "SELECT id, section, \"key\", value, value_type, description, default_value, is_active, version, created_at, updated_at FROM bot_settings WHERE id = $1 LIMIT 1"

	setting, err := scanBotSetting(r.db.QueryRow(query, id))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get bot setting: %w", err)
	}

	return setting, nil
}

// GetBotSettingBySectionAndKey retrieves a bot setting by section and key
func (r *SettingsRepository) GetBotSettingBySectionAndKey(section, key string) (*models.BotSetting, error) {
	query := "SELECT id, section, \"key\", value, value_type, description, default_value, is_active, version, created_at, updated_at FROM bot_settings WHERE section = $1 AND \"key\" = $2 LIMIT 1"

	setting, err := scanBotSetting(r.db.QueryRow(query, section, key))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get bot setting: %w", err)
	}

	return setting, nil
}

// GetBotSettingsBySection retrieves all settings in a section
func (r *SettingsRepository) GetBotSettingsBySection(section string) ([]models.BotSetting, error) {
	query := "SELECT id, section, \"key\", value, value_type, description, default_value, is_active, version, created_at, updated_at FROM bot_settings WHERE section = $1 ORDER BY \"key\" ASC"

	rows, err := r.db.Query(query, section)
	if err != nil {
		return nil, fmt.Errorf("failed to query bot settings: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close bot setting rows: %v", closeErr)
		}
	}()

	var settings []models.BotSetting
	for rows.Next() {
		setting, err := scanBotSetting(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bot setting: %w", err)
		}
		settings = append(settings, *setting)
	}

	return settings, rows.Err()
}

// GetAllBotSettings retrieves all bot settings
func (r *SettingsRepository) GetAllBotSettings() ([]models.BotSetting, error) {
	query := "SELECT id, section, \"key\", value, value_type, description, default_value, is_active, version, created_at, updated_at FROM bot_settings ORDER BY section, \"key\" ASC"

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query all bot settings: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close all bot setting rows: %v", closeErr)
		}
	}()

	var settings []models.BotSetting
	for rows.Next() {
		setting, err := scanBotSetting(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bot setting: %w", err)
		}
		settings = append(settings, *setting)
	}

	return settings, rows.Err()
}

// UpdateBotSetting updates an existing bot setting
func (r *SettingsRepository) UpdateBotSetting(setting *models.BotSetting) error {
	query := `
		UPDATE bot_settings
		SET value = $1, description = $2, is_active = $3, version = $4, updated_at = $5
		WHERE id = $6
	`

	now := time.Now()
	result, err := r.db.Exec(query, setting.Value, setting.Description, setting.IsActive, setting.Version, now, setting.ID)
	if err != nil {
		return fmt.Errorf("failed to update bot setting: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("bot setting not found")
	}

	setting.UpdatedAt = now
	return nil
}

// DeleteBotSetting deletes a bot setting
func (r *SettingsRepository) DeleteBotSetting(id int) error {
	query := `DELETE FROM bot_settings WHERE id = $1`

	result, err := r.db.Exec(query, id)
	if err != nil {
		return fmt.Errorf("failed to delete bot setting: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("bot setting not found")
	}

	return nil
}

// ============ RedisSetting Operations ============

// CreateRedisSetting creates a new redis setting
func (r *SettingsRepository) CreateRedisSetting(setting *models.RedisSetting) error {
	query := "\n\t\tINSERT INTO redis_settings (enabled, host, port, db, password, \"ssl\", created_at, updated_at)\n\t\tVALUES ($1, $2, $3, $4, $5, $6, $7, $8)\n\t\tRETURNING id\n\t"

	now := time.Now()
	err := r.db.QueryRow(
		query,
		setting.Enabled,
		setting.Host,
		setting.Port,
		setting.Db,
		setting.Password,
		setting.SSL,
		now,
		now,
	).Scan(&setting.ID)
	if err != nil {
		return fmt.Errorf("failed to create redis setting: %w", err)
	}
	setting.CreatedAt = now
	setting.UpdatedAt = now

	return nil
}

// GetRedisSetting retrieves redis settings (usually only one row)
func (r *SettingsRepository) GetRedisSetting() (*models.RedisSetting, error) {
	query := "\n\t\tSELECT id, enabled, host, port, db, password, \"ssl\", created_at, updated_at\n\t\tFROM redis_settings\n\t\tLIMIT 1\n\t"

	setting := &models.RedisSetting{}
	err := r.db.QueryRow(query).Scan(
		&setting.ID,
		&setting.Enabled,
		&setting.Host,
		&setting.Port,
		&setting.Db,
		&setting.Password,
		&setting.SSL,
		&setting.CreatedAt,
		&setting.UpdatedAt,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get redis setting: %w", err)
	}

	return setting, nil
}

// UpdateRedisSetting updates redis settings
func (r *SettingsRepository) UpdateRedisSetting(setting *models.RedisSetting) error {
	query := "\n\t\tUPDATE redis_settings\n\t\tSET enabled = $1, host = $2, port = $3, db = $4, password = $5, \"ssl\" = $6, updated_at = $7\n\t\tWHERE id = $8\n\t"

	now := time.Now()
	result, err := r.db.Exec(query, setting.Enabled, setting.Host, setting.Port, setting.Db, setting.Password, setting.SSL, now, setting.ID)
	if err != nil {
		return fmt.Errorf("failed to update redis setting: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("redis setting not found")
	}

	setting.UpdatedAt = now
	return nil
}
