"""
Script to generate the complete MCA college project documentation for ShieldRAG:
docs/Project_Documentation.docx
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, Mm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

def create_element(name):
    return OxmlElement(name)

def add_xml_field(run, field_text):
    """Add a simple XML field like PAGE, NUMPAGES to a run."""
    fldSimple = OxmlElement('w:fldSimple')
    fldSimple.set(qn('w:instr'), field_text)
    run._r.append(fldSimple)

def add_complex_field(p, field_code):
    """Add complex field (like TOC, List of Figures/Tables) to a paragraph."""
    pPr = p._p.get_or_add_pPr()
    r1 = OxmlElement('w:r')
    fld1 = OxmlElement('w:fldChar')
    fld1.set(qn('w:fldCharType'), 'begin')
    r1.append(fld1)
    
    r2 = OxmlElement('w:r')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = field_code
    r2.append(instr)
    
    r3 = OxmlElement('w:r')
    fld2 = OxmlElement('w:fldChar')
    fld2.set(qn('w:fldCharType'), 'separate')
    r3.append(fld2)
    
    r4 = OxmlElement('w:r')
    fld3 = OxmlElement('w:fldChar')
    fld3.set(qn('w:fldCharType'), 'end')
    r4.append(fld3)
    
    p._p.append(r1)
    p._p.append(r2)
    p._p.append(r3)
    p._p.append(r4)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner padding for table cells in dxa."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_shading(cell, color_hex):
    """Set background color for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)

def set_table_borders(table, color="D3D3D3", sz="4", val="single"):
    """Apply borders to a table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def format_paragraph(p, space_before=0, space_after=6, line_spacing=1.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing

def add_body_p(doc, text, space_before=0, space_after=6, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    format_paragraph(p, space_before=space_before, space_after=space_after, line_spacing=1.5, align=align)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)
    return p

def add_bullet_p(doc, bold_prefix, text, space_before=0, space_after=4):
    p = doc.add_paragraph(style='List Bullet')
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.5
    
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Times New Roman'
        r_pre.font.size = Pt(12)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(0, 0, 0)
        
    r_text = p.add_run(text)
    r_text.font.name = 'Times New Roman'
    r_text.font.size = Pt(12)
    r_text.font.color.rgb = RGBColor(0, 0, 0)
    return p

def add_heading_1(doc, chapter_num, title):
    """Add Chapter Heading with Page Break Before, 16pt, Bold, ALL CAPS, Center."""
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(18)
    p.paragraph_format.line_spacing = 1.15
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Associate with Word Heading 1 style for TOC
    p.style = doc.styles['Heading 1']
    
    # We clear any default text that style might inject
    p.text = ""
    r1 = p.add_run(f"CHAPTER {chapter_num}\n{title.upper()}")
    r1.font.name = 'Times New Roman'
    r1.font.size = Pt(16)
    r1.font.bold = True
    r1.font.color.rgb = RGBColor(0, 51, 102) # Deep academic navy blue
    return p

def add_frontmatter_heading(doc, title):
    """Add Front Matter Heading (Abstract, TOC, etc.) Center, 16pt, Bold."""
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(18)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.style = doc.styles['Heading 1']
    p.text = ""
    run = p.add_run(title.upper())
    run.font.name = 'Times New Roman'
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0, 51, 102)
    return p

def add_heading_2(doc, sec_num, title):
    """Add Section Heading (Heading 2), 14pt, Bold, Left."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.style = doc.styles['Heading 2']
    p.text = ""
    run = p.add_run(f"{sec_num} {title}")
    run.font.name = 'Times New Roman'
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0, 51, 102)
    return p

def add_heading_3(doc, subsec_num, title):
    """Add Subsection Heading (Heading 3), 12pt, Bold, Left."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.style = doc.styles['Heading 3']
    p.text = ""
    run = p.add_run(f"{subsec_num} {title}")
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    run.font.bold = True
    run.font.color.rgb = RGBColor(30, 41, 59)
    return p

def add_table_caption(doc, table_num, title):
    """Caption ABOVE table with Word Caption style."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    
    r_label = p.add_run(f"Table {table_num}: ")
    r_label.font.name = 'Times New Roman'
    r_label.font.size = Pt(11)
    r_label.font.bold = True
    r_label.font.color.rgb = RGBColor(0, 51, 102)
    
    r_title = p.add_run(title)
    r_title.font.name = 'Times New Roman'
    r_title.font.size = Pt(11)
    r_title.font.bold = True
    r_title.font.italic = False
    return p

def add_figure_caption(doc, fig_num, title):
    """Caption BELOW figure with Word Caption style."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(12)
    
    r_label = p.add_run(f"Figure {fig_num}: ")
    r_label.font.name = 'Times New Roman'
    r_label.font.size = Pt(11)
    r_label.font.bold = True
    r_label.font.color.rgb = RGBColor(0, 51, 102)
    
    r_title = p.add_run(title)
    r_title.font.name = 'Times New Roman'
    r_title.font.size = Pt(11)
    r_title.font.bold = True
    r_title.font.italic = False
    return p

def add_image_figure(doc, img_path, fig_num, title, width_inches=6.0):
    """Add a centered image followed by its caption."""
    if os.path.exists(img_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(10)
        p_img.paragraph_format.space_after = Pt(4)
        p_img.paragraph_format.keep_with_next = True
        run = p_img.add_run()
        run.add_picture(img_path, width=Inches(width_inches))
    else:
        p_err = doc.add_paragraph()
        p_err.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p_err.add_run(f"[Screenshot {img_path} - Image to be embedded]")
        r.font.italic = True
        r.font.size = Pt(10)
    add_figure_caption(doc, fig_num, title)

print("Helper definitions loaded.")
