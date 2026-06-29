package services

// Deprecated: legacy local-disk CSV/JSON pair-history storage.
//
// This is part of the legacy local-file storage surface the Final Target
// Architecture retires (see docs/FINAL_APPLICATION_IMPROVEMENT_PLAN.md). It is
// retained for backward compatibility but is not the intended storage path for
// new data. Do not extend it; it is slated for Phase 3 cleanup once the
// authoritative artifact/analytics storage paths fully replace it.

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"sync"
	"time"
)

// CointegrationResult represents a cointegration analysis result
type CointegrationResult struct {
	BaseMarket        string  `json:"base_market" csv:"base_market"`
	QuoteMarket       string  `json:"quote_market" csv:"quote_market"`
	HedgeRatio        float64 `json:"hedge_ratio" csv:"hedge_ratio"`
	HalfLife          float64 `json:"half_life" csv:"half_life"`
	ZeroCrossings     int     `json:"zero_crossings" csv:"zero_crossings"`
	PValue            float64 `json:"p_value" csv:"p_value"`
	ZScoreMean        float64 `json:"z_score_mean" csv:"z_score_mean"`
	ZScoreStd         float64 `json:"z_score_std" csv:"z_score_std"`
	AnalysisTimestamp string  `json:"analysis_timestamp" csv:"analysis_timestamp"`
	ConfidenceScore   float64 `json:"confidence_score" csv:"confidence_score"`
}

// PairKey returns unique key for this pair
func (c *CointegrationResult) PairKey() string {
	return fmt.Sprintf("%s_%s", c.BaseMarket, c.QuoteMarket)
}

// IsHighConfidence checks if this is a high-confidence pair (>= 0.7)
func (c *CointegrationResult) IsHighConfidence() bool {
	return c.ConfidenceScore >= 0.7
}

// PairStorageMetadata represents metadata for pair storage
type PairStorageMetadata struct {
	AnalysisTimestamp   string `json:"analysis_timestamp"`
	TotalPairs          int    `json:"total_pairs"`
	Version             string `json:"version"`
	BotVersion          string `json:"bot_version"`
	HighConfidenceCount int    `json:"high_confidence_count"`
}

// PairStorageData represents the complete JSON storage structure
type PairStorageData struct {
	Metadata PairStorageMetadata   `json:"metadata"`
	Pairs    []CointegrationResult `json:"pairs"`
}

// PairStorageManager handles JSON-based pair storage with CSV backward compatibility
type PairStorageManager struct {
	mu          sync.RWMutex
	storagePath string
	jsonFile    string
	csvFile     string
	backupDir   string
}

var (
	pairStorageInstance *PairStorageManager
	pairStorageOnce     sync.Once
)

// GetPairStorage returns singleton instance of PairStorageManager
func GetPairStorage() *PairStorageManager {
	pairStorageOnce.Do(func() {
		pairStorageInstance = &PairStorageManager{
			storagePath: "app",
			jsonFile:    filepath.Join("app", "cointegrated_pairs.json"),
			csvFile:     filepath.Join("app", "cointegrated_pairs.csv"),
			backupDir:   filepath.Join("app", "pair_history"),
		}

		// Create backup directory if it doesn't exist
		if err := os.MkdirAll(pairStorageInstance.backupDir, 0755); err != nil {
			log.Printf("❌ Failed to create backup directory: %v", err)
		} else {
			log.Printf("✅ PairStorageManager initialized with JSON primary storage")
		}
	})
	return pairStorageInstance
}

// SavePairs saves pairs to JSON with CSV fallback for backward compatibility
func (psm *PairStorageManager) SavePairs(pairs []CointegrationResult) (string, error) {
	psm.mu.Lock()
	defer psm.mu.Unlock()

	timestamp := time.Now().Format(time.RFC3339)

	// Count high-confidence pairs
	highConfidenceCount := 0
	for _, pair := range pairs {
		if pair.IsHighConfidence() {
			highConfidenceCount++
		}
	}

	// Primary JSON storage (new format)
	data := PairStorageData{
		Metadata: PairStorageMetadata{
			AnalysisTimestamp:   timestamp,
			TotalPairs:          len(pairs),
			Version:             "2.0",
			BotVersion:          "dydx-trading-bot-enhanced",
			HighConfidenceCount: highConfidenceCount,
		},
		Pairs: pairs,
	}

	// Save JSON
	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		log.Printf("❌ Failed to marshal JSON: %v", err)
		return "", err
	}

	if err := os.WriteFile(psm.jsonFile, jsonData, 0644); err != nil {
		log.Printf("❌ Failed to save JSON pairs: %v", err)
		return "", err
	}
	log.Printf("✅ Saved %d pairs to JSON storage (v2.0)", len(pairs))

	// Legacy CSV compatibility
	if len(pairs) > 0 {
		if err := psm.saveCSV(pairs); err != nil {
			log.Printf("⚠️  CSV compatibility save failed: %v", err)
		} else {
			log.Printf("✅ Maintained CSV compatibility with %d pairs", len(pairs))
		}
	}

	// Create timestamped backup
	psm.createBackup(data)

	// Clean up old backups
	psm.cleanupOldBackups(7)

	return "saved", nil
}

