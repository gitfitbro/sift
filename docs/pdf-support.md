# PDF Support

sift now supports PDF documents as input! Upload PDFs and the tool will automatically extract text for processing.

## How It Works

```
PDF Upload → Text Extraction → Transcript → AI Extraction → Structured Data
```

1. **Upload PDF**: Use `--file document.pdf`
2. **Automatic extraction**: Text is extracted from all pages
3. **Saved as transcript**: Text saved as `transcript.txt`
4. **Original preserved**: PDF saved as `document.pdf`
5. **Continue normally**: Extract structured data with AI

---

## Usage Examples

### Example 1: Discovery Call Notes

```bash
# You have PDF notes from a client meeting
sift new discovery-call --name client-meeting
sift phase capture client-meeting -p context --file meeting-notes.pdf

# Text is automatically extracted and ready for AI extraction
sift phase extract client-meeting -p context
```

### Example 2: Interview Transcript

```bash
# You have a PDF transcript of an interview
sift new workflow-extraction --name user-interview
sift phase capture user-interview -p describe --file interview-transcript.pdf

# No need to transcribe (it's already text), go straight to extraction
sift phase extract user-interview -p describe
```

### Example 3: Document Analysis

```bash
# Analyze a requirements document
sift new discovery-call --name requirements-review
sift phase capture requirements-review -p context --file requirements-doc.pdf
sift phase extract requirements-review -p context

# Extract pain points, tools mentioned, desired outcomes, etc.
```

---

## Supported PDF Features

✅ **Text extraction from all pages**
✅ **Multi-page documents**
✅ **Preserves page numbers** (`[Page 1]`, `[Page 2]`, etc.)
✅ **Original PDF stored** (for reference)
✅ **Automatic text flow** (paragraphs preserved)

⚠️ **Limitations:**
- **Text-based PDFs only** - Scanned images won't work (no OCR)
- **Complex layouts** may not preserve formatting perfectly
- **Tables** may not extract in structured format
- **Images/charts** are ignored (text only)

---

## Command Reference

```bash
# Upload PDF to a session phase
sift phase capture <session> -p <phase> --file document.pdf

# Interactive mode (prompts for file)
sift phase capture <session> -p <phase>
```

---

## What Gets Stored

When you upload a PDF:

```
data/sessions/my-session/phases/describe/
├── document.pdf          # Original PDF (preserved)
└── transcript.txt        # Extracted text
```

The `transcript.txt` file contains:

```
[Page 1]
First page text content goes here...

[Page 2]
Second page text content...

[Page 3]
...and so on
```

---

## Technical Details

### PDF Library
- Uses `pypdf` (PyPDF) library
- Installed automatically via `requirements.txt`
- Pure Python, no external dependencies

### Text Extraction Process
1. Reads PDF file with `PdfReader`
2. Iterates through all pages
3. Extracts text from each page
4. Adds page markers `[Page N]`
5. Combines into single text file

### Installation
```bash
# Already included in requirements.txt
pip install pypdf

# Or run setup script
bash setup.sh
```

---

## Use Cases

### 1. Meeting Notes & Minutes
Convert PDF meeting notes into structured action items, decisions, and follow-ups.

```bash
sift new discovery-call --name board-meeting
sift phase capture board-meeting -p context --file minutes.pdf
sift phase extract board-meeting -p context
# Extracts: decisions made, action items, attendees, etc.
```

### 2. Interview Transcripts
Process interview transcripts to extract themes, pain points, and insights.

```bash
sift new workflow-extraction --name user-research
sift phase capture user-research -p describe --file interview.pdf
sift phase extract user-research -p describe
# Extracts: pain points, workflows, tools used, desired outcomes
```

### 3. Requirements Documents
Analyze requirements docs to extract constraints, features, and stakeholders.

```bash
sift new discovery-call --name project-requirements
sift phase capture project-requirements -p context --file requirements.pdf
sift phase extract project-requirements -p context
# Extracts: requirements, constraints, stakeholders, timeline
```

### 4. Research Papers
Extract methodology, findings, and conclusions from research papers.

