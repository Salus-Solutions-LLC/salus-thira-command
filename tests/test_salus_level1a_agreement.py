"""The filled Word candidate must contain the same exact unit and quote."""

from io import BytesIO
from hashlib import sha256

import pytest
from docx import Document

from salus_level1a_agreement import AgreementRenderError, render_candidate_agreement
from salus_level1a_order import Level1AUnit
from salus_level1a_quote import QuoteFacts


def _unit():
    return Level1AUnit(tenant_id=1,buyer_user_id=2,
        buyer_legal_name='Example Care LLC',unit_kind='Site',
        unit_name='Oak Street daycare',covered_boundary='One building and playground',
        operating_activity='Child care',exclusions='Other locations and operations',
        decision_owner_role='Chief executive',notice_email='buyer@example.test',
        service_use_address='100 Oak Street, Austin, Texas',
        service_use_postal_code='78701',use_country='US',use_region='TX',
        scope_version=1)


def _quote(unit):
    facts=QuoteFacts(1,2,3,1,unit.digest(),'REMOTE-LEVEL1A-US-V1',
        'SAL-D107','US',150000,0,150000,'USD')
    return {'id':4,**facts.__dict__,'quote_sha256':facts.sha256()}


def _synthetic_template():
    doc=Document()
    for text in (
        'Level 1A Access Automated Agreement Review Draft',
        'Protected Member legal name  [Complete before issue]',
        'Covered site address  [Complete before issue]',
        'Primary operating activity  [Complete before issue]',
        'Decision owner role and authorized signatory  [Complete before issue]',
        'Scope and quote identifier  [Complete before issue]',
        'Version and effective date  Controlled draft revision 9, 4 October 2026; '
        'effective only on electronic Member acceptance of the completed issued version',
        'Included buildings and outdoor areas  [Complete before issue]',
        'Express exclusions  [Complete before issue]',
        'Applicable tax and total  [Review the exact order tax before issue]',
    ):
        doc.add_paragraph(text)
    output=BytesIO(); doc.save(output)
    return output.getvalue()


def test_controlled_candidate_fills_every_order_field():
    unit=_unit(); quote=_quote(unit)
    template=_synthetic_template()
    content,digest=render_candidate_agreement(unit,quote,'Alex Example',
                                               template,sha256(template).hexdigest())
    repeated,repeated_digest=render_candidate_agreement(unit,quote,'Alex Example',
                                               template,sha256(template).hexdigest())
    assert content==repeated and digest==repeated_digest
    assert len(digest)==64 and content.startswith(b'PK')
    doc=Document(BytesIO(content))
    text='\n'.join(p.text for p in doc.paragraphs)
    for value in ('Example Care LLC','Oak Street daycare','100 Oak Street',
                  'buyer@example.test','One building and playground',
                  'Other locations and operations','Alex Example',
                  'L1A-3 / Q4 / v1','$1,500.00 total USD',
                  'approved remote Level 1A assessment tax decision'):
        assert value in text
    assert '[Complete before issue]' not in text
    assert 'Review Draft' in text  # The template is still unissued.


def test_changed_quote_cannot_render_old_scope():
    unit=_unit(); quote=_quote(unit)
    quote['total_cents']=150001
    template=_synthetic_template()
    with pytest.raises(AgreementRenderError,match='quote content changed'):
        render_candidate_agreement(unit,quote,'Alex Example',template,
                                   sha256(template).hexdigest())


def test_member_total_cannot_exceed_approved_fixed_price():
    unit=_unit(); quote=_quote(unit)
    facts=QuoteFacts(1,2,3,1,unit.digest(),'TX-STANDARD-CONSULTING-V1',
        'SAL-D099','TX',150000,100,150100,'USD')
    quote.update(facts.__dict__)
    quote['quote_sha256']=facts.sha256()
    template=_synthetic_template()
    with pytest.raises(AgreementRenderError,match='itemized price is inconsistent'):
        render_candidate_agreement(unit,quote,'Alex Example',template,
                                   sha256(template).hexdigest())


def test_approved_terms_revision_fills_all_fields_without_draft_label():
    unit=_unit(); quote=_quote(unit)
    source=Document(BytesIO(_synthetic_template()))
    source.paragraphs[0].text='Level 1A Access Agreement'
    source.paragraphs[6].text=(
        'Version and effective date  Standard terms revision 10, 5 October 2026; '
        'effective only on electronic Member acceptance of the completed issued version')
    stream=BytesIO(); source.save(stream); template=stream.getvalue()
    content,digest=render_candidate_agreement(unit,quote,'Alex Example',
                                               template,sha256(template).hexdigest())
    body='\n'.join(p.text for p in Document(BytesIO(content)).paragraphs)
    assert 'Standard terms revision 10' in body
    assert '[Complete before issue]' not in body and 'Review Draft' not in body
    assert digest==sha256(content).hexdigest()


def test_template_hash_is_required_before_any_buyer_fields_are_rendered():
    unit=_unit(); template=_synthetic_template()
    with pytest.raises(AgreementRenderError,match='controlled Word candidate changed'):
        render_candidate_agreement(unit,_quote(unit),'Alex Example',template,'0'*64)


def test_approved_rev11_template_removes_review_labels_from_issued_copy():
    unit=_unit(); quote=_quote(unit)
    source=Document(BytesIO(_synthetic_template()))
    source.paragraphs[0].text='Level 1A Access Agreement'
    source.paragraphs[6].text=(
        'Version and effective date  Candidate standard terms revision 11, '
        '9 October 2026; effective only after Salus approval, governed issue and '
        'electronic Member acceptance of the completed version')
    source.add_paragraph(
        'Candidate revision for review 9 October 2026; based on standard terms approved 5 October 2026')
    source.add_paragraph('Part B  Standard terms')
    source.add_paragraph(
        'Part B contains the proposed revised standard terms for one Level 1A Access unit. '
        'The published Privacy Notice is at https://www.salus.solutions/privacy-notice. '
        'Member-specific scope, buyer identity, tax treatment and the $1,500 total are '
        'completed in the online order before the buyer accepts the exact agreement. '
        'A completed agreement is issued only through the governed automated order '
        'journey after its release checks pass.')
    stream=BytesIO(); source.save(stream); template=stream.getvalue()
    content,_=render_candidate_agreement(unit,quote,'Alex Example',
        template,sha256(template).hexdigest())
    body='\n'.join(p.text for p in Document(BytesIO(content)).paragraphs)
    assert 'Standard terms revision 11, 9 October 2026' in body
    assert 'Approved standard terms revision 11' in body
    assert 'Part B contains the approved standard terms' in body
    assert 'Candidate' not in body and 'proposed revised standard terms' not in body
