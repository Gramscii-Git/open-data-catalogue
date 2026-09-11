# Global engineering mantra

These are non-negotiable defaults for every repository and task. Do not
weaken, bypass, or reinterpret them silently. If an existing project conflicts
with them, surface the conflict before proceeding.

## Root-cause engineering

- Never introduce workarounds. Identify and fix the actual cause.
- Never introduce fallback behavior, especially silent or automatic fallbacks.
  Required failures must remain explicit, actionable, and observable.
- Never hide incomplete behavior behind defaults, compatibility branches,
  retries, placeholders, mocks, or temporary scaffolding.
- Never claim completion while a relevant test, lint, build, migration, or
  runtime check is failing.
- Never retain obsolete implementations, compatibility branches, version adapters,
  or duplicate behavior to support an older release. Update dependent callers to
  the current contract together.
- Never impose artificial timeouts or arbitrary elapsed-time cutoffs on valid
  work. Diagnose slow or stalled execution at its cause. Any necessary deadline
  must follow an actual protocol or lifecycle requirement, be justified by
  evidence, and live in validated external configuration. An elapsed deadline
  records incomplete work; it never proves missing source data or semantic error.

## Runtime ownership and deployment

- Deployed services run the current coordinated, verified release. A changed
  checkout, installed package, or successful build does not prove that a running
  process loads that release. Verify its actual revision, configuration, endpoint,
  and functional health.
- Every server, worker, subprocess, and model process has an explicit owner and
  lifecycle. Stop and reap owned superseded processes and verify child cleanup
  and listener release. Never leave stale, duplicate, or orphan servers running.
- Prepare and verify the successor before a coordinated cutover. Complete the
  running-service checks before declaring installation or deployment complete.
  Never retain an older server as a compatibility path or automatic fallback.

## No hardcoded product knowledge

- Never hardcode values that belong to configuration, deployment, domain,
  language, model, policy, content, credentials, endpoints, thresholds, UI
  copy, or user data.
- Keep variable behavior in explicit external configuration or content files
  with validated schemas.
- Named constants in code are reserved for genuine program invariants, never
  as a disguise for configuration or domain knowledge.
- Missing required configuration is an error. Do not invent a default or
  recover through a fallback.

## Prompt contract

- Every generative prompt lives in its own external English Markdown file.
  Never embed prompt prose in source code and never assemble a hidden prompt
  from inline fragments.
- Every prompt receives explicit `source_language` and `output_language`
  values through named placeholders.
- Every prompt that reads or reasons over documents also receives an explicit
  `document_category` value. This is the category recorded when the document
  is uploaded; it is never guessed later.
- Validate required prompt placeholders when loading the prompt. A missing
  prompt, placeholder, language, or document category is an explicit error.
- Never provide an inline, generic, or language-specific fallback prompt.

## Language and comments

- Source code, identifiers, comments, docstrings, logs, engine messages, and
  technical configuration are written in English.
- User-facing languages live in external translation or workspace content,
  never in engine code.
- Every comment and docstring uses present tense and accurately describes what
  the current code does. Explain only the responsibility, invariant, constraint,
  or reason that the code cannot express clearly by itself.
- Never write historical comments: no change narrative, dates, former
  behavior, bug-fix story, migration diary, or comparison with an older
  implementation. Version control is the history.
- Keep comments brief, precise, and non-verbose. Do not restate obvious code.

## Code shape

- Prefer direct, compact code with clear names and explicit data flow.
- Avoid verbose implementations, duplicated logic, speculative abstractions,
  unnecessary wrappers, and commentary that compensates for unclear code.
- Each function, component, module, and directory has one coherent
  responsibility and a clear reason to exist.
- Do not create enormous source files. Split growing files at real domain and
  responsibility boundaries into cohesive components and modules.
- Do not fragment code into trivial files merely to reduce line counts. The
  boundary must improve ownership, navigation, testing, or dependency flow.

## Repository organization

- Keep every directory predictable, clean, and easy to navigate.
- Place files by domain and responsibility, using consistent names and a
  shallow structure where possible.
- Keep generated artifacts, caches, runtime state, local secrets, temporary
  files, dead code, duplicate implementations, abandoned scaffolding, and
  unrelated assets out of source directories and version control.
- Before adding a new file, identify its owning module and public boundary. If
  no clean location exists, improve the structure instead of adding clutter.
- Preserve a clear dependency direction and avoid circular ownership between
  modules.

## Verification

- Protect behavior with focused tests that exercise the real contract and the
  root cause, not the implementation accident.
- Run the relevant tests, lint, type checks, builds, migrations, and runtime
  checks after changes.
- Keep verification deterministic and isolated so concurrent runs do not share
  mutable databases, ports, files, caches, or process state unless that sharing
  is the behavior explicitly under test.

## Publisher verification

- Verification runs locally. GitHub hosts code, history and pull requests;
  GitHub Actions is disabled for this repository. Do not add or enable hosted
  or self-hosted Actions workflows.
- Before merging, run the applicable local gates documented in README.md on
  the final change, including integration changes. Record the tested commit,
  commands, platform, results and any checks not run in the pull request.
- Keep verification isolated from active publication jobs and other sessions.
  Do not modify files that a running job reads.
- Missing remote checks do not waive local verification or certify an untested
  platform. Never claim completion while a relevant check is failing.
