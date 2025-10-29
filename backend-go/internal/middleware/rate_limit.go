package middleware

import (
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

type tokenBucket struct {
	tokens    float64
	lastRefil time.Time
	mu        sync.Mutex
}

type RateLimiter struct {
	mu       sync.RWMutex
	buckets  map[string]*tokenBucket
	rps      float64
	capacity int
}

func NewRateLimiter(rps float64, capacity int) *RateLimiter {
	return &RateLimiter{
		buckets:  make(map[string]*tokenBucket),
		rps:      rps,
		capacity: capacity,
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

func RateLimitMiddleware(requestsPerSecond float64, burstSize int) gin.HandlerFunc {
	limiter := NewRateLimiter(requestsPerSecond, burstSize)

	go func() {
		ticker := time.NewTicker(1 * time.Hour)
		defer ticker.Stop()
		for range ticker.C {
			limiter.Cleanup(24 * time.Hour)
		}
	}()

	return func(c *gin.Context) {
		clientIP := c.ClientIP()

		// Bypass rate limiting for local requests to avoid development-time 429s
		if clientIP == "::1" || clientIP == "127.0.0.1" || strings.HasPrefix(clientIP, "127.") {
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
