package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

// CacheService manages all cache operations
type CacheService struct {
	client *redis.Client
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
		log.Printf("Warning: Redis connection failed: %v", err)
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

	ctx := context.Background()
	ttl := time.Duration(ttlSeconds) * time.Second

	err = cs.client.Set(ctx, key, jsonData, ttl).Err()
	if err != nil {
		return fmt.Errorf("failed to set cache: %w", err)
	}

	log.Printf("✅ Cache set: %s (TTL: %d seconds)", key, ttlSeconds)
	return nil
}

// GetCache retrieves a value from cache
func (cs *CacheService) GetCache(key string) (interface{}, error) {
	ctx := context.Background()

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

	log.Printf("✅ Cache hit: %s", key)
	return data, nil
}

// GetCacheString retrieves a string value from cache
func (cs *CacheService) GetCacheString(key string) (string, error) {
	ctx := context.Background()

	val, err := cs.client.Get(ctx, key).Result()
	if errors.Is(err, redis.Nil) {
		return "", nil
	}
	if err != nil {
		return "", fmt.Errorf("failed to get cache: %w", err)
	}

	return val, nil
}

// DeleteCache deletes a key from cache
func (cs *CacheService) DeleteCache(key string) error {
	ctx := context.Background()

	err := cs.client.Del(ctx, key).Err()
	if err != nil {
		return fmt.Errorf("failed to delete cache: %w", err)
	}

	log.Printf("✅ Cache deleted: %s", key)
	return nil
}

// DeleteCachePattern deletes all keys matching a pattern
func (cs *CacheService) DeleteCachePattern(pattern string) error {
	ctx := context.Background()

	keys, err := cs.client.Keys(ctx, pattern).Result()
	if err != nil {
		return fmt.Errorf("failed to find keys: %w", err)
	}

	if len(keys) > 0 {
		err = cs.client.Del(ctx, keys...).Err()
		if err != nil {
			return fmt.Errorf("failed to delete keys: %w", err)
		}
		log.Printf("✅ Cache pattern deleted: %s (removed %d keys)", pattern, len(keys))
	}

	return nil
}

// ClearAllCache clears entire cache
func (cs *CacheService) ClearAllCache() error {
	ctx := context.Background()

	err := cs.client.FlushDB(ctx).Err()
	if err != nil {
		return fmt.Errorf("failed to clear cache: %w", err)
	}

	log.Printf("✅ Cache cleared: All data removed")
	return nil
}

// GetCacheStats returns cache statistics
func (cs *CacheService) GetCacheStats() map[string]interface{} {
	ctx := context.Background()

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
	ctx := context.Background()

	exists, err := cs.client.Exists(ctx, key).Result()
	if err != nil {
		return false, fmt.Errorf("failed to check cache key: %w", err)
	}

	return exists > 0, nil
}

// GetCacheTTL gets the remaining TTL for a key
func (cs *CacheService) GetCacheTTL(key string) (time.Duration, error) {
	ctx := context.Background()

	ttl, err := cs.client.TTL(ctx, key).Result()
	if err != nil {
		return 0, fmt.Errorf("failed to get TTL: %w", err)
	}

	return ttl, nil
}

// IncrementCounter increments a counter in cache
func (cs *CacheService) IncrementCounter(key string, increment int64) error {
	ctx := context.Background()

	err := cs.client.IncrBy(ctx, key, increment).Err()
	if err != nil {
		return fmt.Errorf("failed to increment counter: %w", err)
	}

	return nil
}

// GetCounter gets a counter value from cache
func (cs *CacheService) GetCounter(key string) (int64, error) {
	ctx := context.Background()

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
