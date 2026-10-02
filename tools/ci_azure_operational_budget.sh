#!/usr/bin/env bash
# Exercise the governed cost-alert guard without Azure credentials or resources.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT
cat > "$TEMP_DIR/az" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
case "$1 $2" in
  "group exists") printf '%s\n' "${MOCK_GROUP:-true}" ;;
  "consumption budget")
    if [[ "$MOCK_BUDGET" == "missing" ]]; then exit 3; fi
    printf '%s\n' "$MOCK_BUDGET"
    ;;
  "account show") printf '%s\n' '00000000-0000-0000-0000-000000000001' ;;
  "resource show")
    case "${MOCK_SCANNER:-false}" in
      true) printf '%s\n' '{"properties":{"isEnabled":true}}' ;;
      false) printf '%s\n' 'Code: ResourceNotFound' >&2; exit 3 ;;
      unreadable) printf '%s\n' 'Code: AuthorizationFailed' >&2; exit 3 ;;
      *) echo 'Unexpected scanner mock state.' >&2; exit 4 ;;
    esac
    ;;
  *) echo "Unexpected Azure mock call: $*" >&2; exit 4 ;;
esac
MOCK
chmod +x "$TEMP_DIR/az"
export PATH="$TEMP_DIR:$PATH"
export MOCK_GROUP=true
export MOCK_BUDGET=25
export MOCK_SCANNER=false
test "$(bash "$ROOT_DIR/tools/azure_operational_budget.sh" rg-salcapa-dev dev b48224 existing)" = "25"
export MOCK_BUDGET=75
export MOCK_SCANNER=true
test "$(bash "$ROOT_DIR/tools/azure_operational_budget.sh" rg-salcapa-dev dev b48224 existing)" = "75"
export MOCK_BUDGET=25
if bash "$ROOT_DIR/tools/azure_operational_budget.sh" rg-salcapa-dev dev b48224 existing >/dev/null 2>&1; then
  echo 'Enabled scanner without $75 alert was accepted.' >&2
  exit 1
fi
export MOCK_BUDGET=75
export MOCK_SCANNER=false
if bash "$ROOT_DIR/tools/azure_operational_budget.sh" rg-salcapa-dev dev b48224 existing >/dev/null 2>&1; then
  echo '$75 alert without scanner was accepted.' >&2
  exit 1
fi
export MOCK_SCANNER=unreadable
if bash "$ROOT_DIR/tools/azure_operational_budget.sh" rg-salcapa-dev dev b48224 existing >/dev/null 2>&1; then
  echo 'Unreadable scanner state was accepted.' >&2
  exit 1
fi
export MOCK_SCANNER=false
export MOCK_GROUP=false
export MOCK_BUDGET=missing
test "$(bash "$ROOT_DIR/tools/azure_operational_budget.sh" rg-salcapa-dev dev b48224 foundation)" = "25"
if bash "$ROOT_DIR/tools/azure_operational_budget.sh" rg-salcapa-dev dev b48224 existing >/dev/null 2>&1; then
  echo 'Missing existing resource group was accepted.' >&2
  exit 1
fi
echo 'Azure budget/scanner state guard passed.'
