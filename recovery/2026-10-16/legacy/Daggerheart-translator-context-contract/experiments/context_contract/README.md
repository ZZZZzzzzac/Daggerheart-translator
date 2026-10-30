# Context-contract trial (opt-in, not a replacement for main)

This experiment preserves the entire English source and retrieves terminology as a separate contract, rather than altering source text with inline markers. Applicability is a semantic decision, not a regex result. Longer concepts and ordinary senses can suppress shorter suggestions; accepted canonical phrases cannot be paraphrased away. A fresh reviewer checks mechanics and natural Chinese and directly fixes determined issues.

## Reproduce

From this checkout:

1. `python -m unittest discover -s tests -v`
2. Prepare a JSON array of `{ "id": "T01", "source": "...", "context": "optional unchanged context" }`. `reference` and all other fields are discarded before generation. Never give holdout references to translators.
3. `python experiments/context_contract/pipeline.py prepare cases.json /absolute/new-run`
4. Execute each saved `baseline-generate.txt` / `candidate-generate.txt` in **separate fresh native model workers**. Read the complete prompt and only the assigned condition. Baseline follows the unmodified d7ec63f main prompt, one complete source unit per chunk; candidate reads one deduplicated packet. Store actual task IDs and prompt/output hashes. This package does not silently produce a hand-written or mocked translation when no inference transport is available.
5. `python experiments/context_contract/pipeline.py review-packets /absolute/new-run`
6. Execute `baseline-review.txt` / `candidate-review.txt` in fresh workers with the same runtime configuration. Main's checker creates the baseline review report. Candidate's checker checks accounting, exact evidence and canonical strings. Preserve draft and final outputs separately.
7. `python experiments/context_contract/pipeline.py freeze /absolute/new-run`. Both arms receive the same existing deterministic makeup formatting. Raw finals and delivery files remain distinct. Frozen output hashes must precede blinded adjudication. Never edit scored outputs.
8. A separate assessor receives randomized X/Y delivery texts, full English, the fixed terminology/usage reference, and human-reviewed comparison text with caveats. The mapping stays with the coordinator. Score all units, not only candidate-marker hits. Run additional format checks, report failures, and do not call structural validation a semantic pass.

## Boundaries

- This tests translation + bounded AI review on complete source units, not PDF extraction, downstream JSON serialization, or the full twelve-step production workflow.
- Both arms have the same sources, glossary baseline, runtime configuration and one drafting/one review worker stage. Native workers may use multiple model turns for reading/writing; **two stages does not mean exactly two API calls**. No unavailable model identity, billed token count, temperature, or wall-clock performance claim.
- The baseline uses complete per-unit main prompts rather than claiming its source units match ordinary 5500-character production chunking. This can inflate repeated prompt overhead. Report it; do not infer a production cost saving.
- Count actual visible inputs and outputs by characters/bytes. Unknown hidden/system/reasoning overhead remains unknown. Candidate term dictionaries are deduplicated within a packet; references are retrieved only for reading, never auto-merged or applied as replacements.
- Offset matches preserve English including whitespace. Case-only matches are explicitly unconfirmed. All candidates can be semantically inapplicable. Lexical checking cannot establish mechanics or full coverage.
- Native worker isolation is an instruction/context boundary, not filesystem access control: workers share the workspace. Disclose this limitation.
- Human review history establishes traceable review, not sole-human authorship or flawless translations. Source meaning and frozen project terminology win over a flawed reference. No third-party content grants permission to change platforms.
- No push, merge, ParaTranz write, or Feishu write is performed by this package.

## Post-assessment clarification (v1.1; not part of the frozen model trial)

The initial blind assessment exposed two pre-existing guidance overlaps. Do not hide them by counting every general core phrase as an unconditional rule:

- The explicit shorthand permission in `匕语/匕语.md` for **adversary attack range fields** takes precedence over a general range-name lookup. Both the documented field shorthand and the established full name are allowed there; this does not license shortening rule-prose ranges.
- The dedicated damage template in `官方术语汇总与规范（传承_职业_领域）.md` takes precedence over matching the isolated `using your Proficiency` subphrase. The documented template wording is allowed in that damage sentence, not freely elsewhere.
- Complete explicitly fixed feature templates and frequency phrases retain their existing exactness requirements. This clarification is not general synonym permission.