// LoadPairs loads pairs with JSON-first, CSV fallback strategy
func (psm *PairStorageManager) LoadPairs() ([]CointegrationResult, error) {
	psm.mu.RLock()
	defer psm.mu.RUnlock()

	// Try JSON first
	if psm.jsonFileExists() {
		pairs, metadata, err := psm.loadJSON()
		if err == nil && pairs != nil {
			log.Printf("✅ Loaded %d pairs from JSON storage (v%s, %d high-confidence)",
				len(pairs), metadata.Version, metadata.HighConfidenceCount)
			return pairs, nil
		}
		log.Printf("⚠️  JSON loading failed: %v, falling back to CSV", err)
	}

	// Fallback to CSV
	if psm.csvFileExists() {
		pairs, err := psm.loadCSV()
		if err == nil && pairs != nil {
			log.Printf("✅ Loaded %d pairs from CSV fallback", len(pairs))
			return pairs, nil
		}
		log.Printf("❌ CSV loading failed: %v", err)
	}

	log.Printf("⚠️  No pair storage found, returning empty list")
	return []CointegrationResult{}, nil
}

// GetBestPairs returns top pairs by confidence score
func (psm *PairStorageManager) GetBestPairs(limit int) ([]CointegrationResult, error) {
	pairs, err := psm.LoadPairs()
	if err != nil {
		return nil, err
	}

	// Sort by confidence score (descending)
	sort.Slice(pairs, func(i, j int) bool {
		return pairs[i].ConfidenceScore > pairs[j].ConfidenceScore
	})

	if limit > 0 && len(pairs) > limit {
		return pairs[:limit], nil
	}
	return pairs, nil
}

// GetHighConfidencePairs returns only high-confidence pairs (score >= 0.7)
func (psm *PairStorageManager) GetHighConfidencePairs() ([]CointegrationResult, error) {
	pairs, err := psm.LoadPairs()
	if err != nil {
		return nil, err
	}

	var highConfidence []CointegrationResult
	for _, pair := range pairs {
		if pair.IsHighConfidence() {
			highConfidence = append(highConfidence, pair)
		}
	}
	return highConfidence, nil
}

// GetPairByMarkets gets specific pair by market symbols
func (psm *PairStorageManager) GetPairByMarkets(baseMarket, quoteMarket string) (*CointegrationResult, error) {
	pairs, err := psm.LoadPairs()
	if err != nil {
		return nil, err
	}

	for _, pair := range pairs {
		if pair.BaseMarket == baseMarket && pair.QuoteMarket == quoteMarket {
			return &pair, nil
		}
	}
	return nil, nil
}

// PairStorageInfo represents storage state information
type PairStorageInfo struct {
	TotalPairs          int    `json:"total_pairs"`
	HighConfidencePairs int    `json:"high_confidence_pairs"`
	StorageFormat       string `json:"storage_format"`
	HasJSON             bool   `json:"has_json"`
	HasCSV              bool   `json:"has_csv"`
	BackupCount         int    `json:"backup_count"`
	LastAnalysis        string `json:"last_analysis"`
}

// GetStorageInfo returns information about current storage state
func (psm *PairStorageManager) GetStorageInfo() PairStorageInfo {
	psm.mu.RLock()
	defer psm.mu.RUnlock()

	pairs, _ := psm.LoadPairs()

	highConfidenceCount := 0
	lastAnalysis := ""

	for i, pair := range pairs {
		if pair.IsHighConfidence() {
			highConfidenceCount++
		}
		if i == 0 {
			lastAnalysis = pair.AnalysisTimestamp
		}
	}

	storageFormat := "CSV"
	if psm.jsonFileExists() {
		storageFormat = "JSON"
	}

	// Count backup files
	backupCount := 0
	if entries, err := os.ReadDir(psm.backupDir); err == nil {
		backupCount = len(entries)
	}

	return PairStorageInfo{
		TotalPairs:          len(pairs),
		HighConfidencePairs: highConfidenceCount,
		StorageFormat:       storageFormat,
		HasJSON:             psm.jsonFileExists(),
		HasCSV:              psm.csvFileExists(),
		BackupCount:         backupCount,
		LastAnalysis:        lastAnalysis,
	}
}

// ============ Helper Methods ============

func (psm *PairStorageManager) jsonFileExists() bool {
	_, err := os.Stat(psm.jsonFile)
	return err == nil
}

func (psm *PairStorageManager) csvFileExists() bool {
	_, err := os.Stat(psm.csvFile)
	return err == nil
}

func (psm *PairStorageManager) loadJSON() ([]CointegrationResult, PairStorageMetadata, error) {
	data, err := os.ReadFile(psm.jsonFile)
	if err != nil {
		return nil, PairStorageMetadata{}, err
	}

	var storageData PairStorageData
	if err := json.Unmarshal(data, &storageData); err != nil {
		return nil, PairStorageMetadata{}, err
	}

	return storageData.Pairs, storageData.Metadata, nil
}

