package db

import "testing"

func TestMigrationForceRecoveryAllowed(t *testing.T) {
	cases := []struct {
		name string
		env  map[string]string
		want bool
	}{
		{name: "default is off everywhere", env: map[string]string{}, want: false},
		{name: "development without opt-in", env: map[string]string{"APP_ENV": "development"}, want: false},
		{name: "explicit opt-in outside production", env: map[string]string{"APP_ENV": "development", "DB_MIGRATION_FORCE_RECOVERY": "true"}, want: true},
		{name: "opt-in with no environment set", env: map[string]string{"DB_MIGRATION_FORCE_RECOVERY": "1"}, want: true},
		{name: "opt-in refused in production", env: map[string]string{"APP_ENV": "production", "DB_MIGRATION_FORCE_RECOVERY": "true"}, want: false},
		{name: "opt-in refused for prod label", env: map[string]string{"ENVIRONMENT": "prod", "DB_MIGRATION_FORCE_RECOVERY": "true"}, want: false},
		{name: "CONFIG_ENV production is honoured", env: map[string]string{"CONFIG_ENV": "production", "APP_ENV": "development", "DB_MIGRATION_FORCE_RECOVERY": "true"}, want: false},
		{name: "explicit off", env: map[string]string{"DB_MIGRATION_FORCE_RECOVERY": "false"}, want: false},
	}
	keys := []string{"APP_CONFIG_ENV", "CONFIG_ENV", "APP_ENV", "ENVIRONMENT", "DB_MIGRATION_FORCE_RECOVERY"}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			for _, key := range keys {
				t.Setenv(key, tc.env[key])
			}
			if got := migrationForceRecoveryAllowed(); got != tc.want {
				t.Fatalf("migrationForceRecoveryAllowed() = %v, want %v", got, tc.want)
			}
		})
	}
}
