# The shared `~/.m2` and the published snapshots

Part of the skill [vanillabp-maven-builds](SKILL.md).

In the DevContainer setup of `vanillabp/development-workspace`, `~/.m2/repository` is a mount which
every container on the machine shares (see `dev-containers/devcontainers-config.json`, "the shared
.m2 cache mount is kept"). Several agents in one container share it too. So whatever one build
installs, every other build sees at once. That is fast, and it is the cause of most errors which
look like a broken branch.

## How to recognise it

The error names a class, method or constructor which:

- exists on `origin/main` of the repository that delivers it, and is missing in your build (the
  snapshot in `~/.m2` is too old), or
- does not exist on `origin/main` at all (somebody installed a branch).

Typical messages are `NoSuchMethodError`, `AbstractMethodError`, `NoClassDefFoundError`, and
`cannot find symbol` on a method that was just added. In both cases your code is not the cause, and
searching your diff costs time for nothing.

## A locally installed snapshot always wins

A snapshot which a build put there with `mvn install` counts as the newest, whatever the remote
repository has. `-U` (`--update-snapshots`) does not replace it. This holds both ways: it hides a
snapshot that is not published yet, so a local build compiles while CI fails, and it hides a newer
published one.

You can see it in the files next to the jar:

- `_remote.repositories` has a line ending in `>=` instead of a repository id.
- `maven-metadata-local.xml` has `<localCopy>true</localCopy>`.

```bash
grep -rlE '>=$' ~/.m2/repository/io/vanillabp --include=_remote.repositories
```

While other builds run on the machine, a local build of an adapter against the shared `~/.m2`
proves nothing. The build of the pull request starts with an empty repository on the runner, and
that is the honest test.

## Rules

**Never install into the shared repository while others may build.** Assume that another session
or agent is always building. A platform jar installed by hand once met an auto-configuration from
the published snapshot in another build. Two builds died with `NoSuchMethodError`, and both looked
like failing tests.

**Use a cold repository of your own** for anything you install or update:

```bash
mvn -Dmaven.repo.local=/home/vscode/worktrees/<name>-m2 install
```

It costs a full download once (a few hundred MB and some minutes). Keep it after the build; the
next build in the same area reuses it. After you switch to it, delete
`target/quarkus/bootstrap/` of the Quarkus modules, see the Quarkus section of the skill.

Two cheaper ideas do not work:

- A chained repository (`-Dmaven.repo.local` plus `-Dmaven.repo.local.tail`). The platform POM
  builds the Mockito agent path from `${settings.localRepository}`, and `quarkus-integration`
  passes the same value to the Quarkus tests as `maven.repo`. That value is the head of the chain,
  and Maven never puts the files of the tail there. `test-utils` then fails with
  `agent library failed Agent_OnLoad: instrument`.
- A hard-linked copy (`cp -al ~/.m2/repository ...`). When `~/.m2/repository` is a mount of its
  own, it fails with `Invalid cross-device link`. Check with
  `findmnt -T ~/.m2 -T ~/.m2/repository` before you try it.

**Keep the profile `vanillabp-snapshots` opt-in.** The `README.md` of the workspace shows the
profile which reads the published snapshots from Maven Central. It must not be active by default:
an active profile would pull a published snapshot over the one a build just installed, in the
middle of somebody else's run.

```bash
mvn -Pvanillabp-snapshots verify    # against the published snapshots
mvn verify                          # against what is installed locally
```

## Repairing the shared repository

If hand-installed or stale snapshots broke the shared repository, replace them with the published
ones. Delete the affected folders below `~/.m2/repository/io/vanillabp`, then fetch each
coordinate again (add `:pom` for a parent POM):

```bash
mvn -Pvanillabp-snapshots -U dependency:get -Dartifact=io.vanillabp:spi-for-java:2.0.0-SNAPSHOT
```

Afterwards `_remote.repositories` names a repository and a timestamped version instead of `>=`.
Then check the place where the damage showed, for example with `javap` on the restored jar. A new
timestamp alone proves nothing.

## Proving that something is published

Only an explicit request answers whether a published snapshot carries an artifact, for example
the sources:

```bash
mvn -B -Pvanillabp-snapshots -Dmaven.repo.local=<own repository> \
  org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get \
  -Dartifact=<group>:<artifact>:<version>:jar:sources
```

The own repository is required. If any build installed the artifact into the shared one,
`dependency:get` answers from there and reports success without asking the remote, also with
`-U`. Empty the subtree in your own repository before you check again.

Two things prove nothing:

- That no `-sources.jar` lies next to a downloaded jar. Maven fetches sources only on request.
- `*.lastUpdated` marker files. They say what somebody once asked for, not what is published.

## Which remote repository a build needs

A source of artifacts is needed when the build resolves one of its coordinates, directly or
through another module. Decide it by group id and artifact id, never by the name of a repository.
`io.vanillabp:spring-boot-support` is the 1.x line from the repository `spring-boot-support`, while
`io.vanillabp:vanillabp-spring-boot-support` is a module of `adapter-platform-integration`.

Measure it with a reactor build against an empty `-Dmaven.repo.local` and `-DskipTests -DskipITs`.
`-Dmaven.test.skip=true` resolves the same artifacts, test scope included. Do not use
`dependency:tree` on a reactor which is not built: it fetches the reactor's own modules from the
registry. A `grep` over the POMs sees only direct dependencies.

A rule taken from one output needs a second command before you pass it on. A wrong rule about
test skipping once came from an output cut off by `head`, and a `grep -c` disproved it.
