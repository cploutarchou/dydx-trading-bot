package routes

import (
	"strings"
	"testing"
)

func TestValidateAvatarDataURI(t *testing.T) {
	tinyPNG := "data:image/png;base64,iVBORw0KGgo="

	cases := []struct {
		name    string
		avatar  string
		wantErr bool
	}{
		{"empty clears avatar", "", false},
		{"valid png data url", tinyPNG, false},
		{"valid jpeg data url", "data:image/jpeg;base64,/9j/4AAQ", false},
		{"not a data url", "https://cdn.example.com/a.png", true},
		{"missing payload", "data:image/png;base64", true},
		{"disallowed media type", "data:image/svg+xml;base64,PHN2Zw==", true},
		{"non-image media type", "data:text/html;base64,PGh0bWw+", true},
		{"non-base64 encoding", "data:image/png,raw-bytes", true},
		{"invalid base64 payload", "data:image/png;base64,!!not-base64!!", true},
		{"oversized payload", "data:image/png;base64," + strings.Repeat("A", (6<<20)*4/3), true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			err := validateAvatarDataURI(tc.avatar)
			if (err != nil) != tc.wantErr {
				t.Fatalf("validateAvatarDataURI(%q) error = %v, wantErr %v", tc.avatar[:min(40, len(tc.avatar))], err, tc.wantErr)
			}
		})
	}
}
