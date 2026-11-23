---
name: vanillabp-maven-builds
description: Maven traps of the VanillaBP repositories and how to avoid them. Covers the Maven version (3.9, not 3.10), the flags `-am`, test skipping and `clean`, Quarkus tests, Spotless, the Javadoc gate, the shared `~/.m2` with its snapshots, and releases to Maven Central with their monthly limits. Use before you run a local Maven build, when a build fails with an error your change cannot explain (`NoSuchMethodError`, `cannot find symbol` on code that exists on `origin/main`, mass failures of Quarkus tests), and before you plan a release.
---

# Maven builds in the VanillaBP repositories

The build order of the repositories and the basic commands are in the `README.md` of
`vanillabp/development-workspace`. Each repository explains its own build in its
`CONTRIBUTING.md`. This skill adds the traps which cost time before, and the commands which avoid
them.

Most of these traps have one thing in common: the build fails, and the message points at your
code, but the cause is the Maven setup. Before you search your diff, check the setup.

The shared `~/.m2` and the published snapshots have a file of their own:
[shared-m2-and-snapshots.md](shared-m2-and-snapshots.md).

## Maven 3.9, not 3.10

Build with Maven 3.9. The workflows and the Maven wrappers use 3.9.16.

```bash
mvn -v                 # check the version before a long build
./mvnw install         # adapter-platform-integration and blueprints pin 3.9.16 in the wrapper
```

The `mvn` of the DevContainer image is 3.10. Where a repository has no wrapper, put a Maven 3.9.16
on the `PATH` and call it by its absolute path. A wrong path does not fail. It falls back to 3.10
without a word.

Why there are two separate breaks with 3.10:

