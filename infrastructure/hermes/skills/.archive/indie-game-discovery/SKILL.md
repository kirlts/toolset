---
name: indie-game-discovery
description: Research and recommend indie games from itch.io, especially short horror and PSX-N64 retro titles. Extract real user reviews and ratings from game pages. Present balanced recommendations with pros and cons backed by user data.
---

# Indie Game Discovery (itch.io focus)

Trigger: user asks for indie game recommendations, especially horror/short/retro games they can play on itch.io. Also triggers when user wants to discover games similar to known titles or from specific YouTubers (Manlybadasshero, Alpha Beta Gamer, etc.).

## Research Workflow

### 1. Search for the itch.io game page

Search engines (Brave Search, DuckDuckGo HTML) can index itch.io pages even when direct browsing is blocked:

```
site:itch.io "game name" horror
```

Access the game page URL directly (e.g., `https://username.itch.io/game-name`). itch.io renders server-side HTML that includes:
- Title, developer, description
- Rating (e.g., "Rated 4.1 out of 5 stars")
- Tags (PSX, Psychological Horror, Short, etc.)
- User comments/reviews (visible in the HTML)
- Download info, price, platform support

### 2. Extract key data

From the game page HTML, extract:
- **Rating** — the numerical score
- **Tags** — genre, style, platform support
- **Description** — what the game is about
- **User reviews** — actual comments from players (both positive and negative)
- **Playtime** — if listed (e.g., "Average 20 minutes")
- **Languages** — look for Spanish/Spanish Latin America support
- **Price** — free vs name your own price vs paid

### 3. Search for Reddit discussions via Composio

Use the Composio Reddit integration (the user has Reddit connected via Composio). Do NOT try to scrape Reddit via terminal/curl — it blocks OCI IPs.

Search Reddit using `REDDIT_SEARCH_ACROSS_SUBREDDITS` with the game name as `search_query`:
- Search both exact title and relevant subreddits (r/HorrorGaming, r/itchio, r/gaming)
- Use `restrict_sr: false` for broad search
- Sort by `top` or `relevance`
- Limit to 15-25 results

For posts with comments, use `REDDIT_RETRIEVE_POST_COMMENTS` with the post's base-36 `article` ID to read discussion.

**Critical honesty rule:** If Reddit returns only promotional gameplay videos (0 comments) or irrelevant results, DO NOT fabricate or force a narrative. State clearly: "Este juego no tiene tracción en Reddit. Es muy nicho." The itch.io page comments are a better signal for small games.

Note: The OCI VM IP cannot access Reddit directly via terminal — always use Composio Reddit tools.

## Sources for Short Indie Horror Games

