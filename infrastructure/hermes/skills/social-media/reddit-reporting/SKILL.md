---
name: reddit-reporting
description: "Use when generating scheduled reports from Reddit subreddits via Composio Reddit tools (REDDIT_GET_R_TOP, REDDIT_SEARCH_ACROSS_SUBREDDITS, REDDIT_RETRIEVE_POST_COMMENTS). Covers fetching posts, computing engagement, extracting top comments, and producing either a single-page PDF (fpdf2) or a text summary for group chat delivery."
version: 1.2.0
author: Hermes Agent (user-local)
license: MIT
metadata:
  hermes:
    tags: [reddit, composio, pdf, reporting, cron, social-media]
    related_skills: [nano-pdf, ocr-and-documents]
---

## Reference Files

- `references/cm-punk-sami-zayn-community-analysis.md` — Case study: live community sentiment analysis for a major WWE title change, including Reddit threads, comment extraction, personal message crafting, and full session flow.

## Version History

v1.1.0 — Initial version. Added scheduled report patterns, PDF generation, and text summary delivery.

Generate scheduled reports from Reddit subreddits by fetching posts via Composio Reddit tools, computing engagement scores (score * num_comments), extracting top comments, and producing either:

- **PDF output**: Compact single-page PDF (landscape or portrait) with fpdf2 — for file delivery (email, cron artifact)
- **Text summary output**: Formatted text for group chat delivery (WhatsApp, Discord, Telegram, Slack) — non-PDF, delivered as the final response

The workflow is designed for cron jobs: fully autonomous, no user interaction needed.

## When to Use

- Cron job that needs to deliver a daily Reddit digest (as PDF or text summary)
- Scheduled monitoring of specific subreddits (r/chile, r/chileit, r/SquaredCircle, etc.)
- Generating weekly themed summaries (wrestling promotion recaps, event discussion roundups, community sentiment reports)
- Any task that fetches Reddit posts + comments and produces a static report
- **On-demand community sentiment analysis**: When a group member asks "what is Reddit saying about [event/wrestler/storyline]" — fetch fresh posts and comments, extract sentiment/themes, and respond conversationally in the group's language/tone
- **Personal message for another group member**: When the requesting user asks "do you have any message for [other member]" — synthesize community sentiment into a direct, empathetic message addressed to that person
- **Don't use for**: one-off Reddit lookups (use search tools directly), interactive Reddit browsing, posting/commenting on Reddit

## Prerequisites

- Composio Reddit connection active (verify via COMPOSIO_SEARCH_TOOLS)
- For PDF output only: fpdf2 installed (`pip install fpdf2`) + DejaVuSans fonts on host (`/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf`)
- For text summary output: no extra dependencies
- For cron: the session has no user — plan for zero-interaction execution

## Composio Reddit Tool Access

Session management: always pass `session_id` for workflow grouping. Create a fresh one per report run:
```
session_id = "moon"  # or any short unique string
```

### REDDIT_GET_R_TOP
Fetches top posts from a subreddit by time filter.

```
Parameters: subreddit (required), t ("day"/"week"/"month"/"year"/"all"), limit (1-100)
Response path: data.data.children[].data
Key fields: id, title, author, score, num_comments, permalink, url, created_utc
```

**Critical**: The response nests at `response.data.data.children` (double `data`), NOT `response.data.children`. Always flatten:
```python
data_node = file_data['results'][i]['response']['data']
children = data_node['data']['children']  # double .data
```

### REDDIT_RETRIEVE_POST_COMMENTS
Fetches all comments for a post by article ID.

```
Parameters: article (base-36 ID, without 't3_' prefix)
Response shape: {post_listing: {...}, comments_listing: {data: {children: [...]}}}
Comments: kind=="t1", body field at data.body, nested replies at data.replies
```

