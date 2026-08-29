package services

import (
	"bytes"
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"image/png"
	"net/url"
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

func buildTOTPQRCode(secret, accountName string) (string, error) {
	otpauthURL := fmt.Sprintf(
		"otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=SHA1&digits=6&period=30",
		url.QueryEscape("dYdX Trading Bot"),
		url.QueryEscape(accountName),
		url.QueryEscape(secret),
		url.QueryEscape("dYdX Trading Bot"),
	)

	key, err := otp.NewKeyFromURL(otpauthURL)
	if err != nil {
		return "", fmt.Errorf("failed to build otp key from url: %w", err)
	}

	image, err := key.Image(256, 256)
	if err != nil {
		return "", fmt.Errorf("failed to render qr code: %w", err)
	}

	var pngBuffer bytes.Buffer
	if err := png.Encode(&pngBuffer, image); err != nil {
		return "", fmt.Errorf("failed to encode qr image: %w", err)
	}

	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(pngBuffer.Bytes()), nil
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

	existingCredential, err := s.repo.GetByUserID(user.ID)
	if err != nil {
		return nil, err
	}

	if existingCredential != nil {
		if existingCredential.Enabled {
			return nil, fmt.Errorf("2fa is already enabled for this account")
		}

		existingSecret, err := decryptString(s.secret, existingCredential.EncryptedSecret)
		if err == nil && strings.TrimSpace(existingSecret) != "" {
			qrCode, qrErr := buildTOTPQRCode(existingSecret, accountName)
			if qrErr != nil {
				return nil, qrErr
			}

			backupCodes := []string{}
			if strings.TrimSpace(existingCredential.EncryptedBackupCodes) != "" {
				if decryptedBackupCodes, decryptErr := decryptString(s.secret, existingCredential.EncryptedBackupCodes); decryptErr == nil {
					_ = json.Unmarshal([]byte(decryptedBackupCodes), &backupCodes)
				}
			}

			return &MFASetupResult{Secret: existingSecret, QRCode: qrCode, BackupCodes: backupCodes}, nil
		}
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

	qrCode, err := buildTOTPQRCode(key.Secret(), accountName)
	if err != nil {
		return nil, err
	}

	return &MFASetupResult{Secret: key.Secret(), QRCode: qrCode, BackupCodes: backupCodes}, nil
}

// totpPeriodSeconds matches the TOTP configuration used everywhere in this
// service (GenerateOpts/ValidateOpts Period: 30).
const totpPeriodSeconds int64 = 30

// totpSkewWindows mirrors the historical ValidateCustom skew of 2 (a code
// from up to two windows in the past/future remains valid for clock drift).
const totpSkewWindows int64 = 2

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

	trimmedToken := strings.TrimSpace(token)
	if trimmedToken == "" {
		return fmt.Errorf("invalid authenticator code (use the latest 6-digit code and ensure your device time is automatic)")
	}

	now := time.Now().UTC()
	currentWindow := now.Unix() / totpPeriodSeconds

	// Replay protection: enumerate valid windows newest-first and accept the
	// match only if its window is strictly newer than the last used one.
	// ValidateCustom alone accepted any in-skew code indefinitely within its
	// ~90s validity, so an observed code could be replayed.
	var lastUsedWindow int64 = -1
	if credential.LastUsedAt != nil {
		lastUsedWindow = credential.LastUsedAt.UTC().Unix() / totpPeriodSeconds
	}

	opts := totp.ValidateOpts{
		Period:    uint(totpPeriodSeconds),
		Skew:      uint(totpSkewWindows),
		Digits:    otp.DigitsSix,
		Algorithm: otp.AlgorithmSHA1,
	}

	for offset := int64(0); offset <= totpSkewWindows; offset++ {
		for _, sign := range []int64{1, -1} {
			w := currentWindow + sign*offset
			if offset == 0 && sign == -1 {
				continue
			}
			if w <= lastUsedWindow {
				continue
			}
			expected, genErr := totp.GenerateCodeCustom(secret, time.Unix(w*totpPeriodSeconds, 0).UTC(), opts)
			if genErr != nil {
				return fmt.Errorf("failed to validate token: %w", genErr)
			}
			if subtle.ConstantTimeCompare([]byte(expected), []byte(trimmedToken)) == 1 {
				if err := s.repo.MarkUsed(userID, w); err != nil {
					return err
				}
				return nil
			}
		}
	}

	// Backup codes: one-time recovery codes from setup. Each accepted code
	// is removed so it cannot be reused.
	if matched, err := s.consumeBackupCode(credential, trimmedToken, currentWindow); err != nil {
		return err
	} else if matched {
		return nil
	}

	return fmt.Errorf("invalid authenticator code (use the latest 6-digit code and ensure your device time is automatic)")
}

// consumeBackupCode checks the token against the stored (encrypted) backup
// codes; on a match it removes that code, persists the remainder, and burns
// the TOTP window so the used backup code and a replayed TOTP code cannot
// both succeed around the same moment.
func (s *MFAService) consumeBackupCode(
	credential *models.UserMFA,
	token string,
	currentWindow int64,
) (bool, error) {
	if strings.TrimSpace(credential.EncryptedBackupCodes) == "" {
		return false, nil
	}
	decrypted, err := decryptString(s.secret, credential.EncryptedBackupCodes)
	if err != nil {
		return false, nil // undecryptable store behaves as "no backup codes"
	}
	var codes []string
	if err := json.Unmarshal([]byte(decrypted), &codes); err != nil {
		return false, nil
	}

	matchIdx := -1
	for idx, code := range codes {
		if subtle.ConstantTimeCompare([]byte(strings.TrimSpace(code)), []byte(token)) == 1 {
			matchIdx = idx
			break
		}
	}
	if matchIdx < 0 {
		return false, nil
	}

	remaining := append(codes[:matchIdx:matchIdx], codes[matchIdx+1:]...)
	payload, err := json.Marshal(remaining)
	if err != nil {
		return false, fmt.Errorf("failed to encode remaining backup codes: %w", err)
	}
	encryptedRemaining, err := encryptString(s.secret, string(payload))
	if err != nil {
		return false, fmt.Errorf("failed to encrypt remaining backup codes: %w", err)
	}
	if err := s.repo.UpdateBackupCodes(credential.UserID, encryptedRemaining); err != nil {
		return false, err
	}
	if err := s.repo.MarkUsed(credential.UserID, currentWindow); err != nil {
		return false, err
	}
	return true, nil
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
