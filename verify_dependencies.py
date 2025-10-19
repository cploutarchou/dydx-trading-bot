#!/usr/bin/env python3
"""
Verification script to confirm all dependencies are properly installed.
Run this after installing requirements.txt to validate the environment.
"""

import subprocess
import sys


def check_import(module_name, display_name=None):
    """Check if a module can be imported."""
    if display_name is None:
        display_name = module_name

    try:
        __import__(module_name)
        print(f"✅ {display_name}")
        return True
    except ImportError as e:
        print(f"❌ {display_name}: {e}")
        return False


def get_version(package_name, module_name=None):
    """Get installed version of a package."""
    if module_name is None:
        module_name = package_name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
        return "Unknown"
    except Exception as e:
        return f"Error: {e}"


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("dYdX Trading Bot - Dependency Verification")
    print("=" * 60)
    print()

    # Critical imports
    print("Core Package Imports:")
    print("-" * 40)
    critical_packages = [
        ("redis", "Redis client"),
        ("grpc", "gRPC"),
        ("v4_proto", "dYdX v4 Protocol"),
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("dydx_v4_client", "dYdX v4 Client"),
        ("google.protobuf", "Protocol Buffers"),
        ("web3", "Web3.py"),
        ("requests", "Requests"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
    ]

    all_passed = True
    for module, display in critical_packages:
        if not check_import(module, display):
            all_passed = False

    print()
    print("Package Versions:")
    print("-" * 40)

    version_checks = [
        ("protobuf", "Protocol Buffers", "google.protobuf"),
        ("dydx-v4-client", "dYdX Client", "dydx_v4_client"),
        ("v4-proto", "v4 Protocol", "v4_proto"),
        ("grpcio", "gRPC"),
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("redis", "Redis"),
        ("pydantic", "Pydantic"),
        ("uvicorn", "Uvicorn"),
        ("web3", "Web3.py"),
        ("requests", "Requests"),
    ]

    for pkg_name, display_name, *module_name in version_checks:
        module = module_name[0] if module_name else pkg_name.replace("-", "_")
        version = get_version(pkg_name, module)
        print(f"  {display_name:20} {version}")

    print()
    print("=" * 60)

    if all_passed:
        print("✅ All critical packages imported successfully!")
        print("Your environment is ready for development.")
        return 0
    else:
        print("❌ Some packages failed to import.")
        print("Please run: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
