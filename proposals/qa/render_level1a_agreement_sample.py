"""Create a fictional, unissued Level 1A Word copy for page-by-page QA."""

import argparse
from hashlib import sha256
from pathlib import Path

from salus_level1a_agreement import render_candidate_agreement
from salus_level1a_order import Level1AUnit
from salus_level1a_quote import QuoteFacts


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--template',required=True)
    parser.add_argument('--template-sha256',required=True)
    args=parser.parse_args()
    unit=Level1AUnit(1,2,'Example Care LLC','Site','Oak Street daycare',
        'One building and playground','Child care','Other locations and operations',
        'Chief executive','buyer@example.test',
        '100 Oak Street, Austin, Texas','78701','US','TX',1)
    facts=QuoteFacts(1,2,3,1,unit.digest(),'TX-STANDARD-CONSULTING-V1',
        'SAL-D099','TX',150000,0,150000,'USD')
    quote={'id':4,**facts.__dict__,'quote_sha256':facts.sha256()}
    template=Path(args.template).read_bytes()
    if sha256(template).hexdigest() != args.template_sha256.lower():
        raise SystemExit('The controlled template hash differs from the review record.')
    content,digest=render_candidate_agreement(unit,quote,'Alex Example',
                                               template,args.template_sha256)
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(content)
    print(f'candidate_sha256={digest}; bytes={len(content)}; output={output}')


if __name__=='__main__':
    main()
