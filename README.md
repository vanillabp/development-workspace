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
| `camunda7-adapter` | `vanillabp/camunda7-adapter` | vanillabp |
| `camunda7-adapter.wiki` | `camunda-community-hub/vanillabp-camunda7-adapter.wiki` | camunda-community-hub |
| `camunda8-adapter` | `vanillabp/camunda8-adapter` | vanillabp |
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

### GitLab integration is optional

GitLab integration kicks in only when **both** `glabHostname` **and**
`glabVersion` are non-empty in `devcontainers-config.json`. With either left
empty the spawn script:

- skips the `glab` install in the Dockerfile,
- skips the bind-mount of the host's glab-cli config,
- skips the git credential helper setup for the GitLab host,
- skips the glab-related section in the generated workspace README.

The mechanism is `__GLAB_BLOCK_START__` / `__GLAB_BLOCK_END__` marker
pairs in the heredoc templates inside `spawn-workspace.sh`. When enabled
just the marker lines are stripped (content stays); when disabled both
the markers and the content between them are dropped.

### IntelliJ run configurations

`dev-containers/runConfigurations/` holds the XMLs that end up in
`<new-workspace>/.idea/runConfigurations/`. The `runConfigs` array in
`devcontainers-config.json` lists which files get copied (in order). The XMLs
may use the placeholders for host ports defined in `devcontainers-config.json`
(e.g. `__PORT_4200__`, `__PORT_8080__`) — `spawn-workspace.sh` substitutes them
to the actual port-offsetted host ports when copying.

To add/change run configs:
1. Drop a new XML into `dev-containers/runConfigurations/` (or edit an existing one).
2. Add its filename to `runConfigs` in `devcontainers-config.json`.

*Hint:* To get an XML from an existing run configuration one can use the
`store as project file` feature:

![store as project file](dev-containers/readme/run-configuration-store-as-project-file.png)

**Avoid `$PROJECT_DIR$` in run config fields passed to external processes.**
In JetBrains Gateway's ijent/Eel mode (2025.x+), `$PROJECT_DIR$` expands to
a virtual Eel path (`/$devcontainer.ij/<hash>@/…`) which IntelliJ uses
internally but which real processes (JVM, shell) cannot resolve. Use
`__WORKSPACE_PATH__` instead — `spawn-workspace.sh` substitutes it to the
literal container path `/workspaces/<PROJECT_NAME>` when copying the XML.

### Optional initialization hook

If `dev-containers/initialize.sh` exists, `spawn-workspace.sh` copies it into
the new workspace's `.devcontainer/` and `post-create.sh` runs it **before**
the Maven warmup builds, with the workspace root as the working directory.

Use it for one-time setup that must precede Maven dependency resolution —
for example starting a Docker service that hosts an artifact proxy, seeding a
local registry, or pulling Docker images while the network is still available.

### Workspace welcome README

The README placed at each new workspace root (the "First-time setup" /
"Running the stack locally" steps) lives in `dev-containers/README.md.tpl`.
Edit it freely when porting — no changes to `spawn-workspace.sh` needed. It
uses the same `__PLACEHOLDER__` / `__GLAB_BLOCK__` mechanism as the other
templates (see `spawn-workspace.sh:substitute_placeholders`).

## Prerequisites

### Host machine

- **macOS** (tested) or Linux. Docker Desktop on macOS provides the
  bind-mount / ssh-agent forwarding magic the scripts rely on.
- **Docker Desktop** (or `docker` + `docker compose` plugin) running.
- **IntelliJ IDEA Ultimate** (≥ 2025.3) with **JetBrains Gateway** enabled
  for Dev Container connections.
- **Bash 4+** (macOS' default `/bin/bash` 3.2 is fine for the spawn script;
  newer is not required).
- **Git** with worktree support (any modern version).
- **`~/.ssh`** populated and (optionally) an ssh-agent running on the host —
  the container forwards the agent socket so passphrase-protected keys work
  without prompting.
- **`glab` login** (only needed when GitLab integration is enabled in
  `devcontainers-config.json`): `glab auth login --hostname <glabHostname>`. The
  config is bind-mounted into the container so the login flows in both directions.

### Workspace layout the scripts assume

```
<workspaces-root>/
├── <PROJECT_NAME>/                         ← source workspace (READ by spawn)
│   ├── dev-containers/                     ← this directory (lives in the source workspace)
│   ├── project-a/                    .git  ← each is a normal git repo (here: a submodule)
│   ├── project-b/                    .git
└── <PROJECT_NAME>-<branch-leaf>            ← created by spawn-workspace.sh
    ├── project-a/                    .git  (worktree of source)
    ├── …
    └── .devcontainer/                      DevContainer build + config
```

If any source repo is missing, the corresponding worktree is silently
skipped — the workspace still spawns with the rest.

