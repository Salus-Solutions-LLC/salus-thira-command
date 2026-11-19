"""Private synthetic evidence for assessment-level research-entry validation."""
import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone

try:
    from .assessment_research_entry import check_research_entry
except ImportError:
    from assessment_research_entry import check_research_entry


def stamp(minute):
    return f'2026-01-08T10:{minute:02d}:00+00:00'


def research_fixture(task_id='fictional-review'):
    """Create private fixture bytes and a task. Uses fictional names and domains."""
    member = {'name': 'Alder Centre', 'locality': 'Fiction Parish',
              'domains': ['alder.example'], 'aliases': ['Alder Community Centre']}
    partner = {'name': 'Fiction Parish Board', 'jurisdiction': 'Fiction Parish',
               'domains': ['fiction.example'], 'aliases': []}
    requirement = {'id': 'A', 'version': '3', 'title': 'Community Welfare Guide'}
    selected = {'member': member, 'partners': [partner], 'required_sources': [requirement]}
    raw, meta = {}, {}

    def put(key, value, provenance='private fixture'):
        data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
        raw[key] = data
        meta[key] = {'sha256': hashlib.sha256(data).hexdigest(), 'provenance': provenance,
                     'method': 'original_content', 'result': 'verified', 'path': key}
        return key

    def rec(key, value, **fields):
        return put(key, {'task_id': task_id, 'phase': value, **fields})

    req = put('instructions', b'Review Alder Centre in Fiction Parish. Use Community Welfare Guide.')
    rec('selection', 'request', original=req, **selected)
    member_url='https://alder.example/participation'
    partner_url='https://fiction.example/minutes'
    put('about', b'Alder Centre serves Fiction Parish as Alder Community Centre.', member_url)
    put('relationship', b'Fiction Parish Board and Alder Centre documented their public relationship.', partner_url)
    rec('scope', 'scope', request='selection', identity_evidence=['about','relationship'],
        at=stamp(1), **selected)
    reviews={location:[] for location in ['internet','knowledge','osint','other_authorized_locations']}
    sources=[]
    def add(key, version, title, loc, content, portion, *, party=None, url=None):
        eid=put('body-'+key,content.encode(),url or 'private fixture')
        item={'id':key,'version':version,'title':title,'state':'content_reviewed','evidence':[eid],
              'portion_reviewed':portion, 'relevant':True, 'reason':'Original addresses this question.',
              'where_used':'Task-specific coordination review.'}
        row={'id':key,'version':version,'location':loc,'body':eid,'excerpt':content,'portion':portion}
        if party:
            row.update(target=party,url=url)
            item.update(url=url,publisher=party,accessed_at=stamp(3))
        reviews[loc].append(item)
        sources.append(row)

    add('M','1','Family care','internet','Caregivers may request a change to their contact preferences.',
        'Family communication',party=member['name'],url=member_url)
    add('P','2','Council record','internet','The Board approved a conditional service agreement involving Alder Centre.',
        'Item twelve',party=partner['name'],url=partner_url)
    add('A','3',requirement['title'],'knowledge','Read the current communication methods and document their limits.','Page two')
    add('T','4','Accessible communication','osint','Choosing accessible communication requires attention to the recipient.','Section three')
    add('U','1','Member submission','other_authorized_locations','The centre describes its existing family contact procedures.','Page four')
    locations={}
    for loc,items in reviews.items():
        review=put('review-'+loc,{'task_id':task_id,'items':items})
        locations[loc]={'state':'considered','review':review,'evidence':[review]}
    searches=[]
    queries=[]
    for index,party in enumerate([member,partner]):
        qualifiers = [*party['aliases'], *party['domains'], party.get('locality') or party['jurisdiction']]
        query = ' '.join([party['name'], *qualifiers, 'family services'])
        result=put(f'results-{index}', f'Search response from the fixture for {query}'.encode())
        at=stamp(2)
        search={'target':party['name'],'query':query,'at':at,'disposition':'found'}
        eid=rec(f'query-{index}','search',result=result,**search)
        searches.append(dict(search,evidence=eid))
        queries.append({'query':query,'searched_at':at,'evidence':[eid]})
    challenges={}
    for purpose,terms in [('contrary','exceptions and corrections'),('supersession','amended or superseded guidance')]:
        query=f'"Alder Centre" {terms}'
        result=put('result-'+purpose,('Search result did not locate a responsive publication for '+query).encode())
        search={'target':member['name'],'query':query,'at':stamp(3),'disposition':'no_match'}
        eid=rec('search-'+purpose,'search',result=result,purpose=purpose,**search)
        searches.append(dict(search,evidence=eid))
        queries.append({'query':query,'searched_at':stamp(3),'evidence':[eid]})
        challenges[purpose]={'searches':[eid],'outcome':'bounded_no_find','sources':[],
                             'interpretation':'This specified query yielded no responsive source.',
                             'limitation':'Unpublished evidence could change the conclusion.',
                             'decision_effect':'Preserve the publication date and limit the conclusion.'}
    locations['internet']['queries']=queries
    def binding(loc):
        return [{'location':loc,'review':'review-'+loc,'items':[{'id':x['id'],'version':x['version']} for x in reviews[loc]]}]
    streams={'public_open_source':binding('internet'),'approved_knowledge':binding('knowledge'),
             'thought_leader':binding('osint'),'member_uploads':binding('other_authorized_locations')}
    rec('research','research',at=stamp(4),scope_sha256=meta['scope']['sha256'],sources=sources,
        streams=streams,searches=searches,challenges=challenges)
    output=put('initial-analysis',b'The first analysis distinguishes the conditional partner vote from actual use.')
    rec('analysis','analysis',at=stamp(5),research_sha256=meta['research']['sha256'],output=output)
    task={'task_type':'assessment','task_id':task_id,'started_at':stamp(0),
          'assessment_research':{'scope':'scope','research':'research','analysis':'analysis'},
          'evidence':meta,'locations':locations}
    return task,raw,datetime.fromisoformat(stamp(10))


