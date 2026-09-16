#!/usr/bin/env bash
set -euo pipefail

curl() {
  command curl --connect-timeout 10 --max-time 90 --retry 2 --retry-delay 2 --retry-all-errors "$@"
}

BASE="${PROTECTION_ADVISOR_BASE_URL:-https://salcapa-dev-b48224.ashycoast-29444a28.southcentralus.azurecontainerapps.io}"
WORK="$(mktemp -d)"
COOKIE="$WORK/cookies.txt"
PASSWORD="Pa!$(openssl rand -hex 18)"
RUN_KEY="${GITHUB_RUN_ID:-$(date -u +%Y%m%d%H%M%S)}"
EMAIL="mduncan+pa-v3121-${RUN_KEY}@salus.solutions"
DELETED=0
cleanup() {
  if [ "$DELETED" = "0" ] && [ -n "${CSRF:-}" ] && [ -s "$COOKIE" ]; then
    command curl --connect-timeout 5 --max-time 20 -sS -c "$COOKIE" -b "$COOKIE" \
      -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d '{}' \
      "$BASE/public/protection-advisor/delete" >/dev/null 2>&1 || true
  fi
  : > "$COOKIE" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT
STAGE="public page"
trap 'printf "Acceptance failed during: %s\n" "$STAGE" >&2' ERR

curl -fsS -D "$WORK/page.headers" -o "$WORK/page.html" "$BASE/protection-advisor"
grep -qi '^content-security-policy:' "$WORK/page.headers"
grep -qi '^x-frame-options: DENY' "$WORK/page.headers"
grep -q 'Protection Advisor' "$WORK/page.html"

STAGE="session and consent"
jq -nc '{organization_type:"Business",primary_consent:true,secondary_deidentified_consent:false}' > "$WORK/start.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' \
  -d @"$WORK/start.json" "$BASE/public/protection-advisor/session" > "$WORK/session.json"
CSRF="$(jq -r '.csrf_token' "$WORK/session.json")"
jq -e '.questionnaire_version=="SPA-PUBLIC-QUESTIONNAIRE-2.0.0" and (.questions|length)==28' "$WORK/session.json" >/dev/null
jq -e '[.questions[].mission_areas[]]|unique|sort == ["Mitigation","Prevention","Protection","Recovery","Response"]' "$WORK/session.json" >/dev/null
jq -e '[.questions[].capabilities[]]|unique|length == 32' "$WORK/session.json" >/dev/null

STAGE="question answers"
index=0
while IFS= read -r key; do
  case $((index % 5)) in
    0) state="No" ;;
    1) state="Partially" ;;
    2) state="Unknown" ;;
    3) state="Documented" ;;
    4) state="Validated" ;;
  esac
  jq -nc --arg k "$key" --arg s "$state" '{question_key:$k,answer_state:$s,note:"Governed fictional launch-acceptance response; not a real organization."}' > "$WORK/answer.json"
  curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d @"$WORK/answer.json" "$BASE/public/protection-advisor/answer" > "$WORK/answer-result.json"
  jq -e '.saved==true' "$WORK/answer-result.json" >/dev/null
  index=$((index+1))
  sleep 0.15
done < <(jq -r '.questions[].key' "$WORK/session.json")

STAGE="preliminary result"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{}' "$BASE/public/protection-advisor/preliminary" > "$WORK/preliminary.json"
jq -e '.anonymous==true and ((.result.notice|length)>0)' "$WORK/preliminary.json" >/dev/null

STAGE="account creation and verification email"
jq -nc --arg email "$EMAIL" --arg password "$PASSWORD" '{email:$email,password:$password,detailed_assessment_acknowledged:true,identifiable_retention_consent:true}' > "$WORK/account.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d @"$WORK/account.json" "$BASE/public/protection-advisor/account" > "$WORK/account-result.json"
jq -e '.authenticated==true and .email_verification=="Delivered" and (.email_verification_error==null or .email_verification_error=="")' "$WORK/account-result.json" >/dev/null

