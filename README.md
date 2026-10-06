![](./readme/vanillabp-headline.png)

# VanillaBP development workspace

This repository is the **top-level git superproject** for the VanillaBP
development workspace. It bundles, as git submodules, the active VanillaBP
repositories, plus two things that are developed here directly:

- **`.claude/skills/`** — shared Claude Code skills for working on VanillaBP.
- **`dev-containers/`** — the project-specific configuration
  (`devcontainers-config.json`) for the tooling that spins up one **isolated
  IntelliJ DevContainer per story** on top of this multi-repo workspace. The
  scripts themselves are **not** checked in here; they are cloned once from
  `Phactum/dev-containers` and put on your PATH.

Everything else in the workspace is pulled in as a submodule. Sibling
directories that are **not** part of this repo (legacy repos
`blueprint-workflowmodule-*` and `vanillabp-camunda*`, and plain scratch dirs
such as `prompts*`, `dev-containers-blueprints`, `processengineapi-adapter`)
stay untracked by design — see `.gitignore`.

## From a bug to a pull request

Found a bug in VanillaBP? You can hand it to a coding agent.

1. Clone this repository with `git clone --recurse-submodules` (see [Cloning](#cloning)).
2. Start your coding agent at the root of the workspace and describe the bug. Claude Code picks up
   the skills in `.claude/skills` from there.
3. The agent builds a scenario which reproduces the bug, looks for the cause and fixes it. Then it
   pushes a branch to your fork and opens a pull request from there.
4. The VanillaBP team reviews the pull request and merges it.

You need a GitHub account, the GitHub CLI logged in with `gh auth login`, a fork of the repository
you change (the agent can create it with `gh repo fork`), and Java 21, Maven and Docker for the
build. The [DevContainer](#devcontainer-tooling-dev-containers) below brings Java, Maven, Docker,
the GitHub CLI and Claude Code, but it is optional. The `CONTRIBUTING.md` of each repository says
the same in detail, for example the one of
[`adapter-platform-integration`](https://github.com/vanillabp/adapter-platform-integration/blob/main/CONTRIBUTING.md#from-a-bug-to-a-pull-request).

## Cloning

Clone with all submodules in one go:

```sh
git clone --recurse-submodules <this-repo-url>
```

If you already cloned without `--recurse-submodules`, initialise them
afterwards:

```sh
git submodule update --init
```

To later pull submodule updates and advance the recorded commits:

```sh
git submodule update --remote --merge   # fetch + fast-forward each submodule
```

Submodules record a specific commit of each referenced repo. For a recursive
clone to succeed, that commit must exist on the submodule's remote — so push
your submodule work **before** committing an advanced pointer here.

## Referenced repositories (submodules)

| Submodule | Remote | Org |
|-----------|--------|-----|
| `spi-for-java` | `vanillabp/spi-for-java` | vanillabp |
| `adapter-platform-integration` | `vanillabp/adapter-platform-integration` | vanillabp |
| `adapter-platform-integration.wiki` | `vanillabp/adapter-platform-integration.wiki` | vanillabp |
| `process-engine-api-adapter` | `vanillabp/process-engine-api-adapter` | vanillabp |
| `process-engine-api-adapter.wiki` | `vanillabp/process-engine-api-adapter.wiki` | vanillabp |
| `camunda7-adapter` | `camunda-community-hub/vanillabp-camunda7-adapter` | camunda-community-hub |
| `camunda7-adapter.wiki` | `camunda-community-hub/vanillabp-camunda7-adapter.wiki` | camunda-community-hub |
| `camunda8-adapter` | `camunda-community-hub/vanillabp-camunda8-adapter` | camunda-community-hub |
| `camunda8-adapter.wiki` | `camunda-community-hub/vanillabp-camunda8-adapter.wiki` | camunda-community-hub |
| `renovate-config` | `vanillabp/renovate-config` | vanillabp |
| `blueprints` | `vanillabp-blueprints/blueprints` | vanillabp-blueprints |
| `blueprints-organisation-page` | `vanillabp-blueprints/.github` | vanillabp-blueprints |

### Moving a submodule to another GitHub organisation

Submodule remotes are just URLs stored in `.gitmodules`, so an org migration is
a retroactive, low-risk edit. After the repo has moved (e.g. the `camunda*`
adapters relocating to a different org):

```sh
git submodule set-url <path> <new-url>   # rewrites .gitmodules
git submodule sync <path>                # applies it to .git/config
git add .gitmodules && git commit -m "chore: move <path> submodule to <org>"
```

The submodule's checked-out contents don't change — only where future
fetches/clones pull from.

---

# DevContainer tooling (`dev-containers/`)

Tooling to spin up one **isolated IntelliJ DevContainer per story** on top of
this workspace. The scripts are **not** checked in here — they are cloned once
from [`Phactum/dev-containers`](https://github.com/Phactum/dev-containers) and
put on your PATH. This repo only carries the project-specific configuration in
**`dev-containers/devcontainers-config.json`**.

Usage (run from the workspace root, with the scripts on your PATH):

```shell
spawn-workspace.sh feature/new-feature-branch
```

Each story gets:

- a sibling workspace directory `workspace/<PROJECT_NAME>-<leaf>/`
- one git worktree per source repo
- a Dev Container (Java 21 + Maven + Node + Docker-in-Docker) with a
  preselected JetBrains backend, pre-wired run configs, port offset to
  run several stories in parallel, and a shared Claude-Code memory mount
- all Maven repos are built to ensure all dependencies are available
- Claude plugin Caveman installed (mode full)

After work ist done, the worktree and the DevContainer can be removed using this command:

```shell
dispose-workspace.sh --delete-branch feature/new-feature-branch
```

## Files

Only project-specific files live here; the scripts come from the upstream clone
on your PATH.

| File / Directory                          | Purpose                                                          |
|-------------------------------------------|------------------------------------------------------------------|
| `dev-containers/devcontainers-config.json`| Project-specific config (names, repos, ports, base image, …)     |
| `dev-containers/README.md.tpl`            | Template for the welcome README placed at each new workspace root |
| `dev-containers/initialize.sh`            | Optional hook run before Maven warmup builds (create if needed)  |
| `dev-containers/runConfigurations/*.xml`  | IntelliJ run configs copied verbatim into each new workspace     |

Both scripts read `devcontainers-config.json` at startup. The full list of
configuration settings is documented in that file itself; for the tooling's
internal design see the upstream `Phactum/dev-containers` (its `README.md` and
the header comment in `spawn-workspace.sh`).

## Prerequisites

### Host machine

- **macOS** (tested), **Windows** (tested) or Linux. Docker Desktop provides the
  bind-mount / ssh-agent forwarding magic the scripts rely on.
- **Docker Desktop** (or `docker` + `docker compose` plugin) running.
- **IntelliJ IDEA Ultimate** (≥ 2025.3) with **JetBrains Gateway** enabled
  for Dev Container connections.
- **Bash 4+** (macOS' default `/bin/bash` 3.2 is fine for the spawn script;
  newer is not required) or **PowerShell** (on Windows).
- **Git** with worktree support (any modern version).
- **`~/.ssh`** populated and (optionally) an ssh-agent running on the host —
  the container forwards the agent socket so passphrase-protected keys work
  without prompting.

## Noteworthy & Contributors

VanillaBP was developed by [Phactum](https://www.phactum.at) with the intention of giving back to the community as it has benefited the community in the past.

![Phactum](./readme/phactum.png)

## License

Copyright 2022 Phactum Softwareentwicklung GmbH

Licensed under the Apache License, Version 2.0
