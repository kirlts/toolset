---
name: pubmed-literature-search
description: "Search PubMed/MEDLINE via NCBI E-utilities for clinical evidence and biomedical literature — supplements, drugs, conditions, treatments. Quick, structured lookups via curl + Python XML/JSON parsing."
version: 1.0.0
author: Hermes Agent / Toolset Personal
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [research, pubmed, ncbi, clinical-trials, evidence-based, biomedical]
    related_skills: [arxiv, researchit, ocr-and-documents]
---

# PubMed Literature Search (NCBI E-utilities)

Search clinical and biomedical literature via the NCBI E-utilities API — free, no key needed, stable since 2005.

## When to use

- User asks about **supplements, drugs, herbs, adaptogens, nootropics, treatments** and you need clinical evidence
- User asks about **health conditions, diseases, interventions** and you need RCTs or systematic reviews
- User asks about **mechanisms of action** (how does X work in the body?)
- Any time the answer should be **evidence-based, not just model knowledge**

## Architecture

| Endpoint | Function | Output |
|----------|----------|--------|
| `esearch.fcgi` | Find papers by query | JSON: paper IDs, count, translated query |
| `esummary.fcgi` | Get paper metadata (title, authors, journal, year) | JSON per paper |
| `efetch.fcgi` | Get full abstracts | XML (best for structured parsing) |

## Quick Reference

### 1. Search for papers

```bash
# Option A: JSON output (for counting, IDs)
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=QUERY&retmax=10&retmode=json"

# Option B: XML output (for abstract parsing)
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=QUERY&retmax=5&retmode=xml"
```

### 2. Get paper metadata (titles, authors, dates)

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=ID1,ID2,ID3&retmode=json"
```

### 3. Get full abstracts (XML → parse with Python)

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=ID1&retmode=xml&rettype=abstract"
```

## Proven Parsing Pattern

Use this Python script to extract labeled abstract sections (BACKGROUND, METHODS, RESULTS, CONCLUSIONS) from NCBI XML:

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=PAPER_ID&retmode=xml&rettype=abstract" | python3 -c "
import sys, xml.etree.ElementTree as ET
data = sys.stdin.read()
root = ET.fromstring(data)
for a in root.iter('AbstractText'): 
    label = a.get('Label', '')
    txt = ''.join(a.itertext())
    if label: print(f'{label}: {txt[:500]}')
    else: print(txt[:500])
"
```

## Query Tuning

### Translate your question into PubMed fields

PubMed automatically maps common terms to MeSH but you can be explicit:

| Prefix | Searches | Example |
|--------|----------|---------|
| bare text | All fields (auto-mapped via MeSH) | `cordyceps antifatigue` |
| `[All Fields]` | Explicit all-fields | `adaptogenic[All Fields]` |
| `[MeSH Terms]` | Medical Subject Headings | `cordyceps[MeSH Terms]` |
| `[Publication Type]` | Filter by article type | `randomized controlled trial[Publication Type]` |

### Add study type filters

```bash
# Randomized controlled trials only
term=cordyceps+antifatigue+AND+randomized+controlled+trial[Publication+Type]

# Systematic reviews / meta-analyses
term=cordyceps+AND+systematic+review[Publication+Type]

# Humans only (use MeSH)
term=cordyceps+AND+humans[MeSH+Terms]
```

### Common study type terms for `[Publication Type]`

- `randomized controlled trial`
- `systematic review`
- `meta-analysis`
- `clinical trial`
- `observational study`
- `review`
- `journal article` (catches most original research)

### Narrow with MeSH subheadings

```bash
# Cordyceps AND therapeutic use
term=cordyceps[MeSH]+AND+therapeutic+use[MeSH+Subheading]

# Cordyceps AND pharmacology
term=cordyceps[MeSH]+AND+pharmacology[MeSH+Subheading]
```

## Two-Stage Workflow

**Stage 1 — Discover count + IDs:**
```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=YOUR_QUERY&retmax=5&retmode=json"
```
Check `esearchresult.count` — if 0, broaden the query. Check `querytranslation` to verify how PubMed interpreted your terms.

**Stage 2 — Get details on the best hits:**
```bash
# Stage 2a — Metadata
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=ID1,ID2&retmode=json"

# Stage 2b — Abstracts (for the most relevant papers)
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=ID1&retmode=xml&rettype=abstract" | python3 -c "..." 
```

## Pitfalls

- **Empty results**: Check `translationset` in esearch JSON output to see how PubMed interpreted your query. The `warninglist` field shows terms that were ignored.
- **Too many results**: Add `&mindate=2020&maxdate=2026&datetype=pdat` or filter by publication type.
- **Wrong results**: Your terms may be mapping to unexpected MeSH terms. Check `querytranslation` in esearch output — it shows the exact PubMed query executed.
- **Pipe to python3 flagged as "HIGH"**: Security scanner flags curl|python3. The auto-approval mechanism handles known safe sources (eutils.ncbi.nlm.nih.gov) — don't worry, but use `curl -s` (silent) and pipe only to stdlib python, never `bash` or arbitrary interpreters.
- **Rate limiting**: ~3 req/sec without API key, ~10 req/sec with API key. For batch work, add `sleep 0.5` between calls.
- **PMID vs PMC ID**: esearch returns PubMed IDs (PMID). For open-access full text, prepend "PMC" to the PMCID from esummary output and use `efetch?db=pmc` instead of `db=pubmed`.
- **XML namespaces**: The Atom XML responses (like arXiv) use namespaces. efetch XML for PubMed does NOT use namespaces for AbstractText elements — direct `root.iter('AbstractText')` works.
- **Non-English titles**: PubMed indexes non-English papers. The `lang` field in esummary tells you the language before you bother parsing the abstract.
- **Withdrawn/retracted papers**: Check for "withdrawn" or "retracted" in the abstract or the `pubstatus` field. Always mention if a paper was withdrawn.
- **No search_date**: Unlike `standard-research`, don't hard-filter by date — clinical evidence from decades ago is still valid. Only date-filter for rapidly evolving topics (new drugs, COVID treatments, etc.).

## Related Skills

- `arxiv` — For CS/physics/math papers (arXiv XML API)
- `researchit` — For deep-dive reports (SearXNG → scrape → Typst PDF)
- `ocr-and-documents` — For local PDF processing
- `standard-research` — For verifying technical recommendations are current
