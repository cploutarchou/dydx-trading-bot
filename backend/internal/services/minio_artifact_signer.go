package services

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
)

const (
	defaultMinIOArtifactRegion = "us-east-1"
	maxPresignExpiry           = 7 * 24 * time.Hour
)

// MinIOArtifactSigner produces short-lived S3-compatible GET URLs for MinIO.
type MinIOArtifactSigner struct {
	endpoint      *url.URL
	defaultBucket string
	accessKey     string
	secretKey     string
	region        string
	clock         func() time.Time
	metrics       *AsyncMetrics
}

// NewMinIOArtifactSigner returns nil when MinIO signing is not configured.
func NewMinIOArtifactSigner(settings config.MinIOSettings) (*MinIOArtifactSigner, error) {
	if !settings.Enabled {
		return nil, nil
	}
	if strings.TrimSpace(settings.Endpoint) == "" ||
		strings.TrimSpace(settings.AccessKey) == "" ||
		strings.TrimSpace(settings.SecretKey) == "" {
		return nil, nil
	}

	endpoint, err := normalizeMinIOEndpoint(settings.Endpoint, settings.Secure)
	if err != nil {
		return nil, err
	}

	return &MinIOArtifactSigner{
		endpoint:      endpoint,
		defaultBucket: strings.TrimSpace(settings.Bucket),
		accessKey:     strings.TrimSpace(settings.AccessKey),
		secretKey:     strings.TrimSpace(settings.SecretKey),
		region:        defaultMinIOArtifactRegion,
		clock:         time.Now,
		metrics:       GetAsyncMetrics(),
	}, nil
}

// DefaultBucket returns the configured default artifact bucket.
func (s *MinIOArtifactSigner) DefaultBucket() string {
	if s == nil {
		return ""
	}
	return s.defaultBucket
}

// PresignGet returns a short-lived GET URL for the provided bucket/object key.
func (s *MinIOArtifactSigner) PresignGet(bucket, objectKey string, expires time.Duration) (string, time.Time, error) {
	if s == nil {
		// Cannot record metrics if signer is nil (no metrics field to access)
		return "", time.Time{}, fmt.Errorf("artifact signer is not configured")
	}

	bucket = strings.TrimSpace(bucket)
	objectKey = strings.Trim(strings.TrimSpace(objectKey), "/")
	if bucket == "" || objectKey == "" {
		if s.metrics != nil {
			s.metrics.RecordMinIOUploadFailure()
		}
		return "", time.Time{}, fmt.Errorf("bucket and object key are required")
	}

	if expires <= 0 {
		expires = 15 * time.Minute
	}
	if expires > maxPresignExpiry {
		expires = maxPresignExpiry
	}

	now := s.clock().UTC()
	amzDate := now.Format("20060102T150405Z")
	dateStamp := now.Format("20060102")
	expiresSeconds := int(expires / time.Second)
	scope := fmt.Sprintf("%s/%s/s3/aws4_request", dateStamp, s.region)
	escapedPath := "/" + awsPercentEncode(bucket) + "/" + escapeS3ObjectKey(objectKey)

	queryValues := map[string]string{
		"X-Amz-Algorithm":     "AWS4-HMAC-SHA256",
		"X-Amz-Credential":    fmt.Sprintf("%s/%s", s.accessKey, scope),
		"X-Amz-Date":          amzDate,
		"X-Amz-Expires":       fmt.Sprintf("%d", expiresSeconds),
		"X-Amz-SignedHeaders": "host",
	}
	canonicalQuery := canonicalQueryString(queryValues)
	canonicalHeaders := fmt.Sprintf("host:%s\n", s.endpoint.Host)
	canonicalRequest := strings.Join([]string{
		"GET",
		escapedPath,
		canonicalQuery,
		canonicalHeaders,
		"host",
		"UNSIGNED-PAYLOAD",
	}, "\n")

	stringToSign := strings.Join([]string{
		"AWS4-HMAC-SHA256",
		amzDate,
		scope,
		hexSHA256(canonicalRequest),
	}, "\n")

	signingKey := deriveAWSV4Key(s.secretKey, dateStamp, s.region, "s3")
	signature := hex.EncodeToString(hmacSHA256(signingKey, stringToSign))

	signedQuery := canonicalQuery + "&X-Amz-Signature=" + awsPercentEncode(signature)
	signedURL := *s.endpoint
	signedURL.Path = joinURLPath(s.endpoint.Path, escapedPath)
	signedURL.RawQuery = signedQuery

	if s.metrics != nil {
		s.metrics.RecordMinIOUploadSuccess()
	}
	return signedURL.String(), now.Add(expires), nil
}

func normalizeMinIOEndpoint(raw string, secure bool) (*url.URL, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, fmt.Errorf("minio endpoint is required")
	}
	if !strings.Contains(raw, "://") {
		scheme := "http"
		if secure {
			scheme = "https"
		}
		raw = scheme + "://" + raw
	}

	parsed, err := url.Parse(raw)
	if err != nil {
		return nil, fmt.Errorf("parse minio endpoint: %w", err)
	}
	if parsed.Host == "" {
		return nil, fmt.Errorf("minio endpoint host is required")
	}
	return parsed, nil
}

func joinURLPath(basePath, extra string) string {
	basePath = strings.TrimRight(basePath, "/")
	if basePath == "" {
		return extra
	}
	return basePath + extra
}

func escapeS3ObjectKey(key string) string {
	segments := strings.Split(strings.Trim(key, "/"), "/")
	escaped := make([]string, 0, len(segments))
	for _, segment := range segments {
		if segment == "" {
			continue
		}
		escaped = append(escaped, awsPercentEncode(segment))
	}
	return strings.Join(escaped, "/")
}

func canonicalQueryString(values map[string]string) string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, awsPercentEncode(key)+"="+awsPercentEncode(values[key]))
	}
	return strings.Join(parts, "&")
}

func awsPercentEncode(value string) string {
	var builder strings.Builder
	for i := 0; i < len(value); i++ {
		ch := value[i]
		if (ch >= 'A' && ch <= 'Z') ||
			(ch >= 'a' && ch <= 'z') ||
			(ch >= '0' && ch <= '9') ||
			ch == '-' || ch == '_' || ch == '.' || ch == '~' {
			builder.WriteByte(ch)
			continue
		}
		builder.WriteString(fmt.Sprintf("%%%02X", ch))
	}
	return builder.String()
}

func hexSHA256(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func deriveAWSV4Key(secretKey, dateStamp, region, service string) []byte {
	dateKey := hmacSHA256([]byte("AWS4"+secretKey), dateStamp)
	regionKey := hmacSHA256(dateKey, region)
	serviceKey := hmacSHA256(regionKey, service)
	return hmacSHA256(serviceKey, "aws4_request")
}

func hmacSHA256(key []byte, value string) []byte {
	mac := hmac.New(sha256.New, key)
	_, _ = mac.Write([]byte(value))
	return mac.Sum(nil)
}
