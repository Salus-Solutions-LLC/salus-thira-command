"""Fail-closed primitives for quote-bound Salus package checkout.

This module does not authorize intake. The caller must persist a paid decision
only after validating a signed event, retrieving the Session from Stripe, and
atomically matching it to an unchanged accepted quote.
"""

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import time
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


class CheckoutVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class CheckoutBinding:
    tenant_id: int
    assessment_id: int
    quote_id: int
    acceptance_id: int
    quote_sha256: str
    agreement_sha256: str
    amount_cents: int
    currency: str = "usd"

    def __post_init__(self):
        if any(value <= 0 for value in (self.tenant_id, self.assessment_id,
                self.quote_id, self.acceptance_id, self.amount_cents)):
            raise CheckoutVerificationError("Checkout requires positive persisted identifiers and amount.")
        if any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
               for value in (self.quote_sha256, self.agreement_sha256)):
            raise CheckoutVerificationError("Checkout requires exact lowercase SHA-256 values.")
        if self.currency != "usd":
            raise CheckoutVerificationError("The approved package quote must be in USD.")

    def metadata(self):
        return {
            "salus_tenant_id": str(self.tenant_id),
            "salus_assessment_id": str(self.assessment_id),
            "salus_quote_id": str(self.quote_id),
            "salus_acceptance_id": str(self.acceptance_id),
            "salus_quote_sha256": self.quote_sha256,
            "salus_agreement_sha256": self.agreement_sha256,
        }


def _require_https(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CheckoutVerificationError("Checkout return addresses must be configured HTTPS URLs.")


def checkout_form(binding, success_url, cancel_url):
    _require_https(success_url)
    _require_https(cancel_url)
    form = {
        "mode": "payment",
        "client_reference_id": str(binding.acceptance_id),
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][price_data][currency]": binding.currency,
        "line_items[0][price_data][unit_amount]": str(binding.amount_cents),
        "line_items[0][price_data][product_data][name]": "Salus approved assessment package",
        "line_items[0][quantity]": "1",
    }
    form.update({f"metadata[{key}]": value for key, value in binding.metadata().items()})
    return form


def _stripe_post(form, secret_key, idempotency_key):
    request = Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=urlencode(form).encode("utf-8"),
        headers={"Authorization": f"Bearer {secret_key}",
                 "Idempotency-Key": idempotency_key,
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def create_checkout_session(binding, secret_key, success_url, cancel_url, transport=None):
    if not secret_key or not secret_key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
        raise CheckoutVerificationError("A configured Stripe secret or restricted key is required.")
    form = checkout_form(binding, success_url, cancel_url)
    idem = hashlib.sha256(
        f"salus-package:{binding.acceptance_id}:{binding.quote_sha256}".encode("ascii")
    ).hexdigest()
    session = (transport or _stripe_post)(form, secret_key, idem)
    if not isinstance(session, dict) or not session.get("id") or not session.get("url"):
        raise CheckoutVerificationError("Stripe did not return a usable Checkout Session.")
    return {"id": session["id"], "url": session["url"]}


def verify_webhook_signature(payload, signature_header, webhook_secret, now_seconds=None, tolerance=300):
    """Verify Stripe's raw-body HMAC before parsing an event or changing state."""
    if not isinstance(payload, bytes) or not webhook_secret or not signature_header:
        raise CheckoutVerificationError("Missing Stripe webhook verification material.")
    fields = [part.strip().split("=", 1) for part in signature_header.split(",") if "=" in part]
    stamps = [value for key, value in fields if key == "t"]
    signatures = [value for key, value in fields if key == "v1"]
    if len(stamps) != 1 or not stamps[0].isdigit() or not signatures:
        raise CheckoutVerificationError("Invalid Stripe signature header.")
    stamp = int(stamps[0])
    current = int(time.time() if now_seconds is None else now_seconds)
    if abs(current - stamp) > tolerance:
        raise CheckoutVerificationError("Stripe webhook timestamp is outside the allowed window.")
    expected = hmac.new(webhook_secret.encode("utf-8"),
                        str(stamp).encode("ascii") + b"." + payload,
                        hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise CheckoutVerificationError("Stripe webhook signature did not match.")
    try:
        event = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CheckoutVerificationError("Invalid Stripe event JSON.") from exc
    if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
        raise CheckoutVerificationError("Stripe event has no identity or type.")
    return event


def retrieve_checkout_session(session_id, secret_key, transport=None):
    """Fetch Stripe's current Session; a webhook payload alone is not payment proof."""
    if not re.fullmatch(r"cs_(?:test_|live_)?[A-Za-z0-9]{8,255}", session_id or ""):
        raise CheckoutVerificationError("Invalid Checkout Session identifier.")
    if not secret_key or not secret_key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
        raise CheckoutVerificationError("A configured Stripe secret or restricted key is required.")
    if transport is None:
        request = Request(
            "https://api.stripe.com/v1/checkout/sessions/" + quote(session_id, safe=""),
            headers={"Authorization": f"Bearer {secret_key}"}, method="GET",
        )
        with urlopen(request, timeout=15) as response:
            session = json.loads(response.read())
    else:
        session = transport(session_id, secret_key)
    if not isinstance(session, dict) or session.get("id") != session_id:
        raise CheckoutVerificationError("Stripe returned a different Checkout Session.")
    return session


def verify_paid_session(session, binding, expected_livemode):
    """Match Stripe's retrieved Session to the exact accepted quote and fee."""
    if not isinstance(session, dict) or session.get("object") != "checkout.session" or not session.get("id"):
        raise CheckoutVerificationError("No verified Checkout Session was retrieved.")
    if session.get("status") != "complete" or session.get("payment_status") != "paid":
        raise CheckoutVerificationError("The Checkout Session is not paid.")
    if session.get("mode") != "payment" or session.get("livemode") is not expected_livemode:
        raise CheckoutVerificationError("Checkout mode does not match this release.")
    if session.get("amount_total") != binding.amount_cents or session.get("currency") != binding.currency:
        raise CheckoutVerificationError("Paid amount or currency does not match the approved quote.")
    if session.get("client_reference_id") != str(binding.acceptance_id):
        raise CheckoutVerificationError("Checkout acceptance identity does not match.")
    if session.get("metadata") != binding.metadata():
        raise CheckoutVerificationError("Checkout quote or agreement identity does not match.")
    if not session.get("payment_intent"):
        raise CheckoutVerificationError("Checkout has no payment intent to reconcile.")
    return {"session_id": session["id"], "payment_intent": session["payment_intent"]}