### Resolving `<workspaces-root>`

Both scripts pick the workspaces root in this priority order:

1. **`--workspaces-root <path>`** CLI flag — highest priority, overrides everything.
2. **`$<PROJECT_SHORT>_WORKSPACES_ROOT`** environment variable — recommended for
   daily use (export once in your shell profile).
3. **Auto-detect** — walks up from the directory holding
   `devcontainers-config.json` to the directory named `<PROJECT_NAME>` (the
   source workspace) and takes its parent. Since `dev-containers/` lives inside
   the source workspace, that resolves the workspaces root with no configuration.

Each invocation prints the resolved target directory and asks for
confirmation before doing anything. Press Enter to accept, type `n` to
abort. Pass `--yes` (or `-y`) to skip the prompt in scripted runs.

## Usage

### Create a workspace

```sh
spawn-workspace.sh [--workspaces-root <path>] [--yes] <branch-name>
```

Base refs for new branches are not on the CLI — each repo brings its own
in the `repos` list (`{ "name": …, "baseRef": … }`) in `devcontainers-config.json`.

A `repos` entry with an **empty `baseRef`** (`"baseRef": ""`) is not a git repo:
no worktree is created — the host directory is bind-mounted into the workspace at
the same path instead. Use it for pre-built artifacts or other non-versioned
folders that must be visible/buildable in the container. Disposing the workspace
leaves the host source untouched.

Examples:

```sh
# Branch already exists locally or on origin -> reuses / tracks it
spawn-workspace.sh feature/PRJ-4711_example-story

# Brand-new branch: each repo forks from its own configured base ref
spawn-workspace.sh feature/PRJ-4711_new-story

# Point at a non-default workspaces directory (one-shot override)
spawn-workspace.sh --workspaces-root /opt/dev feature/PRJ-4711_new-story

# Same, but via env var (set it once in your shell profile)
export PRJ_WORKSPACES_ROOT=/opt/dev # PRJ is <PROJECT_SHORT>
spawn-workspace.sh feature/PRJ-4711_new-story

# Skip the confirmation prompt (CI / batch use)
spawn-workspace.sh --yes feature/PRJ-4711_new-story
```

Open the new workspace in IntelliJ via **JetBrains Gateway → Dev Containers →
From local project** and point it at the workspace's `.devcontainer/`
directory. Step-by-step first-time setup is in the generated workspace's
own `README.md`.

What it does:

1. Resolves the workspaces root (CLI flag → env var → auto-detect), then
   prints the target directory and prompts for confirmation. Aborts if you
   answer `n` or if the target already exists.
2. Computes the branch leaf (strips `feature/` etc.) → workspace name
   `<PROJECT_NAME>-<leaf>`.
3. Probes host ports and picks the lowest free
   multiple of 10000 as the **port offset** (so parallel stories never
   collide on host ports).
4. Creates one git worktree per source repo with the requested branch
   (reused, tracked, or — for brand-new branches — forked from the
   per-repo base ref defined in `REPOS`).
5. Writes a `.devcontainer/` (Dockerfile + devcontainer.json + post-create
   hooks) into the new workspace, plus `.idea/` (project name, JDK,
   run configs, README.md) and a per-story `.claude/` overlay. Read it
   to learn about host mounts and other details.
6. Sets `core.fileMode=false`, `core.autocrlf=input`, `core.checkStat=minimal`
   and `core.trustctime=false` in each source repo so the bind-mounted
   worktree doesn't trigger stale-stat rebase failures inside the container.

*Hint:* Read the head of the script for a detailed list of features and
their documentation.

### Dispose a workspace

```sh
dispose-workspace.sh [--workspaces-root <path>] [--force] [--delete-branch] [--keep-container] [--keep-image] [--yes] <target>
```

Examples:

```sh
# Default: refuse if any worktree is dirty, keep branch, remove container + volumes + image
dispose-workspace.sh feature/PRJ-4711_example-story

# Also delete the local branch from each source repo
dispose-workspace.sh --delete-branch feature/PRJ-4711_example-story

# Force-remove despite uncommitted changes (you lose them)
dispose-workspace.sh --force feature/PRJ-4711_example-story

# Leave the Docker container alone (IntelliJ still has it open)
dispose-workspace.sh --keep-container feature/FLOW-4711_example-story

# Remove container and volumes but keep the image layer cache for a faster next rebuild
dispose-workspace.sh --keep-image feature/FLOW-4711_example-story

# Use the Docker container name or ID instead of the branch
dispose-workspace.sh PRJ-FLOW-4711_example-story
dispose-workspace.sh a3f2b1c4d5e6

# Non-default workspaces root via flag or env var
dispose-workspace.sh --workspaces-root /opt/dev feature/FLOW-4711_example-story
PRJ_WORKSPACES_ROOT=/opt/dev dispose-workspace.sh feature/FLOW-4711_example-story  # PRJ = <PROJECT_SHORT>

# Skip the confirmation prompt
dispose-workspace.sh --yes feature/FLOW-4711_example-story
```

