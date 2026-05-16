package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/redis/go-redis/v9"
)

// CacheService manages all cache operations
type CacheService struct {
	client *redis.Client
}

const defaultRedisOperationTimeout = 5 * time.Second

func (cs *CacheService) contextWithTimeout() (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), defaultRedisOperationTimeout)
}

// NewCacheService creates a new cache service
func NewCacheService(redisHost string, redisPort int, redisPassword string, redisDB int) *CacheService {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", redisHost, redisPort),
		Password: redisPassword,
		DB:       redisDB,
	})

	// Test connection
	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		slog.Warn("redis connection failed", "error", err)
	}

	return &CacheService{
		client: client,
	}
}

// SetCache sets a value in cache with optional TTL
func (cs *CacheService) SetCache(key string, value interface{}, ttlSeconds int) error {
	jsonData, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal value: %w", err)
	}

	ctx, cancel := cs.contextWithTimeout()
	defer cancel()
	ttl := time.Duration(ttlSeconds) * time.Second

	err = cs.client.Set(ctx, key, jsonData, ttl).Err()
	if err != nil {
		return fmt.Errorf("failed to set cache: %w", err)
	}

	slog.Debug("cache set", "key", key, "ttl_seconds", ttlSeconds)
	return nil
}

// GetCache retrieves a value from cache
func (cs *CacheService) GetCache(key string) (interface{}, error) {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	val, err := cs.client.Get(ctx, key).Result()
	if errors.Is(err, redis.Nil) {
		return nil, nil // Key doesn't exist
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get cache: %w", err)
	}

	var data interface{}
	if err := json.Unmarshal([]byte(val), &data); err != nil {
		return nil, fmt.Errorf("failed to unmarshal cache value: %w", err)
	}

	slog.Debug("cache hit", "key", key)
	return data, nil
}

// GetCacheString retrieves a string value from cache
func (cs *CacheService) GetCacheString(key string) (string, error) {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	val, err := cs.client.Get(ctx, key).Result()
	if errors.Is(err, redis.Nil) {
		slog.Debug("cache miss", "key", key)
		return "", nil
	}
	if err != nil {
		slog.Error("cache get error", "key", key, "error", err)
		return "", fmt.Errorf("failed to get cache: %w", err)
	}

	slog.Debug("cache hit", "key", key)
	return val, nil
}

// DeleteCache deletes a key from cache
func (cs *CacheService) DeleteCache(key string) error {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	err := cs.client.Del(ctx, key).Err()
	if err != nil {
		return fmt.Errorf("failed to delete cache: %w", err)
	}

	slog.Debug("cache deleted", "key", key)
	return nil
}

// DeleteCachePattern deletes all keys matching a pattern
func (cs *CacheService) DeleteCachePattern(pattern string) error {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	var (
		cursor      uint64
		removedKeys int
	)

	for {
		keys, nextCursor, err := cs.client.Scan(ctx, cursor, pattern, 200).Result()
		if err != nil {
			return fmt.Errorf("failed to scan keys: %w", err)
		}

		if len(keys) > 0 {
			if err := cs.client.Del(ctx, keys...).Err(); err != nil {
				return fmt.Errorf("failed to delete keys: %w", err)
			}
			removedKeys += len(keys)
		}

		cursor = nextCursor
		if cursor == 0 {
			break
		}
	}

	if removedKeys > 0 {
		slog.Info("cache pattern deleted", "pattern", pattern, "removed_keys", removedKeys)
	}

	return nil
}

// ClearAllCache clears entire cache
func (cs *CacheService) ClearAllCache() error {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	err := cs.client.FlushDB(ctx).Err()
	if err != nil {
		return fmt.Errorf("failed to clear cache: %w", err)
	}

	slog.Info("cache cleared")
	return nil
}

// GetCacheStats returns cache statistics
func (cs *CacheService) GetCacheStats() map[string]interface{} {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	info := cs.client.Info(ctx, "stats")
	keys := cs.client.DBSize(ctx)

	return map[string]interface{}{
		"info":    info.Val(),
		"db_size": keys.Val(),
		"status":  "operational",
	}
}

// ExistsInCache checks if a key exists in cache
func (cs *CacheService) ExistsInCache(key string) (bool, error) {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	exists, err := cs.client.Exists(ctx, key).Result()
	if err != nil {
		return false, fmt.Errorf("failed to check cache key: %w", err)
	}

	return exists > 0, nil
}

// GetCacheTTL gets the remaining TTL for a key
func (cs *CacheService) GetCacheTTL(key string) (time.Duration, error) {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	ttl, err := cs.client.TTL(ctx, key).Result()
	if err != nil {
		return 0, fmt.Errorf("failed to get TTL: %w", err)
	}

	return ttl, nil
}

// IncrementCounter increments a counter in cache
func (cs *CacheService) IncrementCounter(key string, increment int64) error {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	err := cs.client.IncrBy(ctx, key, increment).Err()
	if err != nil {
		return fmt.Errorf("failed to increment counter: %w", err)
	}

	return nil
}

// GetCounter gets a counter value from cache
func (cs *CacheService) GetCounter(key string) (int64, error) {
	ctx, cancel := cs.contextWithTimeout()
	defer cancel()

	val, err := cs.client.Get(ctx, key).Int64()
	if errors.Is(err, redis.Nil) {
		return 0, nil
	}
	if err != nil {
		return 0, fmt.Errorf("failed to get counter: %w", err)
	}

	return val, nil
}

// Close closes the Redis connection
func (cs *CacheService) Close() error {
	if cs.client != nil {
		return cs.client.Close()
	}
	return nil
}
