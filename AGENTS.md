# Verification

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
