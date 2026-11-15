"""Verify live-acceptance diagnostics expose only closed-set status codes."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

try:
    import jq as jq_library
except ImportError:
    jq_library = None


@unittest.skipUnless(shutil.which("jq") or jq_library,
                     "jq is required by the Linux live-acceptance script")
class VerificationDiagnosticTests(unittest.TestCase):
    def render(self, payload):
        script = (Path(__file__).resolve().parents[1] / "tools" /
                  "live_public_protection_advisor_acceptance.sh").read_text(encoding="utf-8")
        expression = script.split("jq -r '\n  (.email_verification_error", 1)[1]
        expression = "\n  (.email_verification_error" + expression.split(
            "' \"$WORK/account-result.json\" >&2", 1)[0]
        if not shutil.which("jq"):
            return jq_library.compile(expression).input_value(payload).first()
        result = subprocess.run(["jq", "-r", expression], input=json.dumps(payload),
                                text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def test_known_codes_are_available_without_source_contents(self):
        for code in ["graph_http_403", "graph_http_429", "delivery_not_configured",
                     "sender_not_configured", "ClientAuthenticationError", "ReadTimeout"]:
            with self.subTest(code=code):
                self.assertEqual(self.render({"authenticated": True,
                    "email_verification": "Pending", "email_verification_error": code,
                    "email": "private@example.invalid", "token": "secret-value"}),
                    "Advisor verification: authenticated=true state=Pending error=" + code)

    def test_unrecognized_strings_and_nonstring_errors_are_redacted(self):
        for value in ["private@example.invalid", "graph_http_403\nsecret-value", "graph_http_403\n",
                      {"token": "secret-value"}, ["secret-value"], 403]:
            with self.subTest(value=value):
                self.assertEqual(self.render({"email_verification": "secret-value",
                    "email_verification_error": value}),
                    "Advisor verification: authenticated=false state=unexpected error=unrecognized_error")

    def test_success_and_missing_fields_use_fixed_labels(self):
        self.assertEqual(self.render({"authenticated": True, "email_verification": "Delivered"}),
                         "Advisor verification: authenticated=true state=Delivered error=none")
        self.assertEqual(self.render({}),
                         "Advisor verification: authenticated=false state=unexpected error=none")