class AssessmentResearchEntryTests(unittest.TestCase):
    def setUp(self):
        self.task,self.raw,self.now=research_fixture()

    def change(self,key,func):
        data=json.loads(self.raw[key])
        func(data)
        self.raw[key]=json.dumps(data,sort_keys=True).encode()
        self.task['evidence'][key]['sha256']=hashlib.sha256(self.raw[key]).hexdigest()
        if key=='scope':
            self.change('research',lambda d: d.update(scope_sha256=self.task['evidence'][key]['sha256']))
        if key=='research':
            self.change('analysis',lambda d: d.update(research_sha256=self.task['evidence'][key]['sha256']))

    def audit(self,preflight=False):
        return check_research_entry(self.task,self.raw,self.now,preflight)

    def test_originals_from_member_partner_and_all_four_streams(self):
        self.assertEqual([],self.audit())

    def test_ordinary_task_and_legacy_assessment(self):
        self.task['assessment_research']={}
        self.assertTrue(self.audit())
        self.task['task_type']='other'
        self.assertEqual([],self.audit())

    def test_initial_research_does_not_require_analysis_output(self):
        self.task['assessment_research'].pop('analysis')
        self.assertEqual([],self.audit(True))
        self.assertTrue(self.audit())

    def test_first_analysis_must_postdate_source_review(self):
        self.change('analysis',lambda d:d.update(at=stamp(4)))
        self.assertTrue(self.audit())

    def test_future_reversed_naive_and_malformed_receipts(self):
        for value in [stamp(11),stamp(0),'2026-01-08T10:04:00','sometime']:
            with self.subTest(value=value):
                self.setUp()
                self.change('research',lambda d:d.update(at=value))
                self.assertTrue(self.audit(True))

    def test_search_result_with_the_domain_in_its_snippet_is_not_a_first_party_source(self):
        self.change('research',lambda d:d['sources'][0].update(
            url='https://search.example/result?target=alder.example'))
        self.change('review-internet',lambda d:d['items'][0].update(
            url='https://search.example/result?target=alder.example'))
        self.task['evidence']['body-M']['provenance']='https://search.example/result?target=alder.example'
        self.assertTrue(self.audit())

    def test_lookalike_host_cannot_impersonate_member(self):
        url='https://alder.example.bad.example/participation'
        self.change('research',lambda d:d['sources'][0].update(url=url))
        self.change('review-internet',lambda d:d['items'][0].update(url=url))
        self.task['evidence']['body-M']['provenance']=url
        self.assertTrue(self.audit())

    def test_unrelated_partner_even_on_a_genuine_domain(self):
        self.raw['relationship']=b'Fiction Parish Board authorizes the unrelated Ash Town Centre project.'
        self.assertTrue(self.audit())

    def test_appropriate_source_id_but_wrong_original_or_locator(self):
        self.change('research',lambda d:d['sources'][1].update(excerpt='The unqualified service was fully activated.'))
        self.assertTrue(self.audit())

    def test_no_replacement_of_named_library_source_or_named_source_self_omission(self):
        self.change('research',lambda d:d.update(sources=[r for r in d['sources'] if r['id']!='A']))
        self.assertTrue(self.audit())
        self.setUp()
        self.change('scope',lambda d:d.update(required_sources=[]))
        self.change('selection',lambda d:d.update(required_sources=[]))
        self.assertTrue(self.audit())

    def test_absent_partner_and_incomplete_stream_are_open(self):
        self.change('research',lambda d:d.update(sources=[r for r in d['sources'] if r['id']!='P']))
        self.assertTrue(self.audit())
        self.setUp()
        self.change('research',lambda d:d['streams'].pop('thought_leader'))
        self.assertTrue(self.audit())

    def test_later_material_cannot_backfill_preanalysis_review(self):
        self.change('review-internet',lambda d:d['items'][0].update(accessed_at=stamp(6)))
        self.assertTrue(self.audit(True))

    def test_link_to_material_must_be_content_reviewed(self):
        self.change('review-osint',lambda d:d['items'][0].update(state='screened_no_match'))
        self.assertTrue(self.audit())

    def test_preflight_scope_or_research_changes_require_new_corresponding_receipts(self):
        orig_scope=copy.deepcopy(self.raw)
        self.change('scope',lambda d:d.update(at=stamp(2)))
        self.raw['research']=orig_scope['research']
        self.assertTrue(self.audit(True))
        self.setUp()
        original_analysis=self.raw['analysis']
        self.change('research',lambda d:d.update(at='2026-01-08T10:04:30+00:00'))
        self.raw['analysis']=original_analysis
        self.assertTrue(self.audit())

    def test_visible_text_required(self):
        self.raw['body-M']=b'<html><head><title>Caregivers may request a change to their contact preferences.</title></head><body>General contact.</body></html>'
        self.assertTrue(self.audit())

    def test_aliases_cannot_be_dropped_from_scope(self):
        self.change('scope',lambda d:d['member'].update(aliases=[]))
        self.assertTrue(self.audit())

    def test_wrong_city_case_from_correct_publisher_fails(self):
        self.raw['body-P']=b'The board voted to approve an unrelated plan for Cedar City.'
        self.change('research',lambda d:d['sources'][1].update(excerpt=self.raw['body-P'].decode()))
        self.assertTrue(self.audit())

    def test_explicit_nondecisive_stream_exclusion_can_pass(self):
        self.change('research',lambda d:d['streams']['thought_leader'][0].update(items=[],reason='Scope limited to documentary wording.'))
        self.change('research',lambda d:d.update(sources=[r for r in d['sources'] if r['id']!='T']))
        self.assertTrue(self.audit())
        self.change('review-osint',lambda d:d.update(items=[],stream_dispositions={'thought_leader':{
            'state':'screened_no_match','decision_relevant':False,'reason':'Scope limited to documentary wording.',
            'effect':'This comparison does not depend on a named thought leader.'}}))
        self.assertEqual([],self.audit())
        self.change('review-osint',lambda d:d['stream_dispositions']['thought_leader'].update(decision_relevant=True))
        self.assertTrue(self.audit())

    def test_scope_can_exclude_external_partners_when_decision_does_not_depend_on_one(self):
        self.change('scope',lambda d:d.update(partners=[],partner_disposition='Editorial review of internal wording.',
                                               partner_scope_excerpt='Review Alder Centre in Fiction Parish.'))
        self.change('selection',lambda d:d.update(partners=[],partner_disposition='Editorial review of internal wording.',
                                                    partner_scope_excerpt='Review Alder Centre in Fiction Parish.'))
        def remove_partner(d):
            d['searches']=[r for r in d['searches'] if r['target']=='Alder Centre']
            d['sources']=[r for r in d['sources'] if r['id']!='P']
            d['streams']['public_open_source'][0]['items']=[{'id':'M','version':'1'}]
        self.change('research',remove_partner)
        self.assertEqual([],self.audit())

    def test_contrary_and_superseding_searches_cannot_be_attested_or_simply_relabelled(self):
        self.change('research',lambda d:d['challenges'].pop('contrary'))
        self.assertTrue(self.audit())
        self.setUp()
        self.change('research',lambda d:d['challenges']['contrary'].update(searches=['search-supersession']))
        self.assertTrue(self.audit())
        self.setUp()
        self.change('research',lambda d:d['challenges']['supersession'].update(outcome='originals_reviewed'))
        self.assertTrue(self.audit())

    def test_contrary_original_is_bound_to_the_current_review(self):
        def found(d):
            d['challenges']['contrary'].update(outcome='originals_reviewed',
                sources=[{'id':'P','version':'2','location':'internet'}])
            for search in d['searches']:
                if search['evidence']=='search-contrary':
                    search['disposition']='found'
        self.change('research',found)
        self.change('search-contrary',lambda d:d.update(disposition='found'))
        self.assertEqual([],self.audit())
        self.change('research',lambda d:d['challenges']['contrary']['sources'][0].update(version='obsolete'))
        self.assertTrue(self.audit())

    def test_supported_extracted_text_bound_to_original_and_relative_portion(self):
        text=self.raw['body-A']
        self.raw['body-A']=b'%PDF-1.7\nSynthetic opaque fixture.'
        self.raw['extracted-text']=text
        self.raw['extraction']=json.dumps({
            'task_id':self.task['task_id'],'phase':'extraction','source':'body-A',
            'text':'extracted-text','source_sha256':hashlib.sha256(self.raw['body-A']).hexdigest(),
            'text_sha256':hashlib.sha256(text).hexdigest(),'portion':'Page two','method':'Verified document text extraction.'}).encode()
        self.change('research',lambda d:d['sources'][2].update(extraction='extraction'))
        self.assertEqual([],self.audit())
        self.raw['extracted-text']=b'Different text'
        self.assertTrue(self.audit())

    def test_old_editions_do_not_become_mandatory_when_the_named_version_was_read(self):
        def add_old(d):
            previous=dict(d['items'][0],version='1',state='screened_no_match',relevant=False)
            d['items'].append(previous)
        self.change('review-knowledge',add_old)
        self.assertEqual([],self.audit())

    def test_result_bytes_relabelled_as_hosted_original_do_not_suffice(self):
        self.raw['results-0']=self.raw['body-M']
        self.assertTrue(self.audit())

    def test_shorthand_resolves_to_actual_original_and_rejects_different_project(self):
        self.raw['instructions']=b'Review Alder Centre in Fiction Parish. Use the FCRA Family Welfare paper.'
        shorthand='FCRA Family Welfare paper'
        title='Community Welfare Guide'
        imprint=title+'. FCRA Project 10-07. Family Welfare Research. Second edition.'
        self.raw['body-A']=(imprint+' '+self.raw['body-A'].decode()).encode()
        self.raw['resolution']=json.dumps({'task_id':self.task['task_id'],'phase':'source_resolution',
            'id':'A','version':'3','location':'knowledge','title':title,'requested_as':shorthand,
            'body':'body-A','body_sha256':hashlib.sha256(self.raw['body-A']).hexdigest(),
            'identity_excerpt':imprint,'identifier':'FCRA Project 10-07','identity_locator':'Cover and imprint'}).encode()
        self.task['evidence']['resolution']={}
        for eid in ('selection','scope'):
            self.change(eid,lambda d:d['required_sources'][0].update(
                requested_as=shorthand,resolution='resolution',resolved_identifier='FCRA Project 10-07'))
        self.assertEqual([],self.audit())
        self.change('resolution',lambda d:d.update(identifier='FCRA Project 20-11'))
        self.assertTrue(self.audit())

    def test_requests_can_name_member_submissions_and_public_sources_in_their_own_location(self):
        self.raw['instructions']+=b' Review Member submission and Council record.'
        extra=[{'id':'U','version':'1','title':'Member submission','location':'other_authorized_locations'},
               {'id':'P','version':'2','title':'Council record','location':'internet'}]
        for eid in ('selection','scope'):
            self.change(eid,lambda d:d['required_sources'].extend(extra))
        self.assertEqual([],self.audit())
        for eid in ('selection','scope'):
            self.change(eid,lambda d:d['required_sources'][1].update(location='knowledge'))
        self.assertTrue(self.audit())

    def test_no_known_public_site_is_bounded_by_actual_identity_and_search_evidence(self):
        for eid in ('selection','scope'):
            self.change(eid,lambda d:d['member'].update(domains=[]))
        self.change('query-0',lambda d:d.update(disposition='no_match'))
        def without_site(d):
            d['sources']=[s for s in d['sources'] if s['id']!='M']
            d['streams']['public_open_source'][0]['items']=[{'id':'P','version':'2'}]
            d['searches'][0]['disposition']='no_match'
            d['website_gaps']={'Alder Centre':{'decision_relevant':False,'searches':['query-0'],
                'identity_basis':'about','reason':'No official public site could be identified in the named search.',
                'effect':'The conclusion is limited to member-submitted material and the published partner action.'}}
        self.change('research',without_site)
        self.assertTrue(self.audit())
        self.change('review-internet',lambda d:d.update(items=[i for i in d['items'] if i['id']!='M']))
        self.task['evidence']['about']['provenance']='Private member intake.'
        self.assertEqual([],self.audit())
        self.change('research',lambda d:d['website_gaps']['Alder Centre'].update(decision_relevant=True))
        self.assertTrue(self.audit())

if __name__=='__main__':
    unittest.main()
