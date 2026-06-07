# Tiered Graph Node Sheet Design

## Goal

Redesign the mobile graph node bottom sheet and expanded detail page so each node type is presented according to what it actually represents.

The graph should keep representing learning relationships. The sheet should explain the selected node's current role:

- A learned knowledge point should show the user's learning state and next action.
- A source-backed candidate or structure node should show why it appeared and how it can enter learning.
- A source or note node should show context, coverage, and linked learning nodes.

This design extends the approved diagnosis-first panel direction from `2026-06-07-knowledge-node-panel-design.md`. It does not replace the existing semantic evidence card system.

## Clarification: Tiers Are Presentation Templates

`L1`, `L2`, and `L3` are presentation maturity templates, not graph hierarchy levels.

They must not be interpreted as:

- main node / child node / grandchild node,
- subject / chapter / section,
- parent / sibling / child relation,
- or a backend taxonomy.

The real graph relationship is still carried by semantic edges: prerequisite, follow-up, same family, easily confused, source support, outline, diagnostic, note reference, and learning sequence.

Implementation should use existing relation data first. If a fine-grained semantic subtype such as `prerequisite` or `easily confused` is not available in current data, the UI must not invent that subtype as stored data. It can only group and label relations that are present or reasonably derived from existing relation fields.

Example:

```text
Analytic geometry --contains/domain--> Conic sections
Conic sections --contains/type--> Ellipse
Ellipse --same family--> Hyperbola
Ellipse --same family--> Parabola
Ellipse --prerequisite--> Distance formula
Ellipse --follow-up--> Standard equation of ellipse
```

These are graph relations. They do not imply that `Analytic geometry` uses the L1 page and `Ellipse` uses the L2 page. If `Ellipse` has learning evidence, it uses the learning-state template. If `Conic sections` is only extracted from a source and has no learning judgment yet, it uses the candidate/structure template.

## Existing Node Types

The current graph node types remain:

- `kp`: a knowledge point that has entered the learning judgment flow.
- `latent`: a candidate knowledge point extracted from source material or conversation but not yet confirmed as a learned point.
- `section`: a source outline or section node.
- `diagnostic`: a source-analysis diagnostic node.
- `source`: a source material node.
- `note`: a user note or chat-linked note node.

No new node type is required for this design.

## Presentation Templates

### L1: Learning-State Template

Applies to `kp` in the current implementation.

This template answers three questions in the first viewport:

```text
What did I tap?
How am I currently doing?
What should I do next?
```

It should feel like a tutor's current learning-state card, not an encyclopedia card.

#### Compact Bottom Sheet

The compact sheet should use roughly 40%-50% of the mobile viewport where possible.

Structure:

- Node type label: for example, `Knowledge point`.
- Title: the node title, for example, `Derivative definition`.
- Light path: derived from existing source, session, section, or relation context. Do not persist a subject taxonomy just for this path.
- Status and mastery: a natural label plus percentage when available.
- Progress indicator: visual support for mastery, not the main explanation.
- One diagnosis sentence.
- One main stuck point.
- Primary action and secondary action.
- A visible detail affordance: `View details` or an up affordance.

The diagnosis sentence should follow this shape when evidence allows:

```text
You can already do A, but you are still stuck on B.
```

Example:

```text
You can connect derivatives with speed, but you still mix up average rate of change and instantaneous rate of change.
```

The compact sheet must not show:

- full evidence lists,
- full definitions or formulas,
- all related nodes,
- all prerequisites and follow-ups,
- full learning history,
- or raw source logs.

#### Knowledge Point States

The sheet should adapt to these natural states:

- Not started: explain why the point matters and show prerequisite entry points. Do not show a stuck point.
- Newly touched: show weak evidence and encourage one focused question or starter exercise.
- Unstable understanding: show diagnosis, one main stuck point, and corrective action.
- Basically mastered: show proof of mastery, next learning direction, and review action.
- Fluent: show maintenance, transfer, and advanced follow-up.

The exact user-facing labels should follow the app's existing Chinese product copy. English labels in this spec are requirement names, not final UI copy.

The labels can be derived from current mastery helpers. A likely mapping is:

- no evidence and no mastery: `Not started` or `Needs observation`,
- low mastery with evidence: `Newly touched`,
- mid mastery or misconception evidence: `Unstable understanding`,
- high mastery: `Basically mastered` or `Fluent`.

#### Expanded Detail Page

The expanded page for `kp` should answer:

```text
What is this point?
Where is my understanding now?
Why am I stuck?
What evidence supports the judgment?
What should I do next?
```

Recommended modules:

1. Current judgment
2. What you already know
3. Main stuck point
4. Why this is hard
5. Evidence and basis
6. Next step
7. Related nodes

Existing semantic evidence cards remain in the detail page. They should sit inside or near the evidence/basis section, not be deleted or flattened into plain text.

### L2: Candidate, Structure, And Diagnostic Template

Applies to `latent`, `section`, and `diagnostic`.

These nodes are not yet full learning-state nodes. The UI should not pretend that the user has a mastery percentage for them unless existing data proves it.

#### Compact Bottom Sheet

The compact sheet should answer:

```text
Why did this node appear?
Where did it come from?
Can it enter my learning path?
What can I do with it now?
```

