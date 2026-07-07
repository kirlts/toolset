---
name: fitness-visual-reference
description: "Search, select, and deliver exercise demonstration images. Diagram/illustration style, high resolution with legible text, one image per message. Options: YouTube link for complex exercises."
version: 1.0.0
platforms: [linux]
---

# Fitness Visual Reference

## When to use

When the user asks how an exercise looks, how to perform a movement, or requests images of a specific technique. Used by the Entrenador profile for workout routines.

## Image Style Preference

The user prefers **diagram/illustration style** over photo-realistic images for exercise demonstrations. The reference is the Kyodashi Gyaku Tsuki illustration — clean lines, clear labeling, easy to understand at a glance.

## Workflow

### 1. Identify the exercise
Parse the exercise name from the user's request. For non-English names, localized terms, or phonetic variations (e.g. "Yakosuki" = Gyaku Tsuki), search the web first to identify the correct technique before searching for images.

### 2. Search for images
Use COMPOSIO_SEARCH_IMAGE via COMPOSIO_MULTI_EXECUTE_TOOL. Query variations to try:
- English + "diagram", "illustration", "form guide", "technique"
- Spanish + "diagrama", "ilustracion", "tecnica", "ejecucion"
- "poster", "instructional", "step by step"
- High resolution keywords: "HD", "high resolution", "poster"

Use num=5-10 to get enough options.

### 3. Select the best image
Criteria (in priority order):
1. **Style**: Diagram/illustration over photo-realistic
2. **Resolution**: ≥1000px on longest side (verify height/width from results)
3. **Text legibility**: Clear labels and annotations, readable font sizes
4. **Clarity**: Shows the movement clearly, not cluttered

### 4. Download
Use terminal + curl to download the selected image to a working directory:
```bash
curl -sL "<URL>" -o /tmp/workout-imgs/<name>.jpg
```

### 5. Deliver
Send via `MEDIA:/absolute/path/to/file` **one image per message**. Sending multiple MEDIA: in the same response can cause some to fail delivery.

### 6. Add brief technical description
Include 2-4 bullet points about key execution cues:
- Grip/stance width
- Body position
- Movement path
- Breathing
- Common mistakes to avoid

### 7. Complex exercises
If the exercise has multiple phases, common mistakes, or nuanced technique, include a YouTube link to a short demonstration video (3-10 min).

## Pitfalls

| Pitfall | Solution |
|---|---|
| Multiple images in one message | Send ONE MEDIA: per response. Batch images across multiple assistant turns. |
| Images too small / text illegible | Filter for ≥1000px. Avoid images under 500px. |
| Photo-realistic instead of diagram | Explicitly include "diagram", "illustration", "infographic" in search queries. |
| Facebook/Shutterstock lookaside URLs | Skip `lookaside.fbsbx.com` and Shutterstock preview URLs — they either break or require auth. |
| Exercise name is a local variant | Web-search first to map to standard name before image search. |

## Examples

| User says | Search query | Style |
|---|---|---|
| "Cómo se hace press banca" | "press banca diagrama ilustracion tecnica ejecucion" | Diagrama |
| "Yakosuki de karate" | "gyaku tsuki karate reverse punch technique diagram" | Diagrama/Ilustración |
| "Cómo se ve una sentadilla" | "squat form guide diagram infographic" | Infographic |

## Delivery notes

- WhatsApp compresses images sent as `image` type. To preserve quality, the user can tap the HD icon in WhatsApp.
- Images sent as `document` type preserve original quality but appear as file attachments (inline preview may vary).
- If sending a YouTube link, use a short video (3-10 min) focused on technique.
