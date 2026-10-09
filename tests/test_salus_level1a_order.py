import pytest

from salus_level1a_order import (
    ApprovedTaxDecision, BASE_PRICE_CENTS, Level1AUnit,
    OrderBoundaryError, TaxDecisionError,
)


def unit(**changes):
    values = dict(tenant_id=21, buyer_user_id=34,
                  buyer_legal_name='Example Care LLC',unit_kind='Site',
                  unit_name='Oak Street daycare',
                  covered_boundary='123 Oak Street building and playground',
                  operating_activity='Daycare',
                  exclusions='Other sites and investigative services',
                  decision_owner_role='Chief executive',
                  notice_email='buyer@example.test',
                  service_use_address='100 Oak Street, Austin, Texas',
                  service_use_postal_code='78701',
                  use_country='US',use_region='TX',scope_version=1)
    values.update(changes)
    return Level1AUnit(**values)


def test_small_and_large_buyers_have_same_one_unit_base_price():
    daycare = unit()
    enterprise = unit(unit_name='Enterprise campus A',
                      operating_activity='Regional operations')
    assert daycare.snapshot()['base_price_cents'] == BASE_PRICE_CENTS
    assert enterprise.snapshot()['base_price_cents'] == BASE_PRICE_CENTS
    assert daycare.digest() != enterprise.digest()


def test_scope_change_invalidates_prior_tax_and_payment_binding():
    original = unit()
    tax = ApprovedTaxDecision(original.digest(), 'TX-STANDARD-CONSULTING-V1',
                              'TX', 0, 'SAL-D099')
    assert tax.total_cents(original) == 150_000
    changed = unit(unit_name='Second site', scope_version=2)
    with pytest.raises(TaxDecisionError):
        tax.total_cents(changed)


def test_missing_boundary_needs_correction_without_size_screen():
    with pytest.raises(OrderBoundaryError):
        unit(unit_name='  ')
    assert unit(unit_kind='Function', unit_name='Companywide payroll function')


def test_unknown_tax_cannot_become_implicit_zero():
    selected = unit()
    with pytest.raises(TaxDecisionError):
        ApprovedTaxDecision(selected.digest(), '', 'TX', 0, '').total_cents(selected)
    with pytest.raises(TaxDecisionError):
        ApprovedTaxDecision(selected.digest(), 'RULE', 'TX', -1, 'REVIEW').total_cents(selected)
    with pytest.raises(TaxDecisionError):
        ApprovedTaxDecision(selected.digest(), 'TX-STANDARD-CONSULTING-V1',
                            'OK', 0, 'SAL-D099').total_cents(selected)
    with pytest.raises(TaxDecisionError):
        ApprovedTaxDecision(selected.digest(), 'UNREVIEWED',
                            'TX', 0, 'SAL-D099').total_cents(selected)
    outside = unit(use_region='OK')
    with pytest.raises(TaxDecisionError):
        ApprovedTaxDecision(outside.digest(), 'TX-STANDARD-CONSULTING-V1',
                            'TX', 0, 'SAL-D099').total_cents(outside)
    assert ApprovedTaxDecision(outside.digest(), 'TX-PERFORMED-LEVEL1A-V1',
                               'TX', 0, 'SAL-D106').total_cents(outside) == 150_000
    foreign = unit(use_country='CA', use_region='ON')
    with pytest.raises(TaxDecisionError):
        ApprovedTaxDecision(foreign.digest(), 'TX-PERFORMED-LEVEL1A-V1',
                            'TX', 0, 'SAL-D106').total_cents(foreign)
    with pytest.raises(OrderBoundaryError):
        unit(use_region='ZZ')
