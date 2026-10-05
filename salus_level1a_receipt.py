"""Deterministic, one-page Level 1A payment receipt for governed storage."""

from datetime import datetime
from html import escape

from salus_stripe_checkout import CheckoutVerificationError


def render_level1a_receipt(order,quote,agreement,paid):
    if (not order or not quote or not agreement or not paid or
            paid['status']!='Paid' or paid['order_id']!=order['id'] or
            paid['quote_id']!=quote['id'] or
            paid['agreement_sha256']!=agreement['content_sha256'] or
            paid['base_price_cents']!=150_000 or paid['tax_cents']!=0 or
            paid['amount_cents']!=150_000 or paid['currency']!='usd' or
            quote['tax_rule_id']!='TX-STANDARD-CONSULTING-V1'):
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
            ('Sales tax','$0.00 USD — Texas standard consulting'),
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
