#!/usr/bin/env bash
# Preserve the governed total RG alert during foundation/app redeployments.
# $1 resource group, $2 environment, $3 suffix, $4 foundation|existing
set -euo pipefail
if [[ $# -ne 4 ]]; then
  echo "Expected resource group, environment, suffix and budget mode." >&2
  exit 2
fi
RESOURCE_GROUP="$1"
TARGET_ENVIRONMENT="$2"
UNIQUE_SUFFIX="$3"
BUDGET_MODE="$4"
[[ "$RESOURCE_GROUP" == "rg-salcapa-$TARGET_ENVIRONMENT" ]] || exit 2
[[ "$TARGET_ENVIRONMENT" =~ ^(dev|prod)$ ]] || exit 2
[[ "$UNIQUE_SUFFIX" =~ ^[a-z0-9]{4,6}$ ]] || exit 2
[[ "$BUDGET_MODE" =~ ^(foundation|existing)$ ]] || exit 2

BUDGET_NAME="salcapa-$TARGET_ENVIRONMENT-$UNIQUE_SUFFIX-monthly-budget"
if [[ "$BUDGET_MODE" == "foundation" && "$(az group exists --name "$RESOURCE_GROUP")" == "false" ]]; then
  printf "25\n"
  exit 0
fi
if BUDGET_RAW="$(az consumption budget show --resource-group "$RESOURCE_GROUP" --budget-name "$BUDGET_NAME" --query amount -o tsv 2>/dev/null)"; then
  :
elif [[ "$BUDGET_MODE" == "foundation" ]]; then
  BUDGET_RAW="25"
else
  echo "The existing governed Azure budget cannot be read." >&2
  exit 1
fi
case "$BUDGET_RAW" in
  25|25.0|25.00) BUDGET_USD=25 ;;
  75|75.0|75.00) BUDGET_USD=75 ;;
  *) echo 'The live Azure budget is outside the approved $25/$75 states.' >&2; exit 1 ;;
esac

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
SCANNER_ACCOUNT="salcapa$TARGET_ENVIRONMENT$UNIQUE_SUFFIX""scan"
SCANNER_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$SCANNER_ACCOUNT/providers/Microsoft.Security/defenderForStorageSettings/current"
SCANNER_JSON="$(az resource list --resource-group "$RESOURCE_GROUP" --resource-type Microsoft.Security/defenderForStorageSettings -o json)"
SCANNER_ENABLED="$(jq -r --arg id "$SCANNER_ID" '[.[] | select((.id | ascii_downcase) == ($id | ascii_downcase)) | .properties.isEnabled] | if length == 0 then "false" else .[0] end' <<< "$SCANNER_JSON")"
if [[ "$SCANNER_ENABLED" != "true" && "$SCANNER_ENABLED" != "false" ]]; then
  echo "The Defender scanner state could not be established." >&2
  exit 1
fi
if [[ "$SCANNER_ENABLED" == "true" && "$BUDGET_USD" != "75" ]]; then
  echo 'Scanner is enabled but the approved $75 total budget alert is absent.' >&2
  exit 1
fi
if [[ "$BUDGET_USD" == "75" && ( "$SCANNER_ENABLED" != "true" || "$TARGET_ENVIRONMENT" != "dev" ) ]]; then
  echo 'The $75 alert is permitted only for the approved active development scanner.' >&2
  exit 1
fi
printf '%s\n' "$BUDGET_USD"
