package middleware

import (
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gin-gonic/gin"
)

type tokenBucket struct {
	tokens    float64
	lastRefil time.Time
	mu        sync.Mutex
}

type RateLimiter struct {
	mu                sync.RWMutex
	buckets           map[string]*tokenBucket
	rps               float64
	capacity          int
	lastCleanupUnix   int64
	requestCount uint64
}

func NewRateLimiter(rps float64, capacity int) *RateLimiter {
	return &RateLimiter{
		buckets:           make(map[string]*tokenBucket),
		rps:               rps,
		capacity:          capacity,
		lastCleanupUnix:   time.Now().Unix(),
	}
}

func (rl *RateLimiter) Allow(clientID string) bool {
	rl.mu.Lock()
	bucket, exists := rl.buckets[clientID]
	if !exists {
		bucket = &tokenBucket{
			tokens:    float64(rl.capacity),
			lastRefil: time.Now(),
		}
		rl.buckets[clientID] = bucket
	}
	rl.mu.Unlock()

	bucket.mu.Lock()
	defer bucket.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(bucket.lastRefil).Seconds()
	bucket.tokens = minFloat(float64(rl.capacity), bucket.tokens+elapsed*rl.rps)
	bucket.lastRefil = now

	if bucket.tokens >= 1 {
		bucket.tokens--
		return true
	}
	return false
}

func minFloat(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

func (rl *RateLimiter) Cleanup(maxAge time.Duration) {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	for id, bucket := range rl.buckets {
		bucket.mu.Lock()
		if now.Sub(bucket.lastRefil) > maxAge {
			delete(rl.buckets, id)
		}
		bucket.mu.Unlock()
	}
}

// rateLimiterCleanupEveryCalls samples cleanup once every N requests. A const
// replaces the lazily-written field, whose unsynchronized write raced Allows.
const rateLimiterCleanupEveryCalls = 512

func (rl *RateLimiter) MaybeCleanup(maxAge, interval time.Duration) {
	if atomic.AddUint64(&rl.requestCount, 1)%rateLimiterCleanupEveryCalls != 0 {
		return
	}

	now := time.Now()
	lastCleanup := time.Unix(atomic.LoadInt64(&rl.lastCleanupUnix), 0)
	if now.Sub(lastCleanup) < interval {
		return
	}

	rl.Cleanup(maxAge)
	atomic.StoreInt64(&rl.lastCleanupUnix, now.Unix())
}

func RateLimitMiddleware(requestsPerSecond float64, burstSize int) gin.HandlerFunc {
	limiter := NewRateLimiter(requestsPerSecond, burstSize)

	return func(c *gin.Context) {
		limiter.MaybeCleanup(24*time.Hour, time.Hour)
		clientIP := c.ClientIP()

		// Bypass rate limiting for local requests to avoid development-time 429s
		if clientIP == "::1" || clientIP == "127.0.0.1" || clientIP == "localhost" || strings.HasPrefix(clientIP, "127.") {
			c.Next()
			return
		}

		if !limiter.Allow(clientIP) {
			c.JSON(http.StatusTooManyRequests, gin.H{
				"success": false,
				"error":   "rate limit exceeded",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}
