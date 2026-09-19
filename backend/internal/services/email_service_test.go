package services

import (
	"context"
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

const testPlunkSecretKey = "sk_test_0123456789abcdef0123456789abcdef"

func newEmailServiceForTest(t *testing.T) (*EmailService, *sql.DB) {
	t.Helper()
	t.Setenv("ENCRYPTION_KEY", "email-service-test-encryption-key!")
	t.Setenv(plunkAPIURLEnv, "")

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	dbConn.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = dbConn.Close() })

	statements := []string{
		`CREATE TABLE users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT NOT NULL UNIQUE,
			email TEXT NOT NULL UNIQUE,
			role TEXT NOT NULL DEFAULT 'client',
			full_name TEXT,
			avatar TEXT,
			hashed_password TEXT NOT NULL,
			is_active BOOLEAN NOT NULL DEFAULT 1,
			is_admin BOOLEAN NOT NULL DEFAULT 0,
			password_change_required BOOLEAN NOT NULL DEFAULT 0,
			last_login DATETIME,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL
		);`,
		`CREATE TABLE bot_settings (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			section TEXT NOT NULL,
			key TEXT NOT NULL,
			value TEXT NOT NULL,
			value_type TEXT NOT NULL,
			description TEXT NOT NULL DEFAULT '',
			default_value TEXT NOT NULL DEFAULT '',
			is_active BOOLEAN NOT NULL DEFAULT 1,
			version INTEGER NOT NULL DEFAULT 1,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL
		);`,
		`CREATE TABLE external_api_credentials (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			provider TEXT NOT NULL,
			label TEXT NOT NULL DEFAULT '',
			encrypted_api_key TEXT NOT NULL,
			api_key_hash TEXT NOT NULL DEFAULT '',
			api_key_salt TEXT NOT NULL DEFAULT '',
			api_key_masked TEXT NOT NULL DEFAULT '',
			is_active BOOLEAN NOT NULL DEFAULT 1,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL,
			CONSTRAINT uq_external_api_credentials_user_provider UNIQUE (user_id, provider)
		);`,
	}
	for _, statement := range statements {
		if _, err := dbConn.Exec(statement); err != nil {
			t.Fatalf("setup schema: %v", err)
		}
	}

	service := NewEmailService(
		NewExternalAPICredentialService(repository.NewExternalAPICredentialRepository(dbConn)),
		repository.NewSettingsRepository(dbConn),
		repository.NewUserRepository(dbConn),
	)
	return service, dbConn
}

type capturedPlunkRequest struct {
	path          string
	authorization string
	contentType   string
	payload       map[string]any
}

func newFakePlunk(t *testing.T, status int, responseBody string) (*httptest.Server, *capturedPlunkRequest) {
	t.Helper()
	captured := &capturedPlunkRequest{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured.path = r.URL.Path
		captured.authorization = r.Header.Get("Authorization")
		captured.contentType = r.Header.Get("Content-Type")
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &captured.payload)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, responseBody)
	}))
	t.Cleanup(server.Close)
	return server, captured
}

func saveTestEmailConfig(t *testing.T, service *EmailService, apiURL string) *EmailStatus {
	t.Helper()
	status, err := service.SaveSharedConfig(EmailConfigPayload{
		APIKey:    testPlunkSecretKey,
		APIURL:    apiURL,
		FromEmail: "no-reply@executionlab.io",
		FromName:  "ExecutionLab",
		ReplyTo:   "support@executionlab.io",
	})
	if err != nil {
		t.Fatalf("SaveSharedConfig: %v", err)
	}
	return status
}

func TestEmailService_StatusIsUnconfiguredByDefault(t *testing.T) {
	service, _ := newEmailServiceForTest(t)

	status, err := service.GetStatus()
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if status.Configured || status.SharedKeyPresent {
		t.Fatalf("expected an unconfigured status, got %+v", status)
	}
	if status.Provider != "plunk" {
		t.Fatalf("provider = %q, want plunk", status.Provider)
	}
}

