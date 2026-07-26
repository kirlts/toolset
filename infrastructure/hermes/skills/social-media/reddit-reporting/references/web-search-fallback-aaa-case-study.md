# Web Search Fallback — AAA Weekly Report Case Study

**Date**: 2026-07-25
**Context**: Composio Reddit connection was inactive (OAuth expired). Cron mode prevented interactive re-auth. Used workbench `web_search()` as fallback.

## The Problem

COMPOSIO_SEARCH_TOOLS returned: `"No Active connection for toolkit=reddit"`. COMPOSIO_MANAGE_CONNECTIONS returned an OAuth link that expires in 10 minutes — unusable in cron mode.

## The Solution

8 parallel `web_search()` calls in COMPOSIO_REMOTE_WORKBENCH using the built-in Exa AI search:

```python
# Search strategy — layered queries for comprehensive coverage
r1, e1 = web_search("AAA Lucha Libre results July 19-25 2026 full show results")
r2, e2 = web_search("SquaredCircle AAA discussion July 2026")
r3, e3 = web_search("AAA Verano de Escandalo July 25 2026 results winners")
r4, e4 = web_search("AAA Lucha Libre Dominik Mysterio July 2026 reactions SquaredCircle")
r5, e5 = web_search("AAA Lucha Libre El Grande Americano storyline July 2026")
r6, e6 = web_search("Lola Vice AAA NXT champion July 2026")
r7, e7 = web_search("AAA Triplemania 34 2026 date card lineup")
r8, e8 = web_search("Chad Gable AAA Lucha Libre July 2026 Kurt Angle")
```

## What Web Search Returned

Exa AI returned condensed summaries from indexed sources that included:

| Info Type | Quality vs Direct Reddit |
|-----------|------------------------|
| Match results | Excellent — showed full results with winners, finishers, context |
| Storyline developments | Good — summarized ongoing feuds, alliances, betrayals |
| Community sentiment | Fair — captured broad sentiment (positive/negative/mixed) but no specific upvote counts |
| Specific fan reactions | Poor — no verbatim comment quotes or author names |
| Crossover/WWE connections | Excellent — cross-promotional relationships well indexed |
| Upcoming cards | Excellent — full scheduled matches with participants |

## Fallback Caveats

- No access to individual Reddit comment text or upvote scores
- Community sentiment is a paraphrase, not raw data — hedge appropriately ("la mayoría dice" not "el top comment con 500 ups dice")
- Search may miss niche subreddit discussion (SCJerk, Wrasslin meme threads)
- Timeframes are approximate — web search may return older content mixed with new
- Always filter/select based on date relevance in the summary text

## When Fallback is Sufficient vs When You Need Direct Reddit

| Scenario | Fallback OK? |
|----------|-------------|
| Weekly recap with match results | Yes |
| Storyline tracking | Yes |
| General community mood | Yes (with hedging) |
| Specific quote from a comment thread | No — need direct Reddit |
| Numerical analysis (upvote ratios, comment counts) | No — need direct Reddit |
| On-demand "what is Reddit saying" with personal message | Partial — works for Part A (summary), weak for Part B (specific quotes to share) |

## Query Design Tips

1. Use the promotion/event name + date range in every query
2. Include "SquaredCircle" or the subreddit name to bias toward Reddit-indexed content
3. Search wrestler-specific queries for storyline updates
4. Add "results winners" to get match outcomes in search results
5. Search cross-promotional angles specifically ("AAA NXT crossover", "Lola Vice WWE")
6. For upcoming events, add "date card lineup" to get full match cards
