"""Markdown -> A4 PDF with the DRAFT stamp printed at the top and bottom of every page. Used for every document the app generates for the consent pack."""
import io
import markdown, pymupdf
from .stamp import STAMP

CSS = "body{font-family:sans-serif;font-size:9.5pt} h1{font-size:15pt} h2{font-size:12pt} table{border-collapse:collapse} td,th{border:1px solid #999;padding:2px 4px;font-size:8.5pt;vertical-align:top} code{font-size:8.5pt}"

def md_to_pdf(md_text: str, title: str, stamp: str | None = STAMP) -> bytes:
    html = markdown.markdown(md_text, extensions=["tables"])
    story = pymupdf.Story(html=(f"<h1>{title}</h1>" if title else "") + html, user_css=CSS)
    mem = io.BytesIO(); w = pymupdf.DocumentWriter(mem)
    media = pymupdf.paper_rect("a4"); where = media + (40, 50, -40, -50)
    more = 1
    while more:
        dev = w.begin_page(media); more, _ = story.place(where); story.draw(dev); w.end_page()
    w.close()
    doc = pymupdf.open(stream=mem.getvalue(), filetype="pdf")
    for pg in doc:
        if stamp: pg.insert_text((40, 28), stamp, fontsize=8, color=(0.8, 0, 0))
        pg.insert_text((40, media.height - 24), f"{stamp + '  |  ' if stamp else ''}page {pg.number + 1} of {len(doc)}", fontsize=7, color=(0.8, 0, 0))
    out = doc.tobytes(); doc.close(); return out
