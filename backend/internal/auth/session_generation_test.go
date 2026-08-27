package auth

import (
	"context"
	"errors"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
)

// TestSessionStore_GenerationRevocation verifies that bumping a user's
// generation invalidates previously issued sessions while allowing new ones.
func TestSessionStore_GenerationRevocation(t *testing.T) {
	store := NewSessionStore(&config.Config{}) // Redis disabled → memory store
	ctx := context.Background()

	token, data, err := store.Create(ctx, SessionData{UserID: 42, Username: "alice"}, 60_000_000_000)
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if data.Generation != 0 {
		t.Fatalf("expected initial generation 0, got %d", data.Generation)
	}

	if _, err := store.Get(ctx, token); err != nil {
		t.Fatalf("session should be valid before revocation: %v", err)
	}

	if err := store.BumpUserGeneration(ctx, 42); err != nil {
		t.Fatalf("BumpUserGeneration: %v", err)
	}

	if _, err := store.Get(ctx, token); !errors.Is(err, ErrSessionNotFound) {
		t.Fatalf("session must be revoked after generation bump, got %v", err)
	}

	// Sessions issued after the bump carry the new generation and work.
	token2, data2, err := store.Create(ctx, SessionData{UserID: 42, Username: "alice"}, 60_000_000_000)
	if err != nil {
		t.Fatalf("Create after bump: %v", err)
	}
	if data2.Generation <= data.Generation {
		t.Fatalf("expected generation to advance, got %d then %d", data.Generation, data2.Generation)
	}
	if _, err := store.Get(ctx, token2); err != nil {
		t.Fatalf("post-bump session must be valid: %v", err)
	}

	// Other users are unaffected.
	otherToken, _, err := store.Create(ctx, SessionData{UserID: 43, Username: "bob"}, 60_000_000_000)
	if err != nil {
		t.Fatalf("Create other user: %v", err)
	}
	if _, err := store.Get(ctx, otherToken); err != nil {
		t.Fatalf("other user's session must remain valid: %v", err)
	}
}
