import hashlib
import json
import re
from urllib.parse import urlsplit
from database import ID_TABLES, is_postgres

ASSESSMENT_TABLES = [
    'threats','scenarios','capabilities','evidence','gaps','improvements','decisions','accepted_risks','risk_overrides',
    'reassessment_triggers','evidence_attachments','entity_versions','scope_changes','workflow_events','report_versions','package_agreement_artifacts','package_quote_versions','package_quote_advisor_receipt_links','package_agreement_downloads','package_member_authority_reviews','package_acceptances','package_checkout_sessions','package_payment_events','package_payment_holds','package_intake_requests','package_intake_uploads','package_product_report_versions','package_report_conformance','package_report_reconciliations','package_report_qa_evidence','package_report_qa_reviews','package_report_issue_packets','package_report_issue_deliveries','package_report_issue_acknowledgments','package_predecessor_qualifications','package_quote_predecessor_links','ops_engagements','ops_engagement_readiness','expert_conflicts','ops_engagement_assignments','ops_tasks','ops_field_reports','ops_estimates','ops_estimate_lines','ops_expenses','ops_invoice_statements'
]
ASSESSMENT_TABLES.append('package_intake_pending_scans')
RESTORE_ORDER = [
    'users','identity_acceptance_events','governed_intake','observation_intake_channels','observations','observation_attachments','observation_events','industry_profiles','industry_profile_items','industry_profile_events','tenant_industry_configurations','assessments','salintel_investigations','salintel_investigation_items','salintel_investigation_events','materials','material_links','material_events','assessment_access','threats','scenarios','capabilities','evidence',
    'gaps','improvements','decisions','accepted_risks','risk_overrides','reassessment_triggers','assessment_weights',
    'evidence_attachments','scope_changes','workflow_events','report_versions','package_agreement_artifacts','package_quote_versions','package_quote_advisor_receipt_links','package_agreement_downloads','package_member_authority_reviews','package_acceptances','package_checkout_sessions','package_payment_events','package_payment_holds','package_intake_requests','package_intake_uploads','package_product_report_versions','package_report_conformance','package_report_reconciliations','package_report_qa_evidence','package_report_qa_reviews','package_report_issue_packets','package_report_issue_deliveries','package_report_issue_acknowledgments','package_predecessor_qualifications','package_quote_predecessor_links','intel_findings','ops_service_pillars','ops_service_catalog','ops_catalog_events','expert_profiles','expert_credentials','expert_availability','ops_requests','ops_engagements','ops_engagement_readiness','expert_conflicts','ops_engagement_assignments','expert_events','ops_tasks','ops_field_reports','ops_estimates','ops_estimate_lines','ops_expenses','ops_invoice_statements','cop_coordination_threads','cop_coordination_messages','cop_decision_requests','cop_events','entity_versions','audit_log','security_events'
]
RESTORE_ORDER.insert(RESTORE_ORDER.index('package_intake_uploads')+1,
                     'package_intake_pending_scans')

def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params)]