Comment extraction pattern:
```
import re

def is_image_only(body):
    """True if body is just an image/gif markdown or bare URL."""
    stripped = body.strip()
    if re.match(r'^!\[.*?\]\(.*?\)$', stripped):
        return True
    if re.match(r'^https?://\S+\.(png|jpg|jpeg|gif|webp)(\?\S*)?$', stripped, re.I):
        return True
    return False

def sanitize_body(body):
    """Prepare comment body for PDF: flatten newlines, strip gif refs."""
    body = re.sub(r'!\[.*?\]\(.*?\)', '', body)
    body = re.sub(r'https?://\S+\.(png|jpg|jpeg|gif|webp)(\?\S*)?', '', body, flags=re.I)
    body = re.sub(r'\s+', ' ', body).strip()
    return body

def extract_comments(result_data, min_body_length=3):
    cl = result_data.get("comments_listing", {})
    children = cl.get("data", {}).get("children", [])
    def walk(items, depth=0):
        results = []
        for item in items or []:
            if isinstance(item, dict) and item.get("kind") == "t1":
                d = item.get("data", {})
                body = d.get("body", "")
                author = d.get("author", "[deleted]")
                score = d.get("score", 0)
                clean = sanitize_body(body)
                if (clean
                    and clean not in ("[deleted]", "[removed]")
                    and not is_image_only(body)
                    and len(clean) >= min_body_length):
                    results.append({"body": clean, "author": author, "score": score})
                replies = d.get("replies")
                if isinstance(replies, dict):
                    sub = walk(replies.get("data", {}).get("children", []), depth+1)
                    results.extend(sub)
        return results
    return walk(children)
```

### REDDIT_SEARCH_ACROSS_SUBREDDITS
Searches Reddit for posts matching a query, scoped to a subreddit. Use instead of REDDIT_GET_R_TOP when you need **topic-specific** posts (e.g., live discussion threads for a specific promotion, posts about a particular wrestler/event) rather than generic top posts.

```
Parameters: search_query (required), restrict_sr (bool), sort ("relevance"/"new"/"top"/"hot"/"comments"), limit (1-100)
Response path: data.posts[] (top-level array, NOT nested under data.data.children)
Key fields: id, title, author, score, num_comments, permalink, url, created_utc, selftext, subreddit
```

Scoping to a subreddit: use `subreddit:` operator in the query — e.g., `search_query: "subreddit:SquaredCircle AAA"` finds posts about AAA in r/SquaredCircle. Set `restrict_sr: true` to confine to subreddits.

**Critical differences from GET_R_TOP**:
- Response `posts` array is at the top level of `data`, NOT under `data.data.children`
- No native time-range filter — filter by `created_utc` (Unix epoch, UTC) client-side
- Sort `new` gives chronological order; `relevance` finds thematic matches
- Supports `after` pagination cursor

**Strategy for topic-specific weekly reports** (e.g., AAA summary):
1. Search with `sort=new` and `limit=25` to find the week's discussion threads
2. Filter client-side by `created_utc >= cutoff` (7 days ago in epoch seconds)
3. Also search complementary queries (`"Lola Vice"`, `"Psycho Clown"`, etc.) for missed content
4. Check cross-promotional content: search WWE/NXT subreddits or general threads for your topic appearing on other shows

## Workflow Steps

### 1. Fetch Posts

**Option A — Top posts (general coverage)**: Call COMPOSIO_MULTI_EXECUTE_TOOL with one REDDIT_GET_R_TOP per subreddit. Batch them in a single call for parallelism. Use `t="day"` and `limit=10`.

**Option B — Topic-specific (themed report)**: Call COMPOSIO_MULTI_EXECUTE_TOOL with one REDDIT_SEARCH_ACROSS_SUBREDDITS per query. Use `sort=new` and `limit=25`. Then filter client-side by `created_utc >= cutoff` (7 days ago). For themed reports (e.g., a wrestling promotion), also search complementary queries — the promotion's stars, storylines, and cross-promotional appearances on other shows.

**Important**: Set `sync_response_to_workbench=true` on the MULTI_EXECUTE_TOOL call. Without it, the full response is truncated inline and unavailable for workbench processing. With it, the complete JSON lands at `/mnt/files/mex/rich.json` for workbench parsing.

```
multi_execute(tools=[
  {tool_slug: "REDDIT_GET_R_TOP", arguments: {subreddit: "chile", t: "day", limit: 10}},
  {tool_slug: "REDDIT_GET_R_TOP", arguments: {subreddit: "chileit", t: "day", limit: 10}},
  ...
])
```

