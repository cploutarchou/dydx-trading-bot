package repository

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

type PartnerCommissionMetricRepository struct {
	db *sql.DB
}

func NewPartnerCommissionMetricRepository(db *sql.DB) *PartnerCommissionMetricRepository {
	return &PartnerCommissionMetricRepository{db: db}
}

func (r *PartnerCommissionMetricRepository) Upsert(metric *models.PartnerCommissionMetric) error {
	query := `
		INSERT INTO partner_commission_metrics (
			user_id,
			period_start,
			period_end,
			direct_clients,
			sub_ib_count,
			notional_volume_usd,
			gross_commission_usd,
			rebate_usd,
			net_commission_usd,
			created_at,
			updated_at
		)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10)
		ON CONFLICT (user_id, period_start, period_end) DO UPDATE SET
			direct_clients = EXCLUDED.direct_clients,
			sub_ib_count = EXCLUDED.sub_ib_count,
			notional_volume_usd = EXCLUDED.notional_volume_usd,
			gross_commission_usd = EXCLUDED.gross_commission_usd,
			rebate_usd = EXCLUDED.rebate_usd,
			net_commission_usd = EXCLUDED.net_commission_usd,
			updated_at = EXCLUDED.updated_at
		RETURNING id, created_at, updated_at
	`

	now := time.Now().UTC()
	if metric.PeriodStart.IsZero() {
		metric.PeriodStart = now.AddDate(0, 0, -30)
	}
	if metric.PeriodEnd.IsZero() {
		metric.PeriodEnd = now
	}

	if err := r.db.QueryRow(
		query,
		metric.UserID,
		metric.PeriodStart,
		metric.PeriodEnd,
		metric.DirectClients,
		metric.SubIBCount,
		metric.NotionalVolumeUSD,
		metric.GrossCommissionUSD,
		metric.RebateUSD,
		metric.NetCommissionUSD,
		now,
	).Scan(&metric.ID, &metric.CreatedAt, &metric.UpdatedAt); err != nil {
		return fmt.Errorf("failed to upsert partner commission metric: %w", err)
	}

	return nil
}

func (r *PartnerCommissionMetricRepository) GetLatestByUser(userID int) (*models.PartnerCommissionMetric, error) {
	query := `
		SELECT id, user_id, period_start, period_end, direct_clients, sub_ib_count,
		       notional_volume_usd, gross_commission_usd, rebate_usd, net_commission_usd,
		       created_at, updated_at
		FROM partner_commission_metrics
		WHERE user_id = $1
		ORDER BY period_end DESC, updated_at DESC
		LIMIT 1
	`

	metric := &models.PartnerCommissionMetric{}
	if err := r.db.QueryRow(query, userID).Scan(
		&metric.ID,
		&metric.UserID,
		&metric.PeriodStart,
		&metric.PeriodEnd,
		&metric.DirectClients,
		&metric.SubIBCount,
		&metric.NotionalVolumeUSD,
		&metric.GrossCommissionUSD,
		&metric.RebateUSD,
		&metric.NetCommissionUSD,
		&metric.CreatedAt,
		&metric.UpdatedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to load commission metrics: %w", err)
	}

	return metric, nil
}

func (r *PartnerCommissionMetricRepository) ListByUser(userID int, limit int, offset int) ([]*models.PartnerCommissionMetric, error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	if offset < 0 {
		offset = 0
	}
	rows, err := r.db.Query(`
		SELECT id, user_id, period_start, period_end, direct_clients, sub_ib_count,
		       notional_volume_usd, gross_commission_usd, rebate_usd, net_commission_usd,
		       created_at, updated_at
		FROM partner_commission_metrics
		WHERE user_id = $1
		ORDER BY period_end DESC, updated_at DESC
		LIMIT $2 OFFSET $3
	`, userID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list commission metrics: %w", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			log.Printf("failed to close commission metric rows: %v", closeErr)
		}
	}()

	metrics := []*models.PartnerCommissionMetric{}
	for rows.Next() {
		metric := &models.PartnerCommissionMetric{}
		if err := rows.Scan(
			&metric.ID,
			&metric.UserID,
			&metric.PeriodStart,
			&metric.PeriodEnd,
			&metric.DirectClients,
			&metric.SubIBCount,
			&metric.NotionalVolumeUSD,
			&metric.GrossCommissionUSD,
			&metric.RebateUSD,
			&metric.NetCommissionUSD,
			&metric.CreatedAt,
			&metric.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan commission metric: %w", err)
		}
		metrics = append(metrics, metric)
	}
	return metrics, rows.Err()
}

func (r *PartnerCommissionMetricRepository) AggregateByUsers(userIDs []int) (*models.PartnerCommissionMetric, error) {
	if len(userIDs) == 0 {
		return &models.PartnerCommissionMetric{}, nil
	}

	placeholders := make([]string, 0, len(userIDs))
	args := make([]interface{}, 0, len(userIDs))
	for idx, userID := range userIDs {
		placeholders = append(placeholders, fmt.Sprintf("$%d", idx+1))
		args = append(args, userID)
	}

	query := fmt.Sprintf(`
		SELECT
			COALESCE(SUM(direct_clients), 0),
			COALESCE(SUM(sub_ib_count), 0),
			COALESCE(SUM(notional_volume_usd), 0),
			COALESCE(SUM(gross_commission_usd), 0),
			COALESCE(SUM(rebate_usd), 0),
			COALESCE(SUM(net_commission_usd), 0)
		FROM partner_commission_metrics
		WHERE user_id IN (%s)
	`, joinComma(placeholders))

	aggregate := &models.PartnerCommissionMetric{}
	if err := r.db.QueryRow(query, args...).Scan(
		&aggregate.DirectClients,
		&aggregate.SubIBCount,
		&aggregate.NotionalVolumeUSD,
		&aggregate.GrossCommissionUSD,
		&aggregate.RebateUSD,
		&aggregate.NetCommissionUSD,
	); err != nil {
		return nil, fmt.Errorf("failed to aggregate commission metrics: %w", err)
	}

	return aggregate, nil
}

func joinComma(values []string) string {
	if len(values) == 0 {
		return ""
	}
	joined := values[0]
	for i := 1; i < len(values); i++ {
		joined += ", " + values[i]
	}
	return joined
}
