#!/usr/bin/env bash
set -euo pipefail

INSTALLER="${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py"

if [[ ! -f "$INSTALLER" ]]; then
  echo "Could not find Codex skill installer at: $INSTALLER" >&2
  echo "Install from Codex by asking: install the IPB skill from https://github.com/clockless-org/ipb-skills/tree/main/skills/ipb" >&2
  exit 1
fi

python3 "$INSTALLER" --repo clockless-org/ipb-skills --path skills/ipb "$@"
echo "Installed IPB skill. Restart Codex to pick up new skills."
