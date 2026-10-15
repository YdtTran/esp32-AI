# Git workflow and commit conventions

## Start every session with synchronization

Before editing, read the applicable project guidance and inspect the repository:

```powershell
git status --short --branch
git remote -v
git fetch origin
git branch -vv
```

Fetch the latest remote state even when local files have edits; fetching does
not merge into the working tree. If fetching fails, report the failure and the
stale upstream state before making changes that depend on it.

For a clean branch with an upstream, inspect its relationship to upstream:

```powershell
git log --oneline --left-right 'HEAD...@{upstream}'
git pull --ff-only
```

Quote the upstream expression to avoid shell interpretation. Use the configured
upstream rather than assuming every
branch tracks `origin/main`. For a new branch without an upstream, fetch first
and choose its base explicitly, normally the current `origin/main`.

If the working tree is dirty, preserve and identify those changes before any
pull, switch, merge or rebase. Do not automatically stash, commit or discard
someone else's work. Continue only with changes that can coexist safely; request
input if ownership or integration is ambiguous. If branches have diverged,
inspect both sides and resolve intentionally. Do not replace `--ff-only` with a
forced reset or silently rewrite published commits.

## Keep changes focused

- Keep one coherent feature, fix or maintenance change per commit. Include its
  necessary tests and documentation. Split independent changes into separate
  commits.
- Preserve edits belonging to other tasks. Stage explicit paths or selected
  hunks; avoid `git add .` when unrelated work exists.
- Review filenames and staged content for credentials, real environment files,
  model weights, recordings and generated output. Keep these out of Git using
  the project's ignore rules.
- Use a descriptive branch such as `feat/voice-status` or `fix/speaker-output`
  for isolated work when appropriate. Respect an existing task branch and any
  explicit request to work directly on `main`.

## Commit completed, verified work

Once a feature or fix meets its acceptance criteria and affected checks pass,
commit it before reporting it as working. This instruction authorizes routine
local commits for completed task-owned work without another confirmation.
Run `python scripts/validate.py` and the affected module checks described in
[development.md](development.md), then inspect:

```powershell
git diff --check
git diff
git add path/to/changed-file path/to/related-test
git diff --cached --check
git diff --cached
git commit -m "fix(models): restore optional speaker output"
git status --short --branch
```

Do not skip failing checks or bypass hooks to make a completion claim. Diagnose
failures caused by the change. Record pre-existing failures separately. If a
required check cannot run, state why and describe the actual verified scope;
do not call hardware or live-service behavior working based on host tests.
An explicitly requested checkpoint may be committed with its incomplete status
clearly recorded, but it is not completed, verified work.

Report the commit hash, what changed, exact validation commands and material
limitations. A local commit, a push, passing CI and deployment are separate
states. Never describe a change as pushed or deployed without verifying it.

## Conventional Commit messages

Use this header format:

```text
<type>(<optional-scope>): <description>
```

Use a concise imperative description, starting lowercase and without a final
period. Scope names identify affected areas, for example `firmware`, `models`,
`contracts`, `thingsboard`, `infra` or `ci`; issue identifiers are not scopes.

| Type | Purpose |
| --- | --- |
| `feat` | Add, change or remove an application capability |
| `fix` | Correct application behavior |
| `refactor` | Restructure code without changing behavior |
| `perf` | Improve performance without changing intended behavior |
| `style` | Change formatting without changing behavior |
| `test` | Add or correct tests |
| `docs` | Change documentation only |
| `build` | Change build tooling, dependencies or build configuration |
| `ops` | Change deployment, infrastructure, CI/CD or operations |
| `chore` | Perform repository maintenance, including ignore rules |

Examples for this project:

```text
chore: init
chore: ignore generated recordings
fix(models): restore optional speaker output
build(firmware): expand factory application partition
docs: define git workflow and commit conventions
```

Add a body after a blank line when motivation or previous behavior helps a
reviewer. Add issue references such as `Closes #123` in a footer after another
blank line. A breaking interface change requires `!` before the colon and a
`BREAKING CHANGE:` footer explaining the impact and migration:

```text
feat(contracts)!: change speaker audio encoding

Describe the reason for the new encoding and the previous behavior.

BREAKING CHANGE: update both firmware and inference producers to the new
contract version before deployment.
```

Keep standard Git-generated merge and revert subjects. Existing published
commit subjects are historical; do not rewrite them just to apply this policy.
For releases, breaking API/UI changes require a major version, compatible
features a minor version, and other release changes a patch version. Contract
versioning must also follow [the contract procedure](../contracts/README.md).

## Publish and handle concurrent updates

Push when the user requests publishing or the active task already authorizes it.
Before pushing, fetch again and check for concurrent upstream updates. If the
remote advanced, integrate without discarding local or remote changes, resolve
conflicts by reviewing intended behavior, and rerun affected checks. Stop for
input if conflict resolution requires an unresolved product decision.

```powershell
git fetch origin
git push
```

For a new branch, set its upstream explicitly with `git push -u origin <branch>`.
After publishing, verify remote state and inspect CI when available. Report any
pending or failed checks. Do not force-push, amend published history, delete
branches or tags, or use destructive resets without explicit authorization.

These conventions are project guidance; no Git hooks are installed by this
document.

Reference: [Conventional Commits specification](https://www.conventionalcommits.org/en/v1.0.0/).
