package services

import (
	"encoding/json"
	"fmt"
	"log"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

// CandleCacheService manages candle data caching
type CandleCacheService struct {
	cache *CacheService
}

// NewCandleCacheService creates a new candle cache service
func NewCandleCacheService(cache *CacheService) *CandleCacheService {
	return &CandleCacheService{
		cache: cache,
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

// PrefetchCandlesForRun prefetches all candles for a run from database
// This is typically called during backtest initialization
func (ccs *CandleCacheService) PrefetchCandlesForRun(runID int, ttlSeconds int) error {
	// This would typically call the backtest repository to fetch candles
	// Implementation depends on how candles are retrieved from the database
	log.Printf("Prefetching candles for run %d", runID)
	return nil
}

// WarmCache warms up the cache with frequently accessed data
func (ccs *CandleCacheService) WarmCache(runID int, markets []string, durationHours int) error {

	for _, market := range markets {
		// In a real implementation, fetch from database and cache
		// For now, just initialize the cache structure
		key := fmt.Sprintf("backtest:candles:%d:%s", runID, market)
		log.Printf("Warming cache for %s", key)
	}

	return nil
}