### 2. Compute Engagement

Define engagement as `score * num_comments`. Sort posts by engagement descending per subreddit. Select top 3 per subreddit for comment fetching.

### 3. Fetch Top Comments

Call COMPOSIO_MULTI_EXECUTE_TOOL with one REDDIT_RETRIEVE_POST_COMMENTS per selected post. Up to 9 parallel calls (3 subreddits x 3 posts).

### 4. Build Report Text

Collapse into a compact format:
- Subreddit header, then for each post: `+score | comments | author | title`
- Top 2 comments per post as: `>> [+score] author: "body"` (truncate to 120 chars)

### 5. Generate PDF

Two layout options exist — choose based on content volume:

**Landscape (L)** — use for 10+ posts across 4+ subreddits, or when comment bodies are long (~60 lines capacity):
```python
pdf = FPDF(orientation='L', unit='mm', format='A4')
pdf.set_left_margin(10)
pdf.set_right_margin(10)
pdf.set_top_margin(8)
```

**Portrait (P)** — use for 3-4 subreddits with 3 posts each and short comments (~50 lines capacity). Disable auto_page_break and manage space manually:
```python
pdf = FPDF(orientation='P', unit='mm', format='A4')
pdf.set_auto_page_break(auto=False, margin=8)
pdf.set_left_margin(10)
pdf.set_right_margin(10)
```

Font sizing for portrait with tight spacing:
- Title: Bold 14-15pt
- Section headers (r/...): Bold 10-11pt
- Post lines: 7.5pt title, 6.5pt metadata
- Comments: 6pt quote header, 5.5-6pt body
- Separator lines: light gray at 50% opacity
- Footer: 5.5-6pt

Font sizing for landscape:
- Title: Bold 12-14pt
- Section headers (r/...): Bold 8-9pt
- Post lines: 5.5-6pt
- Comments: 5-5.5pt
- Footer: 5.5pt, gray

Continuous layout — no page break checks needed if content fits one page. Trim content to fit (shorten titles to 60-80 chars, drop lowest-engagement posts if needed).

Unicode/encoding: Strip or replace emoji characters and unusual Unicode. ASCII-safe text via `.encode('ascii', 'replace').decode('ascii')` as last resort. The DejaVuSans font supports basic Latin + Spanish accented chars (a, e, i, o, u with acute, n with tilde, inverted punctuation) but NOT emoji or specialized symbols. In fpdf2 v2.5.x, the `uni=True` parameter on `add_font()` is deprecated; omit it.

**Comment body sanitization for PDF**: Before adding comment bodies to the PDF, always:
  - Flatten `\n` and `\r` to spaces (comment bodies can be multi-line)
  - Strip markdown image references: `![...](...)`  
  - Strip bare image URLs ending in png/jpg/gif/webp
  - Collapse consecutive whitespace
  - Truncate to ~120 chars for compact layout
  - Skip comments whose cleaned body is empty, `< 3 chars`, or is only `[deleted]`/`[removed]`

### Two-Phase Pattern (Cron)

In cron mode, `execute_code` is blocked. Use this two-phase approach:

**Phase 1 - COMPOSIO_REMOTE_WORKBENCH**: Fetch posts (via COMPOSIO_MULTI_EXECUTE_TOOL), then in the workbench parse the saved JSON and extract post metadata + top comments. Save a compact JSON report file to the sandbox (`/mnt/files/report_data.json`). Print a summary of the extracted data to stdout for debugging.

**Phase 2 - Terminal heredoc OR write_file+run**: Use `terminal` to generate the PDF. Two approaches:

*Approach A - Heredoc (for compact scripts ~30 lines)*:
```
terminal(command="python3 << 'PYEOF'\\n...\\nPYEOF")
```

*Approach B - write_file + terminal (for complex scripts 40+ lines)*:
```
write_file(path="/tmp/gen_report.py", content="...")
terminal(command="python3 /tmp/gen_report.py")
```

