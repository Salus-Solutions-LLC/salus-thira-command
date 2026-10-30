const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const script=fs.readFileSync(path.join(__dirname,'../static/level1a-staff.js'),'utf8');
const products=Object.fromEntries(['SalINTEL','SalTHIRA','SalOPS','SalCAPA'].map((key,index)=>
  [key,{report:{id:index+10,version_no:1,status:'Draft',content_sha256:'a'.repeat(64)},
    draft_scan:null,qa_archive_scan:null,qa_pdf_scan:null,qa_evidence:null,
    conformance:null,review:null}]));
const workspace={order_id:10,assessment_id:7,buyer_user_id:44,
  source_record_sha256:'b'.repeat(64),products,reconciliation:null,issue:null};

async function render({member=false,blockers=[],withQa=false,priorIssue=false,issuedReports=false,scanStatus=null,newerScan=false}={}){
  const content={innerHTML:''},picker={value:'7',onchange:null};
  const selectedWorkspace=structuredClone(workspace);
  if(withQa) selectedWorkspace.products.SalINTEL.qa_evidence={id:19,archive_sha256:'c'.repeat(64)};
  if(scanStatus) selectedWorkspace.products.SalOPS.draft_scan={id:31,status:scanStatus,
    content_sha256:newerScan?'e'.repeat(64):'a'.repeat(64)};
  if(priorIssue) selectedWorkspace.issue={id:3,record_sha256:'d'.repeat(64)};
  if(issuedReports) Object.values(selectedWorkspace.products).forEach(item=>item.report.status='Issued');
  const context={
    currentRole:member?'Client Executive':'System Administrator',
    activeAssessmentId:7,
    isProtectedMember:()=>member,
    $:selector=>selector==='#content'?content:picker,
    document:{querySelectorAll:()=>[]},
    localStorage:{setItem:()=>{}},
    esc:value=>String(value??''),
    api:async url=>url==='/api/level1a/staff/assessments'?[{id:7,name:'Fictional Cedar Site'}]:
      url.endsWith('/level1a-report-workspace')?selectedWorkspace:
      {status:blockers.length?'Blocked':'Technically ready for named human issue',blockers}
  };
  vm.runInNewContext(script,context);
  await context.level1aStaffView();
  return content.innerHTML;
}

async function main(){
  const blocked=await render({blockers:['SalOPS: qualified human review missing']});
  assert.match(blocked,/qualified human review missing/);
  assert.match(blocked,/1\. Stage Word draft for screening/);
  assert.match(blocked,/5\. Separate issue decision/);
  assert.match(blocked,/Version, screening, and review details/);
  assert.doesNotMatch(blocked,/id="level1a-staff-issue"/);
  const ready=await render();
  assert.match(ready,/id="level1a-staff-issue"/);
  assert.match(ready,/Marc's separate report issue decision/);
  assert.doesNotMatch(ready,/class="level1a-staff-review"/);
  const withQa=await render({withQa:true});
  assert.match(withQa,/Single-operator review requires the protected staff identity/);
  const pending=await render({scanStatus:'Pending',newerScan:true});
  assert.match(pending,/Waiting for newer file/);
  assert.match(pending,/In progress/);
  assert.doesNotMatch(pending,/data-finalize-scan="31"/);
  const cleared=await render({scanStatus:'Cleared',newerScan:true});
  assert.match(cleared,/data-finalize-scan="31"/);
  assert.match(cleared,/Register cleared Word draft/);
  const successor=await render({priorIssue:true});
  assert.match(successor,/Latest issued packet/);
  assert.match(successor,/id="level1a-staff-issue"/);
  const priorVersions=await render({issuedReports:true,blockers:['Current report versions are issued']});
  assert.match(priorVersions,/Stage revised Word draft for screening/);
  assert.doesNotMatch(priorVersions,/id="level1a-staff-issue"/);
  const buyer=await render({member:true});
  assert.match(buyer,/limited to assigned Salus staff/);
  assert.doesNotMatch(buyer,/id="level1a-staff-issue"/);
  process.stdout.write('Level 1A staff UI gates passed.\n');
}
main().catch(error=>{console.error(error);process.exitCode=1});
