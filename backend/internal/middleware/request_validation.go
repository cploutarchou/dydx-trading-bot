package middleware

import (
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// ValidationRule defines a validation rule for request data
type ValidationRule struct {
	Field       string                    // field name
	Required    bool                      // field is required
	MinLength   int                       // minimum length
	MaxLength   int                       // maximum length
	Pattern     string                    // regex pattern to match
	AllowedVals []string                  // allowed values
	Type        string                    // expected type: string, int, float, bool
	Custom      func(v interface{}) error // custom validation function
}

// Validator validates request data
type Validator struct {
	rules map[string][]ValidationRule
}

// NewValidator creates a new validator
func NewValidator() *Validator {
	return &Validator{
		rules: make(map[string][]ValidationRule),
	}
}

// AddRule adds a validation rule for an endpoint
func (v *Validator) AddRule(endpoint string, rule ValidationRule) {
	v.rules[endpoint] = append(v.rules[endpoint], rule)
}

// ValidateField validates a single field against a rule
func (v *Validator) ValidateField(value interface{}, rule ValidationRule) error {
	// Check required
	if rule.Required {
		if value == nil || value == "" {
			return fmt.Errorf("field '%s' is required", rule.Field)
		}
	}

	// If not required and empty, skip other validations
	if value == nil || value == "" {
		return nil
	}

	strValue := fmt.Sprintf("%v", value)

	// Check type
	if rule.Type != "" {
		if !v.checkType(value, rule.Type) {
			return fmt.Errorf("field '%s' must be of type %s", rule.Field, rule.Type)
		}
	}

	// Check length
	if rule.MinLength > 0 && len(strValue) < rule.MinLength {
		return fmt.Errorf("field '%s' must be at least %d characters", rule.Field, rule.MinLength)
	}

	if rule.MaxLength > 0 && len(strValue) > rule.MaxLength {
		return fmt.Errorf("field '%s' must be at most %d characters", rule.Field, rule.MaxLength)
	}

	// Check pattern
	if rule.Pattern != "" {
		matched, err := regexp.MatchString(rule.Pattern, strValue)
		if err != nil {
			return fmt.Errorf("invalid pattern for field '%s': %w", rule.Field, err)
		}
		if !matched {
			return fmt.Errorf("field '%s' does not match required pattern", rule.Field)
		}
	}

	// Check allowed values
	if len(rule.AllowedVals) > 0 {
		allowed := false
		for _, av := range rule.AllowedVals {
			if strValue == av {
				allowed = true
				break
			}
		}
		if !allowed {
			return fmt.Errorf("field '%s' must be one of: %s", rule.Field, strings.Join(rule.AllowedVals, ", "))
		}
	}

	// Check custom validation
	if rule.Custom != nil {
		if err := rule.Custom(value); err != nil {
			return fmt.Errorf("field '%s': %w", rule.Field, err)
		}
	}

	return nil
}

func (v *Validator) checkType(value interface{}, expectedType string) bool {
	switch expectedType {
	case "string":
		_, ok := value.(string)
		return ok
	case "int":
		switch value.(type) {
		case int, int32, int64, float64:
			return true
		}
		return false
	case "float":
		switch value.(type) {
		case float64, float32:
			return true
		}
		return false
	case "bool":
		_, ok := value.(bool)
		return ok
	}
	return true
}

// RequestValidationMiddleware creates a Gin middleware for request validation
func RequestValidationMiddleware(validator *Validator) gin.HandlerFunc {
	return func(c *gin.Context) {
		endpoint := c.Request.URL.Path

		// Get rules for this endpoint
		rules, exists := validator.rules[endpoint]
		if !exists {
			c.Next()
			return
		}

		// Get request data
		var requestData map[string]interface{}
		if err := c.ShouldBindJSON(&requestData); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"success": false,
				"error":   fmt.Sprintf("invalid request body: %v", err),
			})
			c.Abort()
			return
		}

		// Validate each rule
		for _, rule := range rules {
			value := requestData[rule.Field]
			if err := validator.ValidateField(value, rule); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{
					"success": false,
					"error":   err.Error(),
				})
				c.Abort()
				return
			}
		}

		// Store validated data in context
		c.Set("validated_data", requestData)
		c.Next()
	}
}

// CommonValidationRules provides preset validation rules for common scenarios

// EmailValidationRule returns a rule for email validation
func EmailValidationRule(fieldName string, required bool) ValidationRule {
	return ValidationRule{
		Field:     fieldName,
		Required:  required,
		Type:      "string",
		MaxLength: 255,
		Pattern:   `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`,
	}
}