Approach B is preferred when the PDF generation logic is involved (multi-section layout, font registration, conditional page breaks) because it avoids shell escaping issues and allows linting before execution. Remember to add `add_font('D', 'B', ...)` without the deprecated `uni=True` parameter in fpdf2 v2.5+.

Run `ls -la /tmp/reddit-chile-report-YYYY-MM-DD.pdf` and `file /tmp/reddit-chile-report-YYYY-MM-DD.pdf` to verify the output is a valid PDF before delivering.

### 6. Output

#### PDF Output

For cron delivery (file artifact): the final response is a single `MEDIA:/path/to/pdf` line.

#### Text Summary Output (group chat delivery)

For delivery to WhatsApp, Discord, Telegram, or Slack groups — the final response IS the summary itself. No `MEDIA:` prefix, no file path. Format considerations:

- **Language/localization**: Match the group's language. The user or group description often specifies it (e.g., Chilean Spanish, Mexican Spanish). When specified, use local dialect, slang, and tone appropriate for the group.
- **Structure**: Lead with the key results/developments, then community reactions, then theories/speculation. Use bullet points for match results. Keep it conversational and engaging.
- **Length**: WhatsApp groups prefer conciseness — aim for 1500-3000 chars. Trim low-engagement posts if needed.
- **Cross-promotional content**: When reporting on a promotion, include relevant crossovers on other shows (e.g., AAA championships defended on WWE SmackDown).

For cron jobs: the text summary IS your final tool response. The system delivers it automatically.

## On-Demand Community Sentiment Analysis (Live Mode)

When a group member asks for live community reactions (e.g., "what is Reddit saying about [event/wrestler]?"), use this workflow instead of the scheduled report pattern. This mode prioritizes conversational tone, empathy, and group-specific language over structured PDF output.

### Trigger Signals

- "Que dice la comunidad" / "qué está diciendo Reddit" / "busca en Reddit"
- "Que opina la gente" / "cómo reaccionaron"
- Explicit request to check community reaction to a specific event
- Follow-up request after a day has passed: "ya pasó un día, qué dice la comunidad ahora?"

### Workflow Steps

#### 1. Map the Event

Identify what the user is referring to:
- The specific show/episode (Raw, SmackDown, PLE)
- The wrestlers involved (who vs who)
- The outcome (who won, title change, return, debut, injury)
- How long ago it happened (live vs "a day later")

Use session_search or bank recall to retrieve context if needed.

#### 2. Fetch Fresh Reddit Data

