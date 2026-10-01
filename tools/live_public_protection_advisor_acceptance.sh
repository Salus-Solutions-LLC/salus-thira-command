#!/usr/bin/env bash
set -euo pipefail

curl() {
  command curl --connect-timeout 10 --max-time 90 --retry 2 --retry-delay 2 --retry-all-errors "$@"
}

BASE="${PROTECTION_ADVISOR_BASE_URL:-https://salcapa-dev-b48224.ashycoast-29444a28.southcentralus.azurecontainerapps.io}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
COOKIE="$WORK/cookies.txt"
PASSWORD="Pa!$(openssl rand -hex 18)"
if [ -n "${GITHUB_RUN_ID:-}" ]; then
  RUN_KEY="${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT:-1}"
else
  RUN_KEY="$(date -u +%Y%m%d%H%M%S)-$"
fi
EMAIL="mduncan+pa-v3143-${RUN_KEY}@salus.solutions"
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

curl -fsS -D "$WORK/page.headers" -o "$WORK/page.html" "$BASE/protection-advisor/embed"
grep -qi '^content-security-policy:' "$WORK/page.headers"
grep -qi 'frame-ancestors https://www.salus.solutions https://salus.solutions' "$WORK/page.headers"
! grep -qi '^x-frame-options:' "$WORK/page.headers"
grep -q 'Part 1 — Anonymous Protection Readiness Review' "$WORK/page.html"
grep -q 'class="question-nav"' "$WORK/page.html"
grep -q '.question-nav{position:sticky;bottom:0' "$WORK/page.html"
grep -q '<aside class="assessment-important"><strong>Important notice:</strong>' "$WORK/page.html"
grep -q 'document.getElementById("assessment").scrollIntoView' "$WORK/page.html"
grep -q 'preferred_min_height:900' "$WORK/page.html"
grep -q 'Print or Save Preliminary Summary' "$WORK/page.html"
grep -q 'Download Scope and Readiness Report' "$WORK/page.html"
grep -q 'print-part1' "$WORK/page.html"
grep -q 'CONFIDENTIAL' "$WORK/page.html"
grep -q 'href="https://salcapa.salus.solutions/protection-advisor/services" target="_blank" rel="noopener noreferrer"' "$WORK/page.html"

STAGE="session and consent"
jq -nc '{organization_type:"Business",primary_consent:true,secondary_deidentified_consent:false}' > "$WORK/start.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' \
  -d @"$WORK/start.json" "$BASE/public/protection-advisor/session" > "$WORK/session.json"
CSRF="$(jq -r '.csrf_token' "$WORK/session.json")"
jq -e '.questionnaire_version=="SPA-PUBLIC-QUESTIONNAIRE-2.3.0" and (.questions|length)==9' "$WORK/session.json" >/dev/null
jq -e '[.questions[].mission_areas[]]|unique|sort == ["Mitigation","Prevention","Protection","Recovery","Response"]' "$WORK/session.json" >/dev/null
jq -e '[.questions[].capabilities[]]|unique|length == 18' "$WORK/session.json" >/dev/null

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
jq -nc --arg email "$EMAIL" '{fields:{protected_member_code_name:"Fictional Acceptance Member",project_code_name:"Automated Acceptance",handling_profile:"Commercial Confidential",organization_name:"Salus Fictional Acceptance Organization",contact_name:"Fictional Acceptance Reviewer",contact_email:$email,facility_scope:"Multiple facilities",facility_locations:"Fictional locations only",personnel_range:"101-500",affected_population_range:"501-2,000",annual_revenue_range:"$25M-$100M",specific_activities:["Hazardous materials, fuels, chemicals, or regulated waste","Sensitive information, technology, research, or intellectual property"],essential_functions:"Fictional essential operations",maximum_tolerable_downtime:"24 hours",existing_program_maturity:"Developing",internal_implementation_capacity:"Limited",primary_objective:"Prioritize protection improvements",external_requirements:"Contractual and regulatory requirements",recent_concerns:"Fictional acceptance concerns",desired_timing:"Within 90 days",decision_authority:"Executive leadership",investment_range:"$50,000-$150,000"}}' > "$WORK/draft.json"
jq '.fields += {covered_operation:"Two fictional facilities",decision_units:"Two",separate_findings:"Yes",group_priorities:"No"}' "$WORK/draft.json" > "$WORK/draft-scope.json"
mv "$WORK/draft-scope.json" "$WORK/draft.json"
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
jq -e '.authenticated==true and (.questions|length)==28 and (.answers|length)==9 and .draft.organization_name=="Salus Fictional Acceptance Organization"' "$WORK/login-result.json" >/dev/null
jq -S '.answers' "$WORK/login-result.json" > "$WORK/part1-answers.json"
jq -e '. as $response | ([.questions[].key | select($response.answers[.] == null)] | length)==19' "$WORK/login-result.json" >/dev/null

STAGE="consented Part 2 capability questions"
while IFS= read -r key; do
  jq -nc --arg k "$key" '{question_key:$k,answer_state:"Unknown",note:"Governed fictional launch-acceptance response."}' > "$WORK/answer.json"
  curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -d @"$WORK/answer.json" "$BASE/public/protection-advisor/answer" > "$WORK/answer-result.json"
  jq -e '.saved==true' "$WORK/answer-result.json" >/dev/null
