package main

import "testing"

func TestAutoMigrateEnabled(t *testing.T) {
	tests := []struct {
		name    string
		value   string
		want    bool
		wantErr bool
	}{
		{name: "unset is safe off", value: "", want: false},
		{name: "true", value: "true", want: true},
		{name: "on", value: "on", want: true},
		{name: "false", value: "false", want: false},
		{name: "invalid", value: "sometimes", wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("DB_AUTO_MIGRATE", tt.value)
			got, err := autoMigrateEnabled()
			if (err != nil) != tt.wantErr {
				t.Fatalf("autoMigrateEnabled error=%v wantErr=%v", err, tt.wantErr)
			}
			if got != tt.want {
				t.Fatalf("autoMigrateEnabled=%v want=%v", got, tt.want)
			}
		})
	}
}
