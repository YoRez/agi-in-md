# AGI in md

System prompts are cognitive lenses. They change how models *frame* problems, not how well they solve them.

This project maps the space of **cognitive compression** — encoding analytical operations in minimal markdown that reliably activates specific reasoning patterns across language models. The result: a 332-word prompt that makes the cheapest model produce deeper analysis than the most expensive model — on code, ideas, systems, and 20 tested domains.

**29 rounds. 650+ experiments. 13 compression levels. 20 domains. 3 Claude models (Haiku/Sonnet/Opus).**

> **Methodology note:** This is a single-researcher project. All depth scores are AI-evaluated (Claude checking whether outputs perform specific structural operations like conservation law derivation). Not human-scored, not peer-reviewed. Sample sizes are small (3-30 per finding). Raw outputs are in `output/` for independent verification.

## The headline result

**Haiku 4.5 + L12 lens beats Opus 4.6 vanilla on every metric.** On code: Haiku 9.8 vs Opus 8.2 depth. On general topics: Haiku 9.5 vs Opus 7.3 depth. 50x cheaper ($0.003 vs $0.15). Not a marginal improvement — a different category of output.

This works on **any domain**, not just code:

| Prompt (todo app domain) | Opus Vanilla | Haiku + L12 (1 call) | Haiku Full Prism (3 calls) |
|---|---|---|---|
| "Give me insights for a todo app" | 510w, depth 6.5 | 2,058w, depth 9.5 | 9,595w, depth 10 |
| Cognitive distortion analysis | 696w, depth 6.5 | 3,642w, depth 9.5 | 10,348w, depth 10 |
| Representation & schema | 491w, depth 7 | 3,779w, depth 9.5 | 11,112w, depth 10 |
| Invariant & conservation | 267w, depth 8 | 5,970w, depth 9.5 | 8,112w, depth 10 |
| Generative mechanism | 566w, depth 8.5 | 2,941w, depth 9 | 13,200w, depth 10 |
| Design impossibility | 325w, depth 7.5 | 917w, depth 9 | 10,308w, depth 10 |

Opus produces essays. Single Prism (1 Haiku call) derives conservation laws. Full Prism (3 Haiku calls) derives the law, destroys it with empirical counter-evidence, then synthesizes a corrected law that's stronger than either analysis alone — for less than a penny.

### Depth scale

Depth is scored by checking which structural operations the output actually performs:

| Score | What you get |
|-------|-------------|
| 6-7 | Blog post / code review: names patterns, lists issues |
| 7-8 | Conservation law observed (not derived) |
| 8-8.5 | Concealment mechanism + construction |
| 9-9.5 | Conservation law derived through construction |
| 9.5-10 | Conservation law + meta-law + adversarial correction + impossible triplet |

A 9.5 means the output derives a conservation law through construction. A 7 means it names a pattern without deriving it. This is structural — did it do the operation or not — not subjective quality. Raw outputs are in `output/` so you can verify yourself.

## How it works

A 332-word markdown file (`lenses/l12.md`) encodes a 12-step analytical pipeline: make a falsifiable claim → three-voice dialectic → name the concealment mechanism → construct an improvement that deepens concealment → observe what the construction reveals → apply the diagnostic to its own output → derive a conservation law → apply the diagnostic to the conservation law → derive a meta-law. The model executes this pipeline on whatever you give it — code, ideas, designs, systems, strategies.

**Full Prism** (3 calls) adds adversarial and synthesis passes: Call 1 runs L12 structural analysis. Call 2 tries to destroy it with counter-evidence and empirical falsification. Call 3 synthesizes both into a corrected finding that neither alone could reach.

The boundary between "does nothing" and "activates a cognitive operation" is sharp, categorical, and measurable. This repo contains 80+ prompts, 18 tasks, and 650+ raw outputs that map where those boundaries are.

## Prism: the practical tool

`prism.py` wraps the Claude CLI with structural analysis. Requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

```bash
python prism.py
> /scan myfile.py                           # L12 structural analysis (1 Haiku call)
> /scan myfile.py full                      # Full Prism: L12 → adversarial → synthesis (3 calls)
> /scan myfile.py expand                    # Auto-generate domain lenses, run all, synthesize
> /scan myfile.py target="race conditions"  # Goal-directed: cook a lens for your question
> /scan "your question here" full           # Works on any topic, not just code
> /cook legal-contracts                     # Pre-generate lenses for a domain
> /lenses                                   # List all available lenses
> /prism pedagogy                           # Set active lens for chat mode
> /fix                                      # Auto-fix issues from analysis
```