func TestEmailService_SaveConfigStoresSettingsAndNeverReturnsTheKey(t *testing.T) {
	service, dbConn := newEmailServiceForTest(t)
	server, _ := newFakePlunk(t, http.StatusOK, `{}`)

	status := saveTestEmailConfig(t, service, server.URL+"/")

	if !status.Configured || !status.SharedKeyPresent {
		t.Fatalf("expected configured status, got %+v", status)
	}
	if status.APIURL != server.URL {
		t.Fatalf("api url = %q, want trailing slash trimmed to %q", status.APIURL, server.URL)
	}
	if status.FromEmail != "no-reply@executionlab.io" || status.FromName != "ExecutionLab" || status.ReplyTo != "support@executionlab.io" {
		t.Fatalf("sender details not stored: %+v", status)
	}
	encoded, _ := json.Marshal(status)
	if strings.Contains(string(encoded), testPlunkSecretKey) {
		t.Fatal("status response leaks the secret key")
	}

	var stored string
	if err := dbConn.QueryRow(`SELECT encrypted_api_key FROM external_api_credentials WHERE provider = 'plunk'`).Scan(&stored); err != nil {
		t.Fatalf("load stored credential: %v", err)
	}
	if stored == "" || strings.Contains(stored, testPlunkSecretKey) {
		t.Fatal("secret key must be stored encrypted")
	}
}

func TestEmailService_SaveConfigKeepsExistingKeyWhenKeyIsBlank(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	server, captured := newFakePlunk(t, http.StatusOK, `{"success":true,"emails":[{"email":"msg-1"}]}`)
	saveTestEmailConfig(t, service, server.URL)

	status, err := service.SaveSharedConfig(EmailConfigPayload{
		APIURL:    server.URL,
		FromEmail: "alerts@executionlab.io",
	})
	if err != nil {
		t.Fatalf("SaveSharedConfig without key: %v", err)
	}
	if !status.Configured || status.FromEmail != "alerts@executionlab.io" || status.ReplyTo != "" {
		t.Fatalf("unexpected status after update: %+v", status)
	}

	if _, err := service.SendEmail(context.Background(), "user@example.com", "s", "b", ""); err != nil {
		t.Fatalf("SendEmail: %v", err)
	}
	if captured.authorization != "Bearer "+testPlunkSecretKey {
		t.Fatal("the previously stored key was not reused")
	}
}

func TestEmailService_SaveConfigRejectsBadInput(t *testing.T) {
	cases := []struct {
		name    string
		payload EmailConfigPayload
		want    string
	}{
		{"missing key", EmailConfigPayload{APIURL: "https://api.example.com", FromEmail: "a@example.com"}, "api key is required"},
		{"public key", EmailConfigPayload{APIKey: "pk_abc", APIURL: "https://api.example.com", FromEmail: "a@example.com"}, "secret key"},
		{"missing url", EmailConfigPayload{APIKey: testPlunkSecretKey, FromEmail: "a@example.com"}, "api url is required"},
		{"plain http", EmailConfigPayload{APIKey: testPlunkSecretKey, APIURL: "http://api.example.com", FromEmail: "a@example.com"}, "must use https"},
		{"credentials in url", EmailConfigPayload{APIKey: testPlunkSecretKey, APIURL: "https://u:p@api.example.com", FromEmail: "a@example.com"}, "must not contain credentials"},
		{"query in url", EmailConfigPayload{APIKey: testPlunkSecretKey, APIURL: "https://api.example.com?x=1", FromEmail: "a@example.com"}, "must not contain credentials"},
		{"other scheme", EmailConfigPayload{APIKey: testPlunkSecretKey, APIURL: "file:///etc/passwd", FromEmail: "a@example.com"}, "absolute URL"},
		{"bad sender", EmailConfigPayload{APIKey: testPlunkSecretKey, APIURL: "https://api.example.com", FromEmail: "not-an-email"}, "sender email"},
		{"display-name sender", EmailConfigPayload{APIKey: testPlunkSecretKey, APIURL: "https://api.example.com", FromEmail: "Ops <a@example.com>"}, "plain email address"},
		{"bad reply-to", EmailConfigPayload{APIKey: testPlunkSecretKey, APIURL: "https://api.example.com", FromEmail: "a@example.com", ReplyTo: "nope"}, "reply-to"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			service, _ := newEmailServiceForTest(t)
			_, err := service.SaveSharedConfig(tc.payload)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("error = %v, want it to contain %q", err, tc.want)
			}
			status, statusErr := service.GetStatus()
			if statusErr != nil {
				t.Fatalf("GetStatus: %v", statusErr)
			}
			if status.Configured {
				t.Fatal("a rejected payload must not leave delivery configured")
			}
		})
	}
}