For `latent`:

- Identity: candidate knowledge point.
- Source: source material, chat context, or extracted topic.
- Reason: why the app thinks it may matter.
- Learning state: not yet diagnosed or not yet connected to a learning judgment.
- Actions: ask about it, connect it through a learning question, open source.

For `section`:

- Identity: source section or outline node.
- Source name and section label.
- Preview or summary.
- Extracted or related learning nodes.
- Actions: open source, inspect related nodes, ask from this section.

For `diagnostic`:

- Identity: source diagnostic node.
- Diagnostic status: blocked, needs visual model, incomplete extraction, or analyzed.
- Reason for diagnostic appearance.
- Recovery action: reopen source, reprocess when possible, ask about available text.

#### Expanded Detail Page

The expanded page should show:

- Identity and source context.
- Why this node appeared.
- Source preview or section excerpt.
- Analysis/extraction state.
- Related or connectable learning nodes.
- Relation groups.
- Available actions.

It should not lead with mastery, stuck point, or "what you already know" unless the node has been promoted into or linked to a real `kp`.

### L3: Context Source Template

Applies to `source` and `note`.

These nodes provide context. They are not learning-state nodes.

#### Compact Bottom Sheet

The compact sheet should answer:

```text
What context is this?
What does it cover?
What learning nodes came from or link back to it?
Where can I open it?
```

For `source`:

- Identity: source material.
- Source type and source name.
- Coverage: extracted sections, candidate topics, linked knowledge points, or diagnostics.
- Recent or strongest linked node.
- Actions: open source, view extracted nodes, ask from source.

For `note`:

- Identity: note or chat note.
- Note title or short body preview.
- Linked knowledge point, source, or chat turn.
- Actions: return to chat, open related source, inspect linked node.

#### Expanded Detail Page

The expanded page should show:

- Origin and source metadata.
- Source or note preview.
- Linked knowledge nodes.
- Extracted sections or candidates.
- Recent references.
- Actions to open source, return to chat, or focus related nodes.

It should not show a mastery score or stuck point unless those belong to a linked `kp`.

## Relation Display Rules

The graph should not hide logical neighbors just to keep the UI visually small. The number of relations should come from actual relation logic, not from an arbitrary neighbor cap.

The UI may group and prioritize relations without deleting them:

- prerequisite / foundation,
- follow-up / next learning,
- same family,
- easily confused,
- source support,
- source outline,
- diagnostic,
- note reference,
- learning sequence,
- general related.

Compact sheets can show one or two representative relation chips. Expanded details should show grouped relation chips or lists and allow jumping to related nodes.

## Light Path Rules

The light path in the compact sheet is a navigation hint, not a stored academic category.

Allowed sources:

- existing source name,
- existing source section label,
- session title,
- node type,
- direct semantic relations,
- source outline relation,
- current focus graph center.

Fallback examples:

```text
Knowledge point / Current session
Source / Imported material
Candidate / Source extraction
Note / Chat note
```

Do not add new backend fields such as subject, textbook chapter, school stage, or curriculum path just to render this path.

## Data Derivation

The implementation should use current graph data and helpers:

- `node.nodeType`,
- `graphNodeTitle(node)`,
- `graphNodeTypeLabel(node)`,
- `graphNodeRelations(node)`,
- `graphNodeSourceTargets(node)`,
- mastery level and existing evaluation fields for `kp`,
- source fields such as `sourceName`, `sourceType`, `preview`, `content`, `sourceDiagnostics`,
- `memoryExpansion`,
- `chatMessageIds`, `messageId`, and semantic fragment helpers,
- existing digest evidence, errors, and next steps.

No schema migration is part of this design.

## Actions

Actions should adapt by template:

- `kp`: practice, ask about the stuck point, review evidence, view details.
- `latent`: ask about this concept, connect to learning, open source.
- `section`: open source, ask from this section, view extracted nodes.
- `diagnostic`: open source, inspect diagnostic, retry/reprocess only if such action already exists.
- `source`: open source, view extracted nodes, ask from source.
- `note`: return to chat, open related source, focus linked node.

Actions must use existing app capabilities. Do not add nonfunctional buttons that imply unavailable backend behavior.

## Non-Goals

- Do not redesign the whole graph canvas.
- Do not introduce a subject/chapter backend taxonomy.
- Do not create extra backend data only to make the UI look organized.
- Do not cap one-hop graph relations for visual convenience.
- Do not publish or change release metadata.
- Do not change update-source behavior.
- Do not remove the existing semantic evidence card system.
- Do not create a dedicated heavy detail UI for light chat nodes unless existing data justifies it.

## Validation

Minimum validation for implementation:

- Existing graph panel tests should be updated from the uniform six-card compact panel to the tiered template behavior.
- `kp` compact sheet shows learning-state content and state-specific actions.
- `kp` expanded detail includes the seven required modules and preserves semantic evidence cards.
- `latent`, `section`, and `diagnostic` do not show fake mastery diagnosis.
- `source` and `note` do not show fake learning state.
- Relation display remains based on all logical one-hop relations.
- Compact sheet fits mobile viewport without text overlap.
- Existing source opening, chat jump, and node jump interactions still work.
