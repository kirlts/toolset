---
name: security-report-triage
description: "Validate DAST/SAST security reports (ZAP, SonarQube, etc.) against source code: parse findings, verify against codebase, classify as false positive / accepted risk / true vulnerability."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [security, zap, dast, sast, vulnerability-triage, code-review, audit]
    related_skills: [requesting-code-review, dogfood]
---

# Security Report Triage

Evaluate external DAST/SAST security scan reports by verifying each finding against
the actual source code, infrastructure configuration, and documented design decisions.
Produces a clear classification: **False Positive** / **Accepted Risk** / **True Vulnerability**.

## When to Use

- User shares a security report (ZAP, SonarQube, Trivy, Dependency Check, Burp, etc.)
- A deployment gate requires security sign-off
- You need to separate actionable vulnerabilities from scanner noise

## Workflow

### Phase 1: Parse the Report

Most security scanners produce HTML. Parse systematically:

**ZAP HTML reports** have a nested `<section id="alerts">` structure:
- Each alert type has a `<li><h5><a href="#alert-type-N">...</a></h5>` entry in the main section
- The appendix (`<section id="appendix">`) has `<section class="alert-type" id="alert-type-N">` with the full description, solution, and references
- Each instance block has a `<details>` with URL, request/response, parameter, and other info

Write a Python script to extract structured data. Key fields per finding:
- Alert name and risk level
- URL and HTTP response code (critical: 503/403 means infrastructure blocked it)
- Parameter and attack payload used
- Alert description and solution text

**Response codes** tell a story:
- `200` with manipulated content → may be a real finding
- `403` → blocked by Nginx/WAF (mitigated at infrastructure level)
- `503` → blocked by rate limiting or Bot Shield
- `500` → server-side processing happened (needs investigation)
- `404` → endpoint or resource doesn't exist

### Phase 2: Classify Each Finding

Use this taxonomy:

| Classification | Meaning | What to do |
|---|---|---|
| **False Positive** | The code/infra already prevents this | Show evidence of mitigation |
| **Accepted Risk** | Deliberate architectural decision | Reference the documented trade-off |
| **True Vulnerability** | Confirmed and needs fixing | Provide remediation steps |
| **Informational** | Not a security issue per se | Explain what it is |

### Phase 3: Verify Against Source Code

For each alert type, follow the verification guide below.

#### SQL Injection

- Find how the targeted parameter is processed in the codebase
- Check for whitelist validation, parameterized queries, ORM usage
- Check if the HTTP response was 503/403 (infrastructure blocked it before it reached the app)
- **Common false positive pattern**: whitelist-validated parameters (e.g., `language` limited to `{"es", "en"}`) that the scanner tried to SQL-inject

#### Path Traversal

- Check if Nginx has a `location ~ \.\. { return 403; }` or similar block
- Verify the URL ZAP attacked — often it's a normal static file (CSS/JS) with a query parameter that the scanner misinterpreted
- Check if the app uses `send_from_directory` with proper path validation

#### CSP Issues

- CSP headers can be set in multiple layers: Nginx config, Flask middleware, or both
- Check Nginx `add_header Content-Security-Policy` directives in each `location` block
- Check Flask `@app.after_request` handlers that inject CSP with per-request nonces
- **Known patterns**:
  - `style-src 'unsafe-inline'`: usually a Bootstrap 4 requirement (documented trade-off)
  - Missing `frame-ancestors` / `form-action`: check if defined in a Flask-level CSP_TEMPLATE that not all endpoints receive
  - CSP header not present on JSON/AJAX endpoints: deliberate — CSP is typically HTML-only

#### SRI (Subresource Integrity)

- Check HTML templates for `<script>` and `<link>` tags loading from CDNs
- Resources with `integrity="sha384-..."` have SRI
- Resources without it are valid findings
- Common sources: fontawesome, marked.js, chart.js, specific jQuery versions

#### Vulnerable JavaScript Library

