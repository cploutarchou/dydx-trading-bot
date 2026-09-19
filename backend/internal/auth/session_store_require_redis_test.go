package auth

import "testing"

func TestRequireRedisSessions_ProductionLabels(t *testing.T) {
	cases := []struct {
		name        string
		appEnv      string
		environment string
		override    string
		want        bool
	}{
		{name: "production label", appEnv: "production", want: true},
		{name: "prod label", appEnv: "prod", want: true},
		{name: "case and whitespace", appEnv: " PROD ", want: true},
		{name: "ENVIRONMENT variable", environment: "production", want: true},
		{name: "explicit override in dev", appEnv: "development", override: "true", want: true},
		{name: "development", appEnv: "development", want: false},
		{name: "test", appEnv: "test", want: false},
		{name: "unset", want: false},
		{name: "substring is not a match", appEnv: "preprod", want: false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Setenv("APP_ENV", tc.appEnv)
			t.Setenv("ENVIRONMENT", tc.environment)
			t.Setenv("AUTH_REQUIRE_REDIS_SESSIONS", tc.override)
			if got := requireRedisSessions(); got != tc.want {
				t.Fatalf("requireRedisSessions() = %v, want %v", got, tc.want)
			}
		})
	}
}