Accepts any of: full branch name (`feature/PRJ-…`), branch leaf (`PRJ-…`),
workspace directory name (`<PROJECT_NAME>-PRJ-…`), Docker container name
(`<PROJECT_SHORT>-PRJ-…`), or Docker container ID (hex, ≥12 chars).

What it does:

1. Checks every worktree for uncommitted changes. Aborts unless `--force`.
2. Removes each git worktree from its source repo's metadata.
3. Optionally deletes the local branch from each source repo.
4. Removes the Docker container `<PROJECT_SHORT>-<leaf>`, all its named
   volumes, and the devcontainer image (unless `--keep-container`; use
   `--keep-image` to skip only the image removal).
5. Removes the workspace directory.

*Hint:* Read the head of the script for a detailed list of features and
their documentation.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Spawn aborts: "Workspace already exists" | Previous spawn for the same branch | Dispose first, or pick a different branch |
| Container starts but Maven fails with `401 Unauthorized` | `~/.m2/setting.xml` does not include password for host or uses a variable not passed | Export the tokens variable (or `direnv allow`), then re-spawn |
| `git push` keeps prompting for username/password | `glab` not logged in on the host | `glab auth login --hostname XXXXXX` (host or container) |
| `git` keeps prompting for password *despite* `glab` being logged in and the helper printed via `git config` looking correct | Three glab × git × GitLab quirks stack: (1) container's `git` < 2.46 ignores the `authtype` capability glab advertises; (2) glab rejects `get` requests where `username=<x>` doesn't match its (empty) OAuth-login username; (3) GitLab expects `oauth2` as the HTTP Basic username for OAuth tokens, not the URL-embedded user. | New spawns: Dockerfile installs git ≥ 2.46, and `post-create.sh` installs a small `glab-creds.sh` wrapper that strips the input `username=`, drops the misleading `capability` line, and rewrites the output username to `oauth2`. Old containers: rebuild via "Rebuild Container" in Gateway, or run a fresh spawn. |
| `git rebase -i` aborts with "Your local changes would be …" | bind-mount stat drift in an existing source repo | `git config core.checkStat minimal && git config core.trustctime false` in the offending repo (new spawns get this automatically) |
| Project dropdown shows `<PROJECT_NAME> (Devcontainer: <id>)` after IDE restart | JetBrains Gateway 2026.1 ignores `frameTitle` pre-connect | Open the container once; the proper name is restored until the next restart |
| "Datei wurde extern geändert"-Dialog right after IDE save | bind-mount stat drift triggered by safe-write rename pattern | **HOST IntelliJ (ijent Dev Container mode):** Settings → Appearance & Behavior → System Settings → uncheck "Use 'safe write'", restart the IDE. Global, one-time, applies to every project. |
| `IllegalStateException` on EDT on first save (MavenUtil/EelProvider stack), then "Spotless applied" notification but file unchanged | Spotless Applier (Lipiridi 1.2.3) is not Eel-aware — its on-save service init calls Maven resolution on EDT, and its `-DspotlessIdeHook` argument leaks the `//$devcontainer.ij/...` virtual scheme into the in-container `mvn` process | Disable "Actions on Save → Run Spotless" for the remote project. Use IntelliJ's built-in Reformat / Optimize-imports on save and `mvn spotless:apply` before commit. |
| IntelliJ Database "Test Connection" fails with `RemoteJdbcServer … No such file or directory (os error 2)`, host JBR path + `/workspaces/...` cwd | ijent Dev Container mode: the Database plugin execs the **host** JBR path inside the container to introspect, but a macOS binary can't run on Linux → ENOENT. | Don't introspect in-container. Create an **SSH-tunnel data source** (tunnel → `localhost:<2222+offset>` user `vscode`; DB host `127.0.0.1:3307`); add `2222` to `hostPorts` in `devcontainers-config.json` to publish the tunnel port. See the generated workspace README "Database access". |

## Notes

- The scripts contain long header comments documenting every design decision
  (`spawn-workspace.sh` has the most). Read them when something surprises you.
- Self-references inside the scripts still use the old `bin/…` path. They
  are informational only — invocation works fine from any path.

## Noteworthy & Contributors

VanillaBP was developed by [Phactum](https://www.phactum.at) with the intention of giving back to the community as it has benefited the community in the past.

![Phactum](./readme/phactum.png)

## License

Copyright 2022 Phactum Softwareentwicklung GmbH

Licensed under the Apache License, Version 2.0
