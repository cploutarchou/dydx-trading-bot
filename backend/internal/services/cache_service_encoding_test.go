package services

import (
	"encoding/json"
	"testing"
)

func TestMarshalCacheValue_PreservesRawString(t *testing.T) {
	raw := `{"ok":true}`
	data, err := marshalCacheValue(raw)
	if err != nil {
		t.Fatalf("marshalCacheValue returned error: %v", err)
	}
	if string(data) != raw {
		t.Fatalf("expected raw string payload %q, got %q", raw, string(data))
	}
}

func TestMarshalCacheValue_MarshalsStructuredPayload(t *testing.T) {
	payload := map[string]interface{}{"a": 1, "b": "x"}
	data, err := marshalCacheValue(payload)
	if err != nil {
		t.Fatalf("marshalCacheValue returned error: %v", err)
	}

	var decoded map[string]interface{}
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("json unmarshal failed: %v", err)
	}
	if decoded["a"].(float64) != 1 {
		t.Fatalf("expected a=1, got %v", decoded["a"])
	}
	if decoded["b"].(string) != "x" {
		t.Fatalf("expected b=x, got %v", decoded["b"])
	}
}
