---
name: vanillabp-adapter-building
description: How to build a VanillaBP BPMS adapter repository — module layout, adapter SPI implementation, Spring Boot and Quarkus registration patterns, adapter id vs. type, configuration, build order and documentation conventions. Use when creating or extending an adapter (Camunda 7, Camunda 8, Process-Engine-API, ZenBPM) or when writing prompts for adapter work.
---

# Building a VanillaBP Adapter (Version 2)

*Last checked against decision 70 of `adapter-platform-integration`, decision 23 of `camunda7-adapter`, decision 30 of `camunda8-adapter` and decision 12 of `process-engine-api-adapter`. A story which changes behaviour re-reads this skill and moves the anchor.*

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
- what an adapter repository brings, and the checklist before a pull request.

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
- The Camunda adapter repos will later **replace `main` of the existing GitHub repos**
  `vanillabp/camunda7-adapter` and `vanillabp/camunda8-adapter` (Camunda Community
  Hub; not under our control, no new repos possible there). Therefore: directory and
  artifact names must match those repos, and the Version-1 groupId
  `org.camunda.community.vanillabp` is kept.
- The Process-Engine-API adapter is a new repo (`process-engine-api-adapter`),
  groupId `io.vanillabp`.
- ZenBPM is built by its vendor, in a repository of its own and outside this workspace
  (decided 2026-08-28). What we owe that team is the guide named above, kept true.
- All adapter artifacts are versioned **2.0.0-SNAPSHOT** (aligned with
  adapter-platform-integration).
- After creating a new adapter repo, add it to the repository list in the workspace's
  `CLAUDE.md`.

## Build order and commands

```
io.vanillabp:spi-for-java:1.2.0-SNAPSHOT                     (user-facing annotations)
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

## C7-family portability rules (Operaton / CIB seven readiness)

The Camunda 7 adapter stays Camunda-7-only, but every line of it must stay **trivially
copyable** to the forks Operaton (`org.operaton.bpm.*`) and CIB seven
(`org.cibseven.bpm.*`) — both renamed all packages; the copy will be generated with
OpenRewrite later. Rules for ALL C7 adapter code:

- Write against `org.camunda.bpm` only; never mix in fork artifacts.
- Prefer **namespace-generic model-API reads** (`getAttributeValueNs(CAMUNDA_NS, ...)`
  with a single namespace constant) over typed extension getters — Operaton renamed
  those symbols (`getCamundaExpression()` → `getOperatonExpression()`), plain package
  renaming would not fix them.
- Keep engine access behind the adapter's own classes (no engine types leaking into
  shared/platform-neutral modules beyond the `BPMN` type parameter).
- Know the fork quirks for the later copy: CIB seven needs an explicit
  `com.fasterxml.uuid:java-uuid-generator` dependency (its FEEL engine does not pull it
  transitively); per-fork engine-spring artifacts (`operaton-engine-spring`,
  `cibseven-engine-spring-7`); fork Spring Boot baselines differ (Operaton 2.x = Boot 4,
  CIB seven ships a `-starter-4`).
- The whole C7 family is **JVM-mode only** on Quarkus (no native image) — decided.

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
- **A finding which is not this story's job becomes a roadmap line**, not a widened scope.
- **When the SPI contract itself changes, the author guide changes with it.** A story which
  changes what an adapter implements, calls back or promises is not done until
  `migration-adapter/ADAPTER-AUTHORS.md` says the new thing; the platform repository's
  `AGENTS.md` and `CONTRIBUTING.md` say so as well.
