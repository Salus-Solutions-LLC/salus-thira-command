"""Verify private assessment research records against pre-verified source bytes.

This checks provenance, identity, review order and source coverage. Determining
the sufficiency of a search or the truth of source content remains a review duty.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

STREAMS = {
    'public_open_source': {'internet', 'osint'},
    'approved_knowledge': {'knowledge'},
    'thought_leader': {'internet', 'osint', 'knowledge'},
    'member_uploads': {'other_authorized_locations'},
}
ERROR = 'ASSESSMENT_RESEARCH_ENTRY_'


class Invalid(ValueError):
    """The correlation or proof required at the current checkpoint is missing."""


def need(condition):
    if not condition:
        raise Invalid()


def words(value):
    need(isinstance(value, str) and value.strip())
    return ' '.join(value.casefold().split())


def moment(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(stamp.utcoffset() is not None)
    return stamp


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'template', 'head'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'template', 'head'} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def original_text(raw):
    if raw.startswith(b'%PDF-'):
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
        try:
            return '\n'.join(p.extract_text() for p in PdfReader(BytesIO(raw)).pages)
        except (OSError, PdfReadError, IndexError) as exc:
            raise Invalid() from exc
    if raw.startswith(b'PK'):
        with ZipFile(BytesIO(raw)) as archive:
            xml = ElementTree.fromstring(archive.read('word/document.xml'))
            return ' '.join(n.text or '' for n in xml.iter()
                            if n.tag == '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
    text = raw.decode('utf-8-sig')
    if re.search(r'<(?:html|body|p|div)\b', text, re.I):
        parser = VisibleHTML()
        parser.feed(text)
        return ' '.join(parser.parts)
    return text


def read_source(row, verified, task_id):
    """A retained extraction may accompany an unreadable original, including a scanned PDF."""
    raw = verified[row['body']]
    if 'extraction' not in row:
        return original_text(raw)
    receipt = json.loads(verified[row['extraction']])
    need(receipt['task_id'] == task_id and receipt['phase'] == 'extraction'
         and receipt['source_sha256'] == digest(raw) and words(receipt['method'])
         and receipt['source'] == row['body'] and receipt['text'] != row['body'])
    extracted = verified[receipt['text']]
    need(receipt['text_sha256'] == digest(extracted) and words(receipt['portion']) == words(row['portion']))
    return extracted.decode('utf-8-sig')


def host(url):
    parsed = urlsplit(url)
    need(parsed.scheme in {'https', 'http'} and parsed.hostname
         and not parsed.username and not parsed.password)
    return parsed.hostname.casefold().rstrip('.')


def domain_matches(url, domains):
    actual = host(url)
    return any(actual == domain or actual.endswith('.' + domain) for domain in domains)


def identity(entity):
    name = words(entity['name'])
    aliases = entity['aliases']
    domains = entity['domains']
    need(isinstance(aliases, list) and isinstance(domains, list))
    names = [name] + [words(alias) for alias in aliases]
    need(len(names) == len(set(names)))
    for domain in domains:
        need(isinstance(domain, str) and '.' in domain and domain == domain.casefold()
             and re.fullmatch(r'[a-z0-9.-]+', domain) and not domain.startswith('.')
             and not domain.endswith('.'))
    return names


def validate_named_source(required, location, item, row, source_text, verified, task_id):
    need(words(required['title']) == words(item['title']))
    if 'requested_as' not in required or words(required['requested_as']) == words(required['title']):
        return
    resolution = json.loads(verified[required['resolution']])
    need(resolution['task_id'] == task_id and resolution['phase'] == 'source_resolution'
         and resolution['location'] == location and resolution['body'] == row['body']
         and resolution['body_sha256'] == digest(verified[row['body']])
         and all(resolution[k] == required[k] for k in ('id', 'version', 'title', 'requested_as')))
    imprint = words(resolution['identity_excerpt'])
    identifier = words(resolution['identifier'])
    need(words(resolution['identity_locator']) and imprint in source_text
         and identifier == words(required['resolved_identifier']) and identifier in imprint
         and words(required['title']) in imprint)
    authority = imprint
    if 'catalog' in resolution:
        catalog = words(original_text(verified[resolution['catalog']]))
        catalog_excerpt = words(resolution['catalog_excerpt'])
        need(catalog_excerpt in catalog and identifier in catalog_excerpt)
        authority += ' ' + catalog_excerpt
    # Resolve the request as written. Publication types alone cannot disambiguate a work.
    ignored = {'a', 'an', 'and', 'the', 'of', 'for', 'on', 'in', 'by', 'paper', 'report',
               'study', 'publication', 'article', 'document', 'original'}
    def terms(value):
        return {token.rstrip('s') for token in re.findall(r'[\w]+', words(value)) if token not in ignored}
    distinctive = terms(required['requested_as'])
    need(distinctive and distinctive.issubset(terms(authority)))


def check_research_entry(task, verified, now, preflight=False):
    """Return a stable code at the earliest failed stage. Never fetch sources."""
    if task.get('task_type') == 'other':
        return []
    stage = 'SCOPE'
    try:
        need(task.get('task_type') == 'assessment' and now.utcoffset() is not None)
        task_id = task['task_id']
        refs = task['assessment_research']
        metadata = task['evidence']
        started = moment(task['started_at'])

        def record(ref, phase):
            data = json.loads(verified[ref])
            need(data['task_id'] == task_id and data['phase'] == phase)
            return data

        scope = record(refs['scope'], 'scope')
        selected = record(scope['request'], 'request')
        need(all(scope[field] == selected[field] for field in ('member', 'partners', 'required_sources')))
        original_request = words(original_text(verified[selected['original']]))
        member = scope['member']
        parties = [member] + scope['partners']
        need(isinstance(scope['partners'], list))
        if not scope['partners']:
            need(words(scope['partner_disposition']) == words(selected['partner_disposition'])
                 and words(scope['partner_scope_excerpt']) == words(selected['partner_scope_excerpt'])
                 and words(scope['partner_scope_excerpt']) in original_request)
        names = [identity(party) for party in parties]
        need(len({n for aliases in names for n in aliases}) == sum(map(len, names)))
        need(any(n in original_request for n in names[0]))
        locality = words(member['locality'])
        required = scope['required_sources']
        need(isinstance(required, list))
        named = {}
        for r in required:
            locations = r.get('locations', [r.get('location','knowledge')])
            need(isinstance(locations, list) and locations and
                 set(locations).issubset(set().union(*STREAMS.values())))
            label = words(r.get('requested_as', r['title']))
            need(label in original_request)
            for loc in locations:
                key = (loc, (r['id'], r['version']))
                need(key not in named)
                named[key] = r
        required_titles = {words(r['title']) for r in required}
        targets = {p['name']: p for p in parties}
        originals = scope['identity_evidence']
        need(isinstance(originals, list) and originals)
        evidence = [(words(original_text(verified[e])), metadata[e]['provenance']) for e in originals]
        for party, aliases in zip(parties, names):
            own = any(any(name in text for name in aliases) and
                      (locality in text if party is member else any(n in text for n in names[0]))
                      and (party is member or words(party['jurisdiction']) in text)
                      and (not party['domains'] or any(d in text for d in party['domains']) or
                           (str(origin).startswith(('https://', 'http://')) and
                            domain_matches(origin, party['domains']))) for text, origin in evidence)
            need(own)
        scope_at = moment(scope['at'])
        research = record(refs['research'], 'research')
        research_at = moment(research['at'])
        need(started <= scope_at <= research_at <= now
             and research['scope_sha256'] == digest(verified[refs['scope']]))

        stage = 'STREAMS'
        links = research['streams']
        need(set(links) == set(STREAMS))
        locations = task['locations']
        inventories = {}
        stream_items = set()
        for stream, allowed in STREAMS.items():
            bindings = links[stream]
            need(isinstance(bindings, list) and bindings)
            seen = set()
            for bind in bindings:
                loc = bind['location']
                need(loc in allowed and loc not in seen)
                seen.add(loc)
                source = locations[loc]
                need(source['review'] == bind['review'] and source['state'] == 'considered'
                     and bind['review'] in source['evidence'])
                review = json.loads(verified[bind['review']])
                need(review['task_id'] == task_id and isinstance(review['items'], list))
                inventories[loc] = {(i['id'], i['version']): i for i in review['items']}
                items = bind['items']
                need(isinstance(items, list))
                if not items:
                    # A scoped negative result still requires a corroborated inventory and explanation.
                    exclusion = review['stream_dispositions'][stream]
                    need(exclusion['state'] == 'screened_no_match' and
                         exclusion['decision_relevant'] is False and
                         words(bind['reason']) == words(exclusion['reason']) and
                         words(exclusion['effect']))
                for member_item in items:
                    key = (member_item['id'], member_item['version'])
                    need(inventories[loc][key]['state'] == 'content_reviewed')
                    stream_items.add((loc, key))
        need(set(inventories) == {'knowledge', 'osint', 'internet', 'other_authorized_locations'})

        stage = 'SEARCH'
        searches = research['searches']
        need(isinstance(searches, list) and searches)
        queries = locations['internet']['queries']
        search_targets = set()
        executed = {}
        non_originals = {scope['request'], selected['original'], refs['scope'], refs['research']}
        for row in searches:
            target = row['target']
            party = targets[target]
            query = words(row['query'])
            need(any(n in query for n in identity(party)) or
                 any(d in query for d in party['domains']))
            seen_at = moment(row['at'])
            need(scope_at <= seen_at <= research_at)
            sid = row['evidence']
            saved = record(sid, 'search')
            need(all(saved[key] == row[key] for key in ('target', 'query', 'at', 'disposition')))
            need(any(words(q['query']) == query and moment(q['searched_at']) == seen_at
                     and sid in q['evidence'] for q in queries))
            result_id = saved['result']
            need(result_id != sid and len(verified[result_id].strip()) > 0)
            need(metadata[result_id]['method'] not in {'attestation', 'metadata_only', 'filename'})
            non_originals.update((sid, result_id))
            need(row['disposition'] in {'found', 'no_match', 'unavailable'})
            need(sid not in executed)
            executed[sid] = (target, query, row['disposition'])
            search_targets.add(target)
        need(search_targets == set(targets))
        for party in parties:
            queries_run = [query for target, query, _ in executed.values() if target == party['name']]
            required_terms = [*identity(party), *party['domains'],
                              locality if party is member else words(party['jurisdiction'])]
            need(all(any(term in query for query in queries_run) for term in required_terms))

        stage = 'ORIGINALS'
        read = set()
        published = set()
        body_ids = set()
        for row in research['sources']:
            key = (row['id'], row['version'])
            loc = row['location']
            need((loc, key) not in read)
            item = inventories[loc][key]
            eid = row['body']
            need(item['state'] == 'content_reviewed' and eid in item['evidence'])
            need(words(row['portion']) == words(item['portion_reviewed']))
            need(eid not in non_originals and not any(
                digest(verified[eid]) == digest(verified[n]) for n in non_originals))
            text = words(read_source(row, verified, task_id))
            sample = words(row['excerpt'])
            need(sample in text and sample != words(item.get('title', item['id']))
                 and sample not in {n for aliases in names for n in aliases})
            if loc == 'internet' or 'target' in row:
                url = row['url']
                need(item['url'] == url and metadata[eid]['provenance'] == url and host(url))
                need(words(item['title']) and words(item['publisher']))
                accessed = moment(item['accessed_at'])
                need(scope_at <= accessed <= research_at)
                if row.get('use') == 'external_comparison':
                    need('target' not in row and words(row['limitation']))
                else:
                    party = targets[row['target']]
                    need(domain_matches(url, party['domains']) and any(
                        n in words(item['publisher']) or n in text for n in identity(party)))
                    if party is not member:
                        if row.get('use', 'member_specific') == 'member_specific':
                            need(any(n in text for n in names[0]))
                        else:
                            need(row['use'] == 'jurisdiction_guidance' and words(row['limitation']))
                    published.add(party['name'])
            if (loc, key) in named:
                validate_named_source(named[(loc, key)], loc, item, row, text, verified, task_id)
            body_ids.add(eid)
            read.add((loc, key))
        need(set(named).issubset(read))
        need(stream_items.issubset(read))
        # A search result or an unrelated publisher cannot satisfy a first-party reading.
        website_gaps = research.get('website_gaps', {})
        need(set(website_gaps) == set(targets) - published)
        for entity_name, gap in website_gaps.items():
            need(not targets[entity_name]['domains'] and gap['decision_relevant'] is False
                 and words(gap['reason']) and words(gap['effect']))
            entity_names = identity(targets[entity_name])
            need(not any(i.get('state') == 'content_reviewed' and i.get('url') and
                         i.get('publisher') and words(i['publisher']) in entity_names
                         for i in inventories['internet'].values()))
            refs_checked = gap['searches']
            need(isinstance(refs_checked, list) and refs_checked and all(
                executed[e][0] == entity_name and executed[e][2] == 'no_match' for e in refs_checked))
            basis = words(original_text(verified[gap['identity_basis']]))
            need(gap['identity_basis'] in originals and any(n in basis for n in identity(targets[entity_name])))
        for inventory in inventories.values():
            for item in inventory.values():
                if item.get('title') and words(item['title']) in original_request:
                    need(words(item['title']) in required_titles)

        stage = 'CONTRARY_AND_SUPERSESSION'
        challenges = research['challenges']
        need(set(challenges) == {'contrary', 'supersession'})
        examined = set()
        for lens, case in challenges.items():
            search_ids = case['searches']
            need(isinstance(search_ids, list) and search_ids)
            queries_run = {executed[s][1] for s in search_ids}
            need(queries_run.isdisjoint(examined))
            examined.update(queries_run)
            for sid in search_ids:
                saved = record(sid, 'search')
                need(saved['purpose'] == lens and executed[sid][2] != 'unavailable')
            originals = case['sources']
            need(isinstance(originals, list) and words(case['interpretation'])
                 and words(case['limitation']) and words(case['decision_effect']))
            if case['outcome'] == 'bounded_no_find':
                need(not originals and all(executed[s][2] == 'no_match' for s in search_ids))
            else:
                need(case['outcome'] == 'originals_reviewed' and originals and
                     any(executed[s][2] == 'found' for s in search_ids) and
                     all((o['location'], (o['id'], o['version'])) in read for o in originals))

        if not preflight:
            stage = 'ANALYSIS'
            analysis = record(refs['analysis'], 'analysis')
            output = analysis['output']
            need(research_at < moment(analysis['at']) <= now)
            need(analysis['research_sha256'] == digest(verified[refs['research']]))
            need(output in verified and len(verified[output].strip()) > 0 and
                 all(digest(verified[output]) != digest(verified[r])
                     for r in (body_ids | non_originals | set(refs.values())) if r in verified))
        return []
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError,
            IndexError, ImportError, BadZipFile, ElementTree.ParseError):
        return [ERROR + stage]
