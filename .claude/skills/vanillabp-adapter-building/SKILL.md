---
name: vanillabp-adapter-building
description: How to build a VanillaBP BPMS adapter repository — module layout, adapter SPI implementation, Spring Boot and Quarkus registration patterns, adapter id vs. type, configuration, build order and documentation conventions. Use when creating or extending an adapter (Camunda 7, Camunda 8, Process-Engine-API, ZenBPM) or when writing prompts for adapter work.
---

# Building a VanillaBP Adapter (Version 2)

*Last checked against decision 93 of `adapter-platform-integration`, decision 23 of `camunda7-adapter`, decision 30 of `camunda8-adapter` and decision 12 of `process-engine-api-adapter`. A story which changes behaviour re-reads this skill and moves the anchor.*

## The SPI itself is described once, and not here

`adapter-platform-integration/migration-adapter/ADAPTER-AUTHORS.md` is the guide for adapter
authors, written for a team without access to this workspace. It carries what an adapter
implements and what that costs when answered wrongly:

- what an adapter is and what belongs to the core instead;
- `AdapterDeploymentService` along its pipeline and `MigratableProcessService` with its handler
  per operation;
- `AdapterCollaborators`, the wiring calls due in `wireBpmn`, and the ones due at the end of
  `deployResources`;
- what an awareness probe promises (scope, never advancing, `UNKNOWN_TO_BPMS` against
  `BPMS_UNAVAILABLE`, the redispatch probe, `canLocateWorkflows()`), and where the core waits;
- what may never be assumed about threads, deliveries and ordering;
- registration on Spring Boot and on Quarkus, with the dummy adapters as templates;
- which VanillaBP artifacts an adapter depends on, imported through `io.vanillabp:vanillabp-bom`
  with one version property, and the part descriptor which pairs an adapter with a platform;
- what an adapter repository brings, the floor the platform really enforces, and the checklist
  before a pull request.

The floor is worth knowing before you plan a story, because it is what decides whether something is
mandatory. It holds five things: the five mandatory collaborators, the seven `PhaseOperation`s which
are `requiredOfEveryAdapter()`, the part descriptor, the platform's registration (a Quarkus
capability respectively an `AdapterConfigurationBase` bean), and the wiring calls which let the core
check the `@WorkflowTask` methods. Nothing else ends a boot from the platform's side.

Everything above that floor is the adapter's own judgement, and the Process-Engine-API adapter
proves it: no registered deployed version, no version catalog, no open-task probe, no health check,
and it boots. So a story which says an adapter "must" do something outside the floor is saying what
we want rather than what is checked, and it should be worded that way.

**Read that document for all of it.** This skill keeps only what an agent working IN this
workspace needs on top: which repositories are here, how they are built, and how a prompt for
adapter work is cut. Where the document and this skill disagree, the document is measured against
the code and wins; fix the skill in the same story.

Read `vanillabp-concepts` (architecture, glossary) and `vanillabp-bpms-characteristics` (per-BPMS
traits) as well. The per-BPMS answers stay in the latter: the document describes the contract,
that skill describes what each engine can do about it.

## Repositories and workspace conventions

- Each adapter is an **own Git repository**, cloned as a sibling of
  `adapter-platform-integration` in the workspace root. Initialize with
  `git init -b main`.
- The Camunda adapters live in `vanillabp/camunda7-adapter` and `vanillabp/camunda8-adapter`.
  Version 2 is published as `io.vanillabp`; version 1 stays under the groupId
  `org.camunda.community.vanillabp` (decision 56 of `camunda7-adapter`). The artifact names
  changed too, and each adapter's `UPGRADE.md` lists the new coordinates.
- The Process-Engine-API adapter is a new repo (`process-engine-api-adapter`),
  groupId `io.vanillabp`.
- ZenBPM is built by its vendor, in a repository of its own and outside this workspace
  (decided 2026-08-28). What we owe that team is the guide named above, kept true.
- All adapter artifacts are versioned **2.0.0-SNAPSHOT** (aligned with
  adapter-platform-integration). The exception is an adapter with release lines: the
  Camunda 8 adapter publishes one snapshot per line, `2.0.0-<line>-SNAPSHOT` (e.g.
  `2.0.0-8.10-SNAPSHOT`), and the Business Cockpit's Camunda 8 adapter does the same with
  `0.9.0-<line>-SNAPSHOT`.
