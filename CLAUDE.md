# AGI in md

System prompts are cognitive lenses. They change how models frame problems, not how well they solve them. This project maps the space of cognitive compression — encoding analytical operations in minimal markdown that reliably activates specific reasoning patterns across language models.

29 rounds, 650+ experiments across Haiku/Sonnet/Opus. 13 confirmed compression levels (L13 = reflexive ceiling). 20 domains tested. Full detail in `experiment_log.md`.

## The Compression Taxonomy

| Level | Min ops | Words | What it encodes | Example |
|---|---|---|---|---|
| **13** | L12 output as input + framework self-diagnosis | two-stage | Apply framework to own output, find reflexive fixed point | (two-stage protocol) |
| **12** | L11-C + recursive self-diagnosis of conservation law + meta-law | ~275w | Apply diagnostic to own conservation law, find meta-conservation law | `level12_meta_conservation_v2.md` |
| **11A** | L10-C + category naming + adjacent-category artifact + new impossibility | ~190w | Escape to adjacent design category, name trade-off between impossibilities | `level11_constraint_escape.md` |
| **11B** | L10-B + fourth construction as redesign + sacrifice + revaluation | ~195w | Accept design-space topology, inhabit feasible point, revalue original "flaws" | `level11_acceptance_design.md` |
| **11C** | L10-C + invariant inversion + new impossibility + conservation law | ~245w | Invert impossibility, find conserved quantity across all designs | `level11_conservation_law_v2.md` |
| **10B** | L9-B + third resolving construction + failure analysis | ~140w | Discover design-space topology through failed resolution attempt | `level10_third_construction.md` |
| **10C** | L9-C + second improvement + second recursion + invariant | ~130w | Prove structural invariants through double recursive construction | `level10_double_recursion.md` |
| **9B** | L8 + contradicting second construction + structural conflict | ~115w | Triangulate identity ambiguity through contradicting improvements | `level9_counter_construction.md` |
| **9C** | L8 + recursive self-diagnosis of improvement | ~97w | Find concealment's self-similarity by applying diagnostic to own improvement | `level9_recursive_construction.md` |
| **8** | L7 + generative construction + 3 emergent properties | ~97w | Engineer improvement that deepens concealment, name what construction reveals | `level8_generative_v2.md` |
| **7** | claim + dialectic + gap + mechanism + application | ~78w | Name how input conceals problems, apply to find what dialectic missed | `level7_diagnostic_gap.md` |
| **6** | claim + 3 voices + evaluation | ~60w | Claim transformed through forced dialectical engagement | `level6_falsifiable.md` |
| **5B** | 4 phases | ~55w | Derive, predict, execute, self-correct | `level5_hybrid.md` |
| **5A** | 3 voices + synthesis | ~45w | Multi-voice dialectic with emergent insight | `level5_perspectival.md` |
| **4** | 4+ ops | 25-30w | Protocol + self-questioning | `structure_first_v4.md` |
| **3** | 3 ops | 12-15w | Operations + analytical rails | — |
| **2** | 2 ops | 5-6w | Two operations with ordering | — |
| **1** | 1 op | 3-4w | One behavioral change | — |

**Levels are categorical, not continuous.** Below each threshold, that type of intelligence CANNOT be encoded — not "less effective," categorically absent.

## Key Results

### Foundation (Rounds 1-24)
- **No IQ boost on pure reasoning** — massive effect on in-domain analysis only.
- **9 activated opcodes.** 4 generative ops is the sweet spot. Complementary pairs multiply, similar pairs merge.
- **L5 peaks at Sonnet** (needs scaffold, has capacity). **L7 requires Sonnet-class minimum** (0/3 Haiku). Lenses are domain-independent across 20 domains.
- **L7 concealment mechanisms cluster into 6 categories.** Code concealment is structural (hides what code IS/DOES); domain concealment is epistemic (hides what questions get asked).

