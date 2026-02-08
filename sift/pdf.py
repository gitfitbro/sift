"""PDF extraction utilities for sift."""

import re
from pathlib import Path

try:
    import pdfplumber

    PDF_AVAILABLE = True
    PDF_ENGINE = "pdfplumber"
except ImportError:
    try:
        from pypdf import PdfReader  # noqa: F401

        PDF_AVAILABLE = True
        PDF_ENGINE = "pypdf"
    except ImportError:
        PDF_AVAILABLE = False
        PDF_ENGINE = None


def _table_to_markdown(table: list[list]) -> str:
    """Convert a pdfplumber table (list of rows) to a markdown table."""
    if not table or not table[0]:
        return ""

    # Clean cell values: replace newlines with spaces, strip whitespace
    cleaned = []
    for row in table:
        cleaned.append([re.sub(r"\s+", " ", (cell or "").strip()) for cell in row])

    # Calculate column widths for alignment
    num_cols = max(len(row) for row in cleaned)
    col_widths = [0] * num_cols
    for row in cleaned:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(cell))

    # Build markdown table
    lines = []
    for row_idx, row in enumerate(cleaned):
        # Pad row to num_cols
        padded = row + [""] * (num_cols - len(row))
        cells = [cell.ljust(col_widths[i]) for i, cell in enumerate(padded)]
        lines.append("| " + " | ".join(cells) + " |")

        # Add separator after header row
        if row_idx == 0:
            sep = ["-" * col_widths[i] for i in range(num_cols)]
            lines.append("| " + " | ".join(sep) + " |")

    return "\n".join(lines)


def _detect_headers_footers(pages) -> tuple[set[str], set[str]]:
    """Detect repeating headers and footers across pages."""
    if len(pages) < 3:
        return set(), set()

    first_lines = []
    last_lines = []

    for page in pages:
        text = page.extract_text()
        if not text:
            continue
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            first_lines.append(lines[0])
        if lines:
            last_lines.append(lines[-1])

    # A header/footer repeats on most pages (>60%)
    threshold = len(pages) * 0.6
    headers = set()
    footers = set()

    from collections import Counter

    for line, count in Counter(first_lines).items():
        if count >= threshold:
            headers.add(line)

    # Footer pattern: "Page N" or exact repeating text
    page_pattern = re.compile(r"^Page\s+\d+$")
    for line, count in Counter(last_lines).items():
        if count >= threshold or page_pattern.match(line):
            footers.add(line)

    return headers, footers


def _extract_page_content(page, headers: set[str], footers: set[str]) -> list[tuple[float, str]]:
    """Extract all content from a page as positioned blocks (text + tables interleaved).

    Returns a list of (vertical_position, content_string) sorted by position.
    """
    content_blocks = []
    found_tables = page.find_tables()

    # Collect table regions and their markdown content
    table_regions = []
    for table_obj in found_tables:
        bbox = table_obj.bbox  # (x0, top, x1, bottom)
        table_data = table_obj.extract()
        if table_data and any(any(cell for cell in row) for row in table_data):
            md = _table_to_markdown(table_data)
            if md:
                table_regions.append((bbox[1], bbox[3]))  # (top, bottom)
                content_blocks.append((bbox[1], md))

    # Sort table regions by vertical position
    table_regions.sort()

    # Extract text from gaps between tables
    gap_regions = []
    current_top = 0
    for table_top, table_bottom in table_regions:
        if table_top > current_top + 1:  # small tolerance
            gap_regions.append((current_top, table_top))
        current_top = table_bottom
    # After last table to page bottom
    if current_top < page.height - 1:
        gap_regions.append((current_top, page.height))

    # If no tables, the whole page is one gap
    if not table_regions:
        gap_regions = [(0, page.height)]

    for gap_top, gap_bottom in gap_regions:
        try:
            cropped = page.crop((0, gap_top, page.width, gap_bottom))
            text = cropped.extract_text()
        except Exception:
            continue

        if not text or not text.strip():
            continue

        # Clean the text: remove headers/footers, fix spacing
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped in headers or stripped in footers:
                continue
            if re.match(r"^Page\s+\d+$", stripped):
                continue
            cleaned = re.sub(r"  +", " ", stripped)
            if cleaned:
                cleaned_lines.append(cleaned)

        if cleaned_lines:
            content_blocks.append((gap_top, "\n".join(cleaned_lines)))

    # Sort by vertical position and return
    content_blocks.sort(key=lambda x: x[0])
    return content_blocks


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, dict]:
    """Extract text content from a PDF file with table preservation.

    Returns:
        Tuple of (extracted_text, stats_dict) where stats contains
        page_count, table_count, and char_count.
    """
    if not PDF_AVAILABLE:
        raise ImportError("PDF libraries not installed. Install with: pip install pdfplumber")

    stats = {"page_count": 0, "table_count": 0, "char_count": 0}

    if PDF_ENGINE == "pdfplumber":
        return _extract_with_pdfplumber(pdf_path, stats)
    else:
        return _extract_with_pypdf(pdf_path, stats)


def _extract_with_pdfplumber(pdf_path: Path, stats: dict) -> tuple[str, dict]:
    """Extract using pdfplumber with table structure preservation."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            stats["page_count"] = len(pdf.pages)

            # Detect headers/footers
            headers, footers = _detect_headers_footers(pdf.pages)

            text_parts = []

            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract all content blocks in reading order
                blocks = _extract_page_content(page, headers, footers)

                if blocks:
                    # Count tables on this page
                    for _, content in blocks:
                        if content.startswith("|") and " | " in content:
                            stats["table_count"] += 1

                    page_text = "\n\n".join(content for _, content in blocks)
                    text_parts.append(f"[Page {page_num}]\n{page_text}")

        full_text = "\n\n".join(text_parts)

        if not full_text.strip():
            raise ValueError("No text could be extracted from the PDF")

        stats["char_count"] = len(full_text)
        return full_text, stats

    except Exception as e:
        if "No text could be extracted" in str(e):
            raise
        raise


def _extract_with_pypdf(pdf_path: Path, stats: dict) -> tuple[str, dict]:
    """Fallback extraction using pypdf (no table support)."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(pdf_path)
        text_parts = []
        stats["page_count"] = len(reader.pages)

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                # Clean double spacing
                cleaned = re.sub(r"  +", " ", text)
                text_parts.append(f"[Page {page_num}]\n{cleaned}")

        full_text = "\n\n".join(text_parts)

        if not full_text.strip():
            raise ValueError("No text could be extracted from the PDF")

        stats["char_count"] = len(full_text)
        return full_text, stats

    except Exception as e:
        if "No text could be extracted" in str(e):
            raise
        raise