- After creating a new adapter repo, add it to the repository list in the workspace's
  `CLAUDE.md`.

## Build order and commands

```
io.vanillabp:spi-for-java:2.0.0-SNAPSHOT                     (user-facing annotations)
io.vanillabp:vanillabp-integration-spi:2.0.0-SNAPSHOT        (integration SPI, business code)
io.vanillabp:vanillabp-extension-spi:2.0.0-SNAPSHOT          (extension SPI)
io.vanillabp:vanillabp-adapter-spi:2.0.0-SNAPSHOT            (adapter SPI)
io.vanillabp:vanillabp-spring-boot-integration:2.0.0-SNAPSHOT   (spring-boot module)
io.vanillabp:vanillabp-quarkus-integration:2.0.0-SNAPSHOT       (quarkus runtime module)
io.vanillabp:vanillabp-quarkus-integration-deployment:2.0.0-SNAPSHOT (quarkus deployment module)
```

Build order: `spi-for-java` → `adapter-platform-integration` (`./mvnw install`) →
adapter repos (`mvn install`). `install` alone: it already runs every phase `verify`
has, and naming both compiles every module twice. Quarkus integration tests load their
modules from the local Maven repository, so `package` is not enough.

Copy the Spotless setup (`formatting_conventions.xml` + plugin config) from
adapter-platform-integration so formatting rules stay identical, and run
`mvn spotless:apply` before committing (it formats Markdown too).

A skeleton whose pipeline methods throw cannot complete a full boot: the core deployment runs
unconditionally at context start and calls `deployResources`/`startWorkflowProcessing` for every
(workflow module × prioritized adapter) even with zero BPMN files. Two proven ways to still test
adapter discovery:

- Spring: `@SpringBootTest` with
  `spring.autoconfigure.exclude=<the platform's DeploymentAutoConfiguration>`, or an
  `ApplicationContextRunner` which does not activate the deployment lifecycle.
- Quarkus: a skeleton wiring no deployment service boots fine (the JDBC outbox stays inactive
  without a datasource).

A test also needs a `META-INF/workflow-module` marker: startup enforces "at least one workflow
module". Everything else about tests is in `vanillabp-testing`.

## What an adapter takes from the BPMS

- **Only the plain Java client, or the engine API of an embedded engine.** The vendor's Spring
  Boot starter and Quarkus extension are not used. They are read for one thing: the names and
  the structure of their configuration properties, which the adapter offers per adapter id. So
  a starter built for another Spring Boot line is no dependency of the adapter, and a question
  about the baseline is asked of the engine or the client alone.
- **Engine events stay hidden.** The execution, task and history events of the engine do not
  reach the application, neither as Spring events (the `eventPublisherPlugin` of the Camunda 7
  starter) nor in any other way. What an application needs to know comes through VanillaBP
  (`@TaskEvent`, listeners). With the raw events an application could work around VanillaBP.
  So do not bring back a starter plugin only because version 1 had it: "defaults stay version 1"
  does not apply here, and the change gets one sentence in `UPGRADE.md` instead. A
  `ProcessEnginePlugin` bean of the application is still picked up by the Camunda 7 adapter,
  on purpose, although an application could register an event publisher that way.
- **A client upgrade brings its new options in the same pull request.** When a new client
  version adds builder or configuration options (for example new `CamundaClientBuilder` methods
  for client certificates), the same upgrade offers them as adapter keys under
  `vanillabp.adapters.<id>.*`, validated at startup, with README and wiki updated. A release
  line whose client lacks the option refuses the key with a message saying so. An option the
  client has and the adapter does not pass on is a gap for every user, so it is not parked as
  "a feature for later".
- **Retries exist only where the model sets them.** A job without explicitly modelled retries
  fails at once and raises an incident. This holds for tasks and for modelled listeners
  (decisions 83 and 87 of `camunda8-adapter`), as in version 1. The task may write somewhere,
  and then a silent default of three attempts repeats work which is not idempotent. So a new
  kind of job, a new adapter or a new default never brings an implicit retry count; a
  deviation needs a decision.