done < <(jq -r -f "$SCRIPT_DIR/advisor_missing_part2_keys.jq" "$WORK/login-result.json")

STAGE="Part 1 carry-forward and Part 2 completion"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{}' "$BASE/public/protection-advisor/logout" > "$WORK/part2-logout.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' \
  -d @"$WORK/login.json" "$BASE/public/protection-advisor/login" > "$WORK/part2-resume.json"
CSRF="$(jq -r '.csrf_token' "$WORK/part2-resume.json")"
jq -e --argjson expected 28 --slurpfile before "$WORK/part1-answers.json" \
  -f "$SCRIPT_DIR/advisor_part1_carry_forward.jq" "$WORK/part2-resume.json" >/dev/null

STAGE="submission and notifications"
jq -nc --arg email "$EMAIL" '{protected_member_code_name:"Fictional Acceptance Member",project_code_name:"Automated Acceptance",handling_profile:"Commercial Confidential",organization_name:"Salus Fictional Acceptance Organization",contact_name:"Fictional Acceptance Reviewer",contact_email:$email,detailed_assessment_acknowledged:true,identifiable_retention_consent:true,facility_scope:"Multiple facilities",facility_locations:"Fictional locations only",personnel_range:"101-500",affected_population_range:"501-2,000",annual_revenue_range:"$25M-$100M",specific_activities:["Hazardous materials, fuels, chemicals, or regulated waste","Sensitive information, technology, research, or intellectual property"],essential_functions:"Fictional essential operations",maximum_tolerable_downtime:"24 hours",existing_program_maturity:"Developing",internal_implementation_capacity:"Limited",primary_objective:"Prioritize protection improvements",external_requirements:"Contractual and regulatory requirements",recent_concerns:"Fictional acceptance concerns",desired_timing:"Within 90 days",decision_authority:"Executive leadership",investment_range:"$50,000-$150,000"}' > "$WORK/submit.json"
jq '. += {covered_operation:"Two fictional facilities",decision_units:"Two",separate_findings:"Yes",group_priorities:"No"}' "$WORK/submit.json" > "$WORK/submit-scope.json"
mv "$WORK/submit-scope.json" "$WORK/submit.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d @"$WORK/submit.json" "$BASE/public/protection-advisor/submit" > "$WORK/submit-result.json"
jq -e '.submitted==true and .result.status=="Preliminary — Salus Review Required" and .package.core_capabilities_considered==32 and (.package.services|length)>0 and ([.package.services[].level]|all(.>=1 and .<=3)) and ([.notifications[].state]|all(.=="Delivered"))' "$WORK/submit-result.json" >/dev/null
jq -e '.package.provisional_path.band=="B" and .package.scope_receipt.requested_boundary=="Two fictional facilities"' "$WORK/submit-result.json" >/dev/null

SUMMARY="$(jq -c '{submitted,result_status:.result.status,capabilities:.package.core_capabilities_considered,services:[.package.services[]|{title,level}],notifications}' "$WORK/submit-result.json")"

STAGE="submitted result logout and long-term account retrieval"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{}' "$BASE/public/protection-advisor/logout" >/dev/null
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' \
  -d @"$WORK/login.json" "$BASE/public/protection-advisor/login" > "$WORK/retained-result.json"
CSRF="$(jq -r '.csrf_token' "$WORK/retained-result.json")"
jq -e '.authenticated==true and .assessment_status=="Submitted" and .result.status=="Preliminary — Salus Review Required" and .package.core_capabilities_considered==32 and (.package.services|length)>0 and ([.package.services[].level]|all(.>=1 and .<=3)) and (.submitted_at|length)>0' "$WORK/retained-result.json" >/dev/null

STAGE="exact original report retrieval"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H "X-CSRF-Token: $CSRF" \
  -D "$WORK/report.headers" -o "$WORK/report-first.pdf" "$BASE/public/protection-advisor/report.pdf"
head -c 4 "$WORK/report-first.pdf" | grep -q '%PDF'
grep -qi '^content-type: application/pdf' "$WORK/report.headers"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H "X-CSRF-Token: $CSRF" \
  -o "$WORK/report-again.pdf" "$BASE/public/protection-advisor/report.pdf"
cmp "$WORK/report-first.pdf" "$WORK/report-again.pdf"

STAGE="test content deletion"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{}' "$BASE/public/protection-advisor/delete" > "$WORK/delete-result.json"
jq -e '.deleted==true' "$WORK/delete-result.json" >/dev/null
DELETED=1

ACCEPTANCE="$(jq -nc --arg email "$EMAIL" --argjson acceptance "$SUMMARY" '{public_page_security_headers:true,questionnaire_version:"SPA-PUBLIC-QUESTIONNAIRE-2.3.0",questions:9,core_capability_framework:32,directly_mapped_capabilities:18,mission_areas:5,primary_consent:true,secondary_deidentified_consent:false,account_email:$email,email_verification:"Delivered",save_resume:true,submission:$acceptance,test_content_deleted:true}')"
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
