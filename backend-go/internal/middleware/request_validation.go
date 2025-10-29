package middleware

import (
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

		// Log request
		if statusCode >= 400 {
			fmt.Printf("❌ [%s] %s %s - Status: %d - Duration: %dms - IP: %s\n",
				method, path, c.Request.URL.RawQuery, statusCode, duration, clientIP)
		} else {
			fmt.Printf("✅ [%s] %s %s - Status: %d - Duration: %dms - IP: %s\n",
				method, path, c.Request.URL.RawQuery, statusCode, duration, clientIP)
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