STAGE="draft save"
jq -nc --arg email "$EMAIL" '{fields:{organization_name:"Salus Fictional Acceptance Organization",contact_name:"Fictional Acceptance Reviewer",contact_email:$email,facility_scope:"Multiple facilities",facility_locations:"Fictional locations only",personnel_range:"101-500",affected_population_range:"501-2,000",annual_revenue_range:"$25M-$100M",specific_activities:["Hazardous materials, fuels, chemicals, or regulated waste","Sensitive information, technology, research, or intellectual property"],essential_functions:"Fictional essential operations",maximum_tolerable_downtime:"24 hours",existing_program_maturity:"Developing",internal_implementation_capacity:"Limited",primary_objective:"Prioritize protection improvements",external_requirements:"Contractual and regulatory requirements",recent_concerns:"Fictional acceptance concerns",desired_timing:"Within 90 days",decision_authority:"Executive leadership",investment_range:"$50,000-$150,000"}}' > "$WORK/draft.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d @"$WORK/draft.json" "$BASE/public/protection-advisor/draft" > "$WORK/draft-result.json"
jq -e '.saved==true' "$WORK/draft-result.json" >/dev/null

STAGE="logout"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{}' "$BASE/public/protection-advisor/logout" > "$WORK/logout.json"
jq -e '.authenticated==false' "$WORK/logout.json" >/dev/null

STAGE="login and resume"
jq -nc --arg email "$EMAIL" --arg password "$PASSWORD" '{email:$email,password:$password}' > "$WORK/login.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' \
  -d @"$WORK/login.json" "$BASE/public/protection-advisor/login" > "$WORK/login-result.json"
CSRF="$(jq -r '.csrf_token' "$WORK/login-result.json")"
jq -e '.authenticated==true and (.questions|length)==28 and (.answers|length)==28 and .draft.organization_name=="Salus Fictional Acceptance Organization"' "$WORK/login-result.json" >/dev/null

STAGE="submission and notifications"
jq -nc --arg email "$EMAIL" '{organization_name:"Salus Fictional Acceptance Organization",contact_name:"Fictional Acceptance Reviewer",contact_email:$email,detailed_assessment_acknowledged:true,identifiable_retention_consent:true,facility_scope:"Multiple facilities",facility_locations:"Fictional locations only",personnel_range:"101-500",affected_population_range:"501-2,000",annual_revenue_range:"$25M-$100M",specific_activities:["Hazardous materials, fuels, chemicals, or regulated waste","Sensitive information, technology, research, or intellectual property"],essential_functions:"Fictional essential operations",maximum_tolerable_downtime:"24 hours",existing_program_maturity:"Developing",internal_implementation_capacity:"Limited",primary_objective:"Prioritize protection improvements",external_requirements:"Contractual and regulatory requirements",recent_concerns:"Fictional acceptance concerns",desired_timing:"Within 90 days",decision_authority:"Executive leadership",investment_range:"$50,000-$150,000"}' > "$WORK/submit.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d @"$WORK/submit.json" "$BASE/public/protection-advisor/submit" > "$WORK/submit-result.json"
jq -e '.submitted==true and .result.status=="Preliminary — Salus Review Required" and (.package.capabilities_considered|length)==32 and (.package.services|length)>0 and ([.notifications[].state]|all(.=="Delivered"))' "$WORK/submit-result.json" >/dev/null

SUMMARY="$(jq -c '{submitted,result_status:.result.status,capabilities:(.package.capabilities_considered|length),services:[.package.services[]|{title,level}],notifications}' "$WORK/submit-result.json")"

STAGE="test content deletion"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{}' "$BASE/public/protection-advisor/delete" > "$WORK/delete-result.json"
jq -e '.deleted==true' "$WORK/delete-result.json" >/dev/null
DELETED=1

ACCEPTANCE="$(jq -nc --arg email "$EMAIL" --argjson acceptance "$SUMMARY" '{public_page_security_headers:true,questionnaire_version:"SPA-PUBLIC-QUESTIONNAIRE-2.0.0",questions:28,core_capabilities:32,mission_areas:5,primary_consent:true,secondary_deidentified_consent:false,account_email:$email,email_verification:"Delivered",save_resume:true,submission:$acceptance,test_content_deleted:true}')"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Protection Advisor live acceptance"
    echo
    echo '```json'
    echo "$ACCEPTANCE" | jq .
    echo '```'
  } >> "$GITHUB_STEP_SUMMARY"
else
  echo "$ACCEPTANCE"
fi
