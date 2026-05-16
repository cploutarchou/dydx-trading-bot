package services

import (
	"encoding/json"
	"fmt"
	"log"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// CandleCacheService manages candle data caching
type CandleCacheService struct {
	cache *CacheService
	repo  *repository.BacktestRepository
}

const candleCachePageSize = 1000

// NewCandleCacheService creates a new candle cache service
func NewCandleCacheService(cache *CacheService) *CandleCacheService {
	return &CandleCacheService{
		cache: cache,
	}
}

// NewCandleCacheServiceWithRepo creates a CandleCacheService with DB access for
// PrefetchCandlesForRun and WarmCache.
func NewCandleCacheServiceWithRepo(cache *CacheService, repo *repository.BacktestRepository) *CandleCacheService {
	return &CandleCacheService{
		cache: cache,
		repo:  repo,
	}
}

// CacheCandles caches backtest candle data
func (ccs *CandleCacheService) CacheCandles(runID int, market string, candles []models.BacktestCandle, ttlSeconds int) error {
	if len(candles) == 0 {
		return nil
	}

	key := fmt.Sprintf("backtest:candles:%d:%s", runID, market)

	candleData, err := json.Marshal(candles)
	if err != nil {
		return fmt.Errorf("failed to marshal candles: %w", err)
	}

	if ttlSeconds == 0 {
		ttlSeconds = 86400 // Default 24 hours
	}

	err = ccs.cache.SetCache(key, string(candleData), ttlSeconds)
	if err != nil {
		return fmt.Errorf("failed to cache candles: %w", err)
	}

	log.Printf("✅ Cached %d candles for run %d market %s (TTL: %d seconds)", len(candles), runID, market, ttlSeconds)
	return nil
}

// GetCachedCandles retrieves cached candle data
func (ccs *CandleCacheService) GetCachedCandles(runID int, market string) ([]models.BacktestCandle, error) {
	key := fmt.Sprintf("backtest:candles:%d:%s", runID, market)

	val, err := ccs.cache.GetCacheString(key)
	if err != nil {
		return nil, fmt.Errorf("failed to get cached candles: %w", err)
	}

	if val == "" {
		return nil, nil // Cache miss
	}

	var candles []models.BacktestCandle
	if err := json.Unmarshal([]byte(val), &candles); err != nil {
		return nil, fmt.Errorf("failed to unmarshal candles: %w", err)
	}

	log.Printf("✅ Cache hit: Retrieved %d candles for run %d market %s", len(candles), runID, market)
	return candles, nil
}

// InvalidateCandleCache invalidates candle cache for a run
func (ccs *CandleCacheService) InvalidateCandleCache(runID int) error {
	pattern := fmt.Sprintf("backtest:candles:%d:*", runID)
	return ccs.cache.DeleteCachePattern(pattern)
}

// InvalidateCandleCacheByMarket invalidates candle cache for a specific market
func (ccs *CandleCacheService) InvalidateCandleCacheByMarket(runID int, market string) error {
	key := fmt.Sprintf("backtest:candles:%d:%s", runID, market)
	return ccs.cache.DeleteCache(key)
}

// CacheCandlesMultiple caches candles for multiple markets
func (ccs *CandleCacheService) CacheCandlesMultiple(runID int, candlesByMarket map[string][]models.BacktestCandle, ttlSeconds int) error {
	for market, candles := range candlesByMarket {
		if err := ccs.CacheCandles(runID, market, candles, ttlSeconds); err != nil {
			return err
		}
	}
	return nil
}

// GetCacheSizeEstimate estimates cache size for run
func (ccs *CandleCacheService) GetCacheSizeEstimate(runID int, markets []string) map[string]interface{} {
	var totalCandles int
	var marketStats []map[string]interface{}

	for _, market := range markets {
		candles, err := ccs.GetCachedCandles(runID, market)
		if err == nil && candles != nil {
			totalCandles += len(candles)
			marketStats = append(marketStats, map[string]interface{}{
				"market":       market,
				"candle_count": len(candles),
			})
		}
	}

	// Rough estimation: ~500 bytes per candle
	estimatedSizeKB := (totalCandles * 500) / 1024

	return map[string]interface{}{
		"run_id":            runID,
		"total_candles":     totalCandles,
		"market_count":      len(markets),
		"estimated_size_kb": estimatedSizeKB,
		"market_statistics": marketStats,
	}
}

// GetCandlesCacheStats returns cache statistics for candles
func (ccs *CandleCacheService) GetCandlesCacheStats() map[string]interface{} {
	return ccs.cache.GetCacheStats()
}

// CacheCandle caches a single candle (for real-time updates)
func (ccs *CandleCacheService) CacheCandle(runID int, market string, candle models.BacktestCandle, ttlSeconds int) error {
	key := fmt.Sprintf("backtest:candle:latest:%d:%s", runID, market)

	if ttlSeconds == 0 {
		ttlSeconds = 3600 // 1 hour for single candles
	}

	return ccs.cache.SetCache(key, candle, ttlSeconds)
}

// GetLatestCandle retrieves the latest cached candle for a market
func (ccs *CandleCacheService) GetLatestCandle(runID int, market string) (*models.BacktestCandle, error) {
	key := fmt.Sprintf("backtest:candle:latest:%d:%s", runID, market)

	val, err := ccs.cache.GetCache(key)
	if err != nil {
		return nil, fmt.Errorf("failed to get latest candle: %w", err)
	}

	if val == nil {
		return nil, nil // Cache miss
	}

	// Convert interface{} to BacktestCandle
	candleJSON, _ := json.Marshal(val)
	var candle models.BacktestCandle
	if err := json.Unmarshal(candleJSON, &candle); err != nil {
		return nil, fmt.Errorf("failed to unmarshal candle: %w", err)
	}

	return &candle, nil
}

// GetAggregatedChart retrieves pre-aggregated OHLCV bars for a run+market+resolution
// from Redis (written by the Python aggregate_backtest_candles Celery task).
// Returns the raw JSON string (caller deserialises) and nil error on cache hit,
// or ("", nil) on cache miss, or ("", err) on Redis error.
// resolution must be "1min" or "1hour".
func (ccs *CandleCacheService) GetAggregatedChart(runID, market, resolution string) (string, error) {
	key := fmt.Sprintf("backtest:chart:%s:%s:%s", resolution, runID, market)
	val, err := ccs.cache.GetCacheString(key)
	if err != nil {
		return "", fmt.Errorf("GetAggregatedChart: %w", err)
	}
	return val, nil
}

// PrefetchCandlesForRun fetches all candles for a completed run from the
// backtest_candles table and stores them in Redis (24h TTL by default).
// Call this after a backtest completes so the first chart render is cache-warm.
func (ccs *CandleCacheService) PrefetchCandlesForRun(runID int, ttlSeconds int) error {
	if ccs.repo == nil {
		log.Printf("CandleCacheService: repo not set, skipping PrefetchCandlesForRun for run %d", runID)
		return nil
	}
	if ttlSeconds <= 0 {
		ttlSeconds = 86400 // 24 h
	}

	markets, err := ccs.repo.GetUniqueMarkets(runID)
	if err != nil {
		return fmt.Errorf("PrefetchCandlesForRun: get markets for run %d: %w", runID, err)
	}
	if len(markets) == 0 {
		log.Printf("CandleCacheService: no markets found for run %d, skipping prefetch", runID)
		return nil
	}

	for _, market := range markets {
		if err := ccs.cacheMarketCandlesInPages(runID, market, ttlSeconds); err != nil {
			log.Printf("CandleCacheService: failed to cache candles for run %d market %s: %v", runID, market, err)
		}
	}

	log.Printf("CandleCacheService: prefetch complete for run %d (%d markets)", runID, len(markets))
	return nil
}

// WarmCache batch-fetches candles for the given markets and caches them.
// durationHours is unused (the full candle history is always fetched) but kept
// for API compatibility.
func (ccs *CandleCacheService) WarmCache(runID int, markets []string, durationHours int) error {
	if ccs.repo == nil {
		log.Printf("CandleCacheService: repo not set, skipping WarmCache for run %d", runID)
		return nil
	}

	ttlSeconds := 86400 // 24 h

	for _, market := range markets {
		if err := ccs.cacheMarketCandlesInPages(runID, market, ttlSeconds); err != nil {
			log.Printf("CandleCacheService: WarmCache cache error for run %d market %s: %v", runID, market, err)
		}
	}

	log.Printf("CandleCacheService: WarmCache complete for run %d (%d markets)", runID, len(markets))
	return nil
}

func (ccs *CandleCacheService) cacheMarketCandlesInPages(runID int, market string, ttlSeconds int) error {
	offset := 0
	allCandles := make([]models.BacktestCandle, 0, candleCachePageSize)

	for {
		candles, err := ccs.repo.GetCandles(repository.CandleFilter{
			RunID:  runID,
			Market: market,
			Limit:  candleCachePageSize,
			Skip:   offset,
		})
		if err != nil {
			return err
		}

		if len(candles) == 0 {
			break
		}

		allCandles = append(allCandles, candles...)
		offset += len(candles)

		if len(candles) < candleCachePageSize {
			break
		}
	}

	if len(allCandles) == 0 {
		return nil
	}

	return ccs.CacheCandles(runID, market, allCandles, ttlSeconds)
}
