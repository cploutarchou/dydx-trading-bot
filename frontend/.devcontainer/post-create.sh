#!/bin/bash
# Compatibility wrapper for devcontainer post-create hook.
# Delegates to setup.sh to keep older references working.

set -euo pipefail

bash .devcontainer/setup.sh