func TestEmailService_SendEmailPostsThePlunkContract(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	server, captured := newFakePlunk(t, http.StatusOK, `{"success":true,"emails":[{"contact":{"id":"c1"},"email":"msg-42"}]}`)
	saveTestEmailConfig(t, service, server.URL)

	result, err := service.SendEmail(context.Background(), " user@example.com ", " Hello ", "line one\nline <two>\n\nsecond paragraph", "", "ico", " ", "confirm")
	if err != nil {
		t.Fatalf("SendEmail: %v", err)
	}
	if !result.Delivered || result.MessageID != "msg-42" {
		t.Fatalf("unexpected result: %+v", result)
	}

	if captured.path != "/v1/send" {
		t.Fatalf("path = %q, want /v1/send", captured.path)
	}
	if captured.authorization != "Bearer "+testPlunkSecretKey {
		t.Fatalf("authorization header = %q", captured.authorization)
	}
	if captured.contentType != "application/json" {
		t.Fatalf("content type = %q", captured.contentType)
	}
	want := map[string]any{
		"to":         "user@example.com",
		"subject":    "Hello",
		"from":       "no-reply@executionlab.io",
		"name":       "ExecutionLab",
		"reply":      "support@executionlab.io",
		"subscribed": false,
		"body":       "<p>line one<br>line &lt;two&gt;</p><p>second paragraph</p>",
	}
	for key, value := range want {
		if captured.payload[key] != value {
			t.Fatalf("payload[%q] = %#v, want %#v", key, captured.payload[key], value)
		}
	}
	data, _ := captured.payload["data"].(map[string]any)
	if data["tags"] != "ico,confirm" {
		t.Fatalf("tags = %#v, want ico,confirm", data["tags"])
	}
}

func TestEmailService_SendEmailPrefersHTMLBody(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	server, captured := newFakePlunk(t, http.StatusOK, `{}`)
	saveTestEmailConfig(t, service, server.URL)

	if _, err := service.SendEmail(context.Background(), "user@example.com", "s", "text", "<p>html</p>"); err != nil {
		t.Fatalf("SendEmail: %v", err)
	}
	if captured.payload["body"] != "<p>html</p>" {
		t.Fatalf("body = %#v, want the html body", captured.payload["body"])
	}
	if _, present := captured.payload["data"]; present {
		t.Fatal("data must be omitted when no tags are given")
	}
}

func TestEmailService_SendEmailReportsProviderRejection(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	server, _ := newFakePlunk(t, http.StatusUnauthorized, `{"code":401,"error":"Unauthorized","message":"Incorrect Bearer token specified"}`)
	saveTestEmailConfig(t, service, server.URL)

	result, err := service.SendEmail(context.Background(), "user@example.com", "s", "b", "")
	if err != nil {
		t.Fatalf("SendEmail returned a transport error for an API rejection: %v", err)
	}
	if result.Delivered {
		t.Fatal("a 401 must not count as delivered")
	}
	if !strings.Contains(result.Message, "401") || !strings.Contains(result.Message, "Incorrect Bearer token") {
		t.Fatalf("message = %q, want status and provider reason", result.Message)
	}
	if strings.Contains(result.Message, testPlunkSecretKey) {
		t.Fatal("the rejection message leaks the secret key")
	}
}