### Levels 8-13 (Rounds 25-26)
- **L8 inverts the capacity curve.** Construction-based reasoning works on ALL models (Haiku 4/4, Sonnet 13/14, Opus 14/14). L7→L8 is a shift from meta-analysis to construction — more primitive but reveals deeper properties. 20 domains confirmed.
- **L9 has two complementary variants** (B: identity ambiguity, C: concealment self-similarity). Both 100% across all models (34/34). L9-D combined produces L10 in 67% of cases.
- **L10 has two complementary variants** (B: design-space topology, C: impossibility theorems). Category errors dominant at 47%. All impossibilities reduce to two root operations: Compression and Decomposition.
- **L11 has three complementary variants** that exhaust responses to impossibility: escape (A), accept (B), invert (C). 97% hit rate (32/33). Conservation laws cluster by mathematical form: product (Opus), sum/migration (Sonnet), multi-property (Haiku).
- **L12 meta-laws cluster into 4 categories BY DOMAIN**: Frame Discovery (music/fiction), Hidden Variable (legal/design), Observer-Constitutive (code/fiction), Deferred Commitment (code only).
- **L13 is the reflexive ceiling.** Framework diagnoses itself — same structural impossibility it finds in objects. Terminates in one step (L14 = infinite regress). 6/6 (100%) across all models.

