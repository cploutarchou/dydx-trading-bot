package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type IBTierCommissionRateRepository struct {
	db *sql.DB
}

func NewIBTierCommissionRateRepository(db *sql.DB) *IBTierCommissionRateRepository {
	return &IBTierCommissionRateRepository{db: db}
}

func (r *IBTierCommissionRateRepository) List() ([]*models.IBTierCommissionRate, error) {
	query := `
		SELECT id, tier_level, commission_rate_pct, rebate_rate_pct, description, is_active, created_by_user_id, created_at, updated_at
		FROM ib_tier_commission_rates
		ORDER BY tier_level ASC
	`
	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to list ib tier commission rates: %w", err)
	}
	defer func() { _ = rows.Close() }()

	var rates []*models.IBTierCommissionRate
	for rows.Next() {
		rate := &models.IBTierCommissionRate{}
		if err := rows.Scan(
			&rate.ID, &rate.TierLevel, &rate.CommissionRatePct, &rate.RebateRatePct,
			&rate.Description, &rate.IsActive, &rate.CreatedByUserID,
			&rate.CreatedAt, &rate.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan ib tier commission rate: %w", err)
		}
		rates = append(rates, rate)
	}
	return rates, rows.Err()
}

func (r *IBTierCommissionRateRepository) GetByTier(tierLevel int) (*models.IBTierCommissionRate, error) {
	query := `
		SELECT id, tier_level, commission_rate_pct, rebate_rate_pct, description, is_active, created_by_user_id, created_at, updated_at
		FROM ib_tier_commission_rates
		WHERE tier_level = $1
	`
	rate := &models.IBTierCommissionRate{}
	err := r.db.QueryRow(query, tierLevel).Scan(
		&rate.ID, &rate.TierLevel, &rate.CommissionRatePct, &rate.RebateRatePct,
		&rate.Description, &rate.IsActive, &rate.CreatedByUserID,
		&rate.CreatedAt, &rate.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get ib tier commission rate: %w", err)
	}
	return rate, nil
}

// Upsert inserts or updates a tier rate by tier_level.
func (r *IBTierCommissionRateRepository) Upsert(rate *models.IBTierCommissionRate) error {
	now := time.Now().UTC()
	query := `
		INSERT INTO ib_tier_commission_rates (
			tier_level, commission_rate_pct, rebate_rate_pct, description, is_active, created_by_user_id, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
		ON CONFLICT (tier_level) DO UPDATE SET
			commission_rate_pct = EXCLUDED.commission_rate_pct,
			rebate_rate_pct     = EXCLUDED.rebate_rate_pct,
			description         = EXCLUDED.description,
			is_active           = EXCLUDED.is_active,
			updated_at          = EXCLUDED.updated_at
		RETURNING id, created_at, updated_at
	`
	return r.db.QueryRow(
		query,
		rate.TierLevel,
		rate.CommissionRatePct,
		rate.RebateRatePct,
		rate.Description,
		rate.IsActive,
		rate.CreatedByUserID,
		now,
	).Scan(&rate.ID, &rate.CreatedAt, &rate.UpdatedAt)
}

func (r *IBTierCommissionRateRepository) DeleteByTier(tierLevel int) error {
	_, err := r.db.Exec(`DELETE FROM ib_tier_commission_rates WHERE tier_level = $1`, tierLevel)
	if err != nil {
		return fmt.Errorf("failed to delete ib tier commission rate for tier %d: %w", tierLevel, err)
	}
	return nil
}
