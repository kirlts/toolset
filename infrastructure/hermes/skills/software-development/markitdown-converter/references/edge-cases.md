# Edge Cases & Known Issues

## ffmpeg warning on every invocation

MarkItDown imports `pydub` which probes for `ffmpeg`/`avconv`. On OL9 without ffmpeg installed, this emits:

```
RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work
```

**Impact**: None for PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, XML, EPUB, images, ZIP, or YouTube URLs. Only affects WAV/MP3 audio transcription.

**Suppression**: Pipe stderr to `/dev/null`:

```bash
markitdown file.pdf 2>/dev/null
```

## Large documents

MarkItDown outputs to stdout. For large files (100+ page PDFs, complex PPTXs), the output can be tens of thousands of lines. **Pipe to a file**, then use `read_file` with offset/limit:

```bash
markitdown big-report.pdf 2>/dev/null > /tmp/report.md
read_file("/tmp/report.md", limit=200)
```

## Image description accuracy

MarkItDown extracts EXIF metadata and OCR text from images, but does NOT describe image content (it's not an LLM-based vision tool). For image content analysis, still use `vision_analyze` after converting.

## ZIP files

MarkItDown iterates over all files inside a ZIP and converts each individually. Large ZIPs with many files produce a concatenated Markdown output — check the result for completeness.

## Audio transcription

Audio conversion uses `speech_recognition` (Google Web Speech API by default). It requires an internet connection and may have usage limits. For production audio transcription, install ffmpeg and use the `[audio-transcription]` extras.

## Install failures

If `pip install 'markitdown[all]'` fails:
1. The Hermes venv may need `sudo` (owned by root)
2. Python must be ≥3.10 (Hermes venv = 3.11, OK)
3. On ARM64 (our OCI instance), all wheels compile correctly — no known platform issues