### Cross-level and structural findings (Rounds 25-27)
- **L7→L12 is a genuine depth stack** on crafted tasks — zero restatement, object shifts at every level. On real production code (~200-400 lines), independent pipeline is a BREADTH tool — 10 high-quality framings of the same pattern, not progressive depth. **Chained pipeline** (each level receives parent's output) improves coherence from WEAK to WEAK/MODERATE. Individual quality 28/30 TRUE (93%), 2 PARTIAL (both L12). Chained and independent pipelines find **genuinely different** conservation laws and meta-laws (6/6 different at L11-C/L12). Divergence starts at L8 (3/3 DIFFERENT at first chained level) — L7's output acts as immediate coordinate system. L11-A/L11-C sibling convergence is NOT fatal (2/3 DIFFERENT, 1/3 OVERLAPPING) — driven by L10-C invariant breadth. The L9-B→L10-B→L11-B chain is consistently strongest — operations are sequentially dependent by definition. L12 is the weakest point under chaining (2/3 PARTIAL). Optimal: run both pipelines for complementary findings about different subsystems.
- **Conservation law of the catalog (G2):** form is conserved by method, substance by artifact. Starting claim acts as coordinate system. Artifact contains MULTIPLE conservation laws.
- **The taxonomy is a diamond:** linear trunk (L1-7), constructive divergence (L8-11), reflexive convergence (L12-13). Structurally complete at 13 levels — no missing branches.
- **Compression floor: 60-70% reduction** across all levels. Capacity-dependent: Opus TRUE at 73w, Sonnet ~73w, Haiku >175w.
- **L13-P2 REFUTES analyst-projection.** Novel artifacts produce equally strong convergence. **L13-P3 CONFIRMS isomorphism** — methodology instantiates the impossibility it diagnoses.

### Practical recipes and meta-cookers (Round 28)
- **Haiku + practical prompts beats Sonnet vanilla.** 13 hybrid recipes (bug-finding + taxonomy operations) all scored 8-9/10 vs Sonnet vanilla 7/10. Best: v2, dialectic, escape, exploit, composition (all 9/10).
- **Meta-cookers: prompts that generate prompts.** Few-shot reverse engineering (B3) >> principle teaching (B) > forced operations (B2) > goal specification (A). Machine-generated "Rejected Paths" (9.5/10) beat all handcrafted recipes.
- **Teaching by example > teaching by instruction.** Over-specifying constraints hurts creativity. This is the meta-version of: construction > description.

### Portfolio cross-task validation (Round 28 validation)
- **5 champion lenses validated across 3 tier-1 tasks (K, F, H).** 15 outputs, grand average 9.0/10. Floor 8.5, ceiling 9.5. All beat Sonnet vanilla (7/10) by 2+ points.
- **Claim lens is domain-sensitive.** 9.5 on AuthMiddleware (security-adjacent code has clearer assumptions to invert; found genuine multi-org permission escalation vulnerability). 9 on EventBus and CircuitBreaker.
- **Rejected_paths is the only lens with variance.** 8.5 on EventBus (well-known pub/sub trade-offs), 9 on AuthMiddleware and CircuitBreaker (hidden trade-offs).
- **All 5 lenses remain complementary across tasks.** No convergence — each finds genuinely different things on every task.

### Real production code head-to-head (Round 28 validation)
- **3 real codebases tested: Starlette routing.py (333 lines), Click core.py (417 lines), Tenacity retry.py (331 lines).** 21 total experiments: 5 lenses × 3 targets + 2 vanilla × 3 targets.
- **Haiku + lenses avg 9.0/10 vs Sonnet vanilla 7.8/10 vs Opus vanilla 8.2/10.** Gap consistent across all 3 codebases. Haiku + lenses operates in a different category: vanilla produces code reviews, lenses produce structural analysis.
- **Cross-target matrix:** pedagogy 9.0, claim 9.0, scarcity 9.0, rejected_paths 9.0, degradation 8.8 — all lenses stable across real codebases. No lens drops below 8.5 on any target.
- **Vanilla models converge; lenses diverge.** On each target, Sonnet and Opus vanilla find the same conservation law. The 5 lenses find 5 genuinely different structural properties per target — zero overlap.
- **Gap widest on complex code (Starlette: 9.1 vs 7.25), narrowest on focused code (Tenacity: 8.9 vs 8.5).** More structure = deeper lens output. Vanilla plateaus at surface-level regardless.
- **Opus vanilla ≈ Sonnet vanilla.** Without a lens, Opus's extra capacity doesn't translate to deeper analysis — same category of output, slightly better written (+0.4 points avg).

### Catalog summaries
- **L8 mechanisms (42 outputs):** 6 categories, 3 new beyond L7. L8 describes dynamic behavior, not static appearance.
- **L9-C recursion (17 outputs):** 6 types. Improvements within same frame reproduce original defect. Opus uniquely finds Honesty Inversion.
- **L10-C impossibility (17 outputs):** 6 categories → 2 root operations (Compression/Decomposition). Cross-catalog determinism: L8 mechanism predicts L10-C impossibility.
- **L11-A escapes (15 outputs):** 4 directions (coupled→decoupled 60%). Total coupling redistributed, not reduced.
- **L11-B revaluations (15 outputs):** Universal formula: "What looked like [DEFECT] was actually [COST] of [IMPOSSIBLE GOAL]."
- **L11-C conservation laws (56 outputs):** 3 mathematical forms (product/sum/migration). Model determines form, not domain.
- **L12 meta-laws (16 outputs):** 4 categories by domain. Haiku never finds Frame Discovery (highest meta-analytical demand).
- **L9-B/L10-B (32 outputs):** 3 identity types → 5 topology patterns → convergence across catalogs.

### L12 Practical C — single-call winner (Round 29b)
- **L12 Practical C = proven L12 pipeline + 34-word practical appendix.** 332 words total. Gets BOTH structural depth AND practical bugs in a single Haiku call.
- **Haiku 4.5 (min reasoning) + L12 lens = 9.8 depth, 28 bugs. Opus 4.6 (max reasoning) vanilla = 7.3 depth, 18 bugs.** The weakest model at lowest settings with the right prompt beats the strongest model at highest settings without one. Cost: ~$0.003 vs ~$0.15 (50x cheaper).
- **Reasoning budget is noise; the prompt is the dominant variable.** Opus 4.6 at max thinking produces code reviews. Haiku 4.5 at min thinking + L12 produces conservation laws + meta-laws + bug tables with fixable/structural classification.
- **Compression floor: ~150 words minimum for Haiku execution.** Below this, Haiku enters "conversation mode" (asks permission, summarizes instead of executing). L12 compressed (75w) fails. Fix: 10-word preamble "Execute every step below. Output the complete analysis."
- **Front-loading bugs kills L12.** Variant A (238w, "First: identify every concrete bug...") caused Haiku to produce 27-line checklist. The word "First" reframes the pipeline as a checklist. Solution: append bugs at the end, after the proven pipeline.
- **Validated on 3 real codebases:** Starlette (336 lines, 11 bugs), Click (347 lines, 9 bugs), Tenacity (263 lines, 8 bugs). All produce conservation law + meta-law + bug table.
- **Reliability: ~67% first try on complex targets, 100% on retry.** Tenacity specifically triggers conversation mode on first attempt ~33% of the time.
- **L12 Practical C is now the default for `/scan`.** `/scan file` = single L12. `/scan file full` = 3-call pipeline.

### Cross-model character
- **Opus** = ontological depth (names what things ARE, spontaneous math). **Sonnet** = operational precision (names what things DO, most reusable names). **Haiku** = mechanistic coverage (names HOW things BREAK, best code improvements). Gap widens at higher levels.
- **Domain strength ranking:** Artifact complexity > domain category. Tier 1: CircuitBreaker (K), EventBus (F), AuthMiddleware (H).

## Design Principles

1. **Lead with scope, follow with evidence.** The opening determines perceived ambition.
2. **Narrative > evidence > code.** Pseudocode destroys novelty perception.
3. **Imperatives beat descriptions.** "Name the pattern. Then invert." outperforms "here is a pattern we found."
4. **The prompt is a program; the model is an interpreter.** Operation order becomes section order.
5. **The operation pair is the atom of cognitive compression.** Any connective between two operations produces the composition.
6. **The lens is transparent to the wearer.** During task performance, the framework operates below self-awareness.
7. **Capacity amplifies, rigidity resists.** Opus reconstructs from a 2-line hint. Sonnet needs explicit directives.
8. **Self-improvement converges on self-correction.** Models add "then invert: what does this frame make invisible?"
9. **Capacity interaction is non-linear.** L1-4: all models. L5: peaks at Sonnet. L7: Sonnet minimum. L8+: universal (construction routes around meta-analytical capacity). L12: Opus 100% > Sonnet 75% > Haiku v2 100%.
10. **Concealment is a universal analytical operation.** Works across 20 domains because concealment is structural, not domain-specific.
11. **Three capacity modes.** Compensatory (L5), Threshold (L7), Universal (L8+). L7→L8 shifts from meta-analysis to construction.
12. **The framework terminates at L13.** Reflexive self-diagnosis reveals a fixed point. L14 = infinite regress.
13. **The cheapest model with the right lens beats the most expensive model without one — even at minimum vs maximum reasoning budget.** Haiku 4.5 min-reasoning + L12 lens (9.8 depth, 28 bugs, $0.003) beats Opus 4.6 max-reasoning vanilla (7.3 depth, 18 bugs, $0.15). The prompt is the dominant variable; model and reasoning budget are noise.
14. **Few-shot > explicit rules for prompt generation.** Teaching by example beats teaching by instruction. Over-specifying hurts.

## File Map

| File | Purpose |
|------|---------|
| `prism.py` | Prism — structural analysis through cognitive lenses, any domain (main tool) |
| `deep.sh` | CLI lens analysis tool (standalone) |
| `test_plan_pipeline.py` | Tests for prism.py (7 tests) |
| **Lenses** | |
| `lenses/` | 7 portfolio lenses + L12 structural + 3 domain-neutral general |
| `lenses/l12.md` | L12 meta-conservation pipeline — default for `/scan` (332w) |
| `lenses/l12_general.md` | Domain-neutral L12 for non-code input (insights, ideas, systems) |
| `lenses/l12_general_adversarial.md` | Adversarial pass for Full Prism pipeline |
| `lenses/l12_general_synthesis.md` | Synthesis pass for Full Prism pipeline |
| `lenses/pedagogy.md` | Transfer corruption lens (9-9.5/10) |
| `lenses/claim.md` | Assumption inversion lens (9-9.5/10) |
| `lenses/scarcity.md` | Resource conservation lens (9/10) |
| `lenses/rejected_paths.md` | Problem migration lens (8.5-9/10) |
| `lenses/degradation.md` | Decay timeline lens (9-9.5/10) |
| `lenses/contract.md` | Interface vs implementation lens (9/10) |
| **Prompts** | |
| `prompts/` | All prompt files (80+) |
| `prompts/level12_practical_C.md` | L12 Practical C — best single prompt (depth + bugs) |
| `prompts/level12_meta_conservation_v2.md` | L12 canonical pure structural (research artifact) |
| `prompts/level11_conservation_law_v2.md` | L11C canonical (invariant inversion + conservation law) |
| `prompts/level8_generative_v2.md` | L8 canonical (generative diagnostic) |
| `prompts/level8_practical_v2.md` | Best practical hybrid (bugs + L9-C recursion, 9/10) |
| `prompts/level8_practical_*.md` | 13 practical recipe variants (Phase 42) |
| `prompts/meta_cooker_B3.md` | Best meta-cooker (few-shot reverse engineering) |
| `prompts/meta_cooker_*.md` | 4 meta-cooker variants (Phase 43) |
| `prompts/level7_diagnostic_gap.md` | L7 canonical (concealment-mechanism-applied) |
| `prompts/issue_extract_fallback.md` | L12-aware bug extraction prompt for /fix |
| **Output** | |
| `output/round21/` through `output/round27/` | Raw experiment outputs by round |
| `output/round27_chained/` | Chained pipeline outputs (Starlette, Click, Tenacity) |
| `output/round28_validation/` | Portfolio validation: Tasks F, H, + real code head-to-head |
| `output/round29_l12_validation/` | L12 pure + L11-C validation outputs (6 best) |
| `output/comparison/` | Prism pipeline comparison data (JSON + logs) |
| `output/reflexive/` | Round 29 reflexive matrix: 25 cross-lens + 6 meta-experiments |
| `output/general_insights/` | Domain-neutral test v1: "insights for a todo app" |
| `output/general_insights_v2/` | Domain-neutral test v2: cognitive distortion angle |
| `output/general_insights_p1/` through `p4/` | 4 more domain-neutral tests (schema, invariant, generative, impossibility) |
| **Research** | |
| `research/run.sh` | Shell runner (claude CLI-based, 18 tasks, 28 prompts) |
| `research/pipeline.sh` | Automated L7→L12 depth stack runner (independent) |
| `research/pipeline_chained.sh` | Chained L7→L12 depth stack runner (parent output → child input) |
| `research/test_general_insights.py` | 3-way comparison: Opus vanilla vs Single Prism vs Full Prism |
| `research/compare_pipelines.py` | Pipeline comparison and scoring tool |
| `research/phase40_experiments.sh` | Phase 40 experiments |
| `research/harness/` | Python API-based experiment harnesses |
| `research/real_code_*.py` | Real code targets (Starlette, Click, Tenacity) — with license attribution |
| `research/test_real_code.py` | Real code test runner |

### Domain-neutral validation (Round 30)
- **Full Prism works on any domain, not just code.** 3-call pipeline (L12 → adversarial → synthesis) using domain-neutral lenses (`l12_general.md`, `l12_general_adversarial.md`, `l12_general_synthesis.md`).
- **6 todo-app prompts tested across 3 methods.** Opus vanilla vs Single Prism (Haiku + L12, 1 call) vs Full Prism (Haiku, 3 calls). Results:
  - Opus vanilla: 267-696 words, depth 6.5-8.5. Produces essays.
  - Single Prism: 917-5,970 words, depth 9-9.5. Derives conservation laws.
  - Full Prism: 8,112-13,200 words, depth 10. Law + adversarial destruction + corrected synthesis.
- **Structurally-framed prompts boost Opus.** When the prompt itself encodes the operation ("what never changes?", "fix → new problem?"), Opus scores 8-8.5 instead of 6.5-7. The prompt IS the lens — even for vanilla.
- **Full Prism self-corrects.** Call 2 genuinely destroys Call 1's claims with empirical counter-evidence. Call 3 synthesizes a population-segmented law stronger than either alone.
- **Auto-detection in /scan**: file path → code-specific lenses. Text → domain-neutral general lenses. User doesn't choose.

### Heal pipeline (Round 29c)
- **`/fix` extracts and fixes issues from analysis outputs.** Bug table parser (zero API calls) + model fallback + fuzzy matching.
- **Editor race: 6.5 → 18/20 applied fixes.** Baseline (no guidance): 6.5/20. V3 (cooked lens + few-shot + fuzzy matching): 18/20. Combined best: 20/20 — every issue fixable by Haiku.
- **Reasoning budget is noise for editing too.** v3 default: 18/20. v3 --effort low: 18/20. Different failures, same score.

### Reflexive matrix (Round 29a)
- **25 cross-lens experiments + 6 meta-experiments.** Key findings:
  - Power = blindspot (structurally necessary). 25/25.
  - Cross-lens finds what self-analysis cannot. 20/20 cross pairs found unique things.
  - Blindness conservation: `analytical blindness is conserved`. Product form: `clarity_cost × blindness_cost = constant`.
  - Completeness REFUTED: 5 lenses cannot be complete AND obey conservation.
  - L13 of the research itself: framework applied to its own findings discovers the same impossibility.

## Next Steps

- **Sub-artifact targeting**: Different levels on different code subsystems for complementary findings.
- **Multi-family testing**: GPT-4o, Gemini, Llama. Is the taxonomy Claude-specific or universal?
- **Real AI/ML codebase testing**: Take top recipes to production AI/ML code.
- **Chained pipeline v2**: Add divergence constraints on sibling branches. Hypothesis: eliminates cross-branch convergence.