`python experiments/context_contract/guidance_audit.py` checks that the two known evidence anchors still exist and records their narrow scope. Its tests reject cross-scope/general-synonym use. It is a guard for two documented overlaps, **not** exhaustive conflict detection or a new empirically validated translation pipeline. Frozen v1 prompts, translations and scores are untouched. Future prompt integration requires another held-out test.

### Render the assessed comparison

After both the original blind review and its frozen adjudication addendum exist, run:

`python experiments/context_contract/render_comparison.py /absolute/experiment-root /absolute/comparison.html`

This post-assessment renderer verifies output and assessment hashes and exports only full source/old/new/reference texts, public source links, scores and adjudicated findings. The scorecard and conclusions are scoped to this 30-unit experiment. It does not export inference prompts, worker identities or credential material. The standalone page has no external scripts and works offline; exact text identity and filter/search logic can be checked separately from browser pixel verification.

## Two-pass v2 (new user-requested experiment)

V1 remains frozen. V2 separates source-mechanics verification from stylistic refinement:

1. `python experiments/context_contract/two_pass.py prepare fresh-sources.json /absolute/new-run`
2. A fresh worker executes the complete `phase1-generate.txt`, writing the actual `candidate-draft.json`: complete rough Chinese, source-anchored invariant propositions, scoped protected phrases, real unresolved questions.
3. `python experiments/context_contract/two_pass.py polish /absolute/new-run` creates `phase2-polish.txt` and the baseline main review packet. For development-only candidate runs, add `--development`.
4. A different fresh worker executes phase2, rereading the complete English rather than trusting the draft. It refines Chinese, records exact before/after edits, checks each invariant and explicitly corrects source-inconsistent first-draft claims. It checks for new ambiguity and preserves applicable fixed templates.
5. `python experiments/context_contract/two_pass.py freeze /absolute/new-run` stores raw/delivery hashes and a separately computed full text diff. Development-only runs use `--development` and cannot masquerade as fresh holdout evidence.
6. An external assessor evaluates both final arms, then separately examines source/coarse/final for introduced ambiguity and first-draft errors carried forward. Structural checks and model-authored invariant claims are not semantic proof.

The candidate final is delivered verbatim, without the old broad `format_resource_phrases_fn` regex: that regex can turn “已标记的生命点” into “已标记 的 生命点”. Required formatting must be completed during refinement; validators report problems instead of silently rewriting polished sentences. Baseline keeps its existing formatter. This is another package difference and must be disclosed.

V2 uses prior test cases only as development regression, then a new 8-rule/8-question/8-narrative holdout. References remain withheld from both phases. Do not silently modernize an older core-book passage to SRD2. The prospective protocol is `protocol-v2.json`; report per-stratum naturalness, not just an average that hides question regressions, and record the input/output volume added by invariants and difference auditing.

V2 freeze also fingerprints the full local skill .md/.json/.py dependency closure, protocol, stage-two input, raw marked drafts/finals and review records. Schema failures are frozen as failures without a fabricated delivery. Change records are checked for exact spans and non-no-op edits; this does **not** establish exhaustive diff coverage or semantic correspondence. The independent full-text diff and source/coarse/final review remain required. Development freeze predates these structural hardening changes; its raw outputs were revalidated unchanged with zero findings.

### V2 observed result (2026-10-14, 24 fresh passages)

Frozen translation-rule commit: `830188636789eadd3b1c0a07a1a10ff16c72fbae`.
Independent randomized-label final review found naturalness baseline→candidate:
8 rules 4.000→3.875; 8 character questions 4.000→3.875; 8 narrative 4.500→3.625.
Both arms had zero confirmed terminology/mechanics errors; baseline had two minor
factual-scope errors versus candidate zero. All three naturalness gates failed.
Keep the old production default. This opt-in experiment is not a validated replacement.

Separate source/draft/final audit covered 151 propositions, 29 declared changes and
13 retained protected phrases. Of eight model-claimed corrections, four were
supported, three were wording-only and one uncertain. V08 lost explicit quantity
reference clarity; V11 introduced an uncertain exclusive reading. Zero confirmed
new mechanics errors does not mean zero ambiguity. Do not count self-reported
checks as independent success.

The presentation-only `build_two_pass_report.py EXPERIMENT_ROOT OUTPUT.html`
validates frozen hashes and assembles original/source/final/reference comparisons
using separately supplied blind-review and stage-audit artifacts. It does not
regenerate or patch translations. `render_two_pass.py` accepts curated display data
and exports only allowlisted public fields. These display additions postdate model
freeze and do not affect its tested prompts. No push/merge has been performed.

