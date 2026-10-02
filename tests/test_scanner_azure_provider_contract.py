"""Guard Azure provider constraints missed by Bicep compilation alone."""
from pathlib import Path
import re

TEMPLATE = Path(__file__).resolve().parents[1] / "infra" / "azure" / "defender-storage-scanner.bicep"
STEM = "salcapa-dev-b48224"
SUPPORTED_ALERT_WINDOWS = {
    "PT5M", "PT10M", "PT15M", "PT30M", "PT45M", "PT1H", "PT2H",
    "PT3H", "PT4H", "PT5H", "PT6H", "PT12H", "PT24H", "PT48H",
}


def test_scanner_jobs_fit_azure_name_limit():
    source = TEMPLATE.read_text(encoding="utf-8")
    job_suffixes = re.findall(
        r"resource\s+\w+\s+'Microsoft\.App/jobs@[^']+'\s*=\s*\{\s*name:\s*'\$\{stem\}([^']+)'",
        source,
    )
    assert len(job_suffixes) == 2
    assert all(len(STEM + suffix) <= 32 for suffix in job_suffixes)


def test_scanner_alert_windows_and_staged_activation():
    source = TEMPLATE.read_text(encoding="utf-8")
    windows = re.findall(r"windowSize:\s*'([^']+)'", source)
    assert len(windows) == 2
    assert set(windows) <= SUPPORTED_ALERT_WINDOWS
    assert "param activateScanner bool = false" in source
    assert "eventSubscriptions@2022-06-15' = if (activateScanner)" in source
    assert "defenderForStorageSettings@2025-06-01' = if (activateScanner)" in source
    assert "where TimeGenerated > ago(20m)" in source
    assert "where TimeGenerated > ago(27h)" in source