func (psm *PairStorageManager) loadCSV() (pairs []CointegrationResult, err error) {
	file, err := os.Open(psm.csvFile)
	if err != nil {
		return nil, err
	}
	defer func() {
		if closeErr := file.Close(); closeErr != nil && err == nil {
			err = closeErr
		}
	}()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}

	// Skip header
	for i := 1; i < len(records); i++ {
		record := records[i]
		if len(record) < 10 {
			continue
		}

		pair := CointegrationResult{
			BaseMarket:        record[0],
			QuoteMarket:       record[1],
			HedgeRatio:        parseFloat(record[2]),
			HalfLife:          parseFloat(record[3]),
			ZeroCrossings:     parseInt(record[4]),
			PValue:            parseFloat(record[5]),
			ZScoreMean:        parseFloat(record[6]),
			ZScoreStd:         parseFloat(record[7]),
			AnalysisTimestamp: record[8],
			ConfidenceScore:   parseFloat(record[9]),
		}
		pairs = append(pairs, pair)
	}

	return pairs, nil
}

func (psm *PairStorageManager) saveCSV(pairs []CointegrationResult) (err error) {
	file, err := os.Create(psm.csvFile)
	if err != nil {
		return err
	}
	defer func() {
		if closeErr := file.Close(); closeErr != nil && err == nil {
			err = closeErr
		}
	}()

	writer := csv.NewWriter(file)
	defer func() {
		writer.Flush()
		if flushErr := writer.Error(); flushErr != nil && err == nil {
			err = flushErr
		}
	}()

	// Write header
	header := []string{
		"base_market", "quote_market", "hedge_ratio", "half_life",
		"zero_crossings", "p_value", "z_score_mean", "z_score_std",
		"analysis_timestamp", "confidence_score",
	}
	if err := writer.Write(header); err != nil {
		return err
	}

	// Write data
	for _, pair := range pairs {
		record := []string{
			pair.BaseMarket,
			pair.QuoteMarket,
			fmt.Sprintf("%f", pair.HedgeRatio),
			fmt.Sprintf("%f", pair.HalfLife),
			fmt.Sprintf("%d", pair.ZeroCrossings),
			fmt.Sprintf("%f", pair.PValue),
			fmt.Sprintf("%f", pair.ZScoreMean),
			fmt.Sprintf("%f", pair.ZScoreStd),
			pair.AnalysisTimestamp,
			fmt.Sprintf("%f", pair.ConfidenceScore),
		}
		if err := writer.Write(record); err != nil {
			return err
		}
	}

	return nil
}

func (psm *PairStorageManager) createBackup(data PairStorageData) {
	timestamp := time.Now().Format("20060102_150405")
	backupFile := filepath.Join(psm.backupDir, fmt.Sprintf("pairs_%s.json", timestamp))

	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		log.Printf("⚠️  Failed to marshal backup: %v", err)
		return
	}

	if err := os.WriteFile(backupFile, jsonData, 0644); err != nil {
		log.Printf("⚠️  Backup creation failed: %v", err)
	}
}

func (psm *PairStorageManager) cleanupOldBackups(keepDays int) {
	cutoffTime := time.Now().Add(-time.Duration(keepDays*24) * time.Hour).Unix()

	entries, err := os.ReadDir(psm.backupDir)
	if err != nil {
		log.Printf("⚠️  Failed to read backup directory: %v", err)
		return
	}

	cleaned := 0
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			continue
		}

		if info.ModTime().Unix() < cutoffTime {
			backupPath := filepath.Join(psm.backupDir, entry.Name())
			if err := os.Remove(backupPath); err == nil {
				cleaned++
			}
		}
	}

	if cleaned > 0 {
		log.Printf("✅ Cleaned up %d old backup files", cleaned)
	}
}

// Helper functions

func parseFloat(s string) float64 {
	val, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0.0
	}
	return val
}

func parseInt(s string) int {
	val, err := strconv.Atoi(s)
	if err != nil {
		return 0
	}
	return val
}

// CalculateConfidenceScore calculates composite confidence score
// Following project's analytical approach
func CalculateConfidenceScore(pValue float64, halfLife float64, zeroCrossings int) float64 {
	// Statistical significance (higher weight for lower p-value)
	pScore := maxFloat(0, 1-(pValue/0.05)) * 0.5

	// Mean reversion speed (prefer shorter half-lives up to 24h)
	halfLifeScore := maxFloat(0, 1-(halfLife/24)) * 0.3

	// Trading frequency potential (more crossings = better)
	crossingScore := minFloat(1, float64(zeroCrossings)/10) * 0.2

	confidence := pScore + halfLifeScore + crossingScore
	return minFloat(1.0, maxFloat(0.0, confidence))
}

func minFloat(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

func maxFloat(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
