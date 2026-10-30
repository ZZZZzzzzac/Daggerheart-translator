# Translation recovery assets, 2026-10-16

This directory supplements the existing translator trial source at commit af9b77001a09fa4212555856bd8f60c49a762a0d. It is a recovery snapshot, not a deployment, release, or merge into main.

## Contents

- translation-review-site/: all eight tracked files of the buildless review application at source commit e336b2c586ade0305744bceabce93e4b34bea95c, including README, both tests, four runtime files, and existing hosting mapping.
- legacy/: selected older file variants not matched to verified remote history. These are partial historical variants, not complete runnable checkouts. Original bytes and directory labels are preserved in MANIFEST.json.
- quantity-diagnostic-dedup/: previous scanner implementation, original patch and synthetic differential script/result, protocol, portable replay helper, and statistics without source/translation text.

The complete current translator trial source is preserved by the parent commit. The local Site runtime archive alone did not include its README and tests, so those are included here.

## Verification

From the repository root:

    node --test recovery/2026-10-16/translation-review-site/model.test.mjs recovery/2026-10-16/translation-review-site/app.test.mjs
    node --check recovery/2026-10-16/translation-review-site/dist/app.mjs
    node --check recovery/2026-10-16/translation-review-site/dist/model.mjs
    python -B recovery/2026-10-16/quantity-diagnostic-dedup/replay_synthetic.py --repo-root .
    python -B -m unittest discover -s tests -v

The portable helper checks all 900 synthetic cases against the stored matrix without writing source files. The original compare-matrix.py is preserved byte-for-byte and expects its historical sibling-directory layout; use the portable helper for this layout.

## Omissions and limits

No credentials, private notes, runtime databases, authentication/session data, local execution metadata, or original project guidance files are added here. No obsolete QQ bridge is included.

The nonpublic source/translation corpus, all derived reports embedding it, and source-specific reviewed-decision/reference fixtures are omitted. Original local files remain unchanged. Therefore the historical six-unit/eleven-scope real-input experiment, its nine real-copy controls, and some older corpus-specific tests cannot be fully rerun from this public backup. Synthetic regressions, the current translator test suite, and the complete Site suite remain supported verification targets.

The manifest covers original and generated files except itself. Matching hashes establish preservation, not model accuracy, production compatibility, or deployment status.
