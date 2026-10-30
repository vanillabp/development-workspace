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
  [`Phactum/dev-containers`](https://github.com/Phactum/dev-containers) and put on your PATH.

Everything else in the workspace is pulled in as a submodule. Sibling
directories that are **not** part of this repo (legacy repos
`blueprint-workflowmodule-*` and `vanillabp-camunda*`, and plain scratch dirs
such as `prompts*`, `dev-containers-blueprints`, `processengineapi-adapter`)
stay untracked by design — see `.gitignore`.

## From a bug to a pull request

Found a bug in VanillaBP? You can hand it to a coding agent.

1. Clone this repository as [Cloning](#cloning) shows.
2. Start your coding agent at the root of the workspace and describe the bug: what you did, what
   you expected and what happened instead. Claude Code picks up the skills in `.claude/skills`
   from there.
3. The agent builds a scenario which reproduces the bug, looks for the cause and fixes it. Then it
   pushes a branch and opens a pull request, the same way you would do it by hand. See
   [From a change to a pull request](#from-a-change-to-a-pull-request).
4. The VanillaBP team reviews the pull request and merges it.

If the bug is in a repository the workspace does not hold, the agent clones it next to the others.
Before it opens the pull request, the agent follows the `CONTRIBUTING.md` and the `AGENTS.md` of
the repository it changes.

The sections below describe the way without an agent. The agent takes the same steps.

## What you need

- A GitHub account.
- The GitHub CLI `gh`, logged in with `gh auth login`.
- Java 21 or newer, and Maven.
- Docker, for the tests which start a database or a Camunda 8 cluster in a container. The
  `CONTRIBUTING.md` of each repository says which of its tests need it.
- An SSH key in your GitHub account. The submodules are cloned over SSH. See
  [Check your SSH access](#check-your-ssh-access).

The [DevContainer](#devcontainer-tooling-dev-containers) below brings Java, Maven, Docker, the
GitHub CLI and Claude Code. You do not need it.

## Cloning

Clone with all submodules in one go:

```sh
git clone --recurse-submodules git@github.com:vanillabp/development-workspace.git
```

Now every VanillaBP repository is a folder of the workspace. You build them yourself, so you do not
need the published snapshots. [Using the published snapshots](#using-the-published-snapshots) is
for somebody who clones a single repository instead.

If you already cloned without `--recurse-submodules`, initialise them afterwards:

```sh
git submodule update --init
```

To later pull submodule updates and advance the recorded commits:

```sh
git submodule update --remote --merge   # fetch + fast-forward each submodule
```

Submodules record a specific commit of each referenced repo. For a recursive clone to succeed, that
commit must exist on the submodule's remote. So push your submodule work **before** you commit an
advanced pointer here.

### Check your SSH access

Before you clone, check that GitHub accepts your SSH key:

```sh
ssh -T git@github.com
```

GitHub answers `Hi <your-name>! You've successfully authenticated, but GitHub does not provide shell
access.` Then the clone works. If it answers `Permission denied (publickey)`, add a key to your
account first, as GitHub explains in
[Adding a new SSH key to your GitHub account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account).

## Building the repositories in order

Each repository builds on the one before it:

1. `spi-for-java`, the API an application uses.
2. `adapter-platform-integration`, the platform. It needs `spi-for-java`.
3. The adapters: `camunda7-adapter`, `camunda8-adapter` and `process-engine-api-adapter`. Each one
   needs `spi-for-java` and the platform.
4. The adapters `operaton-adapter` and `cibseven-adapter`. Each one needs `spi-for-java`, the
   platform and `camunda7-adapter`, because its module `migration-tests` runs the Camunda 7 adapter
   next to it.
5. `business-cockpit`. It needs `spi-for-java` and the platform. It also reads
   `Phactum/mongodb-changesets`, which is not part of the workspace and comes from GitHub Packages,
   so its build needs a token, see [Using the published snapshots](#using-the-published-snapshots).
6. The Business Cockpit adapters `businesscockpit-operaton-adapter` and
   `businesscockpit-cibseven-adapter`. Each one needs `business-cockpit`, the adapter of its BPMS
   and `camunda7-adapter`.

Build and install the repositories before the one you change. You may skip their tests:

```sh
(cd spi-for-java && mvn install -Dmaven.test.skip=true -DskipITs)
(cd adapter-platform-integration && ./mvnw install -Dmaven.test.skip=true -DskipITs)
```

`-Dmaven.test.skip=true` skips the unit tests, and `-DskipITs` skips the integration tests.
`-DskipTests` is not enough, because it does not stop the integration tests.

Then build the repository you change, with its tests. Its `CONTRIBUTING.md` says how. When you pull
new commits into a repository earlier in the order, install it again.

## From a change to a pull request

A submodule starts on the commit the workspace recorded, which may be behind `main`. So start your
branch from a fresh `main` of the repository you change:

```sh
cd camunda7-adapter
git switch main
git pull
git switch -c fix-message-correlation
```

Commit your change there. One pull request covers one repository. If your change touches two
repositories, open one pull request in each. The build of an adapter reads the published snapshot of
the platform. So a pull request in an adapter which needs a new platform change turns green only
after the platform pull request is merged and its snapshot is published.

Do not commit the moved submodule pointer in the workspace. A workflow moves the pointers to the
newest `main` of each repository once a day.

There are two ways to open the pull request. Which one is yours depends on whether you may push to
the repository.

### You can push to the repository

You are a member of the organisation, or the repository gave you write access. Push the branch to
the repository and open the pull request:

```sh
git push -u origin fix-message-correlation
gh pr create --fill
```

### You cannot push to the repository

Push to a fork of your own instead. Work in the workspace as above. When you are done, create the
fork and add it as a second remote of the submodule:

```sh
gh repo fork --remote=false
git remote add fork git@github.com:<your-account>/vanillabp-camunda7-adapter.git
git push -u fork fix-message-correlation
gh pr create --repo camunda-community-hub/vanillabp-camunda7-adapter \
  --head <your-account>:fix-message-correlation --fill
```

`gh repo fork` reads the repository from the remote `origin`, and the fork gets the same name.
`--remote=false` keeps `origin` as it is, so `git pull` still reads the original repository. The
table in [Referenced repositories](#referenced-repositories-submodules) shows the GitHub name of
each submodule.

### The license agreement of the Camunda Community Hub

`camunda7-adapter` and `camunda8-adapter` live in the
[Camunda Community Hub](https://github.com/camunda-community-hub). The Hub asks every contributor to
sign its [contributor license agreement](https://cla-assistant.io/camunda-community-hub/community)
(CLA). The other repositories do not ask for one.

You do not need to sign it in advance. On your first pull request in one of the two repositories,
the CLA assistant adds the check `license/cla` and writes a comment with a link. Open the link, sign
in with GitHub and accept the agreement. The check turns green. If it stays pending, use the
"recheck" link in the same comment.

### What the build of a pull request can do

The workflows start on `pull_request`. None of them uses `pull_request_target`. For a pull request
from a fork, GitHub runs the workflows with your code, but without the secrets of the repository
and with a token which can only read.

That is enough to build and test. The build reads the snapshots it needs from Maven Central, and
reading them needs no login. A pull request from a fork cannot publish anything. Only a push to
`main` publishes a snapshot.

There are three exceptions, because reading GitHub Packages needs a secret:

- `blueprints` reads the snapshots of the two Camunda adapters,
  which stay in GitHub Packages and need a token. So in the blueprints, the build of a pull request
  from a fork fails with HTTP 401 before it compiles your change. Say so in the pull request, and a
  maintainer takes it from there.
- `business-cockpit` reads `Phactum/mongodb-changesets` from GitHub Packages. Its build fails with
  HTTP 401 before it compiles your change.
- In `operaton-adapter`, `cibseven-adapter` and their two Business Cockpit adapters, the module
  `migration-tests` runs the Camunda 7 adapter, whose snapshots are only in GitHub Packages. The
  build of that module fails with HTTP 401.

Such a red build says nothing about your change. If your build failed this way, say so in the pull
request. A maintainer can push your branch to the repository, and there the build gets the secret.

Also, a maintainer approves the first run of the workflows for a contributor whose first pull
request this is in the repository. Until then, the checks wait.

## Using the published snapshots

This is for somebody who clones a single repository and does not want to build the ones before it.
In the workspace you need it only for `Phactum/mongodb-changesets`, which `business-cockpit` reads
and the workspace does not hold.

Every push to `main` publishes a `2.0.0-SNAPSHOT`. Most repositories publish it to the snapshot
repository of Maven Central, `https://central.sonatype.com/repository/maven-snapshots/`. Their
parent POM `io.vanillabp:release-parent` names that repository, and reading it needs no login.

Three registries are different. `camunda7-adapter` and `camunda8-adapter` publish their snapshots
to the GitHub Packages registry of their repository, and the Business Cockpit reads
`Phactum/mongodb-changesets` from GitHub Packages too. GitHub Packages asks for a login even for a
public package. So for these three you need:

1. A personal access token (classic) with the scope `read:packages` and nothing else. Create it
   under GitHub, Settings, Developer settings, Personal access tokens, Tokens (classic). GitHub
   Packages does not accept a fine-grained token here.
2. A `server` and a `repository` entry in your `~/.m2/settings.xml` for each registry, with the
   same `id`.

Put the entries into a profile which is not active by default. Otherwise a build of the workspace
could take a published snapshot instead of the one you just installed. Here is an example with the
token in an environment variable, so the file holds no secret:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd">

    <profiles>
        <!-- The published snapshots: -Pvanillabp-snapshots. Almost every repository deploys its
             snapshots to Maven Central. Three still use GitHub Packages: the Camunda 7 and the
             Camunda 8 adapter in the Camunda Community Hub, and Phactum/mongodb-changesets, which
             the Business Cockpit reads. GitHub Packages asks for a login even for public
             packages, so each of them has a server entry below. -->
        <profile>
            <id>vanillabp-snapshots</id>
            <repositories>
                <repository>
                    <id>central-snapshots</id>
                    <url>https://central.sonatype.com/repository/maven-snapshots/</url>
                    <releases><enabled>false</enabled></releases>
                    <snapshots><enabled>true</enabled></snapshots>
                </repository>
                <repository>
                    <id>vanillabp-camunda7-adapter</id>
                    <url>https://maven.pkg.github.com/camunda-community-hub/vanillabp-camunda7-adapter</url>
                    <releases><enabled>false</enabled></releases>
                    <snapshots><enabled>true</enabled></snapshots>
                </repository>
                <repository>
                    <id>vanillabp-camunda8-adapter</id>
                    <url>https://maven.pkg.github.com/camunda-community-hub/vanillabp-camunda8-adapter</url>
                    <releases><enabled>false</enabled></releases>
                    <snapshots><enabled>true</enabled></snapshots>
                </repository>
                <repository>
                    <id>phactum-mongodb-changesets</id>
                    <url>https://maven.pkg.github.com/Phactum/mongodb-changesets</url>
                    <releases><enabled>false</enabled></releases>
                    <snapshots><enabled>true</enabled></snapshots>
                </repository>
            </repositories>
        </profile>
    </profiles>

    <servers>
        <server>
            <id>vanillabp-camunda7-adapter</id>
            <username>your-github-username</username>
            <password>${env.GITHUB_PACKAGES_TOKEN}</password>
        </server>
        <server>
            <id>vanillabp-camunda8-adapter</id>
            <username>your-github-username</username>
            <password>${env.GITHUB_PACKAGES_TOKEN}</password>
        </server>
        <server>
            <id>phactum-mongodb-changesets</id>
            <username>your-github-username</username>
            <password>${env.GITHUB_PACKAGES_TOKEN}</password>
        </server>
    </servers>

</settings>
```

Then build with the profile:

```sh
export GITHUB_PACKAGES_TOKEN=<your token>
mvn -Pvanillabp-snapshots install
```

Keep only the repositories you need. An adapter needs `spi-for-java` and the platform. The platform
needs `spi-for-java`. An application which tries an adapter needs that adapter as well. You need the
token only for the Camunda 7 adapter, the Camunda 8 adapter and the Business Cockpit. The modules
`migration-tests` of `operaton-adapter`, `cibseven-adapter` and their two Business Cockpit adapters
need the Camunda 7 adapter, too. The `CONTRIBUTING.md` of each one says how.

Take the account from the URLs above. The two Camunda adapters moved to `camunda-community-hub`.
Their old URLs `https://maven.pkg.github.com/vanillabp/camunda7-adapter` and
`https://maven.pkg.github.com/vanillabp/camunda8-adapter` still answer, but with an old snapshot
which no longer changes. A build against them stays green and tests old code.

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
| `operaton-adapter` | `vanillabp/operaton-adapter` | vanillabp |
| `operaton-adapter.wiki` | `vanillabp/operaton-adapter.wiki` | vanillabp |
| `cibseven-adapter` | `vanillabp/cibseven-adapter` | vanillabp |
| `cibseven-adapter.wiki` | `vanillabp/cibseven-adapter.wiki` | vanillabp |
| `business-cockpit` | `vanillabp/business-cockpit` | vanillabp |
| `business-cockpit.wiki` | `vanillabp/business-cockpit.wiki` | vanillabp |
| `businesscockpit-operaton-adapter` | `vanillabp/businesscockpit-operaton-adapter` | vanillabp |
| `businesscockpit-operaton-adapter.wiki` | `vanillabp/businesscockpit-operaton-adapter.wiki` | vanillabp |
| `businesscockpit-cibseven-adapter` | `vanillabp/businesscockpit-cibseven-adapter` | vanillabp |
| `businesscockpit-cibseven-adapter.wiki` | `vanillabp/businesscockpit-cibseven-adapter.wiki` | vanillabp |
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
internal design see the upstream [`Phactum/dev-containers`](https://github.com/Phactum/dev-containers) (its `README.md` and
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
