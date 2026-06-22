# Convergence Blacklist (CBL)

Statistical inertia values of LLMs when generating interfaces. Matching these values requires explicit atmospheric justification.

| ID | Axis | Inertia Value | Appearance Context | Required Deviation |
|---|---|---|---|---|
| CBL-01 | Primary Color | `#6366F1` (indigo-500), `#8B5CF6` (purple-500) | Buttons, links, primary accents | Derive custom palette in OKLCH with consistent luminance between background-text pairs |
| CBL-02 | Hero Gradient | `#8B5CF6→#3B82F6` (purple→blue) via `bg-clip-text` | Hero headings, main section backgrounds | Gradient derived from the project's atmosphere. If the gradient does not serve the identity, do not use it |
| CBL-03 | Emergent Green | `#10B981` (emerald-500) as post-purple accent | Success badges, status indicators, secondary CTAs | Color derived from the project's chromatic identity |
| CBL-04 | Dark Surface | `#09090B` / `#18181B` (zinc-950/900) | Dark mode backgrounds, navbars, footers | Surface derived with intentional tone and luminance |
| CBL-05 | Universal Font | Inter, system-ui, sans-serif as sole family. 48px/800/tracking-tight on H1 | All site typography, with no typographic variation | ≥1 font with character. Modulated scale (Golden Ratio, Minor Third, Perfect Fourth). `clamp()` for fluidity |
| CBL-06 | Symmetrical Layout | `max-w-7xl mx-auto`, symmetrical `grid-cols-3`, universal `text-center items-center` | General structure of the entire page, sections, grids | ≥1 asymmetrical or fluid-width composition. Real routing if ≥2 thematic contexts |
| CBL-07 | Uniform Space | Indiscriminate `p-6`/`gap-4`/`gap-6`. Macro:micro ratio <3:1 | Spacing between components, card padding, grid gaps | Macro:micro ratio ≥4:1. Intentional variation in spacing |
| CBL-08 | Generic Surface | `rounded-xl` + `border-gray-200` + `shadow-md` on everything. Identical cards | Cards, containers, modals, dropdowns | Radii, shadows, and borders differentiated by affordance level |
| CBL-09 | Uniform Movement | Universal `transition-all duration-300 ease-in-out`. Fade-in-up without stagger | All animations and transitions | Selective transitions by property. Varied duration and easing. Sequential stagger |
| CBL-10 | Corporate Copy | "Get Started", "Learn More", "Unlock your potential", "Seamless experience", "Cutting-edge" | CTAs, taglines, feature descriptions, onboarding | CTAs describing the domain's concrete action. Niche jargon copy. 0 fictitious testimonials |
