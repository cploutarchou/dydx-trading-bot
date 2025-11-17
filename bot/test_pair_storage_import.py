#!/usr/bin/env python
"""Test imports for pair_storage module"""

try:
    from internal.domain.persistence.cointegration_storage import CointegrationResult
    print("✓ Direct import from cointegration_storage works")
except Exception as e:
    print(f"✗ Direct import failed: {e}")

try:
    from internal.domain import CointegrationResult as CR
    print("✓ Package import from domain works")
except Exception as e:
    print(f"✗ Package import failed: {e}")

try:
    from func_cointegration import store_cointegration_results
    print("✓ func_cointegration imports successfully")
except Exception as e:
    print(f"✗ func_cointegration import failed: {e}")

try:
    from func_entry_pairs import open_positions
    print("✓ func_entry_pairs imports successfully")
except Exception as e:
    print(f"✗ func_entry_pairs import failed: {e}")

print("\nAll critical imports working!")

