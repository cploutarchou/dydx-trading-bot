package config

import (
	"os"
	"path/filepath"
)

func isStructuredConfigRoot(dir string) bool {
	configProfilesPath := filepath.Join(dir, "config", "profiles")
	if info, err := os.Stat(configProfilesPath); err == nil && info.IsDir() {
		return true
	}

	runConfigPath := filepath.Join(dir, "run.json")
	if _, err := os.Stat(runConfigPath); err == nil {
		return true
	}

	return false
}