- The Central Portal refuses the bundle that `central-publishing-maven-plugin` builds under 3.10:
  "Bundle has content that does NOT have a .pom file". The issue is
  [mavenplugins/central-publishing-maven-plugin#78](https://github.com/mavenplugins/central-publishing-maven-plugin/issues/78),
  still open. So every release and snapshot workflow has a step "Use Maven 3.9". A new repository
  which publishes to Maven Central needs that step from its first workflow on.
- Maven 3.10 writes `_remote.repositories` with a hashed repository key. The resolver inside a
  Quarkus test JVM is older and looks for the plain key `central`. It finds nothing it trusts and
  downloads everything again, about a thousand downloads per Quarkus job. Maven Central then throttles,
  and random jobs turn red. The fix for a later move to 3.10 is a line in `.mvn/maven.config`:
  `-Daether.system.trackingRepositoryKeyFunction=nid`.

All repositories stay on 3.9 until both are solved. Do not move one repository to 3.10 alone.

## Flags

**`-pl` needs `-am`.** A module build without `-am` takes its sibling modules from `~/.m2`, and
that copy can be days old. The error then names a constructor or method which exists on your
branch and on `origin/main`. That is the sign: the branch is fine, the build is not.

```bash
mvn verify -pl <module> -am
```

**Skipping tests.** `-DskipTests` does not stop the integration tests in these repositories, so a
quick `install` still starts Failsafe and with it a BPMS cluster. To install without any test:

```bash
mvn install -Dmaven.test.skip=true -DskipITs
```

Why: two agents once started clusters this way while another cluster was already running, and
the machine ran out of memory.

**`clean` after a changed signature.** When a method or constructor of the platform or SPI changes
its signature, build the dependent repositories with `mvn clean install`. Incremental compilation
only compiles changed source files. A class which calls the changed method, but did not change
itself, keeps its old `.class` file. The compiler says nothing, the build is green, and at runtime
you get a `NoSuchMethodError` on the OLD signature. If such an error names a signature which no
longer exists in the source, run `clean` first and do not search the source.

## Quarkus tests

Four traps, all of them look like failing tests.

**Use `install`, not `test` or `package`.** The Quarkus integration tests and every
`QuarkusProdModeTest` load the modules from the local Maven repository, not from the `target`
folders. After `package`, they test the jar of the last `install`. This also holds when you resume
with `-rf`. If a Quarkus test fails at startup although the source is right, check that the jar
in `~/.m2` holds your change:

```bash
unzip -l ~/.m2/repository/io/vanillabp/<artifact>/<version>/<artifact>-<version>.jar | grep <Class>
```

**A new local repository needs a fresh bootstrap.** A Quarkus module remembers the Maven repository
of its last build in `target/quarkus/bootstrap/test-app-model.dat`. After you change
`-Dmaven.repo.local`, delete `<module>/target/quarkus/bootstrap/` first. Otherwise nearly all
Quarkus test classes fail at startup with paths into the old repository.

**Name profiles with `-P`.** The resolver in the test JVM reads its options only from
`MAVEN_CMD_LINE_ARGS`, which holds the command line and `.mvn/maven.config`. It does not read
`MAVEN_ARGS`, and it ignores a settings profile which is activated by an environment variable
(`<activation><property><name>env.X</name>`). Maven itself resolves everything, and only the tests
fail with "Failed to collect dependencies of ...-deployment". So a profile that Quarkus tests need
goes on the command line. `bin/mvn_with_retry.sh` of the blueprints repository does this for
`-Psnapshots-from-github-packages`.

**Give `-s` an absolute path.** The same resolver reads a relative settings path relative to the
module folder. In the blueprints repository:

```bash
./mvnw -s "$PWD/.github/maven/settings.xml" install
```

In CI the path is absolute (`$GITHUB_WORKSPACE`), so the problem shows only locally.

## Spotless

Spotless formats Java, POMs, Markdown and YAML, and fails the build on a violation. Read its version
from the `pom.xml` of the repository, never from a note or an older command. An older version
once reported a green `main` as red, because it wanted to change the quotes in 18 OpenAPI files.

Where to run it depends on the repository:

- **Platform, adapters, Business Cockpit.** The plugin sits in the `<plugins>` of the root POM and
  runs in every module. Run `mvn spotless:apply` at the root without `-N` before every commit. A
  `-N` run covers POMs and Markdown only: the Java formatter reads the source folders of the module
  it runs in, and the root module has none. `-N` is fine only when the commit changes nothing but
  Markdown at the root.
- **Blueprints.** The plugin is declared in the root POM only, because a blueprint POM shows what an
  application needs and no build tooling. So a build with `-pl <blueprint>` never runs it, and the
  CI job on the root module fails. Run `./mvnw -N spotless:apply` at the root.

Two more rules:

- After a script (Python, `sed`) changed a Markdown file, run `spotless:apply` before the commit.
  A script once left one blank line too few at the end of `DECISIONS.md`, and the pull request
  turned red.
- Spotless merges two block quotes which follow each other directly into one. Before-and-after pairs
  then run into each other, and the build stays green. Put a short line of text between them.

## The Javadoc gate

The repositories run `maven-javadoc-plugin` with `failOnWarnings` set to `true`, and the parent POM
sets `doclint=all`. So any missing or wrong comment fails the build. Nobody checks Javadoc in
`src/test`. A class which moves from `src/test/java` to `src/main/java` enters the gate, and the
tests do not show it. A comment which starts with `@return`, or a record component without
`@param`, is enough to fail. Before you push such a class, run the phase the gate is bound to:

```bash
./mvnw package -pl <module> -am -DskipTests
```

The log must have no `warning:` line. Treat every missing comment as fatal, also on fields.

## What a test can know about the build

`${session.goals}` in the `systemPropertyVariables` of Surefire arrives as an empty string, because
Maven passes a list to a string parameter. `${session.goals[0]}` gives only the first goal. What
works is `${env.MAVEN_CMD_LINE_ARGS}`, which `mvn` and `mvnw` set to the whole command line. A test
which reads it treats an empty or unresolved value as "check as usual", never as "skip". A wrong
guess here does nothing and raises no error, so it is hard to find.

## Releases to Maven Central

How a release runs is described in the `README.md` of `vanillabp/maven-release-parent`. What to
keep in mind when you plan one:

- Maven Central counts per calendar month and namespace: files (signatures and checksums
  included), megabytes and deployments. The free tier is 1000 files, 80 MB and 7 deployments.
  The `io.vanillabp` namespace has been granted 2500 files, 100 MB and 9 deployments.
- One release of one repository is one deployment. An update of all repositories is 13
  deployments, about 1420 files and 26 MB. The deployment count is the tightest limit. The
  Business Cockpit Camunda 8 adapter alone costs three, one per release line.
- `deploymentName` only labels an upload. It does not merge anything. To bundle, each repository
  builds its bundle with `skipUpload` (property `central.skip.upload`, plugin 0.12.0), and
  `release-train.yaml` in `maven-release-parent` merges the bundles and uploads them once.
- The parent POM sets `<checksums>required</checksums>`, MD5 and SHA-1 only. The default `all`
  doubles the number of checksum files.
- Plan release waves in deployments, not in repositories. Check the usage at
  https://central.sonatype.com/publishing/usage before you start.

Rate limits of Maven Central while building are a CI topic, see the skill
`vanillabp-ci-and-github`.
