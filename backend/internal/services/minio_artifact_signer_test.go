package services

import (
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
)

func TestNewMinIOArtifactSignerReturnsNilWithoutRequiredConfig(t *testing.T) {
	signer, err := NewMinIOArtifactSigner(config.MinIOSettings{
		Enabled:  true,
		Endpoint: "minio.internal:9000",
	})
	if err != nil {
		t.Fatalf("expected nil signer without error, got err=%v", err)
	}
	if signer != nil {
		t.Fatalf("expected nil signer when credentials are missing")
	}
}

func TestMinIOArtifactSignerPresignGet(t *testing.T) {
	signer, err := NewMinIOArtifactSigner(config.MinIOSettings{
		Enabled:   true,
		Endpoint:  "minio.internal:9000",
		Bucket:    "backtests",
		AccessKey: "access-key",
		SecretKey: "secret-key",
	})
	if err != nil {
		t.Fatalf("create signer: %v", err)
	}
	signer.clock = func() time.Time {
		return time.Date(2026, time.June, 28, 10, 30, 45, 0, time.UTC)
	}

	signedURL, expiresAt, err := signer.PresignGet("backtests", "backtests/run-1/full_result.json", 10*time.Minute)
	if err != nil {
		t.Fatalf("presign get: %v", err)
	}

	if got, want := expiresAt, time.Date(2026, time.June, 28, 10, 40, 45, 0, time.UTC); !got.Equal(want) {
		t.Fatalf("expected expiresAt=%s, got %s", want, got)
	}

	parsed, err := url.Parse(signedURL)
	if err != nil {
		t.Fatalf("parse signed url: %v", err)
	}
	if parsed.Scheme != "http" || parsed.Host != "minio.internal:9000" {
		t.Fatalf("unexpected signed url endpoint: %s", signedURL)
	}
	if parsed.Path != "/backtests/backtests/run-1/full_result.json" {
		t.Fatalf("unexpected signed url path: %s", parsed.Path)
	}

	query := parsed.Query()
	if query.Get("X-Amz-Algorithm") != "AWS4-HMAC-SHA256" {
		t.Fatalf("missing signing algorithm query param: %s", signedURL)
	}
	if query.Get("X-Amz-Expires") != "600" {
		t.Fatalf("expected 600 second expiry, got %q", query.Get("X-Amz-Expires"))
	}
	if !strings.Contains(query.Get("X-Amz-Credential"), "access-key/20260628/us-east-1/s3/aws4_request") {
		t.Fatalf("unexpected credential scope: %q", query.Get("X-Amz-Credential"))
	}
	if signature := query.Get("X-Amz-Signature"); len(signature) != 64 {
		t.Fatalf("expected hex signature, got %q", signature)
	}
}
