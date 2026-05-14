import aiofiles
import urllib
import mistune
import os

async def write_to_file(filename: str, text: str) -> None:
    """Asynchronously write text to a file in UTF-8 encoding.

    Args:
        filename (str): The filename to write to.
        text (str): The text to write.
    """
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)

    # Convert text to UTF-8, replacing any problematic characters
    text_utf8 = text.encode('utf-8', errors='replace').decode('utf-8')

    async with aiofiles.open(filename, "w", encoding='utf-8') as file:
        await file.write(text_utf8)

async def write_text_to_md(text: str, filename: str = "") -> str:
    """Writes text to a Markdown file and returns the file path.

    Args:
        text (str): Text to write to the Markdown file.

    Returns:
        str: The file path of the generated Markdown file.
    """
    file_path = f"outputs/{filename[:60]}.md"
    await write_to_file(file_path, text)
    return urllib.parse.quote(file_path)

def _flatten_table_cells(html: str) -> str:
    """Strip nested tags inside <td> and <th> elements, keeping only text content.

    fpdf2's write_html raises NotImplementedError for nested tags inside table
    cells (e.g. <td><strong>text</strong></td>).  This flattens those cells to
    plain text so the table renders without crashing.
    """
    from html.parser import HTMLParser

    class TableCellFlattener(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.result = []
            self._in_cell = 0   # nesting depth inside td/th
            self._cell_tag = None

        def handle_starttag(self, tag, attrs):
            if tag in ("td", "th"):
                self._in_cell += 1
                self._cell_tag = tag
                attr_str = "".join(f' {k}="{v}"' for k, v in attrs if v is not None)
                self.result.append(f"<{tag}{attr_str}>")
            elif self._in_cell:
                pass  # swallow nested opening tags inside cells
            else:
                attr_str = "".join(f' {k}="{v}"' for k, v in attrs if v is not None)
                self.result.append(f"<{tag}{attr_str}>")

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self._in_cell:
                self._in_cell -= 1
                self.result.append(f"</{tag}>")
            elif self._in_cell:
                pass  # swallow nested closing tags inside cells
            else:
                self.result.append(f"</{tag}>")

        def handle_data(self, data):
            self.result.append(data)

        def handle_entityref(self, name):
            self.result.append(f"&{name};")

        def handle_charref(self, name):
            self.result.append(f"&#{name};")

    flattener = TableCellFlattener()
    flattener.feed(html)
    return "".join(flattener.result)


async def write_md_to_pdf(text: str, filename: str = "") -> str:
    """Converts Markdown text to a PDF file and returns the file path.

    Args:
        text (str): Markdown text to convert.

    Returns:
        str: The encoded file path of the generated PDF.
    """
    file_path = f"outputs/{filename[:60]}.pdf"

    try:
        import mistune
        from fpdf import FPDF

        # Find a CJK-capable font on Windows
        _FONT_CANDIDATES = [
            r"C:\Windows\Fonts\msyh.ttc",    # 微软雅黑
            r"C:\Windows\Fonts\simhei.ttf",  # 黑体
            r"C:\Windows\Fonts\simsun.ttc",  # 宋体
        ]
        cjk_font_path = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), None)

        html = _flatten_table_cells(mistune.html(text))

        class PDF(FPDF):
            def header(self):
                pass

        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        if cjk_font_path:
            bold_candidates = [
                r"C:\Windows\Fonts\msyhbd.ttc",
                r"C:\Windows\Fonts\simhei.ttf",
            ]
            bold_path = next((p for p in bold_candidates if os.path.exists(p)), cjk_font_path)
            pdf.add_font("CJK", style="",   fname=cjk_font_path)
            pdf.add_font("CJK", style="B",  fname=bold_path)
            pdf.add_font("CJK", style="I",  fname=cjk_font_path)
            pdf.add_font("CJK", style="BI", fname=bold_path)
            pdf.set_font("CJK", size=11)
        else:
            pdf.set_font("Helvetica", size=11)

        pdf.write_html(html)
        pdf.output(file_path)
        print(f"Report written to {file_path}")
    except Exception as e:
        print(f"Error in converting Markdown to PDF: {e}")
        return ""

    encoded_file_path = urllib.parse.quote(file_path)
    return encoded_file_path

async def write_md_to_word(text: str, filename: str = "") -> str:
    """Converts Markdown text to a DOCX file and returns the file path.

    Args:
        text (str): Markdown text to convert.

    Returns:
        str: The encoded file path of the generated DOCX.
    """
    file_path = f"outputs/{filename[:60]}.docx"

    try:
        from docx import Document
        from htmldocx import HtmlToDocx
        # Convert report markdown to HTML
        html = mistune.html(text)
        # Create a document object
        doc = Document()
        # Convert the html generated from the report to document format
        HtmlToDocx().add_html_to_document(html, doc)

        # Saving the docx document to file_path
        doc.save(file_path)

        print(f"Report written to {file_path}")

        encoded_file_path = urllib.parse.quote(file_path)
        return encoded_file_path

    except Exception as e:
        print(f"Error in converting Markdown to DOCX: {e}")
        return ""