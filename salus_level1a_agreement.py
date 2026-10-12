"""Populate the controlled Level 1A Word candidate for exact-version review.

This module is deliberately a candidate renderer. Its output retains the
review-draft label and cannot be issued to a Protected Member until the exact
template, generated content and release have qualified approval.
"""

from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from docx import Document

from salus_level1a_order import Level1AUnit
from salus_level1a_quote import QuoteFacts


class AgreementRenderError(ValueError):
    pass


def _stable_docx(content: bytes) -> bytes:
    """Remove ZIP write times so retrying an unchanged order yields one hash."""
    output = BytesIO()
    with ZipFile(BytesIO(content), 'r') as source, ZipFile(output, 'w') as target:
        for member in source.infolist():
            info = ZipInfo(member.filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = member.external_attr
            target.writestr(info, source.read(member.filename))
    return output.getvalue()


def _money(cents):
    if type(cents) is not int or cents < 0:
        raise AgreementRenderError('The quoted amount is invalid.')
    return f'${cents / 100:,.2f}'


def render_candidate_agreement(unit: Level1AUnit, quote: dict,
                               signer_name: str, template: bytes,
                               template_sha256: str) -> tuple[bytes, str]:
    """Return candidate DOCX bytes and hash; never records acceptance or payment."""
    if not isinstance(signer_name, str) or not signer_name.strip() or len(signer_name) > 200:
        raise AgreementRenderError('A named authorized signer is required.')
    if (quote['tenant_id'] != unit.tenant_id or
            quote['buyer_user_id'] != unit.buyer_user_id or
            quote['scope_version'] != unit.scope_version or
            quote['scope_sha256'] != unit.digest()):
        raise AgreementRenderError('The quoted scope differs from the selected unit.')
    facts = QuoteFacts(**{key: quote[key] for key in QuoteFacts.__dataclass_fields__})
    if facts.sha256() != quote['quote_sha256']:
        raise AgreementRenderError('The quote content changed.')
    if (facts.base_price_cents != 150_000 or facts.tax_cents != 0 or
            facts.total_cents != 150_000 or
            facts.currency != 'USD'):
        raise AgreementRenderError('The itemized price is inconsistent.')
    if (not isinstance(template, bytes) or
            not isinstance(template_sha256, str) or
            len(template_sha256) != 64 or
            sha256(template).hexdigest() != template_sha256.lower()):
        raise AgreementRenderError('The controlled Word candidate changed.')
    doc = Document(BytesIO(template))
    review_version = ('Version and effective date  Controlled draft revision 9, '
        '4 October 2026; effective only on electronic Member acceptance of '
        'the completed issued version')
    issue_version = ('Version and effective date  Standard terms revision 10, '
        '5 October 2026; effective only on electronic Member acceptance of '
        'the completed issued version')
    rev11_candidate = ('Version and effective date  Candidate standard terms revision 11, '
        '9 October 2026; effective only after Salus approval, governed issue and '
        'electronic Member acceptance of the completed version')
    rev11_issued = ('Version and effective date  Standard terms revision 11, '
        '9 October 2026; effective only on electronic Member acceptance of '
        'the completed issued version')
    template_version_line = next((line for line in (review_version, issue_version,
                                                   rev11_candidate, rev11_issued)
        if any(p.text.strip() == line for p in doc.paragraphs)), None)
    if not template_version_line:
        raise AgreementRenderError('The controlled template revision is not recognized.')
    replacements = {
        'Protected Member legal name  [Complete before issue]':
            f'Protected Member legal name  {unit.buyer_legal_name}',
        'Covered site address  [Complete before issue]':
            f'Covered unit and use address  {unit.unit_name}; {unit.service_use_address}, '
            f'{unit.use_region} {unit.service_use_postal_code}',
        'Primary operating activity  [Complete before issue]':
            f'Primary operating activity  {unit.operating_activity}',
        'Decision owner role and authorized signatory  [Complete before issue]':
            f'Decision owner role and authorized signatory  {unit.decision_owner_role}; '
            f'{signer_name.strip()}',
        'Scope and quote identifier  [Complete before issue]':
            f'Order and notices  L1A-{quote["order_id"]} / Q{quote["id"]} / '
            f'v{unit.scope_version}; {unit.notice_email}',
        template_version_line:
            (rev11_issued if template_version_line in (rev11_candidate, rev11_issued) else
             issue_version if template_version_line == issue_version else
             'Version and effective date  Candidate revision 9; effective only '
             'after electronic acceptance of an issued version'),
        'Included buildings and outdoor areas  [Complete before issue]':
            f'Covered boundary  {unit.covered_boundary}',
        'Express exclusions  [Complete before issue]':
            f'Express exclusions  {unit.exclusions}',
    }
    if template_version_line == rev11_candidate:
        replacements.update({
            'Candidate revision for review 9 October 2026; based on standard terms approved 5 October 2026':
                'Approved standard terms revision 11, 9 October 2026',
            ('Part B contains the proposed revised standard terms for one Level 1A Access unit. '
             'The published Privacy Notice is at https://www.salus.solutions/privacy-notice. '
             'Member-specific scope, buyer identity, tax treatment and the $1,500 total are '
             'completed in the online order before the buyer accepts the exact agreement. '
             'A completed agreement is issued only through the governed automated order '
             'journey after its release checks pass.'):
                ('Part B contains the approved standard terms for one Level 1A Access unit. '
                 'The published Privacy Notice is at https://www.salus.solutions/privacy-notice. '
                 'Member-specific scope, buyer identity, tax treatment and the $1,500 total are '
                 'completed in the online order before the buyer accepts the exact agreement. '
                 'This completed agreement is issued through the governed automated order journey.'),
        })
    tax_text = (f'Applicable tax and total  {_money(facts.tax_cents)} tax; '
                f'{_money(facts.total_cents)} total USD; '
                f'approved remote Level 1A assessment tax decision '
                f'({facts.tax_decision_reference})')
    count = 0
    for paragraph in doc.paragraphs:
        original = paragraph.text.strip()
        if original in replacements:
            paragraph.text = replacements[original]
            count += 1
        elif original.startswith('Applicable tax and total  ['):
            paragraph.text = tax_text
            count += 1
    if count != len(replacements) + 1:
        raise AgreementRenderError('The controlled template fields were not all found.')
    if template_version_line == rev11_candidate:
        part_b = next((p for p in doc.paragraphs if p.text.strip() == 'Part B  Standard terms'), None)
        if part_b is None:
            part_b = next((p for p in doc.paragraphs if p.text.strip() == 'Part B Standard terms'), None)
        if part_b is None:
            raise AgreementRenderError('The controlled Part B heading was not found.')
        part_b.paragraph_format.page_break_before = True
    all_text = '\n'.join(p.text for p in doc.paragraphs)
    if '[Complete before issue]' in all_text or 'Applicable tax and total  [' in all_text:
        raise AgreementRenderError('A buyer-specific field remains incomplete.')
    output = BytesIO()
    doc.save(output)
    content = _stable_docx(output.getvalue())
    return content, sha256(content).hexdigest()
