package handlers

import (
	"net/http"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
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
	ID           int    `json:"id"`
	Network      string `json:"network"`
	ChainAddr    string `json:"chain_address"`
	SecretMasked string `json:"secret_masked,omitempty"`
	IsActive     bool   `json:"is_active"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
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

func keyToResponse(key *models.DYDXKey) KeyResponse {
	return KeyResponse{
		ID:           key.ID,
		Network:      key.Network,
		ChainAddr:    key.ChainAddress,
		SecretMasked: key.SecretMasked,
		IsActive:     key.IsActive,
		CreatedAt:    key.CreatedAt.Format(time.RFC3339),
		UpdatedAt:    key.UpdatedAt.Format(time.RFC3339),
	}
}

func decryptedKeyToResponse(key *services.DecryptedDYDXKey) KeySecretResponse {
	return KeySecretResponse{
		ID:           key.ID,
		Network:      key.Network,
		ChainAddr:    key.ChainAddress,
		SecretPhrase: key.SecretPhrase,
		CreatedAt:    key.CreatedAt.Format(time.RFC3339),
		UpdatedAt:    key.UpdatedAt.Format(time.RFC3339),
	}
}

func currentUserID(c *gin.Context) (int, bool) {
	userID, exists := c.Get("user_id")
	if !exists {
		return 0, false
	}

	typedUserID, ok := userID.(int)
	if !ok {
		return 0, false
	}
	return typedUserID, true
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

	userID, ok := currentUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	key, err := h.service.CreateKey(userID, req.Network, req.ChainAddress, req.SecretPhrase)
	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Success:   false,
			Error:     "Failed to create key: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	c.JSON(http.StatusCreated, SuccessResponse{
		Success:   true,
		Data:      keyToResponse(key),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *KeyHandler) ListKeys(c *gin.Context) {
	userID, ok := currentUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	keys, err := h.service.GetActiveKeys(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, ErrorResponse{
			Success:   false,
			Error:     "Failed to list keys: " + err.Error(),
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	keyResponses := make([]KeyResponse, 0, len(keys))
	for _, k := range keys {
		keyCopy := k
		keyResponses = append(keyResponses, keyToResponse(&keyCopy))
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
	userID, ok := currentUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	network := c.Param("network")
	keyInfo, err := h.service.GetKeyInfo(userID, network)
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

	c.JSON(http.StatusOK, SuccessResponse{
		Success:   true,
		Data:      keyToResponse(keyInfo),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

func (h *KeyHandler) DeleteKey(c *gin.Context) {
	userID, ok := currentUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	network := c.Param("network")
	err := h.service.DeleteKey(userID, network)
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
	userID, ok := currentUserID(c)
	if !ok {
		c.JSON(http.StatusUnauthorized, ErrorResponse{
			Success:   false,
			Error:     "Unauthorized",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
		return
	}

	network := c.Param("network")
	keyData, err := h.service.GetKey(userID, network)
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

	c.JSON(http.StatusOK, SuccessResponse{
		Success:   true,
		Data:      decryptedKeyToResponse(keyData),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}
