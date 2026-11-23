---
name: vanillabp-dev-environment
description: The working environment of the VanillaBP development workspace. Covers which repositories count and how their names differ between GitHub, the clones and Maven, the shell traps of the DevContainer and of Claude Code's Bash tool (`CDPATH`, `grep` being ugrep, the executable bit, `target` mounts, the MongoDB image), and memory with the rule of one BPMS cluster at a time. Use when you set up or check clones and remotes, when a shell command or a container behaves differently than expected, and before you start tests which need a BPMS cluster.
---

# The VanillaBP development environment

The `README.md` of `vanillabp/development-workspace` explains how to clone the workspace, build the
repositories in order and open a pull request. The file
`dev-containers/devcontainers-config.json` holds the settings of the DevContainer. This skill adds
what the environment does differently from what you would expect.

## Which repositories count

Old versions (1.x) of the Camunda 7 and Camunda 8 adapters lived in the Camunda Community Hub. Now
the repositories of the `vanillabp` organisation are the ones that count, for code, pull requests,
CI, nightly builds, releases and `DECISIONS.md`. The blueprints live in the organisation
`vanillabp-blueprints`. The table "Referenced repositories" in the workspace `README.md` lists the
remote of each submodule.

Before you state anything about a repository, check where its clone points:

```bash
git -C <repo> remote get-url origin     # must be github.com:vanillabp/<repo>
```

An older clone may still point to an old location. Then it shows a state which stopped moving,
and conclusions drawn from it are wrong. Point `origin` at the `vanillabp` repository and fetch.

### Names of the Business Cockpit adapters

| Where                    | Name                                                                          |
|--------------------------|-------------------------------------------------------------------------------|
| GitHub repository        | `vanillabp/business-cockpit-<bpms>-adapter`                                   |
| Workspace folder         | `business-cockpit-<bpms>-adapter`                                             |
| Maven group id           | `io.vanillabp.businesscockpit`                                                |
| Maven artifact ids       | `businesscockpit-<bpms>-adapter-parent` and other `businesscockpit-*` modules |

`<bpms>` is `camunda7`, `camunda8`, `cibseven`, `operaton` or `process-engine-api`. Each repository
has a wiki. The repositories were renamed from `businesscockpit-*`. GitHub forwards the old name
for Git, the web and the API, but not for GitHub Pages. Never create a new repository with an old
name, because that ends the forwarding. Only the CIB seven and Operaton adapters are submodules of
the workspace. Clone the others next to them when you need them.

## Shell traps

### `grep` in Claude Code's Bash tool is ugrep

In the Bash tool of Claude Code, `grep` is a shell function which runs the ugrep that comes with
Claude Code. It does not come from the DevContainer image or from a user profile. Check it with
`type grep`. Some options behave differently from GNU grep:

```bash
printf 'a\nb\n' | grep -qv a; echo $?            # ugrep: 1
printf 'a\nb\n' | /usr/bin/grep -qv a; echo $?   # GNU grep: 0
```

A script and a CI job run `/usr/bin/grep`, because the function is not exported. So an expression
which is right in the Bash tool can be wrong in a script, and the other way round.

- Write tests as `... | grep -q .` rather than `grep -qv`. That gives the same result in both.
- When you need GNU grep exactly, call `/usr/bin/grep` or `command grep`.
- Check every number you measure with a second command that works differently, for example `awk`
  or `wc -l`. A count once lost four hits because of `grep -qv`, and only a second count found it.

### `CDPATH`

The DevContainer image sets `CDPATH` to `.` and the workspace root, so `cd <repo>` works from
anywhere. It also breaks a Maven started by a relative path, for example a Maven 3.9 in a
sub-folder: it stops with
`Could not find or load main class org.codehaus.plexus.classworlds.launcher.Launcher`. Call Maven by
its absolute path, or clear the variable for that call (`CDPATH= <path>/bin/mvn ...`).

### New scripts lose their executable bit

Clones on a bind mount from the host have `core.fileMode=false`, because the mount does not pass
the file mode through. A new script then enters the index as `100644`, even after `chmod +x`. The CI
job which calls it cannot start it, and the error shows only on GitHub. After you add a script:

```bash
git config core.fileMode                 # false: the index ignores chmod
git update-index --chmod=+x <path>
git ls-files -s <path>                   # must show 100755
```

### `target` folders as mounts

With `repoMode` `worktree` or `clone` in `devcontainers-config.json`, the `target` folders are
named volumes. `mvn clean` cannot delete a mount and stops in the first module with "Failed to
delete", so the build never reaches the tests. Clean with

```bash
mvn clean install -Dmaven.clean.failOnError=false
```

which empties the folder and leaves the mount. Or delete the module `target` folders by hand and
build without `clean`. The default `repoMode` `container` clones inside the container and has no
such mounts. `findmnt -T <repo>/target` tells you which case you are in.

### The MongoDB image

A test container with `mongo:8.0` does not start on a Linux kernel 6.19 or newer
([SERVER-121912](https://jira.mongodb.org/browse/SERVER-121912)). The container stops right after
it started, and the failing test does not say why. It looks like a broken Testcontainers setup.
`mongo:8.2` and `mongo:9.0` start.

The pinned images live in `ContainerImages` of `test-utils` in `adapter-platform-integration`. A
test or a script you write for a measurement uses `ContainerImages.MONGODB`, and never types a
version. A machine which needs another version passes `-Dmongodb.image=<image>`.

## Memory and BPMS clusters

All containers of one Docker Desktop VM share its memory. The setting `vmRamSize` in
`devcontainers-config.json` only caps one container. It cannot give it more than the VM has. Each
DevContainer runs its own Docker daemon (Docker in Docker). So `docker ps` does not show the
clusters which another DevContainer runs, but they take memory from the same VM.

What things cost, as measured:

- A Camunda 8.8 cluster: 2 to 4 GB.
- A full `./mvnw test` of `adapter-platform-integration`: up to 6.3 GB. Its `CONTRIBUTING.md`
  says how many full builds a machine can run at once.

When memory runs out, the kernel kills the largest process, and that is often somebody else's
build. Claude Code warns before with "Local memory is contended" and stops runs. Sessions have died
in the middle of work this way.

**Rule: one cluster run at a time.** Start agents with cluster tests one after another, not in
parallel. Remove a cluster as soon as it is no longer needed.

### The cluster lock

Inside one DevContainer, cluster runs take a lock first:

```bash
flock /home/vscode/worktrees/cluster.lock <command that starts the cluster tests>
```

The file lives in the container, so it orders the agents of this container only. Agents in other
containers on the same VM do not see it.

`flock` is not a queue. When the lock is released, any waiting process may get it, and the one
which grabs again at once often wins. An agent with a series of measurements once got the lock four
times in a row, about 30 minutes each time, while others waited one and a half hours. So:

- An agent with several cluster runs checks before each further run whether others wait, and lets
  them go first:

  ```bash
  pgrep -af '[f]lock /home/vscode/worktrees/cluster.lock'
  ```

  The brackets keep `pgrep` from finding the shell which runs this check.
- Start at most two agents which need a cluster at the same time.
