package services

import (
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type fakeCandleCacheStore struct {
	values          map[string]string
	deletedPatterns []string
}

func newFakeCandleCacheStore() *fakeCandleCacheStore {
	return &fakeCandleCacheStore{values: map[string]string{}}
}

func (f *fakeCandleCacheStore) SetCache(key string, value interface{}, _ int) error {
	data, err := marshalCacheValue(value)
	if err != nil {
		return err
	}
	f.values[key] = string(data)
	return nil
}

func (f *fakeCandleCacheStore) GetCache(_ string) (interface{}, error) { return nil, nil }

func (f *fakeCandleCacheStore) GetCacheString(key string) (string, error) {
	return f.values[key], nil
}

func (f *fakeCandleCacheStore) DeleteCache(key string) error {
	delete(f.values, key)
	return nil
}

func (f *fakeCandleCacheStore) DeleteCachePattern(pattern string) error {
	f.deletedPatterns = append(f.deletedPatterns, pattern)
	return nil
}

func (f *fakeCandleCacheStore) GetCacheStats() map[string]interface{} {
	return map[string]interface{}{}
}

type fakeBacktestRepo struct {
	markets []string
	pages   map[string][][]models.BacktestCandle
}

func (f *fakeBacktestRepo) GetUniqueMarkets(_ int) ([]string, error) {
	return f.markets, nil
}

func (f *fakeBacktestRepo) GetCandles(filter repository.CandleFilter) ([]models.BacktestCandle, error) {
	key := fmt.Sprintf("%s:%d", filter.Market, filter.Skip)
	series := f.pages[key]
	if len(series) == 0 {
		return []models.BacktestCandle{}, nil
	}
	return series[0], nil
}

func TestCacheCandlesAndGetCachedCandles_RoundTrip(t *testing.T) {
	store := newFakeCandleCacheStore()
	ccs := &CandleCacheService{cache: store}

	candles := []models.BacktestCandle{
		{Market: "BTC-USD", Timestamp: time.Unix(1, 0).UTC(), OpenPrice: 1, HighPrice: 2, LowPrice: 0.5, ClosePrice: 1.5, Volume: 10},
		{Market: "BTC-USD", Timestamp: time.Unix(2, 0).UTC(), OpenPrice: 1.5, HighPrice: 2.5, LowPrice: 1.2, ClosePrice: 2.0, Volume: 15},
	}

	if err := ccs.CacheCandles(77, "BTC-USD", candles, 60); err != nil {
		t.Fatalf("CacheCandles error: %v", err)
	}

	got, err := ccs.GetCachedCandles(77, "BTC-USD")
	if err != nil {
		t.Fatalf("GetCachedCandles error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("expected 2 candles, got %d", len(got))
	}
	if got[1].ClosePrice != 2.0 {
		t.Fatalf("expected close price 2.0, got %v", got[1].ClosePrice)
	}
}

func TestPrefetchCandlesForRun_PaginatesAndCachesByMarket(t *testing.T) {
	store := newFakeCandleCacheStore()

	firstPage := make([]models.BacktestCandle, candleCachePageSize)
	for i := 0; i < candleCachePageSize; i++ {
		firstPage[i] = models.BacktestCandle{Market: "BTC-USD", Timestamp: time.Unix(int64(i+1), 0).UTC(), ClosePrice: float64(i)}
	}
	secondPage := []models.BacktestCandle{
		{Market: "BTC-USD", Timestamp: time.Unix(2001, 0).UTC(), ClosePrice: 2001},
		{Market: "BTC-USD", Timestamp: time.Unix(2002, 0).UTC(), ClosePrice: 2002},
	}

	repo := &fakeBacktestRepo{
		markets: []string{"BTC-USD"},
		pages: map[string][][]models.BacktestCandle{
			"BTC-USD:0": {firstPage},
			fmt.Sprintf("BTC-USD:%d", candleCachePageSize): {secondPage},
		},
	}

	ccs := &CandleCacheService{cache: store, repo: repo}
	if err := ccs.PrefetchCandlesForRun(99, 0); err != nil {
		t.Fatalf("PrefetchCandlesForRun error: %v", err)
	}

	key := "backtest:candles:99:BTC-USD"
	raw, ok := store.values[key]
	if !ok {
		t.Fatalf("expected cache key %s to be populated", key)
	}

	var decoded []models.BacktestCandle
	if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
		t.Fatalf("failed to decode cached candles: %v", err)
	}
	if len(decoded) != candleCachePageSize+2 {
		t.Fatalf("expected %d candles, got %d", candleCachePageSize+2, len(decoded))
	}
}

func TestInvalidateCandleCache_DeletesRawAndAggregatedPatterns(t *testing.T) {
	store := newFakeCandleCacheStore()
	ccs := &CandleCacheService{cache: store}

	if err := ccs.InvalidateCandleCache(42); err != nil {
		t.Fatalf("InvalidateCandleCache error: %v", err)
	}

	if len(store.deletedPatterns) != 2 {
		t.Fatalf("expected 2 delete patterns, got %d", len(store.deletedPatterns))
	}
	if store.deletedPatterns[0] != "backtest:candles:42:*" {
		t.Fatalf("unexpected raw candle pattern: %s", store.deletedPatterns[0])
	}
	if store.deletedPatterns[1] != "backtest:chart:*:42:*" {
		t.Fatalf("unexpected aggregated chart pattern: %s", store.deletedPatterns[1])
	}
}
