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

async function render({member=false,blockers=[],withQa=false,priorIssue=false}={}){
  const content={innerHTML:''},picker={value:'7',onchange:null};
  const selectedWorkspace=structuredClone(workspace);
  if(withQa) selectedWorkspace.products.SalINTEL.qa_evidence={id:19,archive_sha256:'c'.repeat(64)};
  if(priorIssue) selectedWorkspace.issue={id:3,record_sha256:'d'.repeat(64)};
  const context={
    currentRole:member?'Client Executive':'System Administrator',
    activeAssessmentId:7,
    isProtectedMember:()=>member,
    $:selector=>selector==='#content'?content:picker,
    document:{querySelectorAll:()=>[]},
    localStorage:{setItem:()=>{}},
    esc:value=>String(value??''),
    api:async url=>url==='/api/assessments'?[{id:7,name:'Fictional Cedar Site'}]:
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
  assert.doesNotMatch(blocked,/id="level1a-staff-issue"/);
  const ready=await render();
  assert.match(ready,/id="level1a-staff-issue"/);
  assert.match(ready,/Marc's separate report issue decision/);
  assert.doesNotMatch(ready,/class="level1a-staff-review"/);
  const withQa=await render({withQa:true});
  assert.match(withQa,/Single-operator review requires the protected staff identity/);
  const successor=await render({priorIssue:true});
  assert.match(successor,/Latest issued packet/);
  assert.match(successor,/id="level1a-staff-issue"/);
  const buyer=await render({member:true});
  assert.match(buyer,/limited to assigned Salus staff/);
  assert.doesNotMatch(buyer,/id="level1a-staff-issue"/);
  process.stdout.write('Level 1A staff UI gates passed.\n');
}
main().catch(error=>{console.error(error);process.exitCode=1});
