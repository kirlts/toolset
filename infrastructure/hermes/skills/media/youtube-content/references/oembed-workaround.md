# YouTube oembed Workaround (session 2026-07-24)

## Context
During a WWE profile session, Martín sent a YouTube link (https://youtu.be/KlpmfS98VOA) asking what the video was about.

## Attempted approach (failed)
yt-dlp hit: `ERROR: [youtube] KlpmfS98VOA: Sign in to confirm you're not a bot.`
- `yt-dlp --skip-download --dump-json` failed.
- Raw YouTube page returned only generic description, no video-specific text.
- No browser available for `--cookies-from-browser`.

## Working approach
YouTube oembed API — no auth required, works from server-side:

```python
import urllib.request, json

url = 'https://youtu.be/KlpmfS98VOA'
oembed = 'https://www.youtube.com/oembed?url=' + url + '&format=json'
req = urllib.request.Request(oembed, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
```

## What it returned
- `title`: "Hay algo que NO CUADRA con Dominik Mysterio... | La teoría de Los Perros del Mal"
- `author_name`: "Noah Club"
- `type`: "video"

## What else failed (all blocked on OCI cloud IP)
- yt-dlp: always "Sign in to confirm you're not a bot"
- youtube-transcript-api: `RequestBlocked` (YouTube IP block)
- Invidious instances (inv.nadeko.net, yewtu.be, etc.): empty responses
- Direct YouTube page HTML: only generic placeholder, no video-specific data
- SearXNG (localhost:8888): not available in this session

## Deeper analysis — DuckDuckGo search fallback

When user wanted to know the video content (beyond just title), and all YouTube access was blocked:

```python
import urllib.request, re, html
from urllib.parse import quote

query = quote("Noah Club Dominik Mysterio Perros del Mal teoria youtube")
url = f"https://html.duckduckgo.com/html/?q={query}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=15)
html_content = resp.read().decode()

# Extract result snippets
results = re.findall(r'class="result__snippet">(.*?)</a>', html_content, re.DOTALL)
for r in results:
    clean = re.sub(r'<[^>]+>', '', r)
    clean = html.unescape(clean.strip())
```

**What search found:**
1. "¿Y si todo lo que está haciendo Dominik Mysterio tiene un propósito mucho más grande? Hay detalles que muchos han pasado por alto..."
2. TikTok clip description: "Dominik rescata al Grande Americano de los Perros del Mal"
3. Reference to Daga challenging Dominik Mysterio and El Grande Americano at Verano de Escandalo

**Resulting summary:** The video analyses a theory that Dominik's current character arc is part of a larger plan connected to Los Perros del Mal (AAA stable), involving El Grande Americano, with details fans missed suggesting a potential swerve or alliance.

## Key lesson
When YouTube blocks cloud IPs entirely, the ONLY two working approaches without auth are:
1. **oembed** — for title + channel (fast, always works)
2. **DuckDuckGo HTML search** — for contextual snippets about the video's content (not a transcript, but enough for a meaningful summary)

## Limitations
- No description, no tags, no captions, no duration from oembed.
- DuckDuckGo snippets are short (~200 chars) — synthesize multiple results.
- If the user needs a deep analysis, composio YouTube toolkit (OAuth) or a manual cookie export for yt-dlp is required.
