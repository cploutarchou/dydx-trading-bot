package handlers

import (
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

type KeyHandler struct {
	service *services.KeyManagementService
}

func NewKeyHandler(service *services.KeyManagementService) *KeyHandler {
	return &KeyHandler{service: service}
}

type CreateKeyRequest struct {
	Network      string `json:"network" binding:"required"`
	ChainAddress string `json:"chain_address" binding:"required"`
	SecretPhrase string `json:"secret_phrase" binding:"required"`
}

type KeyResponse struct {
	ID        int    `json:"id"`
	Network   string `json:"network"`
	ChainAddr string `json:"chain_address"`
	IsActive  bool   `json:"is_active"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
}

type KeyListResponse struct {
	Keys  []KeyResponse `json:"keys"`
	Total int           `json:"total"`
}

type KeySecretResponse struct {
	ID           int    `json:"id"`
	Network      string `json:"network"`
	ChainAddr    string `json:"chain_address"`
	SecretPhrase string `json:"secret_phrase"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
}

type ErrorResponse struct {
	Success   bool        `json:"success"`
	Error     string      `json:"error"`
	Timestamp string      `json:"timestamp"`
	Data      interface{} `json:"data,omitempty"`
}

type SuccessResponse struct {
	Success   bool        `json:"success"`
	Data      interface{} `json:"data"`
	Timestamp string      `json:"timestamp"`
}

func (h *KeyHandler) CreateKey(c *gin.Context) {
	var req CreateKeyRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Success:   false,
			Error:     "Invalid request: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	key, err := h.service.CreateKey(userID.(int), req.Network, req.ChainAddress, req.SecretPhrase)
	if err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{
			Success:   false,
			Error:     "Failed to create key: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	response := KeyResponse{
		ID:        key.ID,
		Network:   key.Network,
		ChainAddr: key.ChainAddress,
		IsActive:  key.IsActive,
		CreatedAt: key.CreatedAt.Format(time.RFC3339),
		UpdatedAt: key.UpdatedAt.Format(time.RFC3339),
	}

	c.JSON(http.StatusCreated, SuccessResponse{
		Success:   true,
		Data:      response,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *KeyHandler) ListKeys(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	keys, err := h.service.GetActiveKeys(userID.(int))
	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Success:   false,
			Error:     "Failed to list keys: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	var keyResponses []KeyResponse
	for _, k := range keys {
		keyResponses = append(keyResponses, KeyResponse{
			ID:        k["id"].(int),
			Network:   k["network"].(string),
			ChainAddr: k["chain_address"].(string),
			IsActive:  true,
			CreatedAt: k["created_at"].(string),
			UpdatedAt: k["updated_at"].(string),
		})
	}

	response := KeyListResponse{
		Keys:  keyResponses,
		Total: len(keyResponses),
	}

	c.JSON(http.StatusOK, SuccessResponse{
		Success:   true,
		Data:      response,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *KeyHandler) GetKeyInfo(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	network := c.Param("network")
	keyInfo, err := h.service.GetKeyInfo(userID.(int), network)
	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Success:   false,
			Error:     "Failed to retrieve key: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	if keyInfo == nil {
		c.JSON(http.StatusNotFound, ErrorResponse{
			Success:   false,
			Error:     "No key found for network: " + network,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	response := KeyResponse{
		ID:        keyInfo["id"].(int),
		Network:   keyInfo["network"].(string),
		ChainAddr: keyInfo["chain_address"].(string),
		IsActive:  keyInfo["is_active"].(bool),
		CreatedAt: keyInfo["created_at"].(string),
		UpdatedAt: keyInfo["updated_at"].(string),
	}

	c.JSON(http.StatusOK, SuccessResponse{
		Success:   true,
		Data:      response,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *KeyHandler) DeleteKey(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	network := c.Param("network")
	err := h.service.DeleteKey(userID.(int), network)
	if err != nil {
		if err.Error() == "no key found to delete" {
			c.JSON(http.StatusNotFound, ErrorResponse{
				Success:   false,
				Error:     "No key found for network: " + network,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
			})
			return
		}

		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Success:   false,
			Error:     "Failed to delete key: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	c.Status(http.StatusNoContent)
}

func (h *KeyHandler) GetKeyWithSecret(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	network := c.Param("network")
	keyData, err := h.service.GetKey(userID.(int), network)
	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Success:   false,
			Error:     "Failed to retrieve key: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	if keyData == nil {
		c.JSON(http.StatusNotFound, ErrorResponse{
			Success:   false,
			Error:     "No key found for network: " + network,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	response := KeySecretResponse{
		ID:           keyData["id"].(int),
		Network:      keyData["network"].(string),
		ChainAddr:    keyData["chain_address"].(string),
		SecretPhrase: keyData["secret_phrase"].(string),
		CreatedAt:    keyData["created_at"].(string),
		UpdatedAt:    keyData["updated_at"].(string),
	}

	c.JSON(http.StatusOK, SuccessResponse{
		Success:   true,
		Data:      response,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
