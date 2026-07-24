---
name: youtube-content
description: Process, summarize, and extract information from YouTube videos. Covers metadata lookup, transcript extraction, and content analysis for wrestling analysis and general video research.
---

# YouTube Content Processing

Used by WWE and other profiles to process YouTube video links shared in conversation.

## Two-tier approach

### Tier 1 — Quick metadata (oembed, no auth needed)
Fastest path for getting title, author, thumbnail type. Use when the user just asks "what is this video about?"

```
yt-dlp --skip-download --print "%%(title)s\n%%(uploader)s\n%%(duration)s" "URL"
```

**Fallback when yt-dlp fails** (auth block, rate limit):
Use the YouTube oembed API — no cookies, no auth, works server-side:

```python
import urllib.request, json
oembed = 'https://www.youtube.com/oembed?url=' + url + '&format=json'
req = urllib.request.Request(oembed, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
# Keys: title, author_name, author_url, type, height, width, thumbnail_url, thumbnail_width, thumbnail_height
```

The oembed endpoint returns: title, author_name, author_url, type, height, width, thumbnail_url.

### Tier 2 — Full transcript + analysis (requires yt-dlp with cookies or fallback)
When the user wants a detailed summary, breakdown, or analysis of a specific video.

**yt-dlp approach (auth-gated):**
- Install: `pip install yt-dlp`
- Basic usage: `yt-dlp --skip-download --dump-json "URL"`
- Auth: YouTube may require `--cookies-from-browser` or manual cookie export.
- If blocked by Sign-in wall, fall back to alternative approaches.

**Alternative transcript approaches:**
- YouTube's internal captions API can sometimes be accessed without auth for public videos.
- SearXNG (via researchit profile) can find discussion/recaps of the video.
- Manual viewing is not possible server-side without a browser.

### Workflow for wrestling videos

1. Get metadata via oembed (fast, no auth).
2. If user asks for analysis and yt-dlp fails, explain the auth limitation and offer to:
   - Search for discussions/recaps about the video topic
   - Analyze the video from title + channel context
3. Record key takeaways in the profile bank (wwe-profile for wrestling content).

### Tier 3 — Web search fallback (when oembed is not enough but yt-dlp is blocked)

When the user asks for more depth (transcript, analysis, explanation) and all direct YouTube access is blocked on cloud IPs:

**Approach:** Use DuckDuckGo HTML search with the video title to find discussions, descriptions, and reviews of the video content.

```bash
curl -sL "https://html.duckduckgo.com/html/?q=<search-query>" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

Then extract result snippets with regex patterns:
- Pattern: `class="result__snippet">(.*?)</a>` or `class="result__snippet"[^>]*>(.*?)</(?:a|div)`
- Clean HTML tags and decode HTML entities with Python: `re.sub(r'<[^>]+>', '', text)` and `html.unescape()`

Search results often include:
- TikTok/Reddit posts discussing the video content
- Blog/article snippets that describe the video's thesis
- Forum discussions with context

Combine multiple search result snippets to reconstruct the video's content and thesis. This is NOT a transcript but gives enough context for a meaningful summary.

**Combined workflow when YouTube is blocked:**
1. `oembed` → title + channel (always works)
2. If user wants more depth → DuckDuckGo search with video title
3. Synthesize from search snippets → give user a contextual summary
4. Store learnings in the relevant profile bank (e.g. wwe-profile)

## What does NOT work on cloud IPs (OCI, AWS, GCP)

All of these WILL fail from cloud provider IPs — do not attempt unless the user provides auth:
- `yt-dlp` — always "Sign in to confirm you're not a bot"
- `youtube-transcript-api` — raises `RequestBlocked`
- Invidious instances — cloud IP blocks (all instances return empty/error)
- Direct YouTube page fetch returns only generic placeholder description

**Only two things work without auth from cloud IPs:**
1. oembed API (title + author only)
2. DuckDuckGo HTML search (indirect context via search snippets)

## Pitfalls

- yt-dlp WILL hit "Sign in to confirm you're not a bot" on YouTube without cookies. Do not retry — fall back to oembed immediately.
- youtube-transcript-api WILL raise `RequestBlocked` from cloud IPs. Do not attempt from OCI/AWS/GCP.
- The oembed API does NOT return video description, tags, or full metadata — just title, author, thumbnail.
- Do NOT attempt to use the YouTube Data API without first establishing a Composio connection for the YouTube toolkit.
- Python `yt-dlp` library is available after `pip install yt-dlp` but YouTube auth requirements apply there too.
- DuckDuckGo HTML search snippets are short (~200 chars) and may not capture the video's full argument. Synthesize carefully and caveat the user if the picture is incomplete.

## Verification

After getting metadata, confirm to the user: video title, channel name, brief contextual assessment based on title/channel.