Use COMPOSIO_SEARCH_TOOLS to plan the search, then COMPOSIO_MULTI_EXECUTE_TOOL with parallel calls. **CRITICAL**: run BOTH of these in a single multi-execute call — they are complements, not alternatives. Keyword-only search misses spoiler-tagged event threads (see Pitfall #12). The top-post sweep catches those; the keyword search catches specific discussion threads.

**Option A — Top posts from relevant subreddits** (general pulse):
```
REDDIT_GET_R_TOP (subreddit="SquaredCircle", t="day", limit=25)
REDDIT_GET_R_TOP (subreddit="WWE", t="day", limit=25)
REDDIT_GET_R_TOP (subreddit="Wrasslin", t="day", limit=10)
```

**Option B — Targeted search** (specific event/wrestler):
```
REDDIT_SEARCH_ACROSS_SUBREDDITS (search_query="CM Punk Sami Zayn title change", sort="new", limit=25)
REDDIT_SEARCH_ACROSS_SUBREDDITS (search_query="Sami Zayn reaction WWE Championship", sort="top", limit=25)
```

Set `sync_response_to_workbench=true` so the full JSON lands at `/mnt/files/mex/...json` for parsing.

#### 3. Parse and Identify Top Threads

In COMPOSIO_REMOTE_WORKBENCH, load the saved JSON and extract posts filtered by `created_utc >= (now - 86400)`. Score posts by relevance (keywords matching the event/wrestlers in title+selftext) and engagement (score × num_comments). Identify 3-5 top posts.

Key posts to look for:
- Main event result thread (usually highest engagement)
- Conspiracy/theory threads about booking decisions
- "Spoiler" or backstage update threads
- Post-show promo/video reaction threads
- Meme/jerk subreddit takes (SCJerk, Wrasslin — often the funniest)

#### 4. Fetch Comments from Top Threads

Call COMPOSIO_MULTI_EXECUTE_TOOL with REDDIT_RETRIEVE_POST_COMMENTS for each selected post's article ID (base-36, without `t3_` prefix). Up to 5 parallel calls.

#### 5. Extract Sentiment Themes

In COMPOSIO_REMOTE_WORKBENCH, parse comments from all threads. Extract:

- **Top comments by score** (highest upvoted)
- **Recurring sentiment categories** (sympathy for loser, hype for winner, anger at booking, conspiracy theories, memes)
- **The tone of the majority** (is the subreddit happy, angry, conflicted, laughing?)
- **Standout quotes** — memorable or funny comments that capture the room

Record the raw score and author for each notable comment.

#### 6. Craft Community Report + Personal Message

The response has TWO parts:

**Part A — Community Sentiment Summary**
Use the group's specified tone/language (e.g., Chilean Spanish, Mexican Spanish, English). Structure:
- Overall feeling ("la mayoría está pal lado de Sami")
- Key threads and their scores
- Comment highlights with score and paraphrase
- Conspiracy theories / booking speculation
- Meme/jerk takes for flavor

**Part B — Personal Message for Other Group Member** (if requested)
When the user asks "do you have a message for [someone]" or "what should I tell [person]":
- Synthesize the community sentiment into an empathetic, direct message
- Address the person by name
- Acknowledge how they feel (if they're sad/upset about a result)
- Share a specific comment or insight from Reddit showing they're not alone
- Include a hopeful/optimistic note if the community consensus supports it
- Keep it personal and warm, not analytical
- DO NOT frame as "Hermes says" — frame as the community talking

Example response structure for Javi:
```
Pa la Javi: Decile que no está sola — Reddit entero está con ella. El top comment es "Poor Sami" con 638 ups. Un weon dijo: "Esto debería llevar a que gane de nuevo." El consuelo real: a Sami lo están tratando como main eventer, no como chiste.
```

#### 7. Retain to Bank

Store the conversation's community report to the profile bank. Include:
- What was discussed
- The community sentiment consensus
- Any new preferences about wrestlers or booking learned from the user
- That personal messages were delivered

### Delayed Follow-Up Pattern ("A Day Later")

When the user returns ~24 hours after an event and asks for an update:
1. Fetch fresh Reddit data (same search queries but 24h later)
2. Compare with previous session's sentiment — has opinion shifted?
3. Key patterns to watch for:
   - Analysis/hot takes replacing raw emotional reactions
   - New backstage news or spoilers emerging
   - Meme evolution (new templates, running jokes)
   - Long-term booking speculation gaining traction
4. Highlight the *evolution* in sentiment, not just new posts
5. For the personal message: reinforce the previous message if sentiment is still supportive, or update it if the wind has shifted

### Language & Tone for Group Chat Delivery

- **Group language**: Use the group's specified dialect and slang (Chilean: "po", "weon", "cachai", "eri", "jsjsj"; Mexican: "wey", "no mames"; neutral Spanish; English).
- **Voice**: Conversational, not report-like. No headers or bullet structures. Weave community reactions naturally.
- **Length**: 1500-3000 chars for the community part, 200-500 chars for the personal message.
- **Humor**: Include the funny/crazy takes from the jerk subreddits or meme posts.
- **Empathy**: If the community is sympathetic to the loser, lean into that. If they're celebrating, match that energy.
- **Certainty**: Use hedging where appropriate ("la mayoría", "varios weones", "un comentario dijo") — don't present Reddit as a monolith.

### On-Demand vs Scheduled: Key Differences

| Aspect | Scheduled Report | Live Sentiment Analysis |
|--------|-----------------|------------------------|
| Trigger | Cron job | User message |
| Output | PDF or text summary | Conversational response |
| Audience | Read-only | Active group members |
| Personal message? | No | Yes (if requested) |
| Language | Neutral | Group-specific dialect |
| Structure | Headers, bullets, data | Flowing conversation |
| Comment depth | Top 2-3 per post | Top 10-15 across all posts |
| Follow-up | Next cron tick | "A day later" pattern |

## Common Pitfalls

1. **Double-nested data path (GET_R_TOP).** REDDIT_GET_R_TOP puts children under `response.data.data.children`, not `response.data.children`. Always verify with a debug print before assuming path.

2. **Top-level posts array (SEARCH).** REDDIT_SEARCH_ACROSS_SUBREDDITS returns posts at `data.posts[]` (top-level array), NOT under `data.data.children`. These are full post objects, not kind/data wrapped children — access title, score, etc. directly.

3. **execute_code blocked in cron.** Use `terminal` with heredoc (`python3 << 'PYEOF' ... PYEOF`) instead — `execute_code` requires user approval in cron mode.

4. **Large comment threads.** Some posts have 150+ comments. Always truncate at the extraction level (keep top 5, pick top 2). Never try to render all comments.

5. **Polymorphic `replies` field.** Can be empty string, null, or a listing dict. Always type-check with `isinstance(replies, dict)` before recursing.

6. **PDF overflows.** If the text doesn't fit one page, either: (a) compact the text (shorter titles, fewer posts per subreddit), (b) use smaller fonts (down to 5pt), or (c) accept 2 pages. Landscape A4 at 5-6pt fits ~55-60 lines.

7. **Unicode in PDF.** DejaVuSans does not render emoji, exotic Unicode, or most symbols. Strip them before adding to PDF cell. The `replace` error handler in `.encode('ascii', 'replace')` converts unknown chars to `?`.

8. **Composio session ID.** Always pass the same `session_id` through all COMPOSIO_* calls in a workflow. Generate fresh for each report run.

9. **URLs in titles.** Some post titles contain URLs or gif references. Strip markdown/image syntax before rendering.

10. **Comment bodies with newlines and image-only content.** Reddit comment bodies are multi-line text with embedded `\n` — always flatten to single space for PDF cells. Many comments are image/gif-only (`![gif](...)`, bare `.png` URLs) and must be filtered at extraction time with `is_image_only()` + `sanitize_body()` (see Commment extraction pattern above). A comment whose cleaned body is `< 3 chars` is a gif/emoji-only post, skip it.

11. **Two-phase cron pattern.** In cron mode, do NOT try to do everything in one tool. Phase 1: COMPOSIO_MULTI_EXECUTE_TOOL to fetch posts + COMPOSIO_REMOTE_WORKBENCH to parse/save report JSON. Phase 2: `terminal` with Python heredoc to read the report dict and generate the PDF. This avoids `execute_code` being blocked and keeps each phase under the 3-minute workbench limit.

12. **Spoiler-tagged posts invisible to keyword search (event communities).** Subreddits like r/SquaredCircle, r/NBA, r/movies, and other event-focused communities use spoiler tags or generic titles for result threads: `[RAW SPOILERS] Main Event Result`, `[Post Game Thread] Final Score`, `Official Discussion Megathread`. These titles DON'T contain wrestler/player/movie names, so REDDIT_SEARCH_ACROSS_SUBREDDITS with `search_query=\"CM Punk\"` or `search_query=\"LeBron James\"` returns ZERO results for the most important threads. **Fix**: always run REDDIT_GET_R_TOP (subreddit-wide scope, `t=\"day\"` or `t=\"week\"`) in parallel with keyword searches. The spoiler-tagged threads show up by engagement, not by keyword matching. For sports/wrestling/event sentiment analysis, this is mandatory — never rely on keyword search alone.

## Verification Checklist

- [ ] All subreddits/queries fetched successfully (check `success_count`)
- [ ] Engagement scores computed correctly (if using GET_R_TOP)
- [ ] Top 3 posts per subreddit have comments fetched
- [ ] Comments properly extracted: no `[deleted]`, no gif/image-only bodies, newlines flattened
- [ ] For PDF: generates as single landscape page, verified with `file /tmp/report.pdf`
- [ ] For text summary: formatted for group chat delivery, appropriate length and language
- [ ] Cron delivery format: PDF = `MEDIA:/path/to/pdf` | Text summary = the summary text itself (no prefix)
