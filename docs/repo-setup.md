# Repository setup

Template repositories copy files only, not settings. After creating a repo from this template, apply the settings below.

## Automated

```bash
python scripts/apply_repo_settings.py            # current repo
python scripts/apply_repo_settings.py owner/repo # a specific repo
```

This configures squash-only merging, delete branch on merge, the `skip-changelog` label, secret scanning with push protection, Dependabot alerts and security updates, CodeQL default setup, and the `main` ruleset from `.github/rulesets/main.json`. Requires the `gh` CLI with admin rights.

## Releases and package managers (optional)

Nothing here is needed to start. When you want installers published, or Homebrew, Scoop and winget updated on each release, add the repository variables and the `PACKAGE_MANAGER_TOKEN` secret described in [releasing](releasing.md). They are off until set.

## Protections

| Setting | Value | How |
| --- | --- | --- |
| Dependency graph | On | Default for public repos |
| Dependabot alerts | On | Script |
| Dependabot security updates | On | Script |
| Secret protection | On, with push protection | Script |
| CodeQL | Default setup | Script |
| Malware alerts | On | Manual: Settings > Advanced Security |
| Copilot Autofix | Off | Manual: Settings > Advanced Security > CodeQL |
| Private vulnerability reporting | On | Manual: Settings > Advanced Security |

## Ruleset `main` (default branch)

- Restrict deletions and block force pushes
- Require a pull request: dismiss stale approvals, require code owner review, require conversation resolution, squash merge only
- Require status checks to pass (`ci` and `dependency-review`), with branches up to date
- Require code scanning results (CodeQL)
- Require deployments to succeed: included with no environments, so it does nothing until you list one
- Require code quality results: enable manually in the ruleset UI, as it is not included in the JSON

Repository admins can bypass the ruleset through a pull request. This lets a solo maintainer merge despite the code owner requirement, since authors cannot approve their own PRs. Remove the bypass actor in `main.json` if you have more maintainers.

## Manual steps

- Tick **Template repository** on this repo (Settings > General).
- Run the **Init** workflow (Actions tab) with a short name and a display title; it replaces the template owner and repository name and renames the example packages and commands. Merge its pull request, then delete `.github/workflows/init.yml`. It requires "Allow GitHub Actions to create and approve pull requests", which the settings script turns on. If the owner is an organization, change `.github/CODEOWNERS` to a team.
- Fill in the contact method in `CODE_OF_CONDUCT.md`.
- Run `pre-commit install --hook-type pre-commit --hook-type post-commit` locally (the post-commit type is needed for Sweepito cleanup).
- CodeQL default setup only works once the repo contains a supported language, so run the script after adding code.

## Files to delete after setup

Some files only exist to start a repository. Once you have used them, remove them in a normal pull request:

| File | When |
| --- | --- |
| `.github/workflows/init.yml` | After you have merged Init's pull request. It cannot delete itself, because a workflow's own token may not change workflow files. |
| `scripts/init_template.py` | Nothing to do: Init's pull request already deletes it. |
| `scripts/apply_repo_settings.py`, `.github/rulesets/main.json` | Optional, once the settings are applied. Keep them if you want to re-apply the settings or recreate the repository. |

Do **not** delete these, although they look like template helpers. Workflows run them:

| File | Used by |
| --- | --- |
| `installer/` (including `installer/scripts/build.py`) | `ci-installer.yml`, `release-installer.yml` and the `project-info` action |
| `packages/api/scripts/export_openapi.py` | `ci-api.yml`, which checks `packages/api/docs/openapi.json` is current |

## Parts you may not need

The template has more layers than most projects use. Delete a layer together with everything that belongs to it, and the matching lines in `README.md` and `docs/`:

| If you do not need | Delete |
| --- | --- |
| The Windows window | `packages/ui/`, its entries in the root `pyproject.toml` (workspace members, sources, dev group), the `ui` product in `installer/build.toml`, `ci-ui.yml`, `audit-ui.yml`, `security-ui.yml` and the `ui` jobs and outputs in `ci.yml`, `security.yml`, `audit.yml`, `changes.yml` and `ci-installer.yml` |
| The HTTP API | `packages/api/`, `api-compat.yml`, `ci-api.yml`, `audit-api.yml`, `security-api.yml` and their entries as above (the window needs the API, so remove the window first) |
| Installers | `installer/`, `brand/`, `ci-installer.yml`, `release-installer.yml`, the installer actions (`install-installer-tools`, `test-linux-packages`, `test-windows-installer`, `project-info`) and the `installer` entries in `ci.yml`, `changes.yml` and `release.yml` |
| The command line | `packages/cli/` and the matching workflows and entries (the installers are built from it, so remove them too) |

After removing a layer, run the checks (`uv lock`, `pre-commit run --all-files`), since the names the scripts read must still exist.