def collect_tenant_records(conn, tenant_id:int):
    records={}
    records['tenants']=_rows(conn,'SELECT * FROM tenants WHERE id=?',(tenant_id,))
    records['users']=_rows(conn,'SELECT * FROM users WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['identity_acceptance_events']=_rows(conn,'SELECT * FROM identity_acceptance_events WHERE tenant_id=? ORDER BY accepted_at,event_key',(tenant_id,))
    records['governed_intake']=_rows(conn,'SELECT * FROM governed_intake WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['materials']=_rows(conn,'SELECT * FROM materials WHERE tenant_id=? ORDER BY CASE WHEN parent_material_id IS NULL THEN 0 ELSE 1 END,id',(tenant_id,))
    records['salintel_investigations']=_rows(conn,'SELECT * FROM salintel_investigations WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['salintel_investigation_items']=_rows(conn,'SELECT * FROM salintel_investigation_items WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['salintel_investigation_events']=_rows(conn,'SELECT * FROM salintel_investigation_events WHERE tenant_id=? ORDER BY investigation_id,version_no',(tenant_id,))
    records['material_links']=_rows(conn,'SELECT * FROM material_links WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['material_events']=_rows(conn,'SELECT * FROM material_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['industry_profiles']=_rows(conn,'SELECT * FROM industry_profiles WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['industry_profile_items']=_rows(conn,'SELECT * FROM industry_profile_items WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['industry_profile_events']=_rows(conn,'SELECT * FROM industry_profile_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['tenant_industry_configurations']=_rows(conn,'SELECT * FROM tenant_industry_configurations WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['assessments']=_rows(conn,'SELECT * FROM assessments WHERE tenant_id=? ORDER BY id',(tenant_id,))
    assessment_ids=[r['id'] for r in records['assessments']]
    user_ids=[r['id'] for r in records['users']]
    if assessment_ids:
        marks=','.join('?'*len(assessment_ids)); P=tuple(assessment_ids)
        for table in ASSESSMENT_TABLES:
            records[table]=_rows(conn,f'SELECT * FROM {table} WHERE assessment_id IN ({marks}) ORDER BY id',P)
        records['assessment_weights']=_rows(conn,f'SELECT * FROM assessment_weights WHERE assessment_id IN ({marks}) ORDER BY assessment_id',P)
    else:
        for table in ASSESSMENT_TABLES: records[table]=[]
        records['assessment_weights']=[]
    if user_ids or assessment_ids:
        clauses=[]; params=[]
        if user_ids:
            marks=','.join('?'*len(user_ids)); clauses.append(f'user_id IN ({marks})'); params.extend(user_ids)
        if assessment_ids:
            marks=','.join('?'*len(assessment_ids)); clauses.append(f'assessment_id IN ({marks})'); params.extend(assessment_ids)
        records['assessment_access']=_rows(conn,'SELECT * FROM assessment_access WHERE '+' OR '.join(clauses)+' ORDER BY id',tuple(params))
    else: records['assessment_access']=[]
    records['audit_log']=_rows(conn,'SELECT * FROM audit_log WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['security_events']=_rows(conn,'SELECT * FROM security_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['intel_findings']=_rows(conn,'SELECT * FROM intel_findings WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['observation_intake_channels']=_rows(conn,'SELECT * FROM observation_intake_channels WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['observations']=_rows(conn,'SELECT * FROM observations WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['observation_attachments']=_rows(conn,'SELECT * FROM observation_attachments WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['observation_events']=_rows(conn,'SELECT * FROM observation_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['ops_service_pillars']=_rows(conn,'SELECT * FROM ops_service_pillars WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['ops_service_catalog']=_rows(conn,'SELECT * FROM ops_service_catalog WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['ops_catalog_events']=_rows(conn,'SELECT * FROM ops_catalog_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['expert_profiles']=_rows(conn,'SELECT * FROM expert_profiles WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['expert_credentials']=_rows(conn,'SELECT * FROM expert_credentials WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['expert_availability']=_rows(conn,'SELECT * FROM expert_availability WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['expert_events']=_rows(conn,'SELECT * FROM expert_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['ops_requests']=_rows(conn,'SELECT * FROM ops_requests WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['cop_coordination_threads']=_rows(conn,'SELECT * FROM cop_coordination_threads WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['cop_coordination_messages']=_rows(conn,'SELECT * FROM cop_coordination_messages WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['cop_decision_requests']=_rows(conn,'SELECT * FROM cop_decision_requests WHERE tenant_id=? ORDER BY id',(tenant_id,))
    records['cop_events']=_rows(conn,'SELECT * FROM cop_events WHERE tenant_id=? ORDER BY id',(tenant_id,))
    return records

def validate_records(records, tenant_id:int|None=None):
    errors=[]
    required={'tenants','users','assessments','threats','scenarios','capabilities','evidence','gaps','improvements','decisions','audit_log'}
    missing=sorted(required-set(records))
    if missing: errors.append('Missing required record sets: '+', '.join(missing))
    tenants=records.get('tenants',[])
    if len(tenants)!=1: errors.append(f'Expected exactly one tenant record; found {len(tenants)}')
    elif tenant_id is not None and int(tenants[0].get('id',-1))!=int(tenant_id): errors.append('Tenant ID does not match backup manifest')
    assessments={int(r['id']) for r in records.get('assessments',[]) if r.get('id') is not None}
    if not assessments: errors.append('Recovery records contain no assessments')
    material_ids={int(r['id']) for r in records.get('materials',[]) if r.get('id') is not None}
    for row in records.get('materials',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'material {row.get("id")} crosses the tenant boundary')
        for field in ('parent_material_id','duplicate_of_material_id'):
            linked=row.get(field)
            if linked not in (None,'') and int(linked) not in material_ids: errors.append(f'material {row.get("id")} has invalid {field}')
            if linked not in (None,'') and int(linked)==int(row.get('id',-1)): errors.append(f'material {row.get("id")} cannot reference itself through {field}')
        if row.get('stored_name') and len(str(row.get('sha256','')))!=64: errors.append(f'material {row.get("id")} has invalid content digest')
    for table in ('material_links','material_events'):
        for row in records.get(table,[]):
            if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'{table} record {row.get("id")} crosses the tenant boundary')
            if int(row.get('material_id',-1)) not in material_ids: errors.append(f'{table} record {row.get("id")} has invalid material_id')
    for row in records.get('material_links',[]):
        assessment_id=row.get('assessment_id')
        if assessment_id not in (None,'') and int(assessment_id) not in assessments: errors.append(f'material_link {row.get("id")} references an assessment outside the tenant package')
    investigation_ids={int(r['id']) for r in records.get('salintel_investigations',[]) if r.get('id') is not None}
    event_versions={}
    for row in records.get('salintel_investigations',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'salintel investigation {row.get("id")} crosses the tenant boundary')
        if int(row.get('requested_tier',0)) not in (1,2,3): errors.append(f'salintel investigation {row.get("id")} has invalid requested tier')
        if int(row.get('authorized_tier',0)) not in (0,1,2,3): errors.append(f'salintel investigation {row.get("id")} has invalid authorized tier')
        if int(row.get('completed_tier',0))>int(row.get('authorized_tier',0)): errors.append(f'salintel investigation {row.get("id")} completed beyond its authorized tier')
    for row in records.get('salintel_investigation_items',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'salintel item {row.get("id")} crosses the tenant boundary')
        if int(row.get('investigation_id',-1)) not in investigation_ids: errors.append(f'salintel item {row.get("id")} has invalid investigation_id')
        source_id=row.get('source_material_id')
        if source_id not in (None,'') and int(source_id) not in material_ids: errors.append(f'salintel item {row.get("id")} has invalid source_material_id')
    for row in records.get('salintel_investigation_events',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'salintel event {row.get("id")} crosses the tenant boundary')
        investigation_id=int(row.get('investigation_id',-1))
        if investigation_id not in investigation_ids: errors.append(f'salintel event {row.get("id")} has invalid investigation_id')
        event_versions.setdefault(investigation_id,[]).append(int(row.get('version_no',-1)))
    for investigation_id,versions in event_versions.items():
        if sorted(versions)!=list(range(1,len(versions)+1)): errors.append(f'salintel event history for investigation {investigation_id} is not contiguous')
    industry_profiles={int(r['id']) for r in records.get('industry_profiles',[]) if r.get('id') is not None}
    profile_items={int(r['id']) for r in records.get('industry_profile_items',[]) if r.get('id') is not None}
    for row in records.get('industry_profiles',[]):
        supersedes=row.get('supersedes_id')
        if supersedes not in (None,'') and int(supersedes) not in industry_profiles: errors.append(f'industry_profile {row.get("id")} has invalid supersedes_id')
    for table in ('industry_profile_items','industry_profile_events','tenant_industry_configurations'):
        for row in records.get(table,[]):
            if int(row.get('profile_id',-1)) not in industry_profiles: errors.append(f'{table} record {row.get("id")} has invalid profile_id')
    event_versions={}
    for row in records.get('industry_profile_events',[]): event_versions.setdefault(int(row.get('profile_id',-1)),[]).append(int(row.get('version_no',-1)))
    for profile_id,versions in event_versions.items():
        if sorted(versions)!=list(range(1,len(versions)+1)): errors.append(f'industry profile event history for {profile_id} is not contiguous')
    for row in records.get('assessments',[]):
        profile_id=row.get('industry_profile_id')
        if profile_id not in (None,'') and int(profile_id) not in industry_profiles: errors.append(f'assessment {row.get("id")} has invalid industry_profile_id')
    for table in ASSESSMENT_TABLES:
        for row in records.get(table,[]):
            if int(row.get('assessment_id',-1)) not in assessments: errors.append(f'{table} record {row.get("id")} references an assessment outside the tenant package')
    users={int(r['id']) for r in records.get('users',[]) if r.get('id') is not None}
    agreement_ids={int(r['id']) for r in records.get('package_agreement_artifacts',[]) if r.get('id') is not None}
    quote_ids={int(r['id']) for r in records.get('package_quote_versions',[]) if r.get('id') is not None}
    download_ids={int(r['id']) for r in records.get('package_agreement_downloads',[]) if r.get('id') is not None}
    for row in records.get('package_agreement_artifacts',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'package agreement {row.get("id")} crosses the tenant boundary')
        if len(str(row.get('content_sha256','')))!=64 or not row.get('stored_name'): errors.append(f'package agreement {row.get("id")} has invalid storage proof')
    for row in records.get('package_quote_versions',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'package quote {row.get("id")} crosses the tenant boundary')
        if len(str(row.get('content_sha256','')))!=64: errors.append(f'package quote {row.get("id")} has invalid content digest')
        scope_hash=row.get('assessment_scope_sha256','')
        if scope_hash and len(str(scope_hash))!=64: errors.append(f'package quote {row.get("id")} has invalid scope digest')
        if int(row.get('agreement_artifact_id',0)) not in agreement_ids: errors.append(f'package quote {row.get("id")} has invalid agreement_artifact_id')
    for row in records.get('package_agreement_downloads',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'package agreement download {row.get("id")} crosses the tenant boundary')
        if int(row.get('quote_id',-1)) not in quote_ids: errors.append(f'package agreement download {row.get("id")} has invalid quote_id')
        if int(row.get('agreement_artifact_id',-1)) not in agreement_ids: errors.append(f'package agreement download {row.get("id")} has invalid agreement_artifact_id')
        if int(row.get('member_user_id',-1)) not in users: errors.append(f'package agreement download {row.get("id")} has invalid member_user_id')
    reviews={int(r['quote_id']):r for r in records.get('package_member_authority_reviews',[]) if r.get('quote_id') is not None}
    for row in records.get('package_member_authority_reviews',[]):
        try:
            quote=next(r for r in records.get('package_quote_versions',[]) if r['id']==row['quote_id'])
            content={key:row[key] for key in ('tenant_id','assessment_id','quote_id','member_user_id',
                'authority_basis','evidence_reference','reviewed_by_user_id','reviewed_at')}
            digest=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if (int(row['tenant_id'])!=int(tenant_id) or row['assessment_id']!=quote['assessment_id']
                    or row['member_user_id'] not in users or row['reviewed_by_user_id'] not in users
                    or row['record_sha256']!=digest):
                raise ValueError('signer review boundary')
        except (ValueError,KeyError,TypeError,AttributeError,StopIteration):
            errors.append(f'package member signer review {row.get("id")} has invalid proof')
    for row in records.get('package_acceptances',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'package acceptance {row.get("id")} crosses the tenant boundary')
        if int(row.get('quote_id',-1)) not in quote_ids: errors.append(f'package acceptance {row.get("id")} has invalid quote_id')
        if int(row.get('member_user_id',-1)) not in users: errors.append(f'package acceptance {row.get("id")} has invalid member_user_id')
        if int(row.get('agreement_download_id',0)) not in download_ids: errors.append(f'package acceptance {row.get("id")} has invalid agreement_download_id')
        review=reviews.get(int(row.get('quote_id') or 0))
        if not review or review['member_user_id']!=row.get('member_user_id'):
            errors.append(f'package acceptance {row.get("id")} has no matching signer review')
    for row in records.get('package_intake_requests',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'package intake {row.get("id")} crosses the tenant boundary')
        if int(row.get('quote_id',-1)) not in quote_ids: errors.append(f'package intake {row.get("id")} has invalid quote_id')
        if row.get('response_user_id') not in (None,'') and int(row['response_user_id']) not in users:
            errors.append(f'package intake {row.get("id")} has invalid response_user_id')
    intake_by_id={int(r['id']):r for r in records.get('package_intake_requests',[]) if r.get('id') is not None}
    for row in records.get('package_intake_uploads',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'package intake file {row.get("id")} crosses the tenant boundary')
        if int(row.get('quote_id',-1)) not in quote_ids: errors.append(f'package intake file {row.get("id")} has invalid quote_id')
        request=intake_by_id.get(int(row.get('intake_request_id',-1)))
        if not request or int(request.get('quote_id',-1))!=int(row.get('quote_id',-1)) or int(request.get('assessment_id',-1))!=int(row.get('assessment_id',-1)):
            errors.append(f'package intake file {row.get("id")} has invalid request scope')
        if int(row.get('member_user_id',-1)) not in users: errors.append(f'package intake file {row.get("id")} has invalid uploader')
        if len(str(row.get('content_sha256','')))!=64 or not row.get('stored_name'):
            errors.append(f'package intake file {row.get("id")} has invalid storage proof')
        if row.get('scan_status') not in ('Clean','Reconcile') or row.get('legal_hold') not in (0,1) or not row.get('retention_until'):
            errors.append(f'package intake file {row.get("id")} has incomplete handling proof')
    clean_uploads={int(r['id']):r for r in records.get('package_intake_uploads',[]) if r.get('id') is not None}
    for row in records.get('package_intake_pending_scans',[]):
        marker=f'package pending scan {row.get("id")}'
        try:
            request=intake_by_id.get(int(row['intake_request_id']))
            if (int(row['tenant_id'])!=int(tenant_id) or not request
                    or int(row['assessment_id'])!=int(request['assessment_id'])
                    or int(row['quote_id'])!=int(request['quote_id'])
                    or int(row['member_user_id']) not in users):
                errors.append(f'{marker} crosses its authorized request or uploader boundary')
            digest=row['content_sha256']
            name=row['blob_name']
            scope=(f'tenant-{row["tenant_id"]}/assessment-{row["assessment_id"]}/'
                   f'quote-{row["quote_id"]}/item-{row["intake_request_id"]}/')
            uri=urlsplit(row['blob_uri'])
            if (not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest)
                    or not isinstance(name,str) or not name.startswith(scope)
                    or not re.fullmatch(r'[0-9a-f]{32}_[0-9a-f]{16}',name[len(scope):])
                    or not name.endswith('_'+digest[:16])
                    or uri.scheme!='https' or not re.fullmatch(r'[a-z0-9]{3,24}\.blob\.core\.windows\.net',uri.netloc)
                    or uri.path!='/quarantine/'+name or uri.query or uri.fragment
                    or not row['blob_version_id'] or not row['etag']
                    or not 0<int(row['size_bytes'])<=25*1024*1024):
                errors.append(f'{marker} has invalid external quarantine proof')
            if (row['status'] not in ('Pending','Malicious','Unscanned','Reconcile','Promoted')
                    or row['legal_hold'] not in (0,1) or not row['retention_until']
                    or not row['received_at'] or not row['updated_at']):
                errors.append(f'{marker} has invalid hold or retention state')
            promoted=row.get('promoted_upload_id')
            if row['status']=='Promoted':
                clean=clean_uploads.get(int(promoted or 0))
                if (not clean or int(clean['tenant_id'])!=int(row['tenant_id'])
                        or int(clean['intake_request_id'])!=int(row['intake_request_id'])
                        or clean['content_sha256']!=digest):
                    errors.append(f'{marker} has no matching clean evidence record')
            elif row['status']=='Reconcile' and promoted is not None:
                linked=clean_uploads.get(int(promoted))
                if (not linked or linked.get('scan_status')!='Reconcile'
                        or int(linked['tenant_id'])!=int(row['tenant_id'])
                        or linked['content_sha256']!=digest):
                    errors.append(f'{marker} has invalid suspended evidence link')
            elif promoted is not None:
                errors.append(f'{marker} links evidence before clean promotion')
        except (KeyError,ValueError,TypeError,AttributeError):
            errors.append(f'{marker} has incomplete quarantine metadata')
    suspended_ids={int(r['promoted_upload_id']) for r in records.get('package_intake_pending_scans',[])
                   if r.get('status')=='Reconcile' and r.get('promoted_upload_id') is not None}
    for row in records.get('package_intake_uploads',[]):
        if row.get('scan_status')=='Reconcile' and int(row['id']) not in suspended_ids:
            errors.append(f'package intake file {row.get("id")} has no suspended scan proof')
    report_ids={int(r['id']) for r in records.get('package_product_report_versions',[]) if r.get('id') is not None}
    for row in records.get('package_product_report_versions',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'package product report {row.get("id")} crosses the tenant boundary')
        if int(row.get('quote_id',-1)) not in quote_ids: errors.append(f'package product report {row.get("id")} has invalid quote_id')
        if row.get('product') not in ('SalINTEL','SalTHIRA','SalOPS','SalCAPA'):
            errors.append(f'package product report {row.get("id")} has invalid product')
        if row.get('status') not in ('Draft','Issued'): errors.append(f'package product report {row.get("id")} has an unsupported release state')
        if len(str(row.get('content_sha256','')))!=64 or not row.get('stored_name'):
            errors.append(f'package product report {row.get("id")} has invalid storage proof')
        if row.get('disposition_status')!='Active' or row.get('legal_hold') not in (0,1) or not row.get('retention_until'):
            errors.append(f'package product report {row.get("id")} has incomplete retention metadata')
        if row.get('supersedes_id') not in (None,'') and int(row['supersedes_id']) not in report_ids:
            errors.append(f'package product report {row.get("id")} has invalid supersession link')
    report_by_id={int(r['id']):r for r in records.get('package_product_report_versions',[]) if r.get('id') is not None}
    for row in records.get('package_report_conformance',[]):
        report=report_by_id.get(int(row.get('report_id') or 0))
        if int(row.get('tenant_id',-1))!=int(tenant_id) or report is None:
            errors.append(f'package conformance {row.get("id")} crosses its report boundary')
        elif int(row.get('assessment_id',-1))!=int(report['assessment_id']) or row.get('content_sha256')!=report['content_sha256']:
            errors.append(f'package conformance {row.get("id")} has inconsistent report proof')
        if row.get('matrix_status') not in ('Open','Marked') or len(str(row.get('record_sha256','')))!=64:
            errors.append(f'package conformance {row.get("id")} has invalid matrix proof')
        try:
            checks=json.loads(row['checks_json'])
            expected=hashlib.sha256(json.dumps({'report_id':int(row['report_id']),
                'content_sha256':row['content_sha256'],'checks':checks,'summary':row['summary']},
                sort_keys=True,separators=(',',':')).encode()).hexdigest()
            actual_status='Open' if any(item['status']=='Pending' for item in checks.values()) else 'Marked'
            if expected!=row.get('record_sha256') or actual_status!=row.get('matrix_status'):
                errors.append(f'package conformance {row.get("id")} failed immutable matrix verification')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package conformance {row.get("id")} has unreadable matrix data')
    for row in records.get('package_report_reconciliations',[]):
        capa=report_by_id.get(int(row.get('salcapa_report_id') or 0))
        if (int(row.get('tenant_id',-1))!=int(tenant_id) or capa is None or capa.get('product')!='SalCAPA'
                or int(row.get('assessment_id',-1))!=int(capa['assessment_id'])
                or int(row.get('quote_id',-1))!=int(capa['quote_id'])
                or row.get('salcapa_sha256')!=capa['content_sha256']):
            errors.append(f'package reconciliation {row.get("id")} crosses its SalCAPA boundary')
        try:
            sources=json.loads(row['sources_json'])
            if set(sources)!={'SalINTEL','SalTHIRA','SalOPS'}: raise ValueError('source set')
            for product,source in sources.items():
                target=report_by_id.get(int(source['report_id']))
                if (target is None or target['product']!=product or target['content_sha256']!=source['content_sha256']
                        or capa is None or target['assessment_id']!=capa['assessment_id']
                        or target['quote_id']!=capa['quote_id']
                        or target['assessment_scope_sha256']!=capa['assessment_scope_sha256']
                        or source['alignment'] not in ('Aligned','Qualified difference','Unresolved')
                        or not source['explanation'].strip()):
                    raise ValueError('source boundary')
            expected_status='Open' if any(source['alignment']=='Unresolved' for source in sources.values()) else 'Compared'
            expected_hash=hashlib.sha256(json.dumps({'salcapa_report_id':int(row['salcapa_report_id']),
                'salcapa_sha256':row['salcapa_sha256'],'sources':sources,'summary':row['summary']},
                sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if row.get('comparison_status')!=expected_status or row.get('record_sha256')!=expected_hash:
                raise ValueError('digest')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package reconciliation {row.get("id")} failed immutable source verification')
    for row in records.get('package_report_qa_evidence',[]):
        report=report_by_id.get(int(row.get('report_id') or 0))
        if (int(row.get('tenant_id',-1))!=int(tenant_id) or report is None
                or int(row.get('assessment_id',-1))!=int(report['assessment_id'])
                or row.get('content_sha256')!=report['content_sha256']):
            errors.append(f'package QA evidence {row.get("id")} crosses its report boundary')
        try:
            manifest=json.loads(row['manifest_json'])
            canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'))
            if (manifest.get('report_sha256')!=row.get('content_sha256')
                    or hashlib.sha256(canonical.encode()).hexdigest()!=row.get('manifest_sha256')
                    or len(str(row.get('archive_sha256','')))!=64
                    or int(row.get('archive_size_bytes',0))<1
                    or not row.get('stored_name') or row.get('status')!='Submitted'
                    or row.get('legal_hold') not in (0,1) or not row.get('retention_until')):
                raise ValueError('QA evidence proof')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package QA evidence {row.get("id")} has invalid immutable proof')
        if row.get('submitted_user_id') is not None and int(row['submitted_user_id']) not in users:
            errors.append(f'package QA evidence {row.get("id")} has invalid submitter')
    evidence_by_id={int(r['id']):r for r in records.get('package_report_qa_evidence',[]) if r.get('id') is not None}
    for row in records.get('package_report_qa_reviews',[]):
        evidence=evidence_by_id.get(int(row.get('evidence_id') or 0))
        report=report_by_id.get(int(row.get('report_id') or 0))
        if (int(row.get('tenant_id',-1))!=int(tenant_id) or evidence is None or report is None
                or evidence['report_id']!=row['report_id']
                or int(row.get('assessment_id',-1))!=int(report['assessment_id'])
                or row.get('content_sha256')!=report['content_sha256']
                or row.get('archive_sha256')!=evidence['archive_sha256']
                or int(row.get('reviewer_user_id') or 0) not in users
                or row.get('reviewer_user_id')==evidence.get('submitted_user_id')):
            errors.append(f'package QA review {row.get("id")} crosses its reviewer or report boundary')
        try:
            checks=json.loads(row['checks_json'])
            if (set(checks)!={'all_pages','native_word','accessibility','format_parity','member_isolation'}
                    or any(type(value) is not bool for value in checks.values())
                    or row.get('decision') not in ('Reviewed','Returned')
                    or row['decision']=='Reviewed' and not all(checks.values())):
                raise ValueError('review checks')
            record={key:row[key] for key in ('report_id','evidence_id','content_sha256','archive_sha256',
                'decision','qualification_basis','review_note','reviewer_user_id')}
            record['checks']=checks
            if hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=row.get('record_sha256'):
                raise ValueError('review digest')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package QA review {row.get("id")} has invalid immutable proof')
    conformance_by_id={int(r['id']):r for r in records.get('package_report_conformance',[]) if r.get('id') is not None}
    review_by_id={int(r['id']):r for r in records.get('package_report_qa_reviews',[]) if r.get('id') is not None}
    comparison_by_id={int(r['id']):r for r in records.get('package_report_reconciliations',[]) if r.get('id') is not None}
    issue_by_id={int(r['id']):r for r in records.get('package_report_issue_packets',[]) if r.get('id') is not None}
    issued_report_ids=set()
    for row in records.get('package_report_issue_packets',[]):
        try:
            reports=json.loads(row['reports_json'])
            record={key:row[key] for key in ('assessment_id','quote_id','assessment_scope_sha256',
                'recipient_user_id','comparison_id','issue_basis','issued_by_user_id')}
            record['reports']=reports
            if (int(row.get('tenant_id',-1))!=int(tenant_id)
                    or row['quote_id'] not in quote_ids or row['recipient_user_id'] not in users
                    or row['issued_by_user_id'] not in users
                    or row['comparison_id'] not in comparison_by_id
                    or row.get('supersedes_id') not in (None,'') and int(row['supersedes_id']) not in issue_by_id
                    or set(reports)!={'SalINTEL','SalTHIRA','SalOPS','SalCAPA'}
                    or hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=row['record_sha256']):
                raise ValueError('issue boundary')
            for product,snapshot in reports.items():
                report=report_by_id.get(int(snapshot['report_id']))
                evidence=evidence_by_id.get(int(snapshot['qa_evidence_id']))
                review=review_by_id.get(int(snapshot['qa_review_id']))
                conformance=conformance_by_id.get(int(snapshot['conformance_id']))
                if (report is None or report['assessment_id']!=row['assessment_id']
                        or report['quote_id']!=row['quote_id'] or report['product']!=product
                        or report['status']!='Issued' or report['content_sha256']!=snapshot['content_sha256']
                        or report['version_no']!=snapshot['version_no']
                        or evidence is None or evidence['report_id']!=report['id']
                        or json.loads(evidence['manifest_json'])['pdf_sha256']!=snapshot['pdf_sha256']
                        or review is None or review['evidence_id']!=evidence['id'] or review['decision']!='Reviewed'
                        or conformance is None or conformance['report_id']!=report['id']):
                    raise ValueError('report issue link')
                issued_report_ids.add(report['id'])
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package issue {row.get("id")} has invalid immutable report proof')
    for row in records.get('package_product_report_versions',[]):
        if row.get('status')=='Issued' and row['id'] not in issued_report_ids:
            errors.append(f'package product report {row.get("id")} lacks its issue packet')
    for row in records.get('package_report_issue_deliveries',[]):
        issue=issue_by_id.get(int(row.get('issue_id') or 0))
        try:
            snapshot=json.loads(issue['reports_json'])[row['product']] if issue else None
            expected=(snapshot['content_sha256'] if row['format']=='docx' else snapshot['pdf_sha256'])
            if (int(row.get('tenant_id',-1))!=int(tenant_id) or issue is None
                    or row['assessment_id']!=issue['assessment_id']
                    or row['recipient_user_id']!=issue['recipient_user_id']
                    or row['report_id']!=snapshot['report_id'] or row['content_sha256']!=expected):
                raise ValueError('delivery boundary')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package issue delivery {row.get("id")} crosses its issue boundary')
    for row in records.get('package_report_issue_acknowledgments',[]):
        issue=issue_by_id.get(int(row.get('issue_id') or 0))
        try:
            record={key:row[key] for key in ('issue_id','issue_sha256','recipient_user_id',
                'acknowledgment_note','idempotency_key')}
            digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if (int(row.get('tenant_id',-1))!=int(tenant_id) or issue is None
                    or row['assessment_id']!=issue['assessment_id']
                    or row['issue_sha256']!=issue['record_sha256']
                    or row['recipient_user_id']!=issue['recipient_user_id']
                    or row['record_sha256']!=digest):
                raise ValueError('acknowledgment boundary')
            delivered={delivery['product'] for delivery in records.get('package_report_issue_deliveries',[])
                if delivery['issue_id']==row['issue_id']
                and delivery['recipient_user_id']==row['recipient_user_id']}
            if delivered!={'SalINTEL','SalTHIRA','SalOPS','SalCAPA'}:
                raise ValueError('missing report delivery')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package issue acknowledgment {row.get("id")} has invalid receipt proof')
    acknowledgments={int(r['id']):r for r in records.get('package_report_issue_acknowledgments',[])
        if r.get('id') is not None}
    for row in records.get('package_predecessor_qualifications',[]):
        issue=issue_by_id.get(int(row.get('issue_id') or 0))
        acknowledgment=acknowledgments.get(int(row.get('acknowledgment_id') or 0))
        try:
            keys=('assessment_id','issue_id','issue_sha256','acknowledgment_id',
                'acknowledgment_sha256','quote_id','level','band','covered_operation',
                'exclusions','assessment_scope_sha256','qualification_basis',
                'limitations_disposition','reviewer_user_id')
            record={key:row[key] for key in keys}
            digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if (int(row.get('tenant_id',-1))!=int(tenant_id) or issue is None
                    or acknowledgment is None or row['assessment_id']!=issue['assessment_id']
                    or row['issue_sha256']!=issue['record_sha256']
                    or row['acknowledgment_sha256']!=acknowledgment['record_sha256']
                    or acknowledgment['issue_id']!=issue['id'] or row['quote_id']!=issue['quote_id']
                    or row['quote_id'] not in quote_ids or row['level'] not in (1,2)
                    or row['reviewer_user_id'] not in users
                    or row['reviewer_user_id']==issue['issued_by_user_id']
                    or row['record_sha256']!=digest):
                raise ValueError('predecessor boundary')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package predecessor qualification {row.get("id")} has invalid predecessor proof')
    qualifications={int(r['id']):r for r in records.get('package_predecessor_qualifications',[])
        if r.get('id') is not None}
    quotes={int(r['id']):r for r in records.get('package_quote_versions',[]) if r.get('id') is not None}
    assessment_rows={int(r['id']):r for r in records.get('assessments',[]) if r.get('id') is not None}
    for row in records.get('package_quote_predecessor_links',[]):
        quote=quotes.get(int(row.get('quote_id') or 0))
        qualification=qualifications.get(int(row.get('qualification_id') or 0))
        try:
            record={key:row[key] for key in ('assessment_id','quote_id','qualification_id',
                'qualification_sha256')}
            digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if (int(row.get('tenant_id',-1))!=int(tenant_id) or quote is None
                    or qualification is None or row['assessment_id']!=quote['assessment_id']
                    or qualification['assessment_id']==row['assessment_id']
                    or assessment_rows.get(row['assessment_id']) is None
                    or assessment_rows.get(qualification['assessment_id']) is None
                    or assessment_rows[row['assessment_id']]['organization']!=assessment_rows[qualification['assessment_id']]['organization']
                    or row['qualification_sha256']!=qualification['record_sha256']
                    or qualification['level']!=quote['level']-1
                    or qualification['covered_operation']!=quote['covered_operation']
                    or qualification['exclusions']!=quote['exclusions']
                    or row['record_sha256']!=digest):
                raise ValueError('quote predecessor boundary')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package quote predecessor link {row.get("id")} has invalid prerequisite proof')
    advisor_links={}
    for row in records.get('package_quote_advisor_receipt_links',[]):
        quote=quotes.get(int(row.get('quote_id') or 0))
        try:
            record={key:row[key] for key in ('assessment_id','quote_id','handoff_key','receipt_id',
                'revision_no','receipt_sha256','profile_sha256','assessment_scope_sha256')}
            digest=hashlib.sha256(json.dumps(record,sort_keys=True,
                separators=(',',':')).encode('utf-8')).hexdigest()
            advisor_links.setdefault(row['quote_id'],[]).append(row)
            if (int(row.get('tenant_id',-1))!=int(tenant_id) or quote is None
                    or row['assessment_id']!=quote['assessment_id'] or quote['level']!=1
                    or row['receipt_id']!=quote['source_receipt_id']
                    or row['assessment_scope_sha256']!=quote['assessment_scope_sha256']
                    or not row['handoff_key'] or int(row['revision_no'])<1
                    or len(str(row['receipt_sha256']))!=64
                    or len(str(row['profile_sha256']))!=64
                    or row['record_sha256']!=digest):
                raise ValueError('advisor receipt link boundary')
        except (ValueError,KeyError,TypeError,AttributeError):
            errors.append(f'package quote Advisor receipt link {row.get("id")} has invalid proof')
    for quote in quotes.values():
        count=len(advisor_links.get(quote['id'],[]))
        if (quote.get('source_receipt_id') and count!=1) or (not quote.get('source_receipt_id') and count):
            errors.append(f'package quote {quote["id"]} has an invalid Advisor receipt link count')
    for row in records.get('identity_acceptance_events',[]):
        if int(row.get('tenant_id',-1))!=int(tenant_id): errors.append(f'identity_acceptance_event {row.get("event_key")} crosses the tenant boundary')
        if int(row.get('user_id',-1)) not in users: errors.append(f'identity_acceptance_event {row.get("event_key")} has invalid user_id')
        if len(str(row.get('external_subject_sha256','')))!=64: errors.append(f'identity_acceptance_event {row.get("event_key")} has invalid subject digest')
        if row.get('authority_source')!='server_user_mapping': errors.append(f'identity_acceptance_event {row.get("event_key")} has invalid authority source')
        if row.get('authentication_method')!='oidc_authorization_code': errors.append(f'identity_acceptance_event {row.get("event_key")} has invalid authentication method')
    for row in records.get('assessment_access',[]):
        if int(row.get('assessment_id',-1)) not in assessments: errors.append(f'assessment_access {row.get("id")} has invalid assessment_id')
        if int(row.get('user_id',-1)) not in users: errors.append(f'assessment_access {row.get("id")} has invalid user_id')
    evidence={int(r['id']) for r in records.get('evidence',[]) if r.get('id') is not None}
    threats={int(r['id']) for r in records.get('threats',[]) if r.get('id') is not None}
    override_ids={int(r['id']) for r in records.get('risk_overrides',[]) if r.get('id') is not None}
    for row in records.get('evidence_attachments',[]):
        if int(row.get('evidence_id',-1)) not in evidence: errors.append(f'evidence_attachment {row.get("id")} has invalid evidence_id')
    for row in records.get('risk_overrides',[]):
        if int(row.get('threat_id',-1)) not in threats: errors.append(f'risk_override {row.get("id")} has invalid threat_id')
        evidence_id=row.get('evidence_id')
        if evidence_id not in (None,'') and int(evidence_id) not in evidence: errors.append(f'risk_override {row.get("id")} has invalid evidence_id')
        supersedes=row.get('supersedes_id')
        if supersedes not in (None,'') and int(supersedes) not in override_ids: errors.append(f'risk_override {row.get("id")} has invalid supersedes_id')
    channels={int(r['id']) for r in records.get('observation_intake_channels',[]) if r.get('id') is not None}
    observations={int(r['id']) for r in records.get('observations',[]) if r.get('id') is not None}
    for row in records.get('observations',[]):
        channel_id=row.get('channel_id')
        if channel_id not in (None,'') and int(channel_id) not in channels: errors.append(f'observation {row.get("id")} has invalid channel_id')
    for table in ('observation_attachments','observation_events'):
        for row in records.get(table,[]):
            if int(row.get('observation_id',-1)) not in observations: errors.append(f'{table} record {row.get("id")} has invalid observation_id')
    pillars={int(r['id']) for r in records.get('ops_service_pillars',[]) if r.get('id') is not None}
    services={int(r['id']) for r in records.get('ops_service_catalog',[]) if r.get('id') is not None}
    for row in records.get('ops_service_catalog',[]):
        if int(row.get('pillar_id',-1)) not in pillars: errors.append(f'ops_service_catalog {row.get("id")} has invalid pillar_id')
        supersedes=row.get('supersedes_id')
        if supersedes not in (None,'') and int(supersedes) not in services: errors.append(f'ops_service_catalog {row.get("id")} has invalid supersedes_id')
        profile_id=row.get('industry_profile_id')
        if profile_id not in (None,'') and int(profile_id) not in industry_profiles: errors.append(f'ops_service_catalog {row.get("id")} has invalid industry_profile_id')
    for row in records.get('ops_catalog_events',[]):
        if int(row.get('service_id',-1)) not in services: errors.append(f'ops_catalog_event {row.get("id")} has invalid service_id')
    profiles={int(r['id']) for r in records.get('expert_profiles',[]) if r.get('id') is not None}
    credentials={int(r['id']) for r in records.get('expert_credentials',[]) if r.get('id') is not None}
    for table in ('expert_credentials','expert_availability'):
        for row in records.get(table,[]):
            if int(row.get('profile_id',-1)) not in profiles: errors.append(f'{table} record {row.get("id")} has invalid profile_id')
    for row in records.get('expert_credentials',[]):
        evidence_id=row.get('evidence_id')
        if evidence_id not in (None,'') and int(evidence_id) not in evidence: errors.append(f'expert_credential {row.get("id")} has invalid evidence_id')
    threads={int(r['id']) for r in records.get('cop_coordination_threads',[]) if r.get('id') is not None}
    decision_requests={int(r['id']) for r in records.get('cop_decision_requests',[]) if r.get('id') is not None}
    for row in records.get('cop_coordination_messages',[]):
        if int(row.get('thread_id',-1)) not in threads: errors.append(f'cop_coordination_message {row.get("id")} has invalid thread_id')
    source_ids={
        'intel_finding':{int(r['id']) for r in records.get('intel_findings',[]) if r.get('id') is not None},
        'reassessment_trigger':{int(r['id']) for r in records.get('reassessment_triggers',[]) if r.get('id') is not None},
        'improvement':{int(r['id']) for r in records.get('improvements',[]) if r.get('id') is not None},
        'accepted_risk':{int(r['id']) for r in records.get('accepted_risks',[]) if r.get('id') is not None},
        'ops_request':{int(r['id']) for r in records.get('ops_requests',[]) if r.get('id') is not None},
        'ops_estimate':{int(r['id']) for r in records.get('ops_estimates',[]) if r.get('id') is not None},
    }
    for row in records.get('cop_decision_requests',[]):
        source_type=row.get('source_type'); source_id=int(row.get('source_id',-1))
        if source_type not in source_ids or source_id not in source_ids.get(source_type,set()): errors.append(f'cop_decision_request {row.get("id")} has invalid source')
    for row in records.get('cop_events',[]):
        record_type=row.get('record_type'); record_id=int(row.get('record_id',-1))
        if record_type=='coordination_thread' and record_id not in threads: errors.append(f'cop_event {row.get("id")} has invalid coordination thread')
        elif record_type=='decision_request' and record_id not in decision_requests: errors.append(f'cop_event {row.get("id")} has invalid decision request')
        elif record_type not in {'coordination_thread','decision_request'}: errors.append(f'cop_event {row.get("id")} has invalid record_type')
    ops_requests={int(r['id']) for r in records.get('ops_requests',[]) if r.get('id') is not None}
    engagements={int(r['id']) for r in records.get('ops_engagements',[]) if r.get('id') is not None}
    tasks={int(r['id']) for r in records.get('ops_tasks',[]) if r.get('id') is not None}
    estimates={int(r['id']) for r in records.get('ops_estimates',[]) if r.get('id') is not None}
    conflicts={int(r['id']) for r in records.get('expert_conflicts',[]) if r.get('id') is not None}
    assignments={int(r['id']) for r in records.get('ops_engagement_assignments',[]) if r.get('id') is not None}
    for row in records.get('ops_requests',[]):
        service_id=row.get('service_catalog_id')
        if service_id not in (None,''):
            if int(service_id) not in services: errors.append(f'ops_request {row.get("id")} has invalid service_catalog_id')
            for field in ('service_key_snapshot','service_version_snapshot','service_name_snapshot','service_member_description_snapshot','service_deliverables_snapshot'):
                if row.get(field) in (None,''): errors.append(f'ops_request {row.get("id")} is missing {field}')
    for row in records.get('ops_engagements',[]):
        if int(row.get('ops_request_id',-1)) not in ops_requests: errors.append(f'ops_engagement {row.get("id")} has invalid ops_request_id')
        service_id=row.get('service_catalog_id')
        if service_id not in (None,'') and int(service_id) not in services: errors.append(f'ops_engagement {row.get("id")} has invalid service_catalog_id')
    for row in records.get('ops_engagement_readiness',[]):
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'ops_engagement_readiness {row.get("id")} has invalid engagement_id')
    for row in records.get('expert_conflicts',[]):
        if int(row.get('profile_id',-1)) not in profiles: errors.append(f'expert_conflict {row.get("id")} has invalid profile_id')
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'expert_conflict {row.get("id")} has invalid engagement_id')
    for row in records.get('ops_engagement_assignments',[]):
        if int(row.get('profile_id',-1)) not in profiles: errors.append(f'expert_assignment {row.get("id")} has invalid profile_id')
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'expert_assignment {row.get("id")} has invalid engagement_id')
        if int(row.get('conflict_id',-1)) not in conflicts: errors.append(f'expert_assignment {row.get("id")} has invalid conflict_id')
    expert_targets={
        'expert_profile':profiles,
        'expert_credential':credentials,
        'expert_availability':{int(r['id']) for r in records.get('expert_availability',[]) if r.get('id') is not None},
        'expert_conflict':conflicts,
        'expert_assignment':assignments,
    }
    event_versions={}
    for row in records.get('expert_events',[]):
        record_type=row.get('record_type'); record_id=int(row.get('record_id',-1)); version=int(row.get('version_no',-1))
        if record_type not in expert_targets or record_id not in expert_targets.get(record_type,set()):
            errors.append(f'expert_event {row.get("id")} has invalid target')
        event_versions.setdefault((record_type,record_id),[]).append(version)
    for target,versions in event_versions.items():
        if sorted(versions)!=list(range(1,len(versions)+1)): errors.append(f'expert event history for {target[0]} {target[1]} is not contiguous')
    for row in records.get('ops_tasks',[]):
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'ops_task {row.get("id")} has invalid engagement_id')
        assignment_id=row.get('assignment_id')
        if assignment_id not in (None,'') and int(assignment_id) not in assignments: errors.append(f'ops_task {row.get("id")} has invalid assignment_id')
    for row in records.get('ops_field_reports',[]):
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'ops_field_report {row.get("id")} has invalid engagement_id')
        task_id=row.get('task_id')
        if task_id not in (None,'') and int(task_id) not in tasks: errors.append(f'ops_field_report {row.get("id")} has invalid task_id')
    for row in records.get('ops_estimate_lines',[]):
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'ops_estimate_line {row.get("id")} has invalid engagement_id')
        if int(row.get('estimate_id',-1)) not in estimates: errors.append(f'ops_estimate_line {row.get("id")} has invalid estimate_id')
    for row in records.get('ops_expenses',[]):
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'ops_expense {row.get("id")} has invalid engagement_id')
        task_id=row.get('task_id')
        if task_id not in (None,'') and int(task_id) not in tasks: errors.append(f'ops_expense {row.get("id")} has invalid task_id')
        evidence_id=row.get('evidence_id')
        if evidence_id not in (None,'') and int(evidence_id) not in evidence: errors.append(f'ops_expense {row.get("id")} has invalid evidence_id')
    for row in records.get('ops_invoice_statements',[]):
        if int(row.get('engagement_id',-1)) not in engagements: errors.append(f'ops_invoice_statement {row.get("id")} has invalid engagement_id')
    return errors

def _safe_columns(conn, table):
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}

def _insert_row(conn, table, row):
    allowed=_safe_columns(conn,table)
    data={k:v for k,v in row.items() if k in allowed}
    if not data: return
    cols=','.join(data)
    marks=','.join('?'*len(data))
    conn.execute(f'INSERT INTO {table}({cols}) VALUES({marks})',tuple(data.values()))

def _reset_postgres_sequences(conn):
    if not is_postgres(): return
    for table in sorted(ID_TABLES):
        # pg_get_serial_sequence returns NULL if the table does not have a serial/identity id.
        sql=(f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
             f"COALESCE((SELECT MAX(id) FROM {table}),1), "
             f"EXISTS(SELECT 1 FROM {table})) WHERE pg_get_serial_sequence('{table}','id') IS NOT NULL")
        conn.execute(sql)

def replace_tenant_records(conn, tenant_id:int, records:dict):
    errors=validate_records(records,tenant_id)
    if errors: raise ValueError('; '.join(errors))
    tenant=records['tenants'][0]
    # Preserve backup_history rows so the recovery action itself remains auditable.
    conn.execute('DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE tenant_id=?)',(tenant_id,))
    conn.execute('DELETE FROM identity_acceptance_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM assessment_access WHERE user_id IN (SELECT id FROM users WHERE tenant_id=?) OR assessment_id IN (SELECT id FROM assessments WHERE tenant_id=?)',(tenant_id,tenant_id))
    conn.execute('DELETE FROM material_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM material_links WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM salintel_investigation_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM salintel_investigation_items WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM salintel_investigations WHERE tenant_id=?',(tenant_id,))
    conn.execute('UPDATE materials SET parent_material_id=NULL,duplicate_of_material_id=NULL WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM materials WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM governed_intake WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_quote_predecessor_links WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_quote_advisor_receipt_links WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_predecessor_qualifications WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_report_issue_acknowledgments WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_report_issue_deliveries WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_report_issue_packets WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_report_qa_reviews WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_report_qa_evidence WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_report_reconciliations WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_report_conformance WHERE tenant_id=?',(tenant_id,))
    conn.execute('UPDATE package_product_report_versions SET supersedes_id=NULL WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_product_report_versions WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_intake_pending_scans WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_intake_uploads WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_intake_requests WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_acceptances WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_member_authority_reviews WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_agreement_downloads WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_quote_versions WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM package_agreement_artifacts WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM observations WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM observation_intake_channels WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM cop_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM cop_coordination_messages WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM cop_coordination_threads WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM cop_decision_requests WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM intel_findings WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM ops_requests WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM expert_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM expert_profiles WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM ops_catalog_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM ops_service_catalog WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM ops_service_pillars WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM assessments WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM tenant_industry_configurations WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM industry_profile_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM industry_profile_items WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM industry_profiles WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM users WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM audit_log WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM security_events WHERE tenant_id=?',(tenant_id,))
    conn.execute('DELETE FROM dr_validations WHERE tenant_id=?',(tenant_id,))
    tenant_cols=_safe_columns(conn,'tenants')
    updates={k:v for k,v in tenant.items() if k in tenant_cols and k!='id'}
    if updates:
        conn.execute('UPDATE tenants SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',tuple(updates.values())+(tenant_id,))
    for table in RESTORE_ORDER:
        for row in records.get(table,[]):
            if table=='package_intake_pending_scans' and row['status']=='Pending':
                # A portable backup does not contain quarantined bytes or a fresh scan.
                row={**row,'status':'Reconcile','scan_event_id':'',
                     'scan_result':'','scanned_at':''}
            _insert_row(conn,table,row)
    _reset_postgres_sequences(conn)
