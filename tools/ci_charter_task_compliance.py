"""Check committed authority coverage without operational records or network."""
import sys
from pathlib import Path
from charter_task_compliance import load, register

def main():
    root = Path(__file__).resolve().parents[1]
    actual = register(root)
    recorded = load(root / 'governance/charter_task_requirements_register.json')
    if actual != recorded:
        print('FAIL: regenerate authority coverage after policy/reference changes')
        return 1
    print('PASS: authority coverage current; sources=%s units=%s unexpanded=%s' % (
        len(actual['sources']), len(actual['units']),
        sum(r['state'] == 'unexpanded' for r in actual['references'])))
    print('This check does not verify an operational task or universal platform enforcement.')
    return 0

if __name__ == '__main__':
    sys.exit(main())

