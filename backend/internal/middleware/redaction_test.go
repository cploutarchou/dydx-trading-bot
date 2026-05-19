package middleware

import (
	"net/http"
	"testing"
)

func TestSanitizeHeadersMasksSensitiveValues(t *testing.T) {
	headers := http.Header{
		"Authorization": []string{"Bearer secret-token"},
		"Cookie":        []string{"session=secret"},
		"X-Trace-Id":    []string{"req-123"},
	}

	sanitized := SanitizeHeaders(headers)

	if got := sanitized["Authorization"]; got != "Bearer <masked>" {
		t.Fatalf("Authorization = %q, want Bearer <masked>", got)
	}
	if got := sanitized["Cookie"]; got != "<masked>" {
		t.Fatalf("Cookie = %q, want <masked>", got)
	}
	if got := sanitized["X-Trace-Id"]; got != "req-123" {
		t.Fatalf("X-Trace-Id = %q, want req-123", got)
	}
}

func TestRedactSensitiveRawQueryMasksTokens(t *testing.T) {
	redacted := RedactSensitiveRawQuery("foo=bar&access_token=abc123&refresh_token=refresh123")

	if redacted == "" {
		t.Fatal("expected non-empty redacted query")
	}
	if redacted == "foo=bar&access_token=abc123&refresh_token=refresh123" {
		t.Fatal("expected sensitive query parameters to be redacted")
	}
	if want := "access_token=%3Cmasked%3E"; !contains(redacted, want) {
		t.Fatalf("expected redacted access token in query, got %q", redacted)
	}
	if want := "refresh_token=%3Cmasked%3E"; !contains(redacted, want) {
		t.Fatalf("expected redacted refresh token in query, got %q", redacted)
	}
	if !contains(redacted, "foo=bar") {
		t.Fatalf("expected non-sensitive query parameter to remain, got %q", redacted)
	}
}

func TestIsAllowedBrowserOriginUsesCORSConfig(t *testing.T) {
	t.Setenv("CORS_ALLOWED_ORIGINS", "https://executionlab.io")

	if !IsAllowedBrowserOrigin("https://executionlab.io") {
		t.Fatal("expected configured origin to be allowed")
	}
	if IsAllowedBrowserOrigin("https://evil.example.com") {
		t.Fatal("expected unconfigured origin to be rejected")
	}
	if !IsAllowedBrowserOrigin("") {
		t.Fatal("expected empty origin to be allowed for non-browser clients")
	}
}

func contains(s, sub string) bool {
	return len(sub) == 0 || len(s) >= len(sub) && func() bool {
		for i := 0; i <= len(s)-len(sub); i++ {
			if s[i:i+len(sub)] == sub {
				return true
			}
		}
		return false
	}()
}
