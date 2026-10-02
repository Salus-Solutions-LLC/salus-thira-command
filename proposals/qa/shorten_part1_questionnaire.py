"""Align the local Part 1 Word review copy with the short public screen.

Run once against the existing 2.2.0 review copy. The published Advisor and
approved report template are not changed by this local artifact operation.
"""

import ast
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'public_protection_advisor.py'
TARGET = ROOT / 'proposals/qa/questionnaire_candidates/Protection Advisor Part 1 Questionnaire.docx'


def literal_assignment(name):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f'Missing source assignment: {name}')


def main():
    version = literal_assignment('QUESTIONNAIRE_VERSION')
    text_by_key = literal_assignment('PART1_SCREEN_TEXT')
    blueprints = literal_assignment('QUESTION_BLUEPRINTS')
    document = Document(TARGET)
    paras = document.paragraphs
    if len(blueprints) != 28 or len(text_by_key) != 9:
        raise ValueError('The approved short-screen and legacy-question boundaries changed.')
    old = sum('SPA-PUBLIC-QUESTIONNAIRE-2.2.0' in p.text for p in paras)
    current = sum(version in p.text for p in paras)
    if old == 1 and current == 0:
        headings = [p for p in paras if p.style.name == 'Heading 2'
                    and p.text.split('.', 1)[0].isdigit()]
        if len(headings) != len(blueprints):
            raise ValueError('The Word question blocks do not match the source version.')
        for index, (heading, blueprint) in enumerate(zip(headings, blueprints)):
            key = blueprint[0]
            if key not in text_by_key:
                parent = heading._element.getparent()
                for element in (heading._element, heading._element.getnext(),
                                heading._element.getnext().getnext()):
                    parent.remove(element)
                continue
            number = sum(row[0] in text_by_key for row in blueprints[:index + 1])
            heading.text = f'{number}. {text_by_key[key]}'
    elif old != 0 or current != 1:
        raise ValueError('The expected 2.2.0 or 2.3.0 review copy was not found.')
    for p in paras:
        if 'SPA-PUBLIC-QUESTIONNAIRE-2.2.0' in p.text:
            p.text = p.text.replace('SPA-PUBLIC-QUESTIONNAIRE-2.2.0', version)
        if '29 September 2026  |  Working review copy' in p.text:
            p.text = p.text.replace('29 September 2026', '01 October 2026')
        if p.text.startswith('This educational screen provides an initial readiness picture.'):
            p.text = ('These nine questions help you identify topics to discuss. This is an '
                      'anonymous educational screen, not a completed SalCAPA™ assessment. '
                      'It does not score all 32 core capabilities or establish readiness. '
                      'Choose the best response from what you know today.')
        if p.text.startswith('Your answers can identify possible strengths, concerns and missing information.'):
            p.text = ('Your answers can highlight possible strengths, concerns and missing '
                      'information. Capabilities outside these nine questions remain unassessed. '
                      'If you continue, Part 2 helps Salus understand the operation you want '
                      'assessed and suggest a starting Level 1 package path.')
        if p.text.startswith('☐ Yes, recently tested') and '   ☐ Prefer not to answer' in p.text:
            p.text = p.text.replace('   ☐ Prefer not to answer', '\n☐ Prefer not to answer')
    document.save(TARGET)
    print(TARGET)


if __name__ == '__main__':
    main()
