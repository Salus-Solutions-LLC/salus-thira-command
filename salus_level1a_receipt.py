"""Deterministic, one-page Level 1A payment receipt for governed storage."""

from datetime import datetime
from html import escape

from salus_level1a_order import (ApprovedTaxDecision, OrderBoundaryError,
                                 TaxDecisionError)
from salus_level1a_quote import _unit_from_order
from salus_stripe_checkout import CheckoutVerificationError


def render_level1a_receipt(order,quote,agreement,paid):
    if not order or not quote or not agreement or not paid:
        raise CheckoutVerificationError('The receipt does not match one paid Level 1A order.')
    tax=ApprovedTaxDecision(quote['scope_sha256'],quote['tax_rule_id'],
        quote['tax_jurisdiction'],quote['tax_cents'],quote['tax_decision_reference'])
    try:
        approved_total=tax.total_cents(_unit_from_order(order))
    except (OrderBoundaryError,TaxDecisionError) as exc:
        raise CheckoutVerificationError('The receipt tax decision needs review.') from exc
    if (paid['status']!='Paid' or paid['order_id']!=order['id'] or
            paid['quote_id']!=quote['id'] or
            paid['quote_sha256']!=quote['quote_sha256'] or
            quote['scope_sha256']!=order['scope_sha256'] or
            paid['agreement_sha256']!=agreement['content_sha256'] or
            paid['base_price_cents']!=quote['base_price_cents'] or
            paid['tax_cents']!=quote['tax_cents'] or
            paid['amount_cents']!=quote['total_cents'] or
            paid['amount_cents']!=approved_total or paid['currency']!='usd' or
            quote['tax_rule_id'] not in ('TX-STANDARD-CONSULTING-V1',
                                         'TX-PERFORMED-LEVEL1A-V1',
                                         'REMOTE-LEVEL1A-US-V1')):
        raise CheckoutVerificationError('The receipt does not match one paid Level 1A order.')
    try:
        paid_at=datetime.fromisoformat(paid['paid_at'].replace('Z','+00:00'))
        date_text=paid_at.strftime('%d %B %Y at %H:%M UTC')
    except (ValueError,AttributeError) as exc:
        raise CheckoutVerificationError('The payment time is incomplete.') from exc
    fields=(('Protected Member',order['buyer_legal_name']),
            ('Covered unit',order['unit_name']),
            ('Scope boundary',order['covered_boundary']),
            ('Base price','$1,500.00 USD'),
            ('Sales tax','$0.00 USD — approved assessment tax decision'),
            ('Total paid','$1,500.00 USD'),
            ('Payment verified',date_text),
            ('Order reference',f'L1A-{order["id"]}'),
            ('Quote reference',f'Q{quote["id"]}'),
            ('Stripe payment reference',paid['stripe_session_id']),
            ('Agreement SHA-256',agreement['content_sha256']),
            ('Receipt fingerprint',paid['receipt_sha256']))
    rows=''.join('<tr><th scope="row">'+escape(label)+'</th><td>'+escape(str(value))+
                 '</td></tr>' for label,value in fields)
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salus Level 1A Access payment receipt</title>
<style>@page{size:letter;margin:.65in}body{font-family:"Times New Roman",serif;
color:#17243a;max-width:760px;margin:28px auto;font-size:12pt;line-height:1.32}
h1,th,.mark{font-family:Arial,sans-serif}h1{font-size:19pt;margin:.15em 0 .45em}
.mark{font-size:9pt;font-weight:bold;letter-spacing:.06em;color:#792c36}
table{border-collapse:collapse;width:100%;margin-top:16px}th,td{text-align:left;
vertical-align:top;border-bottom:1px solid #cbd2db;padding:5px;overflow-wrap:anywhere}
th{width:31%;font-size:9pt}td{font-size:10pt}.note{font-size:9pt;margin-top:14px}
footer{font-size:8pt;text-align:right;margin-top:16px}
@media print{body{margin:0}}</style></head><body><main>
<p class="mark">SALUS CONFIDENTIAL — PROTECTED MEMBER COPY</p>
<h1>Level 1A Access payment receipt</h1>
<p>Salus verified prepayment for the one covered assessment unit and the exact
accepted agreement shown below. Keep this receipt with your agreement.</p>
<table>'''+rows+'''</table>
<p class="note">The written agreement controls the included assessment and
exclusions. Payment alone does not authorize disclosure of another person's
records or add a site, investigation, security service, or implementation.</p>
<footer>Page 1 of 1</footer></main></body></html>'''
    return page.encode('utf-8')