## Things this workspace found out the hard way

Not in the author guide, because they are about the engines and toolchains sitting in these
repositories rather than about the SPI.

- **Camunda 7 + Spring Boot 4:** `camunda-bpm-spring-boot-starter:7.24.0` targets Spring Boot
  3.5.x (via `camunda-parent`) and is incompatible with the VanillaBP-2 baseline (Boot 4.1).
  Depend on `org.camunda.bpm:camunda-engine` directly and wire the embedded engine yourself; do
  not fight the starter.
- **The C8 skeleton validated its configuration lazily** (`requireProperty` on first use). That
  is the anti-pattern `vanillabp-config-validation` names; do not copy it into new code.
- **The dummy adapter's `dummy-adapter.two-phase-commit` flag is a test toggle**, not a template
  for real adapter configuration.
- **A published class carries no Lombok and no MapStruct annotation** (decision 81 of
  `adapter-platform-integration`). Javadoc runs neither, so a configuration class with `@Getter` is
  published without a single accessor, and a code generator whose annotations reach the published
  POM puts its runtime library into every application which adds the adapter. Both tools stay
  welcome in tests and in build tools. The conversion of what exists is staged and not finished:
  136 files across the platform and the four adapter repositories, 85 of them carrying `@Slf4j`
  alone. Do not add a new one.
- **A BPMS without isolation of its own keeps the `BY_ADAPTER` default and refuses it while
  deploying**, with `scoping.validateNativeIsolationSupported`. Changing the default is the wrong
  fix: the default is version 1's behaviour and an application upgrading has to find its running
  workflows. The consequence is that every application on such an adapter configures
  `name-clash-avoidance` explicitly, which belongs on the first page of that adapter's wiki.

## C7-family portability rules (Operaton / CIB seven readiness)

The Camunda 7 adapter stays Camunda-7-only, but every line of it must stay **easy to
generate** for the forks Operaton (`org.operaton.bpm.*`) and CIB seven
(`org.cibseven.bpm.*`). Both renamed all packages. The fork adapters are generated from the
C7 source with OpenRewrite into repositories of their own (`cibseven-adapter` and
`operaton-adapter`, each taking the C7 code only through its `bin/sync-from-camunda7.sh`).
Rules for ALL C7 adapter code:

- Write against `org.camunda.bpm` only; never mix in fork artifacts.
- Read BPMN extension attributes with the **typed getters** (`getCamundaExpression()`,
  `getCamundaFormKey()`, ...), not with `getAttributeValueNs(CAMUNDA_NS, ...)`. Operaton has
  its own namespace `operaton:` and treats `camunda:` as an alternative. Its typed getters
  (renamed by its recipe to `getOperatonX()`) read both namespaces; a raw read of
  `CAMUNDA_NS` misses every model drawn with the Operaton Modeler.
- When the adapter **writes** an extension element into a model (`camunda:in`,
  `camunda:properties`, ...), write it in the namespace its siblings already use. Operaton's
  engine reads `camunda:` children only if no `operaton:` child sits under the same parent, so
  one added `operaton:in` hides all `camunda:in` mappings of the modeller.
- Keep property names, paths and class names out of strings where a symbol can carry them
  (`camunda.bpm.enabled`, `/camunda`, plugin class names, schema script paths). A recipe
  renames symbols, not strings; each such string needs a rule or an overlay in the fork.
- Keep engine access behind the adapter's own classes (no engine types leaking into
  shared/platform-neutral modules beyond the `BPMN` type parameter).
- Know the fork differences the generation has to handle:
  - CIB seven 2.x moved the model API's extension classes to the package
    `org.cibseven.bpm.model.bpmn.instance.cibseven` (not `...instance.camunda`); class and
    getter names stayed. A plain package rename does not compile.
  - CIB seven 2.2 checks its own modeler tables (`MOD_*`); with a `table-prefix` the engine
    refuses to start unless `modelerEnabled` is `false`. Its webapp starter brings a webclient
    which needs a JWT secret.
  - Operaton uses the real `jakarta.el` API (EL 6, no `getFeatureDescriptors`); CIB seven
    follows with 2.3. Operaton renamed `AcquireJobsRunnable.MONITOR` to `monitor`.
  - Per-fork engine-spring artifacts (`operaton-engine-spring`, `cibseven-engine-spring-7`).
    The adapter uses neither fork's Spring Boot starter nor its Quarkus extension, so their
    Boot or Quarkus baselines do not bind the adapter.
  - `java-uuid-generator` is NOT needed: the adapter keeps the engine's `DbIdGenerator`.
