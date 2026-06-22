# Narrator Voice Protocol

This file governs how the Living Document is written. It is loaded every time the agent generates or updates Living Document prose. It references the narrator voice profile at `.agents/roles/narrator.md` for behavioral substrate (epistemology, style, lexical anchors, aversions).

**This file is 100% user-modifiable.** Its default contents are a starting point. Users can completely alter these constraints to design their own Living Document voice, cadence, and quality standards. The only invariant is that _some_ voice protocol exists; its content is entirely the user's choice.

---

## Step 1: Load Voice Profile

Load the narrator voice profile from `.agents/roles/narrator.md`.

If no narrator role exists, use baseline voice: clear, direct prose with no corporate language, no hedge patterns, and no decorative complexity. Explanations start from WHY before WHAT or HOW.

---

## Step 2: Apply Generation Constraints

When generating or updating the Living Document, all constraints below are active simultaneously:

### Structural Constraints

1. **WHY before WHAT before HOW.** Every explanation begins with the reason the thing exists, then describes what it is, then explains how it works. Never reverse this order.
2. **Concrete anchor before abstraction.** Introduce an analogy, a scenario, or a physical-world parallel before explaining an abstract mechanism. The reader should have something tangible to hold before the concept arrives.
3. **Chapter-based linear flow.** The document reads as a book, not a reference manual. Chapters are self-contained but build on each other. No random-access structure.
4. **Paragraph length: 3-5 sentences maximum.** Designed for narrow-screen readability (Kindle, mobile). Dense paragraphs are split.

### Voice Constraints

5. **Sentence cadence must alternate.** Short declarative sentences (assertions, conclusions) are followed by longer exploratory sentences (reasoning, context). Monotonous sentence length is a generation failure. If all sentences are within 3 words of the same length, regenerate with explicit variation.
6. **Every clause carries load.** No subordinate clauses exist for decoration. If a clause can be removed without losing meaning, it must be removed.
7. **Domain terms are introduced on first use.** The first time a domain-specific term appears, it is accompanied by a plain-language explanation. Subsequent uses can be bare.
8. **Address the reader as intelligent but uninformed.** Teach, do not lecture. Respect their reasoning capacity. Do not presume their domain knowledge. Avoid condescension. Avoid jargon walls.

### Anti-Slop Constraints

9. **Zero tolerance: Corporate-motivational copy.** The following patterns and their semantic equivalents are prohibited in Living Document prose: "Unlock," "Empower," "Seamless," "Leverage," "Cutting-edge," "Innovative," "Transform," "Elevate," "Harness," "Streamline." Any adjective that adds impressiveness without adding information is prohibited.
10. **Zero tolerance: RLHF hedge patterns.** Prohibited: "It's worth noting that," "It should be noted," "It's important to mention," "Cabe destacar que," "Es importante señalar," negative parallelisms ("not just X, but Y"), servile positivity ("Great question!"), false modesty ("I'll do my best to"), and sycophantic openers ("Certainly!", "Absolutely!", "Of course!").
11. **Zero tolerance: Em dashes.** The character U+2014 is prohibited in all Living Document prose.
12. **Zero tolerance: Filler openers.** Prohibited sentence openers: "In the world of," "When it comes to," "In today's landscape," "At the end of the day," "It goes without saying." These are statistical-probability artifacts, not human writing.

---

## Step 3: Verify Output

Before presenting generated or updated Living Document content:

1. Scan the output for every prohibited pattern in constraints 9-12. If any match is found, rewrite the offending passage without the pattern.
2. Measure sentence length variance across the output. If the standard deviation of word count per sentence is below 4, the cadence is too uniform. Regenerate affected paragraphs with explicit length variation.
3. Verify that every chapter or section begins with WHY (constraint 1). If a section opens with a WHAT or HOW statement, restructure.

---

## Step 4: Calibration Loop

The narrator voice improves over time through user feedback:

- **Silent acceptance:** User reads a section and says nothing. The voice is calibrated. No action needed.
- **Style correction:** User says the prose does not sound right, does not match their thinking, or uses a pattern they dislike. The specific complaint is added to the narrator role's Aversions table and, if applicable, a new constraint is added to this file.
- **Scope correction:** User asks to expand, simplify, deepen, or compress a section. The directive becomes a calibration data point for future content at similar scope.
- **Source enrichment:** User provides additional writing samples, transcripts, or examples of their own voice. The narrator role profile is re-extracted or enriched via `/create-role narrator`.

All calibration changes are applied directly to this file or to `.agents/roles/narrator.md`. No separate calibration log is maintained.
