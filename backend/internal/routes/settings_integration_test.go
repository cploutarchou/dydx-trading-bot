package routes

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/dydx-trading-bot/backend-go/internal/handlers"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/gin-gonic/gin"
)

// ─── in-memory mock service ───────────────────────────────────────────────────

type mockSettingsService struct {
	mu           sync.Mutex
	botSettings  map[string]*models.BotSetting // keyed "section:key"
	redisSetting *models.RedisSetting
	nextBotID    int
	getAllErr    error
	getBotErr    error
	createErr    error

	// call-capture fields
	createdBot   []*models.BotSetting
	updatedBot   []*models.BotSetting
	updatedRedis *models.RedisSetting
}

func newMockSettingsService() *mockSettingsService {
	return &mockSettingsService{
		botSettings: make(map[string]*models.BotSetting),
		nextBotID:   1,
	}
}

func (m *mockSettingsService) key(section, k string) string {
	return section + ":" + k
}

func (m *mockSettingsService) CreateBotSetting(section, key, value, valueType, description, defaultValue string, isActive bool) (*models.BotSetting, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.createErr != nil {
		return nil, m.createErr
	}
	for _, existing := range m.botSettings {
		if existing.ID >= m.nextBotID {
			m.nextBotID = existing.ID + 1
		}
	}
	s := &models.BotSetting{
		ID:           m.nextBotID,
		Section:      section,
		Key:          key,
		Value:        value,
		ValueType:    valueType,
		Description:  description,
		DefaultValue: defaultValue,
		IsActive:     isActive,
		Version:      1,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}
	m.nextBotID++
	m.botSettings[m.key(section, key)] = s
	m.createdBot = append(m.createdBot, s)
	return s, nil
}

func (m *mockSettingsService) GetBotSetting(section, key string) (*models.BotSetting, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.getBotErr != nil {
		return nil, m.getBotErr
	}
	return m.botSettings[m.key(section, key)], nil
}

func (m *mockSettingsService) GetBotSettingsBySection(section string) ([]models.BotSetting, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	var out []models.BotSetting
	for _, s := range m.botSettings {
		if s.Section == section {
			out = append(out, *s)
		}
	}
	return out, nil
}

func (m *mockSettingsService) GetAllBotSettings() ([]models.BotSetting, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.getAllErr != nil {
		return nil, m.getAllErr
	}
	var out []models.BotSetting
	for _, s := range m.botSettings {
		out = append(out, *s)
	}
	return out, nil
}

func (m *mockSettingsService) UpdateBotSetting(id int, value, description string, isActive bool) (*models.BotSetting, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for k, s := range m.botSettings {
		if s.ID == id {
			s.Value = value
			s.Description = description
			s.IsActive = isActive
			s.Version++
			m.botSettings[k] = s
			m.updatedBot = append(m.updatedBot, s)
			return s, nil
		}
	}
	return nil, fmt.Errorf("bot setting %d not found", id)
}

func (m *mockSettingsService) DeleteBotSetting(id int) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	for k, s := range m.botSettings {
		if s.ID == id {
			delete(m.botSettings, k)
			return nil
		}
	}
	return fmt.Errorf("bot setting %d not found", id)
}

func (m *mockSettingsService) GetRedisSetting() (*models.RedisSetting, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.redisSetting, nil
}

func (m *mockSettingsService) UpdateRedisSetting(enabled bool, host string, port, db int, password string, ssl bool) (*models.RedisSetting, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.redisSetting == nil {
		m.redisSetting = &models.RedisSetting{}
	}
	m.redisSetting.Enabled = enabled
	m.redisSetting.Host = host
	m.redisSetting.Port = port
	m.redisSetting.Db = db
	m.redisSetting.Password = password
	m.redisSetting.SSL = ssl
	m.updatedRedis = m.redisSetting
	return m.redisSetting, nil
}

func (m *mockSettingsService) ClearCache() {}

func (m *mockSettingsService) GetCacheStats() map[string]interface{} {
	return map[string]interface{}{"cached_settings": 0}
}

// ─── test helpers ─────────────────────────────────────────────────────────────

const testJWTSecret = "settings-test-jwt-secret-32-chars!!"