- The whole C7 family is **JVM-mode only** on Quarkus (no native image) — decided.

### How a Camunda 7 change reaches the forks

The same holds for the Business Cockpit's forks (`business-cockpit-cibseven-adapter`,
`business-cockpit-operaton-adapter`), which follow the Camunda 7 extension.

- **Only through the sync script.** Code which comes from the Camunda 7 adapter reaches
  `operaton-adapter` and `cibseven-adapter` only by `bin/sync-from-camunda7.sh <camunda7-commit>`.
  It writes the branch `generated`, which is then merged into `main` with a merge commit, never a
  squash. The steps are in the section "Following the Camunda 7 adapter" of each fork's
  `CONTRIBUTING.md`. A change by hand is allowed only where the fork behaves differently, as a
  commit of its own with a test which fails without it. Nobody commits to `generated` by hand.
  Why: four changes were once ported into the Operaton adapter by hand, and the next sync then
  needed three merge corrections.
- **After a merge which changes Camunda 7 code**, wait for the green `main` run of the Camunda 7
  adapter, then run the sync. Several Camunda 7 merges can go into one sync. Where a fork has the
  workflow `sync-from-camunda7.yaml`, it runs every night and on demand.
- **A sync pull request waits for approval.** A pull request the workflow opens as
  `github-actions` does not start its build by itself: the run stays at `action_required`, and the
  pull request waits quietly while `main` may turn red. After every sync, look for open pull
  requests from `sync/` branches and approve their run
  (`gh api -X POST repos/<owner>/<repo>/actions/runs/<id>/approve`), then follow the steps in
  `CONTRIBUTING.md` and merge with a merge commit.
- **A recipe change can lose a race against the nightly sync.** A pull request which changes the
  recipe (`rewrite/*.yml` on `main`) carries its own `generated` commit, which is pushed with a
  fast-forward after the merge. If a sync runs before that merge, it writes `generated` with the
  OLD recipe from `main`, and the fast-forward no longer works. So after merging a recipe change,
  check `origin/generated`. If it moved on: run the sync workflow again with the same Camunda 7
  ref (it reads the recipe from `main`), merge `generated` with a merge commit into a NEW sync
  branch (the old branch name belongs to the open sync pull request, and the workflow fails when
  it pushes), open a pull request and close the old one. That merge changes no file.

## Cutting a prompt for adapter work

- **Name the SPI boundary, not the class.** A story says which duty of the adapter contract
  changes ("the adapter reports the elements which can produce a second token"), because the
  class serving it differs per adapter and moves.
- **One repository per story wherever possible.** An SPI change is its own story in
  `adapter-platform-integration`, merged and published as a snapshot, and only then do the
  adapter stories run. Adapter branches built against an unpublished SPI fail with
  `AbstractMethodError` or `NoSuchMethodError` and the failure looks like an adapter defect.
- **Say which platforms are in scope, and expect both.** A story which reaches only Spring Boot
  is unfinished; the exemplary end-to-end flow runs on both against the real engine.
- **Ask what the BPMS can actually do before deciding the shape.** Most adapter stories which
  went wrong went wrong because a capability was assumed. `vanillabp-bpms-characteristics` holds
  what is known per engine; anything beyond it is a probe to run, not a guess to write down.
- **A finding which is not this story's job becomes a GitHub issue**, not a widened scope.
- **When the SPI contract itself changes, the author guide changes with it.** A story which
  changes what an adapter implements, calls back or promises is not done until
  `migration-adapter/ADAPTER-AUTHORS.md` says the new thing; the platform repository's
  `AGENTS.md` and `CONTRIBUTING.md` say so as well.
