package middleware

import (
	"net/http"
	"net/url"
	"strings"
)

var sensitiveHeaderNames = map[string]struct{}{
	"authorization": {},
	"cookie":        {},
	"set-cookie":    {},
}

var sensitiveQueryParams = map[string]struct{}{
	"access_token":  {},
	"token":         {},
	"jwt":           {},
	"refresh_token": {},
}

// SanitizeHeaders returns a copy of request headers with credential-bearing
// values masked so they are safe to log or echo in debug responses.
func SanitizeHeaders(headers http.Header) map[string]string {
	sanitized := make(map[string]string, len(headers))
	for k, vals := range headers {
		value := strings.Join(vals, ",")
		switch _, sensitive := sensitiveHeaderNames[strings.ToLower(k)]; {
		case sensitive && strings.HasPrefix(strings.ToLower(value), "bearer "):
			sanitized[k] = "Bearer <masked>"
		case sensitive && value != "":
			sanitized[k] = "<masked>"
		default:
			sanitized[k] = value
		}
	}
	return sanitized
}

// RedactSensitiveRawQuery masks credential-bearing query parameters before
// they are written to logs.
func RedactSensitiveRawQuery(rawQuery string) string {
	if strings.TrimSpace(rawQuery) == "" {
		return ""
	}

	values, err := url.ParseQuery(rawQuery)
	if err != nil {
		return rawQuery
	}

	for key := range sensitiveQueryParams {
		if _, exists := values[key]; exists {
			values.Set(key, "<masked>")
		}
	}

	return values.Encode()
}
