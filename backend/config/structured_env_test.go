package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFindRepoRootPrefersMonorepoRootWithStructuredConfig(t *testing.T) {
	base := t.TempDir()

	workspaceRoot := filepath.Join(base, "workspace")
	backendRoot := filepath.Join(workspaceRoot, "backend")

	for _, dir := range []string{
		filepath.Join(workspaceRoot, ".github"),
		filepath.Join(workspaceRoot, "config", "profiles"),
		filepath.Join(backendRoot, ".github"),
	} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatalf("mkdir %s: %v", dir, err)
		}
	}

	for _, file := range []string{
		filepath.Join(workspaceRoot, "AGENTS.md"),
		filepath.Join(backendRoot, "AGENTS.md"),
	} {
		if err := os.WriteFile(file, []byte("test"), 0o644); err != nil {
			t.Fatalf("write %s: %v", file, err)
		}
	}

	got := FindRepoRoot(backendRoot)
	if got != workspaceRoot {
		t.Fatalf("expected monorepo root %s, got %s", workspaceRoot, got)
	}
}