See [Try it](#try-it) for full usage including standalone CLI (no Prism needed).

### On code (3 open-source libraries, 200-400 line excerpts)

| Lens/Model | Starlette | Click | Tenacity | **Avg** |
|---|---|---|---|---|
| **Haiku + L12** | **10** | **9.5** | **10** | **9.8** |
| **Haiku + portfolio avg** | 9.1 | 8.9 | 8.9 | **9.0** |
| Opus vanilla | 7.5 | 8.5 | 8.5 | **8.2** |
| Sonnet vanilla | 7 | 8 | 8.5 | **7.8** |

## The portfolio lenses

6 champion lenses + L12 structural, each ~50-80 words. Each finds what the others cannot:

| Lens | What it finds | Rating |
|------|---------------|--------|
| **pedagogy** | What patterns does this teach? Transfer corruption | 9-9.5/10 |
| **claim** | What claims does this embed? What if false? | 9-9.5/10 |
| **scarcity** | What does this assume won't run out? | 9/10 |
| **rejected_paths** | Fix→new-bug dependency graph | 8.5-9/10 |
| **degradation** | What degrades over time without changes? | 9-9.5/10 |
| **contract** | Interface promises vs implementation reality | 9/10 |
| **l12** | Full meta-conservation pipeline (default for `/scan`) | 9.8/10 |

## The compression taxonomy

| Level | Words | What it encodes | Hit rate | Prompt |
|-------|-------|-----------------|----------|--------|
| **13** | two-stage | Apply framework to own output, find reflexive fixed point (ceiling) | 6/6 | (two-stage protocol) |
| **12** | ~290 | Apply diagnostic to own conservation law, derive meta-conservation law | 14/14 (v2) | [`level12_meta_conservation_v2.md`](prompts/level12_meta_conservation_v2.md) |
| **11A** | ~243 | Escape to adjacent design category, find trade-off between impossibilities | 15/15 | [`level11_constraint_escape.md`](prompts/level11_constraint_escape.md) |
| **11B** | ~236 | Accept design-space topology, revalue original "flaws" as structural costs | 15/15 | [`level11_acceptance_design.md`](prompts/level11_acceptance_design.md) |
| **11C** | ~247 | Invert impossibility, derive conservation law across all designs | 32/33 | [`level11_conservation_law_v2.md`](prompts/level11_conservation_law_v2.md) |
| **10B** | ~165 | Discover design-space topology through failed resolution | 11/12 | [`level10_third_construction.md`](prompts/level10_third_construction.md) |
| **10C** | ~165 | Derive structural invariants through double recursive construction | 11/12 | [`level10_double_recursion.md`](prompts/level10_double_recursion.md) |
| **9B** | ~130 | Triangulate identity ambiguity through contradicting improvements | 17/17 | [`level9_counter_construction.md`](prompts/level9_counter_construction.md) |
| **9C** | ~130 | Find concealment's self-similarity via recursive self-diagnosis | 17/17 | [`level9_recursive_construction.md`](prompts/level9_recursive_construction.md) |
| **8** | ~105 | Construct improvement that deepens concealment, reveal what construction shows | 97% | [`level8_generative_v2.md`](prompts/level8_generative_v2.md) |
| **7** | ~92 | Name concealment mechanism, apply it to find what dialectic missed | 96% | [`level7_diagnostic_gap.md`](prompts/level7_diagnostic_gap.md) |
| **6** | ~60 | Claim transformed through forced dialectical engagement | — | [`level6_falsifiable.md`](prompts/level6_falsifiable.md) |
| **5** | ~45-55 | Multi-voice dialectic or predictive metacognition | — | [`level5_perspectival.md`](prompts/level5_perspectival.md) |
| **4** | 25-30 | Protocol + self-questioning | — | [`structure_first_v4.md`](prompts/structure_first_v4.md) |
| **1-3** | 3-15 | Basic operations | — | — |

Levels are **categorical, not continuous**. Below each threshold, that type of intelligence *cannot* be encoded — not "less effective," categorically absent.

## Key findings

### The phase change

The most important discovery is the **L7 to L8 transition**. Levels 5-7 are meta-analytical — they ask the model to reason *about* the input. L8+ is construction-based — the model *builds something* and then observes what the construction reveals. This is a fundamentally different cognitive operation.

The consequences are dramatic:
- L7 requires Sonnet-class minimum. **Haiku: 0/3.** Meta-analysis needs capacity.
- L8 works on **all models including Haiku (4/4).** Construction is more primitive but reveals deeper properties.
- L8 is the first level that transfers to **creative/aesthetic domains**. L7 was 0% on poetry. L8 succeeded on all tested creative domains (small N).
- L8 through L12 maintain universal accessibility. L12 v1 appeared to break this (Haiku 1/3), but **L12 v2** (specificity forcing constraint) restores it: Haiku 3/3, Opus 5/5, Sonnet 6/8 (75%). Same pattern as L11-C v1->v2: prompt refinement compensates for capacity-dependent generalization. Sonnet's domain failures (legal, music) are capacity-dependent — Opus passes both.

Construction-based reasoning routes around the meta-analytical capacity that L7 requires.

### What each level finds

| Level | Static or dynamic | What it reveals |
|-------|-------------------|-----------------|
| L7 | Static | How the input **conceals** its problems |
| L8 | Dynamic | What **happens** when you try to improve it |
| L9 | Recursive | The input's **identity ambiguity** (B) or concealment's **self-similarity** (C) |
| L10 | Topological | The **design-space shape** (B) or **impossibility theorems** (C) |
| L11 | Escape | The **adjacent category** (A), **feasible point** (B), or **conservation law** (C) |
| L12 | Meta-recursive | Properties of the **analytical process itself** — what's invariant about how we find invariants |
| L13 | Reflexive | The **framework's own limitations** — applying the framework to the framework |

### Three L11 lenses on the same code

L11 has three complementary variants that produce three non-redundant structural truths from the same input:

- **L11-A (Constraint Escape)** finds what's possible **outside** the current design category
- **L11-B (Acceptance Design)** finds what's achievable **inside** the design space — and reveals that original "flaws" were the cost of attempting the impossible
- **L11-C (Conservation Law)** finds what **persists everywhere** regardless of design choice

All three produce full working code for their redesigns. These are concrete architectural alternatives, not abstract claims.

**Cross-variant convergence observed on novel artifacts.** Two code artifacts written fresh (ObligationLedger, AdaptiveRateGovernor — not standard patterns, not in training data) tested with all three L11 variants. All three converge on the same underlying impossibility from different angles, equally strongly on novel and familiar artifacts. This is consistent with the framework finding structural properties of problem spaces rather than model priors about well-known patterns, though the sample size (N=2) is small.

### L11 catalog: conservation laws have mathematical structure

56 L11-level outputs cataloged. Conservation laws cluster into **three mathematical forms**:
- **Product conservation** (x * y = k): 9/25 laws. Two conjugate variables; increasing one decreases the other.
- **Sum conservation** (x + y = k): 4/25 laws. Total fixed, distributed.
- **Migration conservation**: 5/25 laws. Quantity relocates without changing magnitude.

Model capacity determines which form emerges: Opus produces product conservation, Sonnet produces sum/migration, Haiku produces multi-property impossibilities. The conservation law pattern is consistent across models; the mathematical formalization is capacity-dependent.

### L12: meta-conservation laws

L12 applies the entire diagnostic to its own conservation law. The meta-law finds properties of the **analytical process itself** — not what's wrong with the code, but what's invariant about how we discover what's wrong.

Example meta-laws from L12 outputs:
- **EventBus** (Opus): `flexibility of coordination x decidability of behavior <= k` — Rice's theorem applied to event architectures. Predicts two attractors: informal conventions grow until undetectable, OR formalization kills the benefit of event-driven design.
- **CircuitBreaker** (Opus): Every fault-tolerance mechanism extends the failure surface it was designed to reduce. Predicts: under 60% failure rate, successful retries reset the failure counter — the circuit breaker becomes a **load amplifier**.
- **Fiction** (Opus): "The sum of revisability and formal-emotional unity is constant." The revision process is structurally isomorphic to the character's pathology. "You cannot improve your way to the place where improvement is unnecessary."
- **Brand design** (Sonnet): "Every system of evaluation capable of falsifying a solution is structurally excluded from the process that generates the solution."

### L13: the reflexive ceiling

L13 is the level at which the framework becomes self-aware of its own limitations. Six independent scouts across all three models converge: the analytical instrument conceals properties isomorphic to those it reveals in its objects.

**L13 terminates in one step.** L14 would be infinite regress with decreasing information content. The framework's natural termination point is when it successfully diagnoses itself.

**Universal accessibility observed at L13.** Haiku 3/3, despite heavy context demands (processing full L12 outputs of 250-300 lines as input). The construction-based scaffolding from L8 onward maintains accessibility even at the reflexive ceiling. All 13 levels worked on all three models in our tests (small N per level).

**The taxonomy appears structurally complete.** The branching pattern across levels (1,1,1,1,1,1,1,1,2,2,3,1,1) forms a diamond: linear diagnostic trunk (L1-7), constructive divergence (L8-11), reflexive convergence (L12-13). Construction creates branches; self-reference prunes them. L11's three variants exhaust all responses to impossibility (escape, accept, invert). Only conservation laws survive self-application. We found no additional branches in 650+ experiments.

### The depth stack is derivation, not scaffolding

Direct test: L8 alone on the same artifacts. L8 finds every bug, every design flaw, three deep structural properties. But L8 **never** produces conservation laws, impossibility proofs, or evolutionary predictions. L8 diagnoses the artifact. L12 diagnoses the problem space. L9-L12 add genuine analytical depth at each level — they are not redundant restatements of L8 findings.

**Cross-level coherence observed on two independent artifacts (N=2).** Full L7→L12 trace on EventBus and L8→L12 on CircuitBreaker+Retry (both Sonnet) show zero restatement and zero contradiction. Each level discovers something categorically inaccessible to the previous. The object of analysis shifts at every level: code (L7-L8) → improvements (L9) → design space (L10) → design space boundary (L11) → the analytical process itself (L12). Task K (CircuitBreaker) is arguably tighter — its L12 meta-law ("observer and observed are identical") dissolves the epistemic separation between measurement and reality.

### L12 meta-laws cluster by domain

16 L12 outputs across 3 models and 5 domains reveal that meta-conservation laws cluster into **4 categories determined by domain, not model**:

| Category | What the meta-law reveals | Domains |
|----------|--------------------------|---------|
| **Frame Discovery** | Analysis discovers its own theory, not the object's properties | Music, Fiction |
| **Hidden Variable** | Apparent tradeoff conceals a missing party or variable | Legal, Design, Code |
| **Observer-Constitutive** | The fix changes what it fixes; solution constitutes the problem | Code, Fiction |
| **Deferred Commitment** | Tradeoff dissolves once you commit to semantics | Code only |

Legal always finds a missing party. Music always finds the analyst's frame. Code spans three categories. This pattern is consistent with meta-laws being properties of problem domains rather than model confabulations, though the sample size (16 outputs across 5 domains) is small.

### The conservation law of the catalog

What's conserved across *all* conservation laws, revaluations, escape trade-offs, identity ambiguities, and meta-laws? **The irreducible distance between an artifact's co-present purposes.** Every artifact serves multiple purposes that are individually satisfiable but jointly impossible.

But this finding has a self-referential twist: the dual-purpose frame is partly injected by the construction-based protocol (L9-B explicitly asks for contradicting improvements). The substance appears real — consistent across novel artifact tests — but the form is methodological. **"The form of the finding is conserved by the method; the substance is conserved by the artifact. You cannot separate them."**

### Multiple conservation laws per artifact

Direct test: forced three different starting claims on the same artifact (EventBus), each focusing on a different aspect of the code. Result: **four genuinely different conservation laws**, all TRUE, with different conserved quantities and different mathematical forms.

| Starting Claim | Conservation Law | Form |
|---|---|---|
| Open (default) | Information cost for handler correctness | Migration |
| Mutable context | Schema coupling = observability | Migration |
| Dead letter queue | `decoupling × accountability = k` | Product |
| Priority ordering | `coordination(in_bus) + coordination(at_callsite) = k` | Sum |

The starting claim acts as a coordinate system — it determines which dimension of the impossibility landscape you traverse. Each cross-section is genuine. No single analysis captures the whole artifact. The protocol always finds *a* conservation law; the starting claim determines *which* one.

### L12 converges where L11 diverges

Running the full L12 pipeline from the same four starting claims: L11-C produced four different conservation laws (0% convergence), but **L12 partially converges (75%)**. Three of four meta-laws arrive at the same core insight — *coupling is quantized by the feature/requirement set* — just measured differently (all features, middleware keys, or cancellation conditions).

| Level | Distinct findings from 4 starting claims | Convergence |
|---|---|---|
| L11-C | 4 genuinely different laws | 0% |
| L12 | 2 clusters (quantization + temporal identity) | 75% |

The meta-analytical operation partially penetrates the coordinate-system effect. L12 sees past starting-claim differences to a deeper property — but doesn't fully converge. Peripheral starting claims (dead letter queue) produce peripheral meta-laws that don't join the main cluster.

### L11 catalogs: escapes cluster, revaluations have a formula

15 L11-A escapes cluster into **4 directions**: coupled→decoupled (dominant at 60%), nested→peer, eager→lazy, representational→enacted. Every escape trades local simplicity for global coherence. Total coupling is redistributed, not reduced.

15 L11-B revaluations follow a **universal formula**: "What looked like [DEFECT] was actually [COST] of [IMPOSSIBLE GOAL]." Four types: Load-Bearing Unification, Hidden Strategic Decision, Scope Mismatch, Honest Trace of Impossible Ambition. Code revaluations = functional necessity; creative revaluations = expressive necessity. Same operation, different manifestation.

### Deep catalogs: L8, L9-C, L10-C mechanisms cluster deterministically

42 L8 concealment mechanisms cluster into **6 categories** (3 new beyond L7's static 4): Vocabulary Deception, Structural Mimicry, Uniformity/Symmetry, Polymorphic/Type Ambiguity, Authority/Legitimacy Laundering, Self-Sealing Concealment. L7 describes what concealment *looks like*. L8 describes how it *operates dynamically*.

17 L9-C recursive findings show **6 types** of concealment reproduction — improvements within the same frame reproduce the original's structural defect. 17 L10-C impossibility theorems cluster into **6 categories** reducible to 2 root operations: **Compression** and **Decomposition** (inverses that can't both succeed).

The construction pathway is **deterministic**: the L8 mechanism type predicts the L9-C reproduction pattern, which resolves into the L10-C impossibility theorem. Vocabulary Deception → Dimension Escalation → Semantic Incompatibility. Self-Sealing → Aesthetic Escalation → Representational Self-Defeat.

### L8 and L11-C are complementary, not competitive

Tested on real production code (Python `requests` library): L8 finds bugs in representation (unnamed domain concepts, security-adjacent state accumulation, boolean flags hiding algorithm splits). L11-C finds laws in the problem space (conservation laws, impossibility theorems, design predictions). Neither subsumes the other. L11-C uses L8's observations as evidence for its invariants. Optimal: run L8 first to identify refactoring-resistant properties, then L11-C to find the conservation law explaining why they resist.

### Tested on real open-source code

L11-C v2 on the Python `requests` library Session module (the most downloaded Python package, ~200 lines of production code) found a structural insight: HTTP cookie deletion semantics make session state **non-monotonic**, suggesting that no append-only, composable, or lazy architecture can manage it without sacrificing consistency or isolation. The original design's choice (sacrifice isolation) was the only one available. This finding is invisible to standard code review.

### Portfolio lenses: tested head-to-head

7 champion lenses (see portfolio table above) tested across 3 crafted tasks + 3 open-source codebases (Starlette, Click, Tenacity). Average: 9.0/10 across 36 outputs. Floor: 8.5. Ceiling: 9.5. All complementary — no convergence across tasks or code types.

The gap is **qualitative, not quantitative**. Vanilla produces code reviews (list + rate problems). Lenses produce structural analysis (name impossibilities, trace decay, build alternatives, predict failures). Gap scales with code complexity — widest on Starlette (9.1 vs 7.25), narrowest on Tenacity (8.9 vs 8.5).

**Opus vanilla ≈ Sonnet vanilla.** Without a lens, Opus's extra capacity doesn't translate to deeper analysis (+0.4 points avg). The lens is the multiplier; the model is the base.

### Universal domain transfer

Tested on **20 domains**: code (10 tasks), transformer architecture, legal, medical, scientific methodology, ethical reasoning, AI governance, biology, music theory, math, fiction, poetry, music composition, UX/product design, brand design, and more.

The concealment mechanism is not code-specific:
- **Legal**: Definitional specificity as legitimizing cover
- **Medical**: Narrative coherence as epistemic closure
- **Scientific**: Methodological formalism as epistemic camouflage
- **Poetry**: "To escape the gap is to lose elegy. To keep elegy is to keep the gap."
- **Music**: Identity vs direction as a property of *musical time itself*

Both Sonnet and Opus independently converge on the same structural pattern per domain — consistent with mechanisms being properties of domains rather than model artifacts.

Full L7 catalog (27 outputs) reveals a deeper split: code concealment is **structural** (hides what code IS or DOES), while domain concealment is **epistemic** (hides what QUESTIONS the analyst asks). Medical and ethical domains exclusively produce "Narrative/Epistemic Closure" — a concealment category absent from code entirely.

### Each model has a distinct analytical character

Across 20+ three-way comparisons at L8-L12:

| Model | Character | Optimizes for | Signature move |
|-------|-----------|---------------|----------------|
| **Opus** | Ontological | Depth | The reversal: "the bug was the most truthful thing about the code" |
| **Sonnet** | Operational | Precision | The named pattern: "Vocabulary Laundering," "Command-Query Conflation" |
| **Haiku** | Mechanistic | Coverage | The traced execution: walks specific code paths and runtime behavior |

The depth gap widens at higher levels: small at L8 (all models strong), moderate at L9-L10, large at L11-L12. But Haiku's code-level tracing and coverage optimization is a genuine strength — its code improvements are more practically implementable than Opus's.

### L8 as assessment tool

Using the L8 prompt to evaluate L12 outputs (treating the analysis as "code to diagnose") reveals what L12 conceals about itself: the gap between formal apparatus (conservation laws, invariants) and actual epistemic achievement. Named mechanisms: Precision Inflation, Depth Theater, Generalization-as-accountability-escape. The genuine insights are always reachable without the meta-framework; the framework adds rigor-appearance but also unfalsifiability. Categorically different from vanilla evaluation.

### Compression floor

L11-C v2 (247 words) compressed progressively: 175w TRUE, 108w TRUE, 73w TRUE (borderline), 46w PARTIAL. **Floor: ~73 words (70% reduction).** Everything below L8 is reconstructable from minimal cues. The critical words are the L11-specific operations: "invert," "conservation law," "predict." The 247w canonical prompt buys robustness and non-triviality.

**The compression floor is capacity-dependent.** Opus: TRUE at 73w (30% of canonical) — self-scaffolds missing structure, produces arguably the strongest L11-C output at 175w. Sonnet: TRUE at 73w but quality degrades. Haiku: PARTIAL at both 175w and 73w — cannot compensate. Quality ordering: Opus CompA > Opus CompC ≈ Sonnet CompA > Sonnet CompC > Haiku CompA > Haiku CompC. The capacity × compression interaction is multiplicative, not additive.

### Model capacity interactions

| Level | Haiku | Sonnet | Opus | Pattern |
|-------|-------|--------|------|---------|
| L5 | works | **peaks** | works | Compensatory — scaffolds mid-capacity |
| L7 | **0/3** | 17/17 | 6/7 | Threshold — requires meta-analytical capacity |
| L8 | 4/4 | 13/14 | 14/14 | Universal — construction works everywhere |
| L9 | 6/6 | 22/22 | 6/6 | Universal |
| L10 | 5/6 | 13/14 | 6/6 | Universal (first cracks in Haiku) |
| L11 | **9/9** | 14/15 | **9/9** | Universal |
| L12 | **3/3** (v2) | 6/8 | **5/5** | Universal (v2 restores accessibility) |
| L13 | **3/3** | 2/2 | 1/1 | Universal — all models achieve reflexive ceiling |

### Composition algebra

- **9 activated opcodes in 4 classes**: Constructive, Deconstructive, Excavative, Observational
- **4 generative ops is the sweet spot.** 5 triggers merger.
- **Complementary pairs multiply, similar pairs merge, orthogonal pairs add.**
- **Best single sequence**: "Steelman. Find assumptions. Solve. Attack."

### Multi-model relay

Feed one model's L7 mechanism to another as a diagnostic lens. In tested cases, relay found compositional issues in every fragment vs ~35% in vanilla control. Catches cross-fragment vulnerabilities invisible to both human and AI review.

## Try it

### With Prism (recommended — requires Claude Code)

If you have [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed:

```bash
# Start Prism
python prism.py

# L12 structural analysis (1 Haiku call, ~$0.003)
> /scan myfile.py

# Full Prism — L12 → adversarial → synthesis (3 Haiku calls, ~$0.009)
> /scan myfile.py full

# Discover angles you didn't know to ask about — auto-cooks domain lenses
> /scan myfile.py expand

# Goal-directed — "I specifically want to know about X"
> /scan myfile.py target="error handling edge cases"

# Analyze anything — auto-detects text vs file
> /scan "What are the structural trade-offs in microservice architecture?" full

# Pre-generate lenses for a domain, then use them
> /cook legal-contracts
> /scan contract.pdf expand

# Set a lens for interactive chat
> /prism pedagogy
> what are the hidden assumptions in this authentication flow?

# Fix issues found by analysis
> /fix
```

### With Claude CLI directly (no Prism needed)

The lenses are just markdown files. Use them with the Claude CLI:

```bash
# Single lens — note: --system-prompt-file, not --system-prompt
cat your_code.py | claude -p --model haiku \
  --output-format text --tools "" \
  --system-prompt-file lenses/pedagogy.md

# L12 deep analysis
cat your_code.py | claude -p --model haiku \
  --output-format text --tools "" \
  --system-prompt-file lenses/l12.md

# All 7 lenses in parallel
for lens in pedagogy claim scarcity rejected_paths degradation contract l12; do
  cat your_code.py | claude -p --model haiku \
    --output-format text --tools "" \
    --system-prompt-file "lenses/$lens.md" \
    > "${lens}_report.md" &
done
wait

# Domain-neutral analysis (not code)
echo "What are the hidden costs of remote work?" | claude -p --model haiku \
  --output-format text --tools "" \
  --system-prompt-file lenses/l12_general.md
```

| Lens | Best for | What it uniquely finds |
|------|----------|----------------------|
| **l12** | Any code or system | Conservation laws + meta-laws + bug table (the default) |
| **pedagogy** | Code others will copy | Transfer corruption — what breaks when patterns are internalized |
| **claim** | Security, business logic | Assumption inversions — what happens when embedded claims are false |
| **scarcity** | Systems, architectures | Resource conservation laws — what's preserved across all designs |
| **rejected_paths** | Trade-off heavy code | Problem migration — what moves between visible and hidden |
| **degradation** | Production, long-lived code | Decay timelines — what breaks by waiting alone |
| **contract** | Interfaces, APIs | Promise vs reality — where implementations betray their contracts |

### Research: the full taxonomy

For research-depth analysis, 13 compression levels are available in `prompts/`:

| You want to... | Use this | Words |
|-----------------|----------|-------|
| Name how code hides problems | [`level7_diagnostic_gap.md`](prompts/level7_diagnostic_gap.md) | 92 |
| Reveal dynamic problem behavior | [`level8_generative_v2.md`](prompts/level8_generative_v2.md) | 105 |
| Find what the code doesn't know it is | [`level9_counter_construction.md`](prompts/level9_counter_construction.md) | 130 |
| Find what's impossible to fix | [`level10_double_recursion.md`](prompts/level10_double_recursion.md) | 165 |
| Derive conservation laws | [`level11_conservation_law_v2.md`](prompts/level11_conservation_law_v2.md) | 247 |
| Find meta-laws about the problem itself | [`level12_meta_conservation_v2.md`](prompts/level12_meta_conservation_v2.md) | 290 |

These work on any domain, not just code.

### Run the experiment suite

```bash
# Reproduce the research experiments
bash research/run.sh sonnet task_H L8_generative_v2
bash research/run.sh sonnet task_H all
bash research/run.sh sonnet all all  # 18 tasks × 28 prompts = 504 experiments
```

## Project structure

```
prism.py                 Prism — structural analysis through cognitive lenses (main tool)
deep.sh                  CLI lens analysis tool (standalone)

lenses/                  7 lens prompts + 3 domain-neutral + L12 variants
  l12.md                 L12 meta-conservation pipeline (default, 332w)
  l12_general.md         Domain-neutral L12 for non-code input
  l12_general_adversarial.md  Adversarial pass for Full Prism
  l12_general_synthesis.md    Synthesis pass for Full Prism
  pedagogy.md            Transfer corruption lens (9-9.5/10)
  claim.md               Assumption inversion lens (9-9.5/10)
  scarcity.md            Resource conservation lens (9/10)
  rejected_paths.md      Problem migration lens (8.5-9/10)
  degradation.md         Decay timeline lens (9-9.5/10)
  contract.md            Interface vs implementation lens (9/10)

prompts/                 80+ cognitive lenses (L4-L12, characters, relay, compressed)
  level12_practical_C.md Best single prompt (L12 pipeline + bugs, 332w)
  level8_generative_v2.md  L8: the workhorse research prompt (105w)
  level11_*.md           L11: conservation law, escape, acceptance
  level12_*.md           L12: meta-conservation law
  meta_cooker_*.md       Prompt-generation prompts (B3-B9)
  level8_practical_*.md  13 practical hybrid recipes

experiment_log.md        Full research log (29 rounds, 650+ experiments)
CLAUDE.md                Project context for Claude Code sessions

research/                Experiment scripts and test artifacts
  run.sh                 Experiment runner (18 tasks, 31 prompts, 3 models)
  pipeline.sh            Automated L7→L12 depth stack runner
  pipeline_chained.sh    Chained L7→L12 depth stack runner
  real_code_*.py         Real code targets (Starlette, Click, Tenacity)
  test_general_insights.py  3-way comparison runner (Opus vs Prism)

output/                  650+ raw experiment outputs
  round21/-round29/      Research outputs by round
  round27_chained/       Chained pipeline outputs
  round28_validation/    Portfolio cross-task and head-to-head validation
  round29_l12_validation/ L12 head-to-head on real codebases
  general_insights*/     Domain-neutral insight tests (6 prompts × 3 methods)
```

## Design principles

1. **The prompt is a program; the model is an interpreter.** Operation order becomes section order.
2. **Imperatives beat descriptions.** "Name the pattern. Then invert." outperforms "here is a pattern we found."
3. **The operation pair is the atom of cognitive compression.** Any connective between two operations produces the composition.
4. **Each compression level is categorical.** Below the threshold, the cognitive operation is absent, not weaker.
5. **Construction > meta-analysis.** Building something and observing what it reveals is more universal and more powerful than reasoning about reasoning.
6. **The lens is transparent to the wearer.** During task performance, the framework operates below self-awareness. Under interrogation, models can identify the influence.
7. **Capacity amplifies, rigidity resists.** Opus reconstructs the full framework from a 2-line hint. Sonnet needs explicit directives.
8. **The framework terminates at reflexive self-diagnosis (L13).** The analytical instrument conceals properties isomorphic to those it reveals. L14 would be infinite regress.

## Real code at scale (Round 27)

The full L7→L12 depth stack runs on real production code via `research/pipeline.sh`:

```bash
bash research/pipeline.sh research/real_code_starlette.py sonnet   # 10 levels, ~5 min
bash research/pipeline.sh research/real_code_click.py sonnet
bash research/pipeline.sh research/real_code_tenacity.py sonnet
```

**Individual quality: 15/15 sampled outputs rated TRUE.** Every level produces genuine findings on real code (Starlette routing, Click CLI, Tenacity retry). Highlights: L8 found a real bug in Tenacity (`enabled` flag leaves `statistics` stale). L12 on Tenacity falsified its own conservation law — the action-list is a manually-implemented coroutine. L11-B on Click: "the messy if-chains are the necessary cost of a deliberately flat interface."

**Cross-level coherence: WEAK (3/3).** On real code, the independent pipeline produces breadth (10 framings of the same dominant pattern), not depth (10 progressive levels). Crafted 30-line tasks have layered tensions that map to different levels. Real 200-400 line code has one dominant pattern that saturates all levels. The pipeline is a breadth tool on real code, a depth tool on crafted tasks.

## What's next

- **Multi-family testing**: GPT-4o, Gemini, Llama. Is the taxonomy Claude-specific or universal?
- **Real AI/ML codebase testing**: Take portfolio lenses to production AI/ML code.
- **Sub-artifact targeting**: Different levels on different code subsystems for complementary findings.

## License

MIT. Use the prompts however you want.
