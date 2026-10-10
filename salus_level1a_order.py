"""Versioned, side-effect-free rules for the standard Level 1A Access unit.

This module deliberately cannot charge a buyer, issue an agreement, or release
an upload. Those actions require the persisted order and guarded payment path.
"""

from dataclasses import dataclass
from hashlib import sha256
import json


BASE_PRICE_CENTS = 150_000
_US_STATE_CODES = frozenset('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
SKU = 'SALUS-LEVEL-1A-ACCESS-V1'
_APPROVED_TAX_RULES = {
    # Salus's recorded determination applies only to the standard consulting
    # SKU in Texas. It is not a fallback for other jurisdictions or services.
    'TX-STANDARD-CONSULTING-V1': ('TX', 0, 'SAL-D099'),
    # The currently scoped Texas-performed Level 1A assessment has a fixed
    # zero-tax determination for U.S. buyers under the recorded SAL-D106 rule.
    'TX-PERFORMED-LEVEL1A-V1': ('TX', 0, 'SAL-D106'),
}


class OrderBoundaryError(ValueError):
    """The named unit needs correction before an agreement can be issued."""


class TaxDecisionError(ValueError):
    """No approved tax decision covers this exact order."""


def _required_text(value: str, label: str, limit: int = 500) -> str:
    if not isinstance(value, str):
        raise OrderBoundaryError(f'{label} must be text.')
    cleaned = ' '.join(value.split())
    if not cleaned or len(cleaned) > limit:
        raise OrderBoundaryError(f'{label} needs a specific answer of at most {limit} characters.')
    return cleaned


@dataclass(frozen=True)
class Level1AUnit:
    tenant_id: int
    buyer_user_id: int
    buyer_legal_name: str
    unit_kind: str
    unit_name: str
    covered_boundary: str
    operating_activity: str
    exclusions: str
    decision_owner_role: str
    notice_email: str
    service_use_address: str
    service_use_postal_code: str
    use_country: str
    use_region: str
    scope_version: int

    def __post_init__(self) -> None:
        if type(self.tenant_id) is not int or self.tenant_id <= 0:
            raise OrderBoundaryError('A signed-in Protected Member tenant is required.')
        if type(self.buyer_user_id) is not int or self.buyer_user_id <= 0:
            raise OrderBoundaryError('A signed-in buyer is required.')
        if self.unit_kind not in ('Site', 'Function'):
            raise OrderBoundaryError('Choose one named site or one named function.')
        if type(self.scope_version) is not int or self.scope_version <= 0:
            raise OrderBoundaryError('A positive scope version is required.')
        for field, label in (('buyer_legal_name', 'Buyer legal name'),
                             ('unit_name', 'Covered unit'),
                             ('covered_boundary', 'Covered boundary'),
                             ('operating_activity', 'Operating activity'),
                             ('exclusions', 'Exclusions'),
                             ('decision_owner_role', 'Decision owner role'),
                             ('notice_email', 'Buyer notice email'),
                             ('service_use_address', 'Service use address'),
                             ('service_use_postal_code', 'Service use postal code'),
                             ('use_country', 'Service use country'),
                             ('use_region', 'Service use region')):
            object.__setattr__(self, field, _required_text(getattr(self, field), label))
        object.__setattr__(self, 'use_country', self.use_country.upper())
        object.__setattr__(self, 'use_region', self.use_region.upper())
        if len(self.use_country) != 2:
            raise OrderBoundaryError('Use a two-letter service use country code.')
        if self.use_country == 'US' and self.use_region not in _US_STATE_CODES:
            raise OrderBoundaryError('Use a valid two-letter service use state code.')
        if ('@' not in self.notice_email or '\n' in self.notice_email or
                len(self.notice_email) > 254):
            raise OrderBoundaryError('Give a usable buyer notice email.')

    def snapshot(self) -> dict:
        return {
            'sku': SKU,
            'tenant_id': self.tenant_id,
            'buyer_user_id': self.buyer_user_id,
            'buyer_legal_name': self.buyer_legal_name,
            'unit_kind': self.unit_kind,
            'unit_name': self.unit_name,
            'covered_boundary': self.covered_boundary,
            'operating_activity': self.operating_activity,
            'exclusions': self.exclusions,
            'decision_owner_role': self.decision_owner_role,
            'notice_email': self.notice_email,
            'service_use_address': self.service_use_address,
            'service_use_postal_code': self.service_use_postal_code,
            'use_country': self.use_country,
            'use_region': self.use_region,
            'scope_version': self.scope_version,
            'base_price_cents': BASE_PRICE_CENTS,
            'currency': 'USD',
        }

    def digest(self) -> str:
        canonical = json.dumps(self.snapshot(), sort_keys=True,
                               separators=(',', ':'), ensure_ascii=False)
        return sha256(canonical.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class ApprovedTaxDecision:
    scope_sha256: str
    rule_id: str
    jurisdiction: str
    tax_cents: int
    decision_reference: str

    def total_cents(self, unit: Level1AUnit) -> int:
        if self.scope_sha256 != unit.digest():
            raise TaxDecisionError('The tax decision does not cover the current unit.')
        if not self.rule_id or not self.jurisdiction or not self.decision_reference:
            raise TaxDecisionError('The exact order needs a recorded approved tax rule.')
        if type(self.tax_cents) is not int or self.tax_cents < 0:
            raise TaxDecisionError('Tax must be a nonnegative amount in cents.')
        approved = _APPROVED_TAX_RULES.get(self.rule_id)
        if approved != (self.jurisdiction, self.tax_cents, self.decision_reference):
            raise TaxDecisionError('No approved tax rule matches this exact service and jurisdiction.')
        if self.rule_id == 'TX-STANDARD-CONSULTING-V1' and (
                unit.use_country != 'US' or unit.use_region != 'TX'):
            raise TaxDecisionError('The Texas consulting rule does not cover this service use location.')
        if self.rule_id == 'TX-PERFORMED-LEVEL1A-V1' and unit.use_country != 'US':
            raise TaxDecisionError('The Level 1A tax rule does not cover this service use country.')
        return BASE_PRICE_CENTS + self.tax_cents
