#!/usr/bin/env python3
"""
Test script for enhanced pair storage system.
Tests JSON storage, CSV compatibility, and confidence scoring.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add app directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from models.pair_storage import (
        CointegrationResult,
        PairStorageManager,
        calculate_confidence_score,
        pair_storage,
    )
    print("✅ Successfully imported enhanced storage models")
except ImportError as e:
    print(f"❌ Failed to import models: {e}")
    sys.exit(1)


def create_test_pairs():
    """Create sample cointegration results for testing."""
    test_pairs = [
        CointegrationResult(
            base_market="BTC-USD",
            quote_market="ETH-USD",
            hedge_ratio=0.85,
            half_life=12.5,
            zero_crossings=15,
            p_value=0.01,
            z_score_mean=0.02,
            z_score_std=1.15,
            analysis_timestamp=datetime.now().isoformat(),
            confidence_score=0.75
        ),
        CointegrationResult(
            base_market="LINK-USD",
            quote_market="UNI-USD",
            hedge_ratio=1.2,
            half_life=18.0,
            zero_crossings=8,
            p_value=0.03,
            z_score_mean=-0.05,
            z_score_std=0.95,
            analysis_timestamp=datetime.now().isoformat(),
            confidence_score=0.65
        ),
        CointegrationResult(
            base_market="SOL-USD",
            quote_market="AVAX-USD",
            hedge_ratio=0.95,
            half_life=22.0,
            zero_crossings=5,
            p_value=0.045,
            z_score_mean=0.1,
            z_score_std=1.05,
            analysis_timestamp=datetime.now().isoformat(),
            confidence_score=0.45
        ),
        CointegrationResult(
            base_market="ADA-USD",
            quote_market="DOT-USD",
            hedge_ratio=0.78,
            half_life=8.5,
            zero_crossings=20,
            p_value=0.005,
            z_score_mean=0.0,
            z_score_std=0.98,
            analysis_timestamp=datetime.now().isoformat(),
            confidence_score=0.88
        )
    ]
    
    # Calculate confidence scores for validation
    for pair in test_pairs:
        calculated_confidence = calculate_confidence_score(
            pair.p_value, pair.half_life, pair.zero_crossings
        )
        print(f"   {pair.base_market}/{pair.quote_market}: Manual={pair.confidence_score:.3f}, Calculated={calculated_confidence:.3f}")
    
    return test_pairs


def test_storage_manager():
    """Test the PairStorageManager functionality."""
    print("\n🧪 Testing PairStorageManager...")
    
    # Create storage manager instance
    storage = PairStorageManager()
    print("✅ PairStorageManager instance created")
    
    # Test singleton pattern
    storage2 = PairStorageManager()
    assert storage is storage2, "Singleton pattern failed"
    print("✅ Singleton pattern verified")
    
    # Create test data
    test_pairs = create_test_pairs()
    print(f"✅ Created {len(test_pairs)} test pairs")
    
    # Test save functionality
    result = storage.save_pairs(test_pairs)
    assert result == "saved", "Save operation failed"
    print("✅ Pairs saved successfully")
    
    # Verify JSON file exists
    json_file = Path("app/cointegrated_pairs.json")
    assert json_file.exists(), "JSON file not created"
    print("✅ JSON file created")
    
    # Verify CSV file exists (backward compatibility)
    csv_file = Path("app/cointegrated_pairs.csv")
    assert csv_file.exists(), "CSV file not created"
    print("✅ CSV compatibility file created")
    
    # Test load functionality
    loaded_pairs = storage.load_pairs()
    assert len(loaded_pairs) == len(test_pairs), f"Expected {len(test_pairs)} pairs, got {len(loaded_pairs)}"
    print(f"✅ Loaded {len(loaded_pairs)} pairs successfully")
    
    # Test data integrity
    for original, loaded in zip(test_pairs, loaded_pairs):
        assert original.base_market == loaded.base_market, "Base market mismatch"
        assert original.quote_market == loaded.quote_market, "Quote market mismatch"
        assert abs(original.hedge_ratio - loaded.hedge_ratio) < 0.001, "Hedge ratio mismatch"
        assert abs(original.confidence_score - loaded.confidence_score) < 0.001, "Confidence score mismatch"
    print("✅ Data integrity verified")
    
    return storage, test_pairs


def test_json_structure():
    """Test JSON file structure and metadata."""
    print("\n🔍 Testing JSON structure...")
    
    json_file = Path("app/cointegrated_pairs.json")
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Check structure
    assert "metadata" in data, "Missing metadata section"
    assert "pairs" in data, "Missing pairs section"
    print("✅ JSON structure valid")
    
    # Check metadata
    metadata = data["metadata"]
    required_fields = ["analysis_timestamp", "total_pairs", "version", "bot_version"]
    for field in required_fields:
        assert field in metadata, f"Missing metadata field: {field}"
    print("✅ Metadata structure valid")
    
    # Check version
    assert metadata["version"] == "2.0", "Incorrect version"
    print("✅ Version correct")
    
    # Print metadata info
    print(f"   📊 Total pairs: {metadata['total_pairs']}")
    print(f"   ⏰ Analysis timestamp: {metadata['analysis_timestamp']}")
    print(f"   🔢 Version: {metadata['version']}")
    print(f"   🤖 Bot version: {metadata['bot_version']}")
    
    return data


def test_csv_compatibility():
    """Test CSV backward compatibility."""
    print("\n📄 Testing CSV compatibility...")
    
    csv_file = Path("app/cointegrated_pairs.csv")
    df = pd.read_csv(csv_file)
    
    # Check required columns
    required_columns = ["base_market", "quote_market", "hedge_ratio", "half_life", "confidence_score"]
    for col in required_columns:
        assert col in df.columns, f"Missing CSV column: {col}"
    print("✅ CSV structure valid")
    
    print(f"   📊 CSV rows: {len(df)}")
    print(f"   📋 Columns: {list(df.columns)}")
    
    # Test loading from CSV (simulate JSON not existing)
    json_file = Path("app/cointegrated_pairs.json")
    json_backup = json_file.rename("app/cointegrated_pairs.json.backup")
    
    try:
        # Should fallback to CSV
        pairs = pair_storage.load_pairs()
        assert len(pairs) > 0, "CSV fallback failed"
        print("✅ CSV fallback loading works")
    finally:
        # Restore JSON file
        json_backup.rename(json_file)
    
    return df


def test_confidence_scoring():
    """Test confidence scoring functionality."""
    print("\n⭐ Testing confidence scoring...")
    
    # Test various scenarios
    test_cases = [
        {"p_value": 0.01, "half_life": 10.0, "zero_crossings": 15, "expected_range": (0.7, 0.8)},
        {"p_value": 0.04, "half_life": 20.0, "zero_crossings": 8, "expected_range": (0.25, 0.35)},
        {"p_value": 0.049, "half_life": 25.0, "zero_crossings": 3, "expected_range": (0.0, 0.2)},
    ]
    
    for i, case in enumerate(test_cases):
        confidence = calculate_confidence_score(
            case["p_value"], case["half_life"], case["zero_crossings"]
        )
        min_expected, max_expected = case["expected_range"]
        
        print(f"   Test {i+1}: p={case['p_value']}, half_life={case['half_life']}, crossings={case['zero_crossings']} → confidence={confidence:.3f}")
        
        assert min_expected <= confidence <= max_expected, f"Confidence {confidence} not in expected range {case['expected_range']}"
    
    print("✅ Confidence scoring works correctly")


def test_query_methods():
    """Test storage query methods."""
    print("\n🔎 Testing query methods...")
    
    storage = pair_storage
    
    # Test get_best_pairs
    best_pairs = storage.get_best_pairs(limit=2)
    assert len(best_pairs) <= 2, "get_best_pairs limit not respected"
    if len(best_pairs) > 1:
        assert best_pairs[0].confidence_score >= best_pairs[1].confidence_score, "Best pairs not sorted by confidence"
    print(f"✅ get_best_pairs returned {len(best_pairs)} pairs")
    
    # Test get_high_confidence_pairs
    high_confidence = storage.get_high_confidence_pairs()
    for pair in high_confidence:
        assert pair.is_high_confidence, "Non-high-confidence pair in high-confidence results"
    print(f"✅ get_high_confidence_pairs returned {len(high_confidence)} pairs")
    
    # Test get_pair_by_markets
    if best_pairs:
        test_pair = best_pairs[0]
        found_pair = storage.get_pair_by_markets(test_pair.base_market, test_pair.quote_market)
        assert found_pair is not None, "Pair not found by markets"
        assert found_pair.base_market == test_pair.base_market, "Wrong pair returned"
    print("✅ get_pair_by_markets works correctly")
    
    # Test storage info
    storage_info = storage.get_storage_info()
    required_info = ["total_pairs", "high_confidence_pairs", "storage_format", "has_json", "has_csv"]
    for key in required_info:
        assert key in storage_info, f"Missing storage info key: {key}"
    
    print("✅ Storage info method works")
    print(f"   📊 Storage info: {storage_info}")


def test_backup_functionality():
    """Test backup functionality."""
    print("\n💾 Testing backup functionality...")
    
    backup_dir = Path("app/pair_history")
    assert backup_dir.exists(), "Backup directory not created"
    
    backup_files = list(backup_dir.glob("pairs_*.json"))
    assert len(backup_files) > 0, "No backup files created"
    
    # Test backup file structure
    latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
    with open(latest_backup, 'r') as f:
        backup_data = json.load(f)
    
    assert "metadata" in backup_data, "Backup missing metadata"
    assert "pairs" in backup_data, "Backup missing pairs"
    
    print(f"✅ Backup functionality works ({len(backup_files)} backups found)")
    print(f"   📁 Latest backup: {latest_backup.name}")


def run_comprehensive_test():
    """Run all tests."""
    print("🚀 Starting Enhanced Pair Storage Test Suite")
    print("=" * 60)
    
    try:
        # Clean up any existing test files
        for file_path in ["app/cointegrated_pairs.json", "app/cointegrated_pairs.csv"]:
            path = Path(file_path)
            if path.exists():
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    import shutil
                    shutil.rmtree(path)
        
        # Run tests
        storage, test_pairs = test_storage_manager()
        test_json_structure()
        test_csv_compatibility()
        test_confidence_scoring()
        test_query_methods()
        test_backup_functionality()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("\n📊 Test Summary:")
        print(f"   • Created and saved {len(test_pairs)} test pairs")
        print("   • JSON storage: ✅ Working")
        print("   • CSV compatibility: ✅ Working")
        print("   • Confidence scoring: ✅ Working")
        print("   • Query methods: ✅ Working")
        print("   • Backup system: ✅ Working")
        print(f"   • High-confidence pairs: {len([p for p in test_pairs if p.is_high_confidence])}/{len(test_pairs)}")
        
        print("\n🔧 Enhanced storage system is ready for production!")
        
        return True
        
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)