```bash
sift new workflow-extraction --name research-analysis
sift phase capture research-analysis -p describe --file paper.pdf
sift phase extract research-analysis -p describe
# Extracts: key findings, methodology, tools/technologies mentioned
```

### 5. Reports & Documentation
Convert status reports into structured data for tracking and analysis.

```bash
sift new discovery-call --name quarterly-review
sift phase capture quarterly-review -p context --file q4-report.pdf
sift phase extract quarterly-review -p context
# Extracts: achievements, challenges, metrics, next steps
```

---

## Troubleshooting

### "pypdf not installed"
```bash
pip install pypdf
# or
bash setup.sh
```

### "No text could be extracted from the PDF"
- **Cause**: PDF is scanned images (no text layer)
- **Solution**: Use OCR tool first to convert to text-based PDF
- **Tools**: Adobe Acrobat, online OCR services, or `ocrmypdf` library

### "Text is garbled or in wrong order"
- **Cause**: Complex PDF layout or multi-column format
- **Solution**:
  1. Try converting PDF to plain text first (`pdftotext` command)
  2. Or manually copy-paste text and use `--text` flag instead

### "Large PDF is slow"
- **Cause**: Many pages or large file size
- **Solution**: This is normal - wait for extraction to complete
- **Tip**: You'll see a status message while extracting

---

## Comparing Input Methods

| Method | When to Use | Processing |
|--------|-------------|------------|
| Audio file | Recorded conversations | Upload → Transcribe → Extract |
| Text file (.txt, .md) | Already have transcript | Upload → Extract |
| PDF file (.pdf) | PDF documents | Upload → Extract text → Extract |
| Type directly (`--text`) | Short notes | Type → Extract |

---

## Examples with Output

### Example: Meeting Notes PDF

**Input PDF (meeting-notes.pdf):**
```
Meeting Notes - Project Kickoff
Date: 2026-02-07

Attendees: John, Sarah, Mike

Key Points:
- Need to migrate to new CRM system
- Current system (Salesforce) is too slow
- Budget: $50k
- Timeline: 3 months
...
```

**Command:**
```bash
sift new discovery-call --name project-kickoff
sift phase capture project-kickoff -p context --file meeting-notes.pdf
sift phase extract project-kickoff -p context
```

**Extracted Data (extracted.yaml):**
```yaml
current_tools:
  - Salesforce CRM

pain_points:
  - Current CRM system is too slow
  - Need to migrate to new system

decision_makers:
  - John
  - Sarah
  - Mike

hard_constraints:
  - Budget: $50,000
  - Timeline: 3 months
```

---

## Best Practices

1. **Check PDF quality first** - Make sure it's text-based, not a scanned image
2. **Keep PDFs focused** - Shorter, focused documents work better than long reports
3. **Review extracted text** - Check `transcript.txt` to ensure extraction worked well
4. **Use appropriate templates** - Different PDF types work better with different templates
5. **Combine with other phases** - PDFs work great alongside audio recordings and notes

---

## Advanced: Custom PDF Processing

If you need more control over PDF extraction, you can:

1. **Pre-process PDF** to plain text:
   ```bash
   pdftotext document.pdf output.txt
   sift phase capture <session> -p <phase> --file output.txt
   ```

2. **Extract specific pages** (requires custom script):
   ```python
   from pypdf import PdfReader
   reader = PdfReader("document.pdf")
   # Extract pages 3-5
   text = "\n".join([reader.pages[i].extract_text() for i in range(2, 5)])
   with open("excerpt.txt", "w") as f:
       f.write(text)
   ```

3. **Handle scanned PDFs with OCR**:
   ```bash
   # Install ocrmypdf
   pip install ocrmypdf

   # Add text layer to scanned PDF
   ocrmypdf input-scanned.pdf output-searchable.pdf

   # Now use with sift
   sift phase capture <session> -p <phase> --file output-searchable.pdf
   ```

---

## Summary

PDF support makes sift work with documents you already have, without manual copying and pasting. Upload PDFs directly and let the tool extract text automatically!

**Quick Start:**
```bash
sift new discovery-call --name my-session
sift phase capture my-session -p context --file document.pdf
sift phase extract my-session -p context
```

That's it! 🎉
