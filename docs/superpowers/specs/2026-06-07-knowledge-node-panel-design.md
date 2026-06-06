# Knowledge Node Panel Design

## Goal

Redesign the knowledge-node detail panel so a user can understand a knowledge point at a glance:

- What this point is.
- Where the user currently stands.
- Why the app reached that judgment.
- What is blocking progress.
- What the user should do next.

The panel should feel like a tutor diagnosis, not a generic encyclopedia entry or dashboard.

## Approved Direction

Use the "diagnosis first" direction.

The compact state leads with a short personalized judgment, then shows six balanced cards:

1. Already know
2. Stuck point
3. Evidence
4. Next step
5. Related
6. Source

The expanded state keeps the existing card-based evidence experience and places it after the diagnosis header. Existing semantic fragment cards should remain part of the experience rather than being replaced by plain text.

## Compact State

The compact panel should answer three questions in the first viewport:

- Where am I now?
- Why is that the judgment?
- What should I do next?

Recommended structure:

- Header: node type, title, source count, mastery/status indicator.
- Diagnosis statement: one tutor-like sentence describing the user's current state.
- Six-card grid:
  - Already know: strongest current capability.
  - Stuck point: the highest-value weakness or misconception.
  - Evidence: count and preview of supporting turns or source records.
  - Next step: one concrete action.
  - Related: prerequisite, neighboring, or follow-up concepts.
  - Source: chat, document, or note provenance.
- Action row:
  - Practice now
  - Ask why
  - Review evidence

The compact state should avoid long paragraphs, raw logs, or too many metrics. Percentages can appear, but should not be the main explanation.

## Expanded State

The expanded panel should preserve context while offering deeper review.

Recommended structure:

- Diagnosis header remains visible near the top.
- Semantic evidence card deck remains the main proof surface.
- Report sections follow the card deck:
  - Learning status
  - Evidence
  - Misconceptions or weak prerequisites
  - Next-step strategy
  - Related nodes
  - Source materials

The expanded state should keep card affordances for evidence and relationship browsing. It should not flatten the existing card interaction into a plain report.

## Information Priority

Most important information for a knowledge point:

1. Personalized diagnosis
2. Current mastery stage
3. Evidence behind the judgment
4. Weakness or misconception
5. Next recommended action
6. Relationship to other nodes
7. Source provenance
8. Definition or formula

Definitions and formulas are useful but should not lead the panel unless the node has no user-specific evidence yet.

## Data Behavior

The panel should degrade gracefully:

- If evidence exists, show a diagnosis backed by evidence.
- If evidence is thin, say confidence is low and ask for a next action.
- If the node came from source material only, show it as a candidate or source-backed node.
- If the node came from light chat fallback, map `chatMessageIds` back into the existing evidence card system so cards remain available.

No node type should need a special one-off detail layout unless it has genuinely different data, such as source diagnostics.

## Visual Principles

- Compact, tutor-like, and decisive.
- Cards should have clear purposes, not decorative repetition.
- The first screen should have one dominant diagnosis statement.
- Use warm warning styling for weak points and calmer green styling for confirmed strengths.
- Relationship and source cards should be secondary, not competing with the diagnosis.
- Keep mobile density high enough for scanning, but avoid eight-card dashboards in the first screen.

## Non-Goals

- Do not redesign the whole graph view.
- Do not remove or replace the existing semantic fragment card deck.
- Do not change update-source behavior.
- Do not introduce new graph node types just to support this panel design.
- Do not publish or change release metadata as part of this work.

## Implementation Boundaries

Implementation should be limited to the graph detail panel rendering and the data shaping that feeds it.

Any fix for fallback chat nodes should preserve the existing detail/card system by adapting data into the expected structure, not by replacing the panel with a new specialized layout.

## Validation

Minimum validation before shipping:

- Existing graph detail card tests continue to pass.
- Chat fallback nodes still open a detail panel.
- Existing semantic fragment cards are still present when related message IDs exist.
- Compact panel works on mobile viewport without text overlap.
- Update popup behavior remains unchanged from the current test fix.
