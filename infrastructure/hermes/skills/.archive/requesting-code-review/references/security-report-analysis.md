# Security Report Analysis (ZAP / DAST)

Workflow for reviewing external DAST/SAST security reports (OWASP ZAP, SonarQube, etc.) and verifying findings against the actual codebase.

## When to Use

When a security audit report arrives and you need to classify each finding before the user acts on it. Typical triggers:
- UAT/QA handoff requires security sign-off
- Third-party pen test report
- CI pipeline generated a ZAP/SonarQube scan
- "El técnico envió un reporte de seguridad"

## Workflow

### Phase 1: Parse the Report

ZAP HTML reports contain findings in nested `<li>` / `<details>` blocks. Extract systematically:

```python
# Extract alert types from the summary table
# Pattern: <a href="#alert-type-N">NAME</a>
# Each alert has: risk level, count, URL, HTTP status, description, evidence, solution

# Key fields to extract per finding:
# - Risk (Alto/Medio/Bajo/Informativo)
# - Alert name
# - URL that was tested
# - HTTP response code received
# - Parameter tested
# - Evidence (what ZAP saw)
# - Solution (ZAP's recommendation)
```

### Phase 2: Classify Each Finding

Three categories:

**FALSE POSITIVE** — The architecture already handles this:
- The code has explicit validation/whitelisting (e.g., language param restricted to {"es","en"})
- Nginx reverse proxy blocks the vector before it reaches the app (e.g., location ~ \.\. { return 403; })
- The "vulnerability" is by design and documented (e.g., Bootstrap 4 requires unsafe-inline styles)
- The endpoint tested returns non-HTML (JSON API) — CSP headers intentionally don't apply
- HTTPS-only features work in production but the QA environment uses HTTP

**TRUE VULNERABILITY** — Needs fixing:
- Missing security headers on responses that should have them
- Outdated libraries with known CVEs (check the actual version loaded)
- Missing SRI integrity attributes on CDN resources
- Code patterns that actually pass user input to dangerous functions

**INFORMATIVE** — ZAP noise:
- "Modern Web Application" detection
- "Suspicious comments" (HTML comments)
- Session/cookie identification
- Cache-control directives

### Phase 3: Verify Against Codebase

For each finding:

1. **Find the relevant code** — search the codebase for the parameter, endpoint, or feature
2. **Read the actual implementation** — does the code validate/sanitize/escape?
3. **Check the reverse proxy config** — Nginx/Caddy rules may block the vector
4. **Check the app config** — Flask/Django settings for cookies, CSP, HSTS
5. **Check the template files** — HTML for actual CDN URLs, SRI attributes, jQuery version

### Phase 4: Report

Structure the response clearly:

```
**HIGH / MEDIUM / LOW / INFO**

Vulnerability Name (Risk) — VEREDICT

Evidence from report:
  URL tested
  HTTP status received
  Parameter/vector used

Code verification:
  What the code actually does
  Why it's safe (or why it's not)

Action: None needed / Fix by [specific change]
```

## Common False Positive Patterns in Flask+Nginx Stacks

| ZAP Finding | Why False Positive |
|---|---|
| SQL Injection on `language` param | Whitelist-validated in get_locale(); invalid values ignored. Nginx may block with 503 before reaching app. |
| Path Traversal on static files | Nginx blocks `../` at server level. ZAP targeted a normal CSS file with cache-busting param. |
| CSP missing directives | Flask injects CSP via after_request with per-request nonces. Static files get CSP from Nginx. |
| CSP style-src unsafe-inline | Bootstrap 4 requires it. Documented and accepted. script-src uses nonces, not unsafe-inline. |
| Cookie without Secure flag | Config has SESSION_COOKIE_SECURE=True. Works in HTTPS; QA environment may lack HTTPS. |
| HSTS not configured | Configured globally in nginx.conf per server block, not per location. |