### User-found semantic failure and v2.1 (post-feedback)

The earlier v2 “zero terminology errors” result is **withdrawn**. The module defines
Tokens as glowing collectible coins, not tabletop markers; V18 and V19 were wrong
in both arms and both review routes missed the mistake. Corrected v2 totals are
baseline 4 hard errors (2 sense errors + 2 minor fact errors), candidate 2 sense
errors. V1 X03 has the same error separately. Original outputs/reviews stay intact;
the presentation compiler can apply the explicit correction appendix. This is a
failure of the core disambiguation goal, not an incidental typography issue.

`context_senses.py prepare CASES DOCUMENTS RUN` produces a real model sense-planning
packet. Cases provide `id`, `source`, `document_id` and optional existing `context`;
documents provide `id` and complete `text` containing the source. After actual
`sense-decisions.json` generation, `context_senses.py bind RUN BOUND_CASES` validates
quoted evidence, document membership, complete candidate accounting and scoped
entity/applicability decisions, preserving original text and context. Feed the
bound cases to `two_pass.py prepare` for downstream translation. No global word
mapping is changed. “Story setting” alone does not exempt canonical ancestry,
class or named-entity terms. Subsumed candidates must name an actual covering,
applicable longer occurrence. Evidence validation does not prove correct meaning.

This adds a real model stage and cost. The original two-pass code remains unchanged.
The extra stage is a feedback-driven experimental adapter, not an already proven
fix. `protocol-senses-v21.json` specifies a fresh synthetic contrast diagnostic
that scores final Chinese false application AND missed required terminology,
not merely JSON fields. Same-context old-main controls receive the full documents
without seeing the candidate decisions. No generalization or fluency claim follows
from passing synthetic cases.

### Latest Chinese-delivery policy and fail-closed basic gate

The user rejected “守护者 Guardian” in reader-facing Chinese. Old REFERENCE lines
74 and 91–100 conflict about retaining English names; latest explicit Chinese-only
policy overrides both, and overrides bilingual title examples without changing
fixed Chinese mechanism wording. This is a new delivery-policy correction, not a
retroactive rewrite of frozen experiment scores or translations.

Use `delivery_gate.py prepare CASES RUN [--profile PROFILE.json]`, then actual
translation, `delivery_gate.py polish RUN`, actual review/refinement, and
`delivery_gate.py release RUN`. The same resolved policy/profile is injected into
both generation arms and both review stages. The profile is hashed before use.
`allowed_latin` entries are exact names with reasons; optional `required: true`
also prevents dropping an original name present in the source. Dice and logical
link targets are kept. An empty allowlist does not authorize deleting actual names;
unknown Latin blocks delivery for internal editorial resolution.

The gate never strips ASCII or repairs saved text. It blocks unapproved Latin,
internal wrappers/comments/term markers, malformed bold/link patterns, lost source
link targets, lost dice occurrences and missing required original names. It also
rejects missing/duplicate translation units. Exit 2 means BLOCKED; semantic and
fluency review remain required after a basic pass. Markdown display text, link destinations, code spans and emphasis are read from
Pandoc CommonMark AST nodes. Pandoc is required; missing parser or a version change
since prepare blocks release. This checks selected delivery properties, not every
renderer or semantic correctness. A separate render audit found CJK punctuation
adjacent bold failures; those cases are covered by regression tests.

Read-only scan of saved outputs:
`python experiments/context_contract/delivery_gate.py scan SOURCES.json DELIVERY.json --output FINDINGS.json`

The fresh 12 synthetic context contrasts passed semantic applicability in BOTH
arms (false application 0, missing required term 0); no new-vs-old advantage was
shown. Both still retain “骸骨 Bone 领域” in one case. Semantic pass is not clean
Chinese delivery pass. The original Token excerpts lacked the module-wide coin/
competition definitions (empty context fields), but their local floating/buried
story object clues were already enough to warn against tabletop-marker defaults.

Gate hardening: failed revalidation invalidates any previous success record before
reading or hashing current inputs. `two_pass.py freeze` refuses gate-required runs
unless entered through the delivery wrapper. Successful gate records bind output
hashes and parser identity; do not treat an old boolean as approval of changed files.
