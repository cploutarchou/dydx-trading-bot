package services

import (
	"bytes"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"image/png"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
)

type MFASetupResult struct {
	Secret      string   `json:"secret"`
	QRCode      string   `json:"qr_code"`
	BackupCodes []string `json:"backup_codes"`
}

type MFAService struct {
	repo   *repository.UserMFARepository
	secret string
}

func NewMFAService(repo *repository.UserMFARepository) *MFAService {
	return &MFAService{repo: repo, secret: loadEncryptionSecret()}
}

func (s *MFAService) Setup(user *models.User) (*MFASetupResult, error) {
	if user == nil || user.ID <= 0 {
		return nil, fmt.Errorf("user is required")
	}

	accountName := strings.TrimSpace(user.Email)
	if accountName == "" {
		accountName = strings.TrimSpace(user.Username)
	}
	if accountName == "" {
		accountName = fmt.Sprintf("user-%d", user.ID)
	}

	key, err := totp.Generate(totp.GenerateOpts{
		Issuer:      "dYdX Trading Bot",
		AccountName: accountName,
		Period:      30,
		SecretSize:  20,
		Digits:      otp.DigitsSix,
		Algorithm:   otp.AlgorithmSHA1,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to generate totp secret: %w", err)
	}

	backupCodes, err := generateBackupCodes(8)
	if err != nil {
		return nil, fmt.Errorf("failed to generate backup codes: %w", err)
	}
	backupPayload, err := json.Marshal(backupCodes)
	if err != nil {
		return nil, fmt.Errorf("failed to encode backup codes: %w", err)
	}

	encryptedSecret, err := encryptString(s.secret, key.Secret())
	if err != nil {
		return nil, fmt.Errorf("failed to encrypt mfa secret: %w", err)
	}
	encryptedBackupCodes, err := encryptString(s.secret, string(backupPayload))
	if err != nil {
		return nil, fmt.Errorf("failed to encrypt backup codes: %w", err)
	}

	credential := &models.UserMFA{
		UserID:               user.ID,
		EncryptedSecret:      encryptedSecret,
		EncryptedBackupCodes: encryptedBackupCodes,
		Enabled:              false,
		VerifiedAt:           nil,
		LastUsedAt:           nil,
	}
	if err := s.repo.Upsert(credential); err != nil {
		return nil, fmt.Errorf("failed to persist mfa secret: %w", err)
	}

	image, err := key.Image(256, 256)
	if err != nil {
		return nil, fmt.Errorf("failed to render qr code: %w", err)
	}
	var pngBuffer bytes.Buffer
	if err := png.Encode(&pngBuffer, image); err != nil {
		return nil, fmt.Errorf("failed to encode qr image: %w", err)
	}
	qrCode := "data:image/png;base64," + base64.StdEncoding.EncodeToString(pngBuffer.Bytes())

	return &MFASetupResult{Secret: key.Secret(), QRCode: qrCode, BackupCodes: backupCodes}, nil
}

func (s *MFAService) Verify(userID int, token string) error {
	credential, err := s.repo.GetByUserID(userID)
	if err != nil {
		return err
	}
	if credential == nil {
		return fmt.Errorf("mfa setup not found")
	}

	secret, err := decryptString(s.secret, credential.EncryptedSecret)
	if err != nil {
		return fmt.Errorf("failed to decrypt mfa secret: %w", err)
	}

	valid, err := totp.ValidateCustom(strings.TrimSpace(token), secret, time.Now().UTC(), totp.ValidateOpts{
		Period:    30,
		Skew:      1,
		Digits:    otp.DigitsSix,
		Algorithm: otp.AlgorithmSHA1,
	})
	if err != nil {
		return fmt.Errorf("failed to validate token: %w", err)
	}
	if !valid {
		return fmt.Errorf("invalid authenticator code")
	}

	if err := s.repo.MarkVerified(userID, time.Now().UTC()); err != nil {
		return err
	}
	return nil
}

func generateBackupCodes(count int) ([]string, error) {
	if count <= 0 {
		count = 8
	}
	const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	codes := make([]string, 0, count)
	for i := 0; i < count; i++ {
		buf := make([]byte, 10)
		if _, err := rand.Read(buf); err != nil {
			return nil, err
		}
		codeBytes := make([]byte, 10)
		for idx, raw := range buf {
			codeBytes[idx] = alphabet[int(raw)%len(alphabet)]
		}
		formatted := fmt.Sprintf("%s-%s", string(codeBytes[:5]), string(codeBytes[5:]))
		codes = append(codes, formatted)
	}
	return codes, nil
}
