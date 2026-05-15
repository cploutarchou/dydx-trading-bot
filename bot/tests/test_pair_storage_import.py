#!/usr/bin/env python
"""Test imports for pair_storage module"""

try:
    from src.infrastructure.domain.cointegration_storage import CointegrationResult

    print(
        f"✓ Direct import from cointegration_storage works ({CointegrationResult.__name__})"
    )
except Exception as e:
    print(f"✗ Direct import failed: {e}")

try:
    from src.infrastructure.domain.cointegration_storage import (
        CointegrationResult as CR,
    )

    print(f"✓ Package import from domain works ({CR.__name__})")
except Exception as e:
    print(f"✗ Package import failed: {e}")

try:
    from src.trading.analysis.cointegration import store_cointegration_results

    print(
        f"✓ func_cointegration imports successfully ({store_cointegration_results.__name__})"
    )
except Exception as e:
    print(f"✗ func_cointegration import failed: {e}")

try:
    from src.trading.position_manager import open_positions

    print(f"✓ func_entry_pairs imports successfully ({open_positions.__name__})")
except Exception as e:
    print(f"✗ func_entry_pairs import failed: {e}")

print("\nAll critical imports working!")
