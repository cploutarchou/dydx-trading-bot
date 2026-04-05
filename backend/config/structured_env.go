package config

import (
	"crypto/aes"
	"crypto/cipher"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func normalizeAppConfigEnvironment(raw string) string {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "prod", "production":
		return "production"
	default:
		return "development"
	}
}

func ResolveAppConfigEnvironment() string {
	for _, key := range []string{"APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV"} {
		if value := strings.TrimSpace(os.Getenv(key)); value != "" {
			return normalizeAppConfigEnvironment(value)
		}
	}
	return "development"
}

func LoadStructuredConfigEnv(repoRoot string, override bool) (string, error) {
	profilePath, environment, err := resolveStructuredRuntimePath(repoRoot)
	if err != nil {
		return "", err
	}
	config, err := loadStructuredJSON(repoRoot, profilePath)
	if err != nil {
		return "", err
	}

	for key, value := range flattenStructuredEnv(config) {
		if override || strings.TrimSpace(os.Getenv(key)) == "" {
			if err := os.Setenv(key, value); err != nil {
				return "", fmt.Errorf("set env %s: %w", key, err)
			}
		}
	}

	if strings.TrimSpace(os.Getenv("APP_CONFIG_ENV")) == "" || override {
		_ = os.Setenv("APP_CONFIG_ENV", environment)
	}

	return profilePath, nil
}

func resolveStructuredRuntimePath(repoRoot string) (string, string, error) {
	environment := ResolveAppConfigEnvironment()

	if explicitRun := strings.TrimSpace(os.Getenv("APP_RUN_CONFIG_FILE")); explicitRun != "" {
		if _, err := os.Stat(explicitRun); err == nil {
			return explicitRun, environment, nil
		} else {
			return "", "", fmt.Errorf("missing runtime config %s: %w", explicitRun, err)
		}
	}

	runConfigPath := filepath.Join(repoRoot, "run.json")
	if _, err := os.Stat(runConfigPath); err == nil {
		return runConfigPath, environment, nil
	}

	if explicit := strings.TrimSpace(os.Getenv("APP_CONFIG_FILE")); explicit != "" {
		if _, err := os.Stat(explicit); err == nil {
			return explicit, environment, nil
		} else {
			return "", "", fmt.Errorf("missing structured config profile %s: %w", explicit, err)
		}
	}

	for _, candidate := range []string{
		filepath.Join(repoRoot, "config", "profiles", environment+".config.enc.json"),
		filepath.Join(repoRoot, "config", "profiles", environment+".config.json"),
	} {
		if _, err := os.Stat(candidate); err == nil {
			return candidate, environment, nil
		}
	}

	return "", "", fmt.Errorf(
		"missing structured config profile %s or %s",
		filepath.Join(repoRoot, "config", "profiles", environment+".config.enc.json"),
		filepath.Join(repoRoot, "config", "profiles", environment+".config.json"),
	)
}

func resolveStructuredConfigKeyPath(repoRoot string) string {
	if explicit := strings.TrimSpace(os.Getenv("APP_CONFIG_KEY_FILE")); explicit != "" {
		return explicit
	}
	return filepath.Join(repoRoot, ".configkey.bin")
}

func loadStructuredJSON(repoRoot string, path string) (map[string]any, error) {
	rawBytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read structured config %s: %w", path, err)
	}

	decoded := make(map[string]any)
	if err := json.Unmarshal(rawBytes, &decoded); err != nil {
		return nil, fmt.Errorf("parse structured config %s: %w", path, err)
	}

	if strings.HasSuffix(path, ".config.enc.json") || isEncryptedStructuredPayload(decoded) {
		return decryptStructuredJSON(repoRoot, path, decoded)
	}

	return decoded, nil
}

func isEncryptedStructuredPayload(decoded map[string]any) bool {
	_, hasCipher := decoded["cipher"]
	_, hasNonce := decoded["nonce"]
	_, hasCiphertext := decoded["ciphertext"]
	_, hasTag := decoded["tag"]
	return hasCipher && hasNonce && hasCiphertext && hasTag
}

func decryptStructuredJSON(repoRoot string, path string, payload map[string]any) (map[string]any, error) {
	keyPath := resolveStructuredConfigKeyPath(repoRoot)
	key, err := os.ReadFile(keyPath)
	if err != nil {
		return nil, fmt.Errorf("read config key %s: %w", keyPath, err)
	}
	if len(key) != 32 {
		return nil, fmt.Errorf("invalid config key length in %s; expected 32 bytes", keyPath)
	}

	nonce, err := decodeStructuredPayloadValue(payload, "nonce")
	if err != nil {
		return nil, fmt.Errorf("decrypt structured config %s: %w", path, err)
	}
	ciphertext, err := decodeStructuredPayloadValue(payload, "ciphertext")
	if err != nil {
		return nil, fmt.Errorf("decrypt structured config %s: %w", path, err)
	}
	tag, err := decodeStructuredPayloadValue(payload, "tag")
	if err != nil {
		return nil, fmt.Errorf("decrypt structured config %s: %w", path, err)
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("decrypt structured config %s: create cipher: %w", path, err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("decrypt structured config %s: create gcm: %w", path, err)
	}

	plaintext, err := gcm.Open(nil, nonce, append(ciphertext, tag...), nil)
	if err != nil {
		return nil, fmt.Errorf("decrypt structured config %s: invalid key or payload", path)
	}

	decoded := make(map[string]any)
	if err := json.Unmarshal(plaintext, &decoded); err != nil {
		return nil, fmt.Errorf("parse decrypted structured config %s: %w", path, err)
	}

	return decoded, nil
}

func decodeStructuredPayloadValue(payload map[string]any, key string) ([]byte, error) {
	value, ok := payload[key]
	if !ok {
		return nil, fmt.Errorf("missing field %s", key)
	}
	encoded, ok := value.(string)
	if !ok || strings.TrimSpace(encoded) == "" {
		return nil, fmt.Errorf("field %s must be a base64 string", key)
	}
	decoded, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return nil, fmt.Errorf("decode %s: %w", key, err)
	}
	return decoded, nil
}

func flattenStructuredEnv(tree map[string]any) map[string]string {
	flattened := make(map[string]string)

	var walk func(any)
	walk = func(node any) {
		nodeMap, ok := node.(map[string]any)
		if !ok {
			return
		}
		for key, value := range nodeMap {
			if childMap, ok := value.(map[string]any); ok {
				walk(childMap)
				continue
			}
			flattened[key] = normalizeStructuredScalar(value)
		}
	}

	for section, value := range tree {
		if section == "metadata" {
			continue
		}
		walk(value)
	}

	return flattened
}

func normalizeStructuredScalar(value any) string {
	switch typed := value.(type) {
	case nil:
		return ""
	case string:
		return typed
	case bool:
		if typed {
			return "true"
		}
		return "false"
	case float64:
		return strconv.FormatFloat(typed, 'f', -1, 64)
	case []any, map[string]any:
		raw, _ := json.Marshal(typed)
		return string(raw)
	default:
		return fmt.Sprintf("%v", typed)
	}
}
