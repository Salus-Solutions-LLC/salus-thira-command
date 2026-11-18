"""SALUS-DOC-HEADING-SPACING-001: effective DOCX heading paragraph spacing.

Only spacing is changed. Call before saving a controlled successor, never in place
on an issued original. Exact-file rendering/accessibility remain separate checks.
"""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

RULE = {0: (240, 240), 1: (240, 120)}  # Word twips: 20 per point


def _child(parent, name):
    return None if parent is None else parent.find(qn('w:' + name))


def _level(ppr):
    node = _child(ppr, 'outlineLvl')
    return None if node is None else int(node.get(qn('w:val')))


def _styles(document):
    return {s.get(qn('w:styleId')): s for s in document.styles.element}


def _style_level(style_id, styles, seen=()):
    if not style_id or style_id not in styles or style_id in seen:
        return None
    style = styles[style_id]
    level = _level(_child(style, 'pPr'))
    if level is not None:
        return level
    if style_id in ('Heading1', 'Heading2'):
        return int(style_id[-1]) - 1
    base = _child(style, 'basedOn')
    return _style_level(base.get(qn('w:val')) if base is not None else None,
                        styles, (*seen, style_id))


def _paragraph_level(paragraph, styles):
    ppr = _child(paragraph, 'pPr')
    level = _level(ppr)
    if level is not None:
        return level
    style = _child(ppr, 'pStyle')
    return _style_level(style.get(qn('w:val')) if style is not None else None, styles)


def _set(ppr, level):
    spacing = _child(ppr, 'spacing')
    if spacing is None:
        spacing = OxmlElement('w:spacing'); ppr.append(spacing)
    for key in ('beforeAutospacing', 'afterAutospacing', 'beforeLines', 'afterLines'):
        spacing.attrib.pop(qn('w:' + key), None)
    for key, value in zip(('before', 'after'), RULE[level]):
        spacing.set(qn('w:' + key), str(value))
    # Explicit false prevents an inherited contextual-spacing override.
    contextual = _child(ppr, 'contextualSpacing')
    if contextual is None:
        contextual = OxmlElement('w:contextualSpacing'); ppr.append(contextual)
    contextual.set(qn('w:val'), '0')


def _stories(document):
    for part in document.part.package.parts:
        if str(part.partname).startswith('/word/') and hasattr(part, 'element'):
            yield str(part.partname), part.element


def apply_heading_spacing(document):
    """Set styles and every used H1/H2 paragraph, including nested/story content."""
    styles = _styles(document)
    for style_id, style in styles.items():
        if style.get(qn('w:type')) != 'paragraph':
            continue
        level = _style_level(style_id, styles)
        if level in RULE:
            ppr = _child(style, 'pPr')
            if ppr is None:
                ppr = OxmlElement('w:pPr'); style.append(ppr)
            _set(ppr, level)
    for _, root in _stories(document):
        for p in root.iter(qn('w:p')):
            level = _paragraph_level(p, styles)
            if level in RULE:
                ppr = _child(p, 'pPr')
                if ppr is None:
                    ppr = OxmlElement('w:pPr'); p.insert(0, ppr)
                _set(ppr, level)
    return document


def heading_spacing_findings(document):
    """Fail on missing/overridden spacing; does not certify visual or full Charter QA."""
    styles = _styles(document); findings = []
    def chain(sid, seen=()):
        if not sid or sid not in styles or sid in seen: return []
        style=styles[sid];base=_child(style,'basedOn')
        return chain(base.get(qn('w:val')) if base is not None else None,(*seen,sid))+[_child(style,'pPr')]
    def check(properties, level, location):
        values={}; context='0'
        for ppr in properties:
            spacing=_child(ppr,'spacing')
            if spacing is not None: values.update(spacing.attrib)
            contextual=_child(ppr,'contextualSpacing')
            if contextual is not None: context=contextual.get(qn('w:val'),'1')
        actual=tuple(values.get(qn('w:'+k)) for k in ('before','after'))
        overrides=[k for k in ('beforeAutospacing','afterAutospacing','beforeLines','afterLines')
                   if values.get(qn('w:'+k)) not in (None,'0','false','off')]
        if context not in ('0','false','off'): overrides.append('contextualSpacing')
        if actual != tuple(map(str, RULE[level])) or overrides:
            findings.append({'location': location, 'level': level + 1,
                             'actual_twips': actual, 'expected_twips': RULE[level],
                             'overrides': overrides})
    for sid, style in styles.items():
        if style.get(qn('w:type')) == 'paragraph':
            level = _style_level(sid, styles)
            if level in RULE: check(chain(sid), level, 'style:' + sid)
    for name, root in _stories(document):
        for index, p in enumerate(root.iter(qn('w:p'))):
            level = _paragraph_level(p, styles)
            if level in RULE:
                ppr=_child(p,'pPr');style=_child(ppr,'pStyle')
                sid=style.get(qn('w:val')) if style is not None else None
                check(chain(sid)+[ppr], level, f'{name}:paragraph:{index}')
    return findings
