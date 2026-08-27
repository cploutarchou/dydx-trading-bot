package auth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/tls"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/redis/go-redis/v9"
)

const SessionCookieName = "dydx_session"

var ErrSessionNotFound = errors.New("session not found")

type SessionData struct {
	UserID    int    `json:"user_id"`
	Username  string `json:"username"`
	Email     string `json:"email"`
	Role      string `json:"role"`
	IsAdmin   bool   `json:"is_admin"`
	// MFARequired marks a session created by a password-only login for a user
	// with TOTP enrolled: the session stays unusable (MFAPending) until the
	// 2FA challenge endpoint records MFAVerifiedAt.
	MFARequired bool `json:"mfa_required,omitempty"`
	// MFAVerifiedAt records when the TOTP challenge completed for this session.
	MFAVerifiedAt *time.Time `json:"mfa_verified_at,omitempty"`
	// ChallengeAttempts counts failed TOTP challenges against a pending
	// session; the session is deleted once it reaches maxMFAPreAuthAttempts.
	ChallengeAttempts int       `json:"challenge_attempts,omitempty"`
	CreatedAt         time.Time `json:"created_at"`
	ExpiresAt         time.Time `json:"expires_at"`
}

// MaxMFAPreAuthAttempts bounds how many TOTP codes may be tried against a
// single pending login session before the user must authenticate again.
const MaxMFAPreAuthAttempts = 5

// MFAPending reports whether the session still awaits a successful TOTP
// challenge. Sessions issued before login-time MFA enforcement (or when the
// user has no MFA enrolled) are never pending.
func (d *SessionData) MFAPending() bool {
	return d != nil && d.MFARequired && d.MFAVerifiedAt == nil
}

type memorySession struct {
	data      SessionData
	expiresAt time.Time
}

type SessionStore struct {
	redisClient *redis.Client
	prefix      string
	mu          sync.RWMutex
	memory      map[string]memorySession
}

func NewSessionStore(cfg *config.Config) *SessionStore {
	store := &SessionStore{
		prefix: "auth:session:",
		memory: make(map[string]memorySession),
	}

	if cfg == nil || !cfg.Redis.Enabled {
		log.Printf("Auth sessions using in-memory store because Redis is disabled")
		return store
	}

	opts := &redis.Options{
		Addr:         fmt.Sprintf("%s:%d", cfg.Redis.Host, cfg.Redis.Port),
		Password:     cfg.Redis.Password,
		DB:           cfg.Redis.DB,
		Protocol:     2,
		PoolSize:     cfg.Redis.MaxConnections,
		DialTimeout:  time.Duration(cfg.Redis.Timeout) * time.Second,
		ReadTimeout:  time.Duration(cfg.Redis.Timeout) * time.Second,
		WriteTimeout: time.Duration(cfg.Redis.Timeout) * time.Second,
	}
	if cfg.Redis.SSL {
		opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
	}

	client := redis.NewClient(opts)
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(cfg.Redis.Timeout)*time.Second)
	defer cancel()
	if err := client.Ping(ctx).Err(); err != nil {
		if requireRedisSessions() {
			log.Fatalf("Redis auth session store is required but unavailable: %v", err)
		}
		log.Printf("Warning: Redis auth session store unavailable, using in-memory fallback: %v", err)
		_ = client.Close()
		return store
	}

	store.redisClient = client
	log.Printf("Auth sessions using Redis at %s db=%d", opts.Addr, cfg.Redis.DB)
	return store
}

func requireRedisSessions() bool {
	value := strings.TrimSpace(strings.ToLower(os.Getenv("AUTH_REQUIRE_REDIS_SESSIONS")))
	if value == "true" || value == "1" || value == "yes" {
		return true
	}
	return strings.EqualFold(os.Getenv("APP_ENV"), "production")
}

func (s *SessionStore) Create(ctx context.Context, data SessionData, ttl time.Duration) (string, SessionData, error) {
	if ttl <= 0 {
		return "", SessionData{}, fmt.Errorf("session ttl must be positive")
	}

	token, err := newOpaqueSessionToken()
	if err != nil {
		return "", SessionData{}, err
	}

	now := time.Now().UTC()
	data.CreatedAt = now
	data.ExpiresAt = now.Add(ttl)

	if err := s.save(ctx, token, data, ttl); err != nil {
		return "", SessionData{}, err
	}

	return token, data, nil
}

func (s *SessionStore) Get(ctx context.Context, token string) (*SessionData, error) {
	key := s.key(token)
	if key == "" {
		return nil, ErrSessionNotFound
	}

	if s.redisClient != nil {
		raw, err := s.redisClient.Get(ctx, key).Result()
		if errors.Is(err, redis.Nil) {
			return nil, ErrSessionNotFound
		}
		if err != nil {
			return nil, err
		}

		var data SessionData
		if err := json.Unmarshal([]byte(raw), &data); err != nil {
			return nil, err
		}
		if time.Now().UTC().After(data.ExpiresAt) {
			_ = s.Delete(ctx, token)
			return nil, ErrSessionNotFound
		}
		return &data, nil
	}

	s.mu.RLock()
	item, ok := s.memory[key]
	s.mu.RUnlock()
	if !ok || time.Now().UTC().After(item.expiresAt) {
		if ok {
			_ = s.Delete(ctx, token)
		}
		return nil, ErrSessionNotFound
	}
	data := item.data
	return &data, nil
}

func (s *SessionStore) Refresh(ctx context.Context, token string, ttl time.Duration) (*SessionData, error) {
	data, err := s.Get(ctx, token)
	if err != nil {
		return nil, err
	}

	data.ExpiresAt = time.Now().UTC().Add(ttl)
	if err := s.save(ctx, token, *data, ttl); err != nil {
		return nil, err
	}
	return data, nil
}

// Update persists modified session data under the existing token. The TTL is
// derived from the record's own ExpiresAt, so callers control the resulting
// lifetime explicitly (e.g. failed-challenge counters keep the original
// expiry, while MFA promotion extends to the full session TTL).
func (s *SessionStore) Update(ctx context.Context, token string, data SessionData) error {
	ttl := time.Until(data.ExpiresAt)
	if ttl <= 0 {
		return ErrSessionNotFound
	}
	return s.save(ctx, token, data, ttl)
}

func (s *SessionStore) Delete(ctx context.Context, token string) error {
	key := s.key(token)
	if key == "" {
		return nil
	}

	if s.redisClient != nil {
		return s.redisClient.Del(ctx, key).Err()
	}

	s.mu.Lock()
	delete(s.memory, key)
	s.mu.Unlock()
	return nil
}

func (s *SessionStore) save(ctx context.Context, token string, data SessionData, ttl time.Duration) error {
	key := s.key(token)
	if key == "" {
		return ErrSessionNotFound
	}

	if s.redisClient != nil {
		raw, err := json.Marshal(data)
		if err != nil {
			return err
		}
		return s.redisClient.Set(ctx, key, raw, ttl).Err()
	}

	s.mu.Lock()
	s.memory[key] = memorySession{data: data, expiresAt: data.ExpiresAt}
	s.mu.Unlock()
	return nil
}

func (s *SessionStore) key(token string) string {
	if token == "" {
		return ""
	}
	sum := sha256.Sum256([]byte(token))
	return s.prefix + hex.EncodeToString(sum[:])
}

func newOpaqueSessionToken() (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("generate session token: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}
