package services

import (
	"sync"
	"time"
)

const (
	evidenceRunCacheTTL  = 12 * time.Hour
	evidenceRunCacheSize = 256
)

// evidenceRunCache keeps the full per-pair ledger of completed runs. A
// completed run never changes, so a hit is served for the TTL without a bot
// call; concurrent builds of the same key share one fetch.
type evidenceRunCache struct {
	mu       sync.Mutex
	ttl      time.Duration
	capacity int
	entries  map[string]*evidenceRunCacheEntry
	inflight map[string]*evidenceRunCacheCall
	now      func() time.Time
}

type evidenceRunCacheEntry struct {
	ledger   *EvidenceLedger
	expires  time.Time
	lastUsed time.Time
}

type evidenceRunCacheCall struct {
	done   chan struct{}
	ledger *EvidenceLedger
	err    error
}

func newEvidenceRunCache(ttl time.Duration, capacity int) *evidenceRunCache {
	return &evidenceRunCache{
		ttl:      ttl,
		capacity: capacity,
		entries:  make(map[string]*evidenceRunCacheEntry),
		inflight: make(map[string]*evidenceRunCacheCall),
		now:      time.Now,
	}
}

// getOrBuild returns the cached ledger of key or builds it with build once,
// sharing the result with concurrent callers. Failed builds are not cached.
func (c *evidenceRunCache) getOrBuild(key string, build func() (*EvidenceLedger, error)) (*EvidenceLedger, error) {
	if c == nil {
		return build()
	}
	c.mu.Lock()
	now := c.now()
	if entry, ok := c.entries[key]; ok {
		if now.Before(entry.expires) {
			entry.lastUsed = now
			c.mu.Unlock()
			return entry.ledger, nil
		}
		delete(c.entries, key)
	}
	if call, ok := c.inflight[key]; ok {
		c.mu.Unlock()
		<-call.done
		return call.ledger, call.err
	}
	call := &evidenceRunCacheCall{done: make(chan struct{})}
	c.inflight[key] = call
	c.mu.Unlock()

	call.ledger, call.err = build()

	c.mu.Lock()
	delete(c.inflight, key)
	if call.err == nil && call.ledger != nil {
		c.evictLocked()
		c.entries[key] = &evidenceRunCacheEntry{ledger: call.ledger, expires: c.now().Add(c.ttl), lastUsed: c.now()}
	}
	c.mu.Unlock()
	close(call.done)
	return call.ledger, call.err
}

// evictLocked drops expired entries, then the least recently used one while
// the cache is full.
func (c *evidenceRunCache) evictLocked() {
	now := c.now()
	for key, entry := range c.entries {
		if !now.Before(entry.expires) {
			delete(c.entries, key)
		}
	}
	for len(c.entries) >= c.capacity && c.capacity > 0 {
		oldestKey := ""
		var oldest time.Time
		for key, entry := range c.entries {
			if oldestKey == "" || entry.lastUsed.Before(oldest) {
				oldestKey, oldest = key, entry.lastUsed
			}
		}
		delete(c.entries, oldestKey)
	}
}

// size reports the number of cached ledgers.
func (c *evidenceRunCache) size() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.entries)
}