func setupSettingsRouter(svc *mockSettingsService) (*gin.Engine, string) {
	gin.SetMode(gin.TestMode)

	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             testJWTSecret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	jwtMgr := auth.NewManager(auth.JWTConfig{
		Secret:            testJWTSecret,
		ExpiryHours:       1,
		RefreshExpiryDays: 1,
	})
	token, _, _ := jwtMgr.CreateAccessToken(1, "test-user", "test@example.local", false)

	router := gin.New()
	settingsHandler := handlers.NewSettingsHandler(svc)

	v1 := router.Group("/api/v1")
	settings := v1.Group("/settings")
	settings.POST("/initialize", settingsHandler.Initialize)
	settings.GET("/schema", settingsHandler.GetSchema)
	settings.Use(middleware.RequireAuth())
	settings.GET("", settingsHandler.GetSettings)
	settings.PUT("", settingsHandler.UpdateSettings)
	settings.GET("/platform/coming-soon", settingsHandler.GetComingSoonSetting)
	settings.PUT("/platform/coming-soon", settingsHandler.UpdateComingSoonSetting)
	settings.POST("/test-connection", settingsHandler.TestRedisConnection)
	settings.POST("/bot", settingsHandler.CreateBotSetting)
	settings.GET("/bot", settingsHandler.GetBotSetting)
	settings.GET("/bot/section", settingsHandler.GetBotSettingsBySection)
	settings.PUT("/bot/:id", settingsHandler.UpdateBotSetting)
	settings.DELETE("/bot/:id", settingsHandler.DeleteBotSetting)
	settings.GET("/redis", settingsHandler.GetRedisSetting)
	settings.PUT("/redis", settingsHandler.UpdateRedisSetting)
	settings.POST("/cache/clear", settingsHandler.ClearSettingsCache)
	settings.GET("/cache/stats", settingsHandler.GetCacheStats)

	return router, token
}

func TestSettings_ComingSoonReadAndUpdate(t *testing.T) {
	svc := newMockSettingsService()
	router, token := setupSettingsRouter(svc)

	getReq := httptest.NewRequest(http.MethodGet, "/api/v1/settings/platform/coming-soon", nil)
	getReq.Header.Set("Authorization", authHeader(token))
	getRes := httptest.NewRecorder()
	router.ServeHTTP(getRes, getReq)
	if getRes.Code != http.StatusOK {
		t.Fatalf("expected initial read 200, got %d body=%s", getRes.Code, getRes.Body.String())
	}

	var initial struct {
		Data struct {
			ComingSoonEnabled bool `json:"coming_soon_enabled"`
		} `json:"data"`
	}
	if err := json.Unmarshal(getRes.Body.Bytes(), &initial); err != nil {
		t.Fatalf("decode initial response: %v", err)
	}
	if initial.Data.ComingSoonEnabled {
		t.Fatal("expected initial coming soon state to be disabled")
	}

	updateReq := httptest.NewRequest(
		http.MethodPut,
		"/api/v1/settings/platform/coming-soon",
		bytes.NewReader([]byte(`{"coming_soon_enabled":true}`)),
	)
	updateReq.Header.Set("Authorization", authHeader(token))
	updateReq.Header.Set("Content-Type", "application/json")
	updateRes := httptest.NewRecorder()
	router.ServeHTTP(updateRes, updateReq)
	if updateRes.Code != http.StatusOK {
		t.Fatalf("expected update 200, got %d body=%s", updateRes.Code, updateRes.Body.String())
	}

	setting, err := svc.GetBotSetting("platform", "coming_soon_enabled")
	if err != nil {
		t.Fatalf("get saved setting: %v", err)
	}
	if setting == nil || setting.Value != "true" {
		t.Fatalf("expected persisted coming soon setting true, got %+v", setting)
	}
}

