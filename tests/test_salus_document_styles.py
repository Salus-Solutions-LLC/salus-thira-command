import unittest
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from salus_document_styles import apply_heading_spacing, heading_spacing_findings

class HeadingSpacingTests(unittest.TestCase):
    def test_generic_footnote_part_survives_save_and_reload(self):
        from docx.opc.part import Part
        from docx.opc.packuri import PackURI
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
        from io import BytesIO
        d=Document()
        xml=b'<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:id="1"><w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Footnote heading</w:t></w:r></w:p></w:footnote></w:footnotes>'
        part=Part(PackURI('/word/footnotes.xml'),'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml',xml,d.part.package)
        d.part.relate_to(part,RT.FOOTNOTES)
        self.assertTrue(heading_spacing_findings(d))
        apply_heading_spacing(d);b=BytesIO();d.save(b);b.seek(0);reloaded=Document(b)
        self.assertEqual(heading_spacing_findings(reloaded),[])
        self.assertIn(b'Footnote heading',next(p.blob for p in reloaded.part.package.parts if str(p.partname)=='/word/footnotes.xml'))

    def test_detects_direct_override_after_correct_style(self):
        d=Document(); p=d.add_heading('Heading',1); apply_heading_spacing(d)
        p.paragraph_format.space_after=Pt(5)
        self.assertTrue(heading_spacing_findings(d))

    def test_custom_inherited_style_and_nested_stories(self):
        d=Document(); s=d.styles.add_style('Custom section',WD_STYLE_TYPE.PARAGRAPH)
        s.base_style=d.styles['Heading 2']
        p=d.add_table(rows=1,cols=1).cell(0,0).paragraphs[0]; p.style=s; p.text='Nested'
        d.sections[0].header.paragraphs[0].style='Heading 1'
        apply_heading_spacing(d)
        self.assertEqual(heading_spacing_findings(d),[])
        p.paragraph_format.space_before=Pt(2)
        self.assertTrue(heading_spacing_findings(d))

    def test_outline_level_and_automatic_spacing(self):
        d=Document();p=d.add_paragraph('Custom outline')
        node=OxmlElement('w:outlineLvl');node.set(qn('w:val'),'1');p._p.get_or_add_pPr().append(node)
        apply_heading_spacing(d)
        spacing=p._p.pPr.find(qn('w:spacing'));spacing.set(qn('w:afterAutospacing'),'1')
        self.assertTrue(heading_spacing_findings(d))
        apply_heading_spacing(d);self.assertEqual(heading_spacing_findings(d),[])

    def test_preserves_body_text_and_other_level_spacing(self):
        d=Document();body=d.add_paragraph('Preserved body');body.paragraph_format.space_after=Pt(7)
        h=d.add_heading('Other level',3);h.paragraph_format.space_before=Pt(18)
        apply_heading_spacing(d)
        self.assertEqual(body.text,'Preserved body');self.assertEqual(body.paragraph_format.space_after.pt,7)
        self.assertEqual(h.paragraph_format.space_before.pt,18)
        self.assertEqual(heading_spacing_findings(d),[])

if __name__=='__main__':unittest.main()