| Source | URL Pattern | Notes |
|---|---|---|
| itch.io Horror + Short | `itch.io/games/tag-horror/tag-short` | Primary source. Filter by top-rated, newest, or free |
| itch.io Horror + PSX | `itch.io/games/tag-horror/tag-psx` | Retro PSX/N64 aesthetic games |
| itch.io Horror + PSX + Short | `itch.io/games/tag-horror/tag-psx/tag-short` | Narrowest filter |
| itch.io Horror + controller | `itch.io/games/tag-horror/input-playstation` | Games with controller support |
| itch.io collections | `itch.io/c/COLLECTION_ID` | User-curated collections (e.g., Manlybadasshero's played games) |
| Sidequest | `sidequest.zone` | Curated lists of short free horror games |
| Game Jolt | `gamejolt.com` | Alternative indie game platform |
| RPG Maker forums | `rpgmaker.net` | Freeware RPG Maker horror scene |

## How to Access itch.io Pages

itch.io requires JavaScript for its main app, but individual game pages render server-side HTML. Direct curl with a modern User-Agent works:

```bash
curl -sL "https://username.itch.io/game-name" \
  -H "User-Agent: Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  -H "Accept: text/html"
```

Then strip scripts/styles and extract visible text with Python.

For itch.io search, use:
```bash
curl -sL "https://itch.io/search?q=game+name"
```
Then extract game URLs from `developer.itch.io/game-name` patterns using regex: `https://[a-z0-9-]+\.itch\.io/[a-z0-9-]+`

## Language & Price Filtering

When user specifies filters, check game pages carefully:

### Price
- **"100% gratis"** includes Name Your Own Price (NYOP / PWYC) where user can pay $0. itch.io lists these as "Name your own price" with no minimum.
- Paid games ($3.99+) are NOT gratis even if cheap.
- Check the page HTML for `minimum_price` or `name your own price` indicators.

### Language
- Look for language tags on itch.io page: Spanish (Castilian) or Spanish (Latin America).
- Keywords in HTML: `Spanish; Castilian`, `Spanish; Latin America`, `español`, `latino`.
- Many PSX horror games are English-only. Late Pizza Delivery is a notable exception with full Spanish support.

### Filter priority
When user gives multiple filters (e.g., "itch.io + gratis + español + PSX + corto"):
1. Check if the game is on itch.io ✓
2. Check price: free or NYOP ($0) ✓
3. Check language tags for Spanish ✓
4. Check tags for PSX/N64 retro aesthetic ✓
5. Check playtime or tags for "Short" ✓

## Situation-First Approach

When user says "quiero jugar algo esta noche" (or similar), do NOT jump to recommendations. Instead:

1. **Ask** about: solo/en pareja, tiempo disponible, plataforma (PC/tele con mando), estado de ánimo, gustos/referencias
2. **Search** itch.io tags that match (PSX, horror, short, controller support)
3. **Check game pages** directly — rating, user reviews, price, language, playtime
4. **Search Reddit** via Composio for community opinions
5. **Present** 3-6 options max with specific pros/cons backed by user data and ratings

This pattern was validated 4-Jul-2026 with Late Pizza Delivery vs Last Kid on the Bus for a couple (21+25) wanting a PSX horror game on TV with controller, 30-60 min, gratis, en español.

## User Preference: Balanced Recommendations

**NEVER hype every option equally.** This user explicitly complained about "descripciones de mierda" and "puras flores" — being too positive about everything makes recommendations useless.

### Do:
- Present a shortlist (3-6 games max, ideally)
- For each game, give **specific pros AND cons** backed by data
- Include real user reviews (copy actual quotes when possible)
- Mention technical issues (broken AI, bugs, compatibility problems)
- Include the actual rating and what it means
- Make a clear recommendation with reasoning

### Don't:
- Say everything is "great" or "fantastic"
- Describe every game positively without differentiation
- Give only your own opinion without user data
- Overwhelm with too many options and no verdict

## Gaming History & Preferences (Chat Profile)

This section logs gaming sessions and emerging preferences discovered through conversation. New data gets appended here and retained to the `chat-profile` bank.

### Session: 2026-07-05

Con amigos. Jugaron en secuencia:
1. **Late Pizza Delivery** (itch.io, PSX horror, pizza delivery). Entretenido pero historia floja. Confirmación práctica de que el rating 4.1/5 es razonable — no esconder las debilidades de un juego.
2. **Open House / Virtual Open House** — juego de terror de inmobiliaria, casa 3D interactiva, imágenes con anomalías, twist demoníaco. Les gustó más que Late Pizza Delivery por **sistema de gameplay innovador**.
3. Se aburrieron del terror. Buscaron **juegos basados en Chile**.
4. Encontraron uno de **gestión de recursos**: construir hospitales, colegios, hidroeléctricas, etc. Contexto chileno. Les gustó.

### Emerging Patterns

- **Grupo**: juega en compañía (amigos/pareja), no solo.
- **Tolerancia al terror**: alta pero con saturación rápida. Alternar géneros en una misma sesión.
- **Qué pesa más**: innovación en gameplay > historia. Una mecánica novedosa puede salvar un juego con historia regular.
- **Interés local**: juegos ambientados en Chile o con contexto chileno tienen alta prioridad. No solo terror — el de gestión de recursos chileno les gustó.
- **Formato**: sesiones exploratorias, no planeadas. Saltan de juego en juego según interés del momento.

### How to Use This Data

When recommending games in future sessions:
1. Prioritize games with **unique mechanics** over narrative-heavy experiences
2. Include **Chile-themed/location games** as a category even if user didn't ask
3. Offer **genre variety** — don't double down on horror if they just played 2 horror games
4. Consider **co-op/same-screen multiplayer** or games that work well watching together

## Pitfalls

- Search engines (Brave, DuckDuckGo, Google) and Reddit may rate-limit OCI VM IPs quickly. Spread searches across engines, and prioritize direct page access when URLs are known.
- Itch.io pages with JS-required features won't render via curl. Stick to game pages (server-rendered) and avoid the main feed which needs JS.
- Not all games list playtime. Infer from tags (Short) or user comments.
- "PSX-style" games often have controller support but verify via tags (input-playstation, input-xbox, input-generic).
- Many itch.io games are Windows-only. Check before recommending if the user is on another OS.
- Some games made in 1 week or for game jams may have broken mechanics — always check user reviews for this.