// URLValidationRule returns a rule for URL validation
func URLValidationRule(fieldName string, required bool) ValidationRule {
	return ValidationRule{
		Field:     fieldName,
		Required:  required,
		Type:      "string",
		MaxLength: 2048,
		Pattern:   `^https?://`,
	}
}

// AlphanumericValidationRule returns a rule for alphanumeric validation
func AlphanumericValidationRule(fieldName string, required bool, minLen, maxLen int) ValidationRule {
	return ValidationRule{
		Field:     fieldName,
		Required:  required,
		Type:      "string",
		MinLength: minLen,
		MaxLength: maxLen,
		Pattern:   `^[a-zA-Z0-9]+$`,
	}
}

// UUIDValidationRule returns a rule for UUID validation
func UUIDValidationRule(fieldName string, required bool) ValidationRule {
	return ValidationRule{
		Field:    fieldName,
		Required: required,
		Type:     "string",
		Pattern:  `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`,
	}
}

// PhoneValidationRule returns a rule for phone validation (international format)
func PhoneValidationRule(fieldName string, required bool) ValidationRule {
	return ValidationRule{
		Field:     fieldName,
		Required:  required,
		Type:      "string",
		MinLength: 10,
		MaxLength: 15,
		Pattern:   `^\+?[0-9]{10,15}$`,
	}
}

// StrategyValidationRule returns a rule for strategy name validation
func StrategyValidationRule(fieldName string, required bool) ValidationRule {
	return ValidationRule{
		Field:     fieldName,
		Required:  required,
		Type:      "string",
		MinLength: 1,
		MaxLength: 100,
		Pattern:   `^[a-zA-Z0-9_\-\s]+$`,
	}
}

// ValidateStrategyConfig validates backtest strategy configuration
func ValidateStrategyConfig(config map[string]interface{}) error {
	requiredFields := []string{"name", "zscore_threshold", "stats_window"}

	for _, field := range requiredFields {
		if _, exists := config[field]; !exists {
			return fmt.Errorf("required field '%s' missing from strategy config", field)
		}
	}

	// Validate zscore_threshold (should be between 0.5 and 5.0)
	if zscore, ok := config["zscore_threshold"].(float64); ok {
		if zscore < 0.5 || zscore > 5.0 {
			return fmt.Errorf("zscore_threshold must be between 0.5 and 5.0, got %.2f", zscore)
		}
	} else {
		return fmt.Errorf("zscore_threshold must be a float")
	}

	// Validate stats_window (should be between 1 and 100)
	if statsWindow, ok := config["stats_window"].(float64); ok {
		if statsWindow < 1 || statsWindow > 100 {
			return fmt.Errorf("stats_window must be between 1 and 100, got %.0f", statsWindow)
		}
	} else {
		return fmt.Errorf("stats_window must be an integer")
	}

	// Validate max_positions if present
	if maxPos, ok := config["max_positions"].(float64); ok {
		if maxPos < 1 || maxPos > 100 {
			return fmt.Errorf("max_positions must be between 1 and 100")
		}
	}

	return nil
}

// ValidateBacktestParams validates backtest parameters
func ValidateBacktestParams(params map[string]interface{}) error {
	requiredFields := []string{"start_date", "end_date", "num_pairs"}

	for _, field := range requiredFields {
		if _, exists := params[field]; !exists {
			return fmt.Errorf("required field '%s' missing from backtest params", field)
		}
	}

	// Validate date format (YYYY-MM-DD)
	if startDate, ok := params["start_date"].(string); ok {
		if _, err := time.Parse("2006-01-02", startDate); err != nil {
			return fmt.Errorf("invalid start_date format, expected YYYY-MM-DD: %w", err)
		}
	} else {
		return fmt.Errorf("start_date must be a string")
	}

	if endDate, ok := params["end_date"].(string); ok {
		if _, err := time.Parse("2006-01-02", endDate); err != nil {
			return fmt.Errorf("invalid end_date format, expected YYYY-MM-DD: %w", err)
		}
	} else {
		return fmt.Errorf("end_date must be a string")
	}

	// Validate num_pairs
	if numPairs, ok := params["num_pairs"].(float64); ok {
		if numPairs < 1 || numPairs > 1000 {
			return fmt.Errorf("num_pairs must be between 1 and 1000")
		}
	} else {
		return fmt.Errorf("num_pairs must be an integer")
	}

	// Validate start_date is before end_date
	if startDate, ok := params["start_date"].(string); ok {
		if endDate, ok := params["end_date"].(string); ok {
			start, _ := time.Parse("2006-01-02", startDate)
			end, _ := time.Parse("2006-01-02", endDate)
			if !start.Before(end) {
				return fmt.Errorf("start_date must be before end_date")
			}
		}
	}

	return nil
}