- Check the exact version loaded (e.g., `jquery/3.5.1/jquery.min.js`)
- Cross-reference against known CVEs
- Check if a newer version exists elsewhere in the project (version drift)
- The app may use jQuery 3.7.1 in one template but 3.5.1 in another

#### Cookie Security Flags

- Check Flask config for `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`
- Note: Secure flag only activates over HTTPS — local/QA scans over HTTP will not see it
- Check if the session interface is custom (e.g., `CustomRedisSessionInterface`) which may have its own cookie settings

#### HSTS

- Check Nginx config for `Strict-Transport-Security` in the `server` block
- Check individual `location` blocks — sometimes HSTS is set globally but not inherited by all sub-locations in certain Nginx configurations
- If HSTS is present on static files but missing on dynamic responses, Nginx may be overriding it

#### Cross-Domain JS

- CDN resources are cross-domain by design — this is an informational finding
- Check if CSP explicitly allows the CDN origins (via `script-src`)
- Low-severity unless the user/auditor mandates self-hosting

### Phase 4: Check the Two Layers

Security findings must be verified against both layers:

1. **Infrastructure layer** (Nginx, Docker, reverse proxy):
   - Nginx config blocks: `location ~ \.\.`, rate limiting, Bot Shield
   - Health check endpoints that may not serve the same headers
   - Static file serving with restricted CSP

2. **Application layer** (Flask, Python code):
   - Request parameter validation (whitelist vs sanitize vs pass-through)
   - CSP middleware with per-request nonces
   - Session cookie configuration
   - Template rendering context

A finding is a false positive if EITHER layer already handles it.

### Phase 5: Report

Structure the report by risk level (HIGH → MEDIUM → LOW → INFO):

```
## [Risk] Finding Name — CLASSIFICATION

**Evidence:**
- URL attacked: ...
- HTTP response: ...
- Parameter: ...
- What the code does: [reference to specific file:line]

**Veredicto:** False Positive / Accepted Risk / True Vulnerability
```

For true vulnerabilities, include the fix:
1. Which files to modify
2. What to change (specific code changes)
3. Verification step

## Pitfalls

- **Scanner trusts status codes** — ZAP sees 503 as "service may be broken" rather than "blocked by security control". Always check the actual response body.
- **QA vs production config** — HSTS and Secure cookies require HTTPS. If QA is HTTP-only, these will always show as findings.
- **Multiple CSP sources** — Flask and Nginx may both set CSP headers, and one can override the other. `Nginx add_header` with `always` may conflict with Flask `after_request` for the same header.
- **Version drift between microservices** — the main Flask app may use current libraries while the chatbot container uses outdated ones (jQuery 3.7.1 vs 3.5.1, Bootstrap 4.6.2 vs Bootstrap Table 1.12.1).
- **Static files get different headers** — Nginx serves static assets with its own CSP (usually `default-src 'none'`) while dynamic HTML gets Flask's CSP. Don't compare them.
- **Not all HTML responses get CSP** — error pages served directly by Nginx (403, 429, 50x) have their own CSP separate from Flask's middleware.

## Reference: ZAP Alert Types Commonly Seen

| Alert Type | Risk | Common Verdict |
|---|---|---|
| SQL Injection | High | Often FP when whitelist-validated or blocked by Nginx |
| Path Traversal | High | Often FP — ZAP scans cache-busting query params |
| CSP: no fallback | Medium | Check if directive is set in Flask-level CSP |
| CSP: unsafe-inline | Medium | Usually "accepted risk" for Bootstrap 4 |
| Missing CSP header | Medium | Check if endpoint returns HTML or JSON/API |
| Missing SRI | Medium | **Often True** — template oversight |
| Vulnerable JS lib | Medium | **Often True** — version drift or unmaintained dependency |
| Cookie missing Secure | Low | Usually FP when QA is HTTP-only |
| HSTS missing | Low | Usually FP when HSTS is set globally in Nginx |
| Cross-domain JS | Low | Accepted design — CDN usage with CSP allowlisting |