func TestEmailService_SendEmailSkipsWhenNotConfigured(t *testing.T) {
	service, _ := newEmailServiceForTest(t)

	result, err := service.SendEmail(context.Background(), "user@example.com", "s", "b", "")
	if err != nil {
		t.Fatalf("SendEmail: %v", err)
	}
	if result.Delivered || result.Message != emailNotConfiguredMessage {
		t.Fatalf("unexpected result: %+v", result)
	}
}

func TestEmailService_SendEmailReturnsTransportErrors(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	server, _ := newFakePlunk(t, http.StatusOK, `{}`)
	saveTestEmailConfig(t, service, server.URL)
	server.Close()

	if _, err := service.SendEmail(context.Background(), "user@example.com", "s", "b", ""); err == nil {
		t.Fatal("expected a transport error when the API is unreachable")
	}
}

func TestEmailService_APIURLFallsBackToEnvironment(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	t.Setenv(plunkAPIURLEnv, "https://api.mail.example.com")

	status, err := service.GetStatus()
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if status.APIURL != "https://api.mail.example.com" {
		t.Fatalf("api url = %q, want the environment fallback", status.APIURL)
	}
}

func TestEmailService_DeleteRemovesTheKey(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	server, _ := newFakePlunk(t, http.StatusOK, `{}`)
	saveTestEmailConfig(t, service, server.URL)

	if err := service.DeleteSharedConfig(); err != nil {
		t.Fatalf("DeleteSharedConfig: %v", err)
	}
	status, err := service.GetStatus()
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if status.Configured || status.SharedKeyPresent {
		t.Fatalf("expected the key to be gone, got %+v", status)
	}
}

func TestEmailService_OnboardingNoticeAndTestMessage(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	user := &models.User{Username: "trader1", Email: "trader1@example.com", FullName: "Trader One", Role: "client"}

	skipped, err := service.SendPasswordRotationNotice(context.Background(), user)
	if err != nil {
		t.Fatalf("SendPasswordRotationNotice: %v", err)
	}
	if skipped.Delivered || !strings.Contains(skipped.Message, "skipped") {
		t.Fatalf("unexpected unconfigured result: %+v", skipped)
	}

	server, captured := newFakePlunk(t, http.StatusOK, `{}`)
	saveTestEmailConfig(t, service, server.URL)

	sent, err := service.SendPasswordRotationNotice(context.Background(), user)
	if err != nil {
		t.Fatalf("SendPasswordRotationNotice: %v", err)
	}
	if !sent.Delivered || captured.payload["to"] != "trader1@example.com" {
		t.Fatalf("onboarding notice not sent: %+v payload=%v", sent, captured.payload)
	}
	body, _ := captured.payload["body"].(string)
	if !strings.Contains(body, "Trader One") || !strings.Contains(body, "trader1") {
		t.Fatalf("onboarding body misses the user details: %q", body)
	}

	if _, err := service.SendTest(context.Background(), "not-an-email"); err == nil {
		t.Fatal("SendTest must reject an invalid recipient")
	}
	tested, err := service.SendTest(context.Background(), "admin@example.com")
	if err != nil || !tested.Delivered {
		t.Fatalf("SendTest: %+v err=%v", tested, err)
	}
	if captured.payload["to"] != "admin@example.com" {
		t.Fatalf("test message went to %v", captured.payload["to"])
	}
}

func TestEmailService_RequestTimeoutIsBounded(t *testing.T) {
	service, _ := newEmailServiceForTest(t)
	if service.httpClient.Timeout <= 0 || service.httpClient.Timeout > 30*time.Second {
		t.Fatalf("http client timeout = %v, want a bounded value", service.httpClient.Timeout)
	}
}
