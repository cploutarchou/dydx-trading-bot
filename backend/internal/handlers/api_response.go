package handlers

// APIResponse is the handler-layer JSON envelope used by the original
// handler-owned feature routes (trade logs, audit logs, strategies, and the
// delegated backtest tree normalizes to the equivalent gin.H shape).
type APIResponse struct {
	Success   bool        `json:"success"`
	Data      interface{} `json:"data"`
	Timestamp string      `json:"timestamp"`
	Error     string      `json:"error,omitempty"`
}
