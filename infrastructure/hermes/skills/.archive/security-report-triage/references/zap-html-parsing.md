# ZAP HTML Report Parsing Cheatsheet

ZAP 2.17.0 HTML reports have a predictable structure. Extract data with Python's `re` module.

## Structure

```
<section id="alerts">
  <li id="alerts--risk-3-confidence-2">      ← Risk 3=High, Confidence 2=Medium
    <h3><span>Risk</span>=<span class="risk-level">High</span>...</h3>
    <li class="alerts--site-li">
      <h5><a href="#alert-type-0">Inyección SQL</a> <span>(1)</span></h5>
      <li><details>
        <summary><span class="request-method-n-url">GET https://...</span></summary>
        <table class="alerts-table">
          <tr><th>Alert description</th><td><p>...</p></td></tr>
          <tr><th>Other info</th><td><p>evidence...</p></td></tr>
          <tr><th>Parameter</th><td><pre><code>param_name</code></pre></td></tr>
          <tr><th>Solution</th><td><p>...</p></td></tr>
```

## Python extraction pattern

```python
import re

with open('report.html') as f:
    content = f.read()

# Find each alert instance in the main section
alerts_start = content.find('<section id="alerts"')
appendix_start = content.find('<section id="appendix"')
main = content[alerts_start:appendix_start]

pattern = r'<li>\s*<h5>\s*<a\s+href="#alert-type-(\d+)">([^<]+)</a>\s*<span>\(?(\d+)\)?'
for m in re.finditer(pattern, main):
    aid, aname, acount = m.groups()
    
    # Risk level is in the parent <h3> — walk backwards
    before = main[:m.start()]
    risk = re.findall(r'Risk</span>=<span[^>]*>([^<]+)', before)
    risk = risk[-1] if risk else '?'
    
    # Details follow the match
    detail = main[m.end():m.end()+2500]
    
    url = re.search(r'summary>\s*<span[^>]*>\s*([^<]+)', detail)
    resp = re.search(r'HTTP/1\.\d+\s+(\d+)', detail)
    param = re.search(r'Parameter</th>\s*<td>\s*<pre><code>([^<]+)', detail)
    evid = re.search(r'Other info</th>\s*<td>(.*?)</td>', detail, re.DOTALL)
    
    # Solution is in the appendix section
    appendix = content[appendix_start:]
    app_section = re.search(
        r'<section class="alert-type" id="alert-type-' + aid + r'">(.*?)</section>',
        appendix, re.DOTALL
    )
    if app_section:
        sol = re.search(r'Solution</th>\s*<td>\s*<p>(.*?)</p>', app_section.group(1), re.DOTALL)
```

## Risk-to-Number Mapping

| Risk Level | Number |
|---|---|
| High (Alto) | 3 |
| Medium (Medio) | 2 |
| Low (Bajo) | 1 |
| Informational (Informativo) | 0 |

## Confidence-to-Number Mapping

| Confidence | Number |
|---|---|
| Confirmed by User | 4 |
| High (Alta) | 3 |
| Medium (Media) | 2 |
| Low (Baja) | 1 |
| False Positive | 0 |

## Common Response Code Interpretation

- **503**: Nginx rate limiting / Bot Shield blocked the request — the app never saw it
- **403**: Nginx access control blocked it (path traversal, bad bot)
- **200**: Request reached the app — investigate what the app returned
- **500**: App processed it but crashed — potential finding
- **404**: Resource doesn't exist (robots.txt, etc.)