// ValidateUserInput performs general user input validation
func ValidateUserInput(input map[string]interface{}) error {
	for key, value := range input {
		if str, ok := value.(string); ok {
			// Check length
			if len(str) > 5000 {
				return fmt.Errorf("field '%s' exceeds maximum length of 5000 characters", key)
			}

			// Check for null bytes
			if strings.Contains(str, "\x00") {
				return fmt.Errorf("field '%s' contains null bytes", key)
			}

			// Check for excessive whitespace
			if len(strings.TrimSpace(str)) == 0 {
				return fmt.Errorf("field '%s' cannot be empty or whitespace only", key)
			}
		}
	}
	return nil
}

// ValidateJSONFormat validates JSON format
func ValidateJSONFormat(data []byte) error {
	var jsonData interface{}
	if err := json.Unmarshal(data, &jsonData); err != nil {
		return fmt.Errorf("invalid JSON format: %w", err)
	}
	return nil
}

// ValidateAPIKey validates API key format
func ValidateAPIKey(key string) error {
	if len(key) == 0 {
		return fmt.Errorf("API key cannot be empty")
	}
	if len(key) > 255 {
		return fmt.Errorf("API key too long")
	}
	// Check for valid characters (alphanumeric, dash, underscore)
	if matched, _ := regexp.MatchString(`^[a-zA-Z0-9_\-]+$`, key); !matched {
		return fmt.Errorf("API key contains invalid characters")
	}
	return nil
}

// ValidateNetworkAddress validates blockchain network address
func ValidateNetworkAddress(address string, expectedPrefix string) error {
	if len(address) == 0 {
		return fmt.Errorf("address cannot be empty")
	}
	if len(address) > 255 {
		return fmt.Errorf("address too long")
	}
	if expectedPrefix != "" && !strings.HasPrefix(address, expectedPrefix) {
		return fmt.Errorf("address must start with '%s'", expectedPrefix)
	}
	return nil
}

// SafeStringValidationMiddleware prevents common injection attacks
func SafeStringValidationMiddleware() gin.HandlerFunc {
	// Patterns to detect potential injection attempts
	injectionPatterns := []*regexp.Regexp{
		regexp.MustCompile(`(?i)(select|insert|update|delete|drop|union|script|javascript|onerror|onload)`),
		regexp.MustCompile(`[<>"'` + "`" + `\\;]`),
	}

	return func(c *gin.Context) {
		// Get request body
		var requestData map[string]interface{}
		if err := c.ShouldBindJSON(&requestData); err != nil {
			c.Next()
			return
		}

		// Check each string value for injection patterns
		for key, value := range requestData {
			if strVal, ok := value.(string); ok {
				for _, pattern := range injectionPatterns {
					if pattern.MatchString(strVal) {
						c.JSON(http.StatusBadRequest, gin.H{
							"success": false,
							"error":   fmt.Sprintf("suspicious content detected in field '%s'", key),
						})
						c.Abort()
						return
					}
				}
			}
		}

		// Store data in context for next handler
		c.Set("request_data", requestData)
		c.Next()
	}
}

// RequestLoggingMiddleware logs request details with duration
func RequestLoggingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		startTime := time.Now()

		// Process request
		c.Next()

		// Calculate duration
		duration := time.Since(startTime).Milliseconds()

		// Get response details
		statusCode := c.Writer.Status()
		method := c.Request.Method
		path := c.Request.URL.Path
		clientIP := c.ClientIP()
		traceID := GetTraceID(c)

		// Log request
		if statusCode >= 400 {
			fmt.Printf("❌ [%s] %s %s - Status: %d - Duration: %dms - IP: %s - Trace: %s\n",
				method, path, c.Request.URL.RawQuery, statusCode, duration, clientIP, traceID)
		} else {
			fmt.Printf("✅ [%s] %s %s - Status: %d - Duration: %dms - IP: %s - Trace: %s\n",
				method, path, c.Request.URL.RawQuery, statusCode, duration, clientIP, traceID)
		}
	}
}

// ContentTypeValidationMiddleware ensures correct content type
func ContentTypeValidationMiddleware(allowedTypes []string) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Only validate for POST, PUT, PATCH
		if c.Request.Method == http.MethodPost || c.Request.Method == http.MethodPut || c.Request.Method == http.MethodPatch {
			contentType := c.ContentType()

			found := false
			for _, allowed := range allowedTypes {
				if strings.Contains(contentType, allowed) {
					found = true
					break
				}
			}

			if !found {
				c.JSON(http.StatusBadRequest, gin.H{
					"success": false,
					"error":   fmt.Sprintf("unsupported content type: %s. Expected one of: %v", contentType, allowedTypes),
				})
				c.Abort()
				return
			}
		}

		c.Next()
	}
}
