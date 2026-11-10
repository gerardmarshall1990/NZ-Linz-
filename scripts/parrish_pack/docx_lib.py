"""python-docx helpers: tables with yellow (supply) / orange (confirm) shading, tags, page numbers."""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
YEL, ORG, GRY, HDR = "FFF2CC", "F8CBAD", "EDEDED", "1F3864"
def new_doc():
    d = Document(); s = d.sections[0]; s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin = s.right_margin = Cm(1.6); s.top_margin = Cm(1.6); s.bottom_margin = Cm(1.6)
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10); st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for n, sz in (("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11)):
        h = d.styles[n]; h.font.name = "Calibri"; h.font.size = Pt(sz); h.font.bold = True; h.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    # footer with page number
    p = s.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("DRAFT, not certified. Screening values, every number tagged DATA / CALCULATED / ASSUMED / UNVERIFIED.   Page "); r.font.size = Pt(8)
    for t, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        r2 = p.add_run(); r2.font.size = Pt(8)
        if t: e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), t); r2._r.append(e)
        else: e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt; r2._r.append(e)
    return d
def shade(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr()
    for x in tcPr.findall(qn("w:shd")): tcPr.remove(x)
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexcol); tcPr.append(sh)
def auto_fill(txt):
    t = (txt or "").strip()
    if t == "": return YEL
    u = t.upper()
    if t.startswith("[ENGINEER]") or "UNVERIFIED" in u or "ASSUMED" in u or "CONFIRM" in u[:12]: return ORG
    return None
def para(d, text="", bold=False, italic=False, size=None, color=None, style=None, fill=None, after=4):
    p = d.add_paragraph(style=style) if style else d.add_paragraph()
    r = p.add_run(text); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = RGBColor.from_string(color)
    p.paragraph_format.space_after = Pt(after)
    if fill:
        pPr = p._p.get_or_add_pPr(); sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), fill); pPr.append(sh)
    return p
def bullets(d, items, fill_rule=True):
    for it in items:
        txt, fl = (it if isinstance(it, tuple) else (it, auto_fill(it) if fill_rule else None))
        p = d.add_paragraph(style="List Bullet"); r = p.add_run(txt); p.paragraph_format.space_after = Pt(2)
        if fl and fl != YEL:
            pPr = p._p.get_or_add_pPr(); sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), fl); pPr.append(sh)
def numbered(d, items):
    for it in items:
        p = d.add_paragraph(style="List Number"); p.add_run(it); p.paragraph_format.space_after = Pt(2)
def table(d, headers, rows, widths=None, size=8, hdr_fill=HDR, first_col_bold=False, fills=None, rule=True):
    t = d.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for j, h in enumerate(headers):
        c = t.rows[0].cells[j]; c.text = ""; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(size); r.font.color.rgb = RGBColor(255, 255, 255); shade(c, hdr_fill)
    tr = t.rows[0]._tr; trPr = tr.get_or_add_trPr(); e = OxmlElement("w:tblHeader"); e.set(qn("w:val"), "true"); trPr.append(e)
    for i, row in enumerate(rows):
        cells = t.add_row().cells
        for j, v in enumerate(row):
            fl = None
            if isinstance(v, tuple): v, fl = v
            elif rule and j > 0 or (rule and j == 0 and v == ""): fl = auto_fill(str(v))
            if fills and (i, j) in fills: fl = fills[(i, j)]
            cells[j].text = ""; p = cells[j].paragraphs[0]; r = p.add_run("" if v is None else str(v)); r.font.size = Pt(size); p.paragraph_format.space_after = Pt(0)
            if first_col_bold and j == 0: r.bold = True
            if fl: shade(cells[j], fl)
    if widths:
        tblPr = t._tbl.tblPr; lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
        grid = t._tbl.tblGrid
        for j, gc in enumerate(grid.findall(qn("w:gridCol"))): gc.set(qn("w:w"), str(int(widths[j] * 567)))
        for j, w in enumerate(widths): t.columns[j].width = Cm(w)
        for row in t.rows:
            for j, w in enumerate(widths): row.cells[j].width = Cm(w)
    d.add_paragraph().paragraph_format.space_after = Pt(2)
    return t
def img(d, path, width_cm=17.5):
    d.add_picture(str(path), width=Cm(width_cm))