func TestSettings_ComingSoonUpdateRequiresAuth(t *testing.T) {
	svc := newMockSettingsService()
	router, _ := setupSettingsRouter(svc)

	req := httptest.NewRequest(
		http.MethodPut,
		"/api/v1/settings/platform/coming-soon",
		bytes.NewReader([]byte(`{"coming_soon_enabled":true}`)),
	)
	req.Header.Set("Content-Type", "application/json")
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for unauthenticated update, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestSettings_InitializeEmptyDatabaseThenGetSettings(t *testing.T) {
	svc := newMockSettingsService()
	router, token := setupSettingsRouter(svc)

	initReq := httptest.NewRequest(http.MethodPost, "/api/v1/settings/initialize", nil)
	initReq.Header.Set("Authorization", authHeader(token))
	initRes := httptest.NewRecorder()
	router.ServeHTTP(initRes, initReq)
	if initRes.Code != http.StatusOK {
		t.Fatalf("expected initialize 200, got %d body=%s", initRes.Code, initRes.Body.String())
	}

	getReq := httptest.NewRequest(http.MethodGet, "/api/v1/settings", nil)
	getReq.Header.Set("Authorization", authHeader(token))
	getRes := httptest.NewRecorder()
	router.ServeHTTP(getRes, getReq)
	if getRes.Code != http.StatusOK {
		t.Fatalf("expected get settings 200 after initialize, got %d body=%s", getRes.Code, getRes.Body.String())
	}

	var body struct {
		Data struct {
			Sections []struct {
				Section  string `json:"section"`
				Settings []struct {
					Key   string      `json:"key"`
					Value interface{} `json:"value"`
				} `json:"settings"`
			} `json:"sections"`
		} `json:"data"`
	}
	if err := json.Unmarshal(getRes.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode settings response: %v", err)
	}

	foundComingSoon := false
	for _, section := range body.Data.Sections {
		if section.Section != "platform" {
			continue
		}
		for _, setting := range section.Settings {
			if setting.Key == "coming_soon_enabled" {
				foundComingSoon = true
				if setting.Value != "false" {
					t.Fatalf("expected coming soon default false, got %#v", setting.Value)
				}
			}
		}
	}
	if !foundComingSoon {
		t.Fatal("expected platform.coming_soon_enabled in settings response")
	}
}

func TestSettings_InitializeIsIdempotent(t *testing.T) {
	svc := newMockSettingsService()
	router, token := setupSettingsRouter(svc)

	for i := 0; i < 2; i++ {
		req := httptest.NewRequest(http.MethodPost, "/api/v1/settings/initialize", nil)
		req.Header.Set("Authorization", authHeader(token))
		res := httptest.NewRecorder()
		router.ServeHTTP(res, req)
		if res.Code != http.StatusOK {
			t.Fatalf("expected initialize attempt %d to return 200, got %d body=%s", i+1, res.Code, res.Body.String())
		}
	}

	seen := map[string]int{}
	for _, setting := range svc.createdBot {
		seen[setting.Section+":"+setting.Key]++
	}
	for key, count := range seen {
		if count != 1 {
			t.Fatalf("expected one create for %s, got %d", key, count)
		}
	}
}

func TestSettings_InitializePreservesExistingComingSoonValue(t *testing.T) {
	svc := newMockSettingsService()
	_, _ = svc.CreateBotSetting("platform", "coming_soon_enabled", "true", "boolean", "Existing launch gate", "false", true)
	router, token := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/settings/initialize", nil)
	req.Header.Set("Authorization", authHeader(token))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code != http.StatusOK {
		t.Fatalf("expected initialize 200, got %d body=%s", res.Code, res.Body.String())
	}

	setting, err := svc.GetBotSetting("platform", "coming_soon_enabled")
	if err != nil {
		t.Fatalf("get coming soon: %v", err)
	}
	if setting == nil || setting.Value != "true" {
		t.Fatalf("expected existing coming soon value to be preserved, got %+v", setting)
	}
}

func TestSettings_GetSettingsRequiresAuth(t *testing.T) {
	svc := newMockSettingsService()
	router, _ := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/settings", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for unauthenticated settings read, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestSettings_ComingSoonMalformedStoredValueDefaultsDisabled(t *testing.T) {
	svc := newMockSettingsService()
	_, _ = svc.CreateBotSetting("platform", "coming_soon_enabled", "definitely-not-a-bool", "boolean", "Coming soon", "false", true)
	router, token := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/settings/platform/coming-soon", nil)
	req.Header.Set("Authorization", authHeader(token))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data struct {
			ComingSoonEnabled bool `json:"coming_soon_enabled"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.Data.ComingSoonEnabled {
		t.Fatal("expected malformed stored Coming Soon value to resolve disabled")
	}
}

func TestSettings_GetSettingsOmitsSensitiveValues(t *testing.T) {
	svc := newMockSettingsService()
	_, _ = svc.CreateBotSetting("platform", "registration_invitation_code", "join-secret", "string", "Invitation code", "", true)
	_, _ = svc.CreateBotSetting("platform", "coming_soon_enabled", "false", "boolean", "Coming soon", "false", true)
	svc.redisSetting = &models.RedisSetting{Host: "redis-srv", Port: 6379, Password: "redis-secret", Enabled: true}
	router, token := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/settings", nil)
	req.Header.Set("Authorization", authHeader(token))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}
	if strings.Contains(res.Body.String(), "redis-secret") {
		t.Fatalf("settings response exposed redis password: %s", res.Body.String())
	}
}

func TestSettings_GetSettingsReturnsDatabaseError(t *testing.T) {
	svc := newMockSettingsService()
	svc.getAllErr = fmt.Errorf("database offline")
	router, token := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/settings", nil)
	req.Header.Set("Authorization", authHeader(token))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d body=%s", res.Code, res.Body.String())
	}
	if !strings.Contains(res.Body.String(), "Failed to retrieve settings") {
		t.Fatalf("expected database error response, got %s", res.Body.String())
	}
}

func authHeader(token string) string {
	return "Bearer " + token
}

// ─── tests ────────────────────────────────────────────────────────────────────

func TestSettings_PutSettings_UpdatesBothTables(t *testing.T) {
	svc := newMockSettingsService()
	// Pre-seed an existing bot setting
	svc.botSettings["trading:max_position_size"] = &models.BotSetting{
		ID: 1, Section: "trading", Key: "max_position_size",
		Value: "1000", ValueType: "integer", IsActive: true, Version: 1,
	}
	router, token := setupSettingsRouter(svc)

	payload := map[string]interface{}{
		"trading.max_position_size": 2500,      // update existing bot setting
		"api.retry_attempts":        5,         // create new bot setting
		"redis.host":                "myredis", // redis fields
		"redis.port":                6380,
		"redis.enabled":             true,
		"redis.db":                  2,
		"redis.ssl":                 false,
		"redis.password":            "s3cr3t",
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPut, "/api/v1/settings", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		Success bool `json:"success"`
		Data    struct {
			Updated int `json:"updated"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if !resp.Success {
		t.Fatalf("expected success=true, got false; body: %s", w.Body.String())
	}
	if resp.Data.Updated < 2 {
		t.Errorf("expected at least 2 updated keys, got %d", resp.Data.Updated)
	}

	// Verify bot settings table: trading.max_position_size should be updated
	svc.mu.Lock()
	tradingSetting := svc.botSettings["trading:max_position_size"]
	svc.mu.Unlock()
	if tradingSetting == nil {
		t.Fatal("trading:max_position_size not found after update")
	}
	if tradingSetting.Value != "2500" {
		t.Errorf("expected trading.max_position_size='2500', got %q", tradingSetting.Value)
	}

	// Verify bot settings table: api.retry_attempts should be created
	svc.mu.Lock()
	apiSetting := svc.botSettings["api:retry_attempts"]
	svc.mu.Unlock()
	if apiSetting == nil {
		t.Fatal("api:retry_attempts not created")
	}
	if apiSetting.Value != "5" {
		t.Errorf("expected api.retry_attempts='5', got %q", apiSetting.Value)
	}

	// Verify redis_settings table was updated
	svc.mu.Lock()
	redis := svc.redisSetting
	svc.mu.Unlock()
	if redis == nil {
		t.Fatal("redis_settings were not written")
	}
	if redis.Host != "myredis" {
		t.Errorf("expected redis.host='myredis', got %q", redis.Host)
	}
	if redis.Port != 6380 {
		t.Errorf("expected redis.port=6380, got %d", redis.Port)
	}
	if !redis.Enabled {
		t.Error("expected redis.enabled=true")
	}
	if redis.Db != 2 {
		t.Errorf("expected redis.db=2, got %d", redis.Db)
	}
	if redis.Password != "s3cr3t" {
		t.Errorf("expected redis.password='s3cr3t', got %q", redis.Password)
	}
}

func TestSettings_PutSettings_BotOnly(t *testing.T) {
	svc := newMockSettingsService()
	router, token := setupSettingsRouter(svc)

	payload := map[string]interface{}{
		"bot.log_level": "debug",
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPut, "/api/v1/settings", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	svc.mu.Lock()
	defer svc.mu.Unlock()
	s := svc.botSettings["bot:log_level"]
	if s == nil || s.Value != "debug" {
		t.Errorf("expected bot.log_level='debug', got %v", s)
	}
	// redis table must NOT be touched
	if svc.redisSetting != nil {
		t.Error("redis settings should not be modified when no redis.* keys are in the payload")
	}
}

func TestSettings_PutSettings_RedisOnly(t *testing.T) {
	svc := newMockSettingsService()
	svc.redisSetting = &models.RedisSetting{Host: "localhost", Port: 6379, Enabled: false}
	router, token := setupSettingsRouter(svc)

	payload := map[string]interface{}{
		"redis.host":     "prod-redis",
		"redis.port":     6380,
		"redis.enabled":  true,
		"redis.ssl":      true,
		"redis.db":       0,
		"redis.password": "",
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPut, "/api/v1/settings", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	svc.mu.Lock()
	defer svc.mu.Unlock()
	if svc.redisSetting.Host != "prod-redis" {
		t.Errorf("expected redis.host='prod-redis', got %q", svc.redisSetting.Host)
	}
	if !svc.redisSetting.Enabled {
		t.Error("expected redis.enabled=true")
	}
	if !svc.redisSetting.SSL {
		t.Error("expected redis.ssl=true")
	}
	// bot table must NOT be touched
	if len(svc.botSettings) != 0 {
		t.Errorf("bot settings should not be modified, got %d entries", len(svc.botSettings))
	}
}

func TestSettings_PutSettings_RequiresAuth(t *testing.T) {
	svc := newMockSettingsService()
	router, _ := setupSettingsRouter(svc)

	body, _ := json.Marshal(map[string]interface{}{"redis.host": "x"})
	req := httptest.NewRequest(http.MethodPut, "/api/v1/settings", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 without auth, got %d", w.Code)
	}
}

func TestSettings_GetSettings_IncludesRedisSectionWhenConfigured(t *testing.T) {
	svc := newMockSettingsService()
	svc.redisSetting = &models.RedisSetting{
		Host: "redis-srv", Port: 6379, Enabled: true, SSL: false,
	}
	_, _ = svc.CreateBotSetting("trading", "max_position_size", "1000", "integer", "", "1000", true)
	router, token := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/settings", nil)
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		Success bool `json:"success"`
		Data    struct {
			Sections []struct {
				Section  string                   `json:"section"`
				Settings []map[string]interface{} `json:"settings"`
			} `json:"sections"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	foundRedis := false
	for _, sec := range resp.Data.Sections {
		if sec.Section == "redis" {
			foundRedis = true
			hostFound := false
			for _, s := range sec.Settings {
				if s["key"] == "host" {
					hostFound = true
					if s["value"] != "redis-srv" {
						t.Errorf("expected redis host 'redis-srv', got %v", s["value"])
					}
				}
			}
			if !hostFound {
				t.Error("redis section missing 'host' field")
			}
		}
	}
	if !foundRedis {
		t.Error("response sections did not include a 'redis' section")
	}
}

func TestSettings_GetRedisSetting_FallsBackToRuntimeConfig(t *testing.T) {
	originalConfig := config.ConfigInstance
	t.Cleanup(func() {
		config.ConfigInstance = originalConfig
	})

	config.ConfigInstance = &config.Config{
		Redis: config.RedisSettings{
			Enabled: true,
			Host:    "localhost",
			Port:    6379,
			DB:      0,
			SSL:     false,
		},
	}

	svc := newMockSettingsService()
	router, token := setupSettingsRouter(svc)
	config.ConfigInstance.Redis = config.RedisSettings{
		Enabled: true,
		Host:    "localhost",
		Port:    6379,
		DB:      0,
		SSL:     false,
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v1/settings/redis", nil)
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		Success bool `json:"success"`
		Data    struct {
			Enabled bool   `json:"enabled"`
			Host    string `json:"host"`
			Port    int    `json:"port"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !resp.Success {
		t.Fatal("expected success response")
	}
	if !resp.Data.Enabled || resp.Data.Host != "localhost" || resp.Data.Port != 6379 {
		t.Fatalf("unexpected redis fallback data: %+v", resp.Data)
	}
}

func TestSettings_Schema_IncludesRequiredSections(t *testing.T) {
	svc := newMockSettingsService()
	router, _ := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/settings/schema", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		Success bool `json:"success"`
		Data    struct {
			Sections []struct {
				Section string `json:"section"`
			} `json:"sections"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	sectionNames := make(map[string]bool)
	for _, s := range resp.Data.Sections {
		sectionNames[s.Section] = true
	}
	for _, expected := range []string{"trading", "api", "redis"} {
		if !sectionNames[expected] {
			t.Errorf("schema missing section %q", expected)
		}
	}
}

func TestSettings_TestRedisConnection_NotConfigured(t *testing.T) {
	originalConfig := config.ConfigInstance
	t.Cleanup(func() {
		config.ConfigInstance = originalConfig
	})
	config.ConfigInstance = &config.Config{
		Redis: config.RedisSettings{
			Enabled: false,
		},
	}

	svc := newMockSettingsService() // no redis setting
	router, token := setupSettingsRouter(svc)
	config.ConfigInstance.Redis = config.RedisSettings{Enabled: false}

	req := httptest.NewRequest(http.MethodPost, "/api/v1/settings/test-connection", nil)
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var resp struct {
		Success bool `json:"success"`
		Data    struct {
			Connected bool   `json:"connected"`
			Message   string `json:"message"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !resp.Success {
		t.Fatalf("success should be true even when not configured")
	}
	if resp.Data.Connected {
		t.Error("connected should be false when Redis is not configured")
	}
}

func TestSettings_TestRedisConnection_UsesRuntimeConfigFallback(t *testing.T) {
	originalConfig := config.ConfigInstance
	t.Cleanup(func() {
		config.ConfigInstance = originalConfig
	})
	config.ConfigInstance = &config.Config{
		Redis: config.RedisSettings{
			Enabled: true,
			Host:    "127.0.0.2",
			Port:    19999,
			DB:      0,
			SSL:     false,
		},
	}

	svc := newMockSettingsService()
	router, token := setupSettingsRouter(svc)
	config.ConfigInstance.Redis = config.RedisSettings{
		Enabled: true,
		Host:    "127.0.0.2",
		Port:    19999,
		DB:      0,
		SSL:     false,
	}

	req := httptest.NewRequest(http.MethodPost, "/api/v1/settings/test-connection", nil)
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var resp struct {
		Success bool `json:"success"`
		Data    struct {
			Connected bool   `json:"connected"`
			Message   string `json:"message"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !resp.Success {
		t.Fatal("expected success response")
	}
	if resp.Data.Message == "Redis is not configured" {
		t.Fatal("expected runtime redis config to be used instead of not-configured fallback")
	}
}

func TestSettings_TestRedisConnection_UnreachableHost(t *testing.T) {
	svc := newMockSettingsService()
	svc.redisSetting = &models.RedisSetting{
		Host: "127.0.0.2", Port: 19999, Enabled: true,
	}
	router, token := setupSettingsRouter(svc)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/settings/test-connection", nil)
	req.Header.Set("Authorization", authHeader(token))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var resp struct {
		Success bool `json:"success"`
		Data    struct {
			Connected bool   `json:"connected"`
			Message   string `json:"message"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !resp.Success {
		t.Fatalf("handler success should be true even for a failed ping")
	}
	if resp.Data.Connected {
		t.Error("connected should be false for unreachable host")
	}
	if resp.Data.Message == "" {
		t.Error("message should explain why connection failed")
	}
}
