---
name: vanillabp-conventions
description: Development rules for implementing VanillaBP Version 2 features — use before writing or changing code in spi-for-java or adapter-platform-integration, covering module placement, compatibility constraints, build/test commands, formatting and documentation conventions.
---

# VanillaBP Development Conventions (Version 2)

*Last checked against decision 70 of `adapter-platform-integration` and decision 8 of `spi-for-java`. A story which changes behaviour re-reads this skill and moves the anchor.*

## Design rules (in priority order)

1. **Platform-neutral first.** New logic goes into
   `adapter-platform-integration/migration-adapter` (plain Java, no Spring/Quarkus
   dependencies). Platform integrations get only the thin glue: config loading, code
   scanning, bean creation. If you find yourself writing business logic in
   `spring-boot-integration` or `quarkus-integration`, stop and move it to the core.
2. **Both platforms, always.** Every feature must work in Spring Boot *and* Quarkus.
   Spring Boot uses runtime mechanisms (auto-configuration, BeanDefinitions,
   reflection scanning); Quarkus does the equivalent at build time (BuildSteps, Jandex
   index, Gizmo bytecode generation). Implement platform glue for both, plus tests for
   both.
3. **SPI compatibility.** Existing V1 applications must migrate to V2 without changes
   to their Java code (the `spi-for-java` API stays compatible). Configuration changes
   are allowed. Never break `io.vanillabp.spi.*` signatures; extend additively.
4. **Eventual consistency belongs to the core.** Remote BPMS (e.g. Camunda 8) may not
   know an instance yet. Handling this (retries, fallback to the next adapter in the
   prioritized list) is the migration adapter's job — never an individual adapter's.
5. **Extension SPI stays out of the core.** Extension-specific annotations/interfaces
   (e.g. Business Cockpit's `@UserTaskDetailsProvider`) live in the extension's
   `ExtensionWiringService.wireBpmn` implementation, not in VanillaBP itself.
6. **Mechanics shared by adapters and extensions live once, in the core.** Before an
   extension (the Business Cockpit commons or one of its BPMS halves) implements a
   mechanism, check whether the core already does the same or something close for the
   adapters: version ranges and tags (`VersionRange`, `ProcessVersions`), wiring of
   annotated methods (`HandlerContract`), configuration resolved over levels, the outbox
   store per aggregate, scoping of ids. If it does, generalize it there, in a platform
   story merged and published first, and let adapters and extensions use the one
   implementation. A second implementation in the extension is not acceptable where the
   generalization is possible with reasonable effort (decided 2026-09-08). The balance:
   an adapter or an extension must remain buildable without touching the core, so what
   is generalized is a mechanism which really is the same on both sides, never
   something BPMS-specific or specific to one extension; the SPI has to carry an ordinary
   extension as it is.

## Testing conventions

Strategy and patterns live in the `vanillabp-testing` skill — read it before writing
any test. Core points: feature/acceptance tests (E2E) first for everything
user-facing; integration tests for the rest; unit tests for edge cases; **>90%
instruction coverage per platform, measured separately** (Spring tests must not cover
Quarkus code), enforced by the `test-coverage-report/coverage-gate` module of every
repository, which also fails a build whose aggregates forgot a module producing
coverage data; adapters test primarily at the migration-adapter SPI boundary; every test class
uses `test-utils` (`SuppressOutputExtension` etc.). Platform tests use the **dummy
adapter** (and, for Spring, the dummy extension) instead of a real BPMS; MongoDB/C8
tests use Testcontainers. Quarkus log suppression: see
`quarkus-integration/README.md`, section "Logging during tests".

## Build & verify

```bash
# Build order matters: spi-for-java before adapter-platform-integration.
cd spi-for-java && mvn install
cd adapter-platform-integration && ./mvnw install           # install, NOT package:
                                                           # Quarkus ITs load modules
                                                           # from the local Maven repo

# Single unit test / single integration test
mvn test -pl <module-path> -Dtest=TestClassName
mvn verify -pl <module-path> -Dit.test=ITClassName

# Formatting (Spotless fails the build on violations)
mvn spotless:apply
```

`install` alone, never `install verify`: install runs every phase verify has, so
naming both walks two lifecycles per module. The tests skip their second run, the
compiler does not, and every warning is then reported twice.

Deprecating with `forRemoval = true` obliges the same commit to add
`@SuppressWarnings("removal")` to every implementation and every call site which is
meant to stay until the removal. The `removal` lint is mandatory, and `@Deprecated`
on an overriding method does not silence it, so without the suppression the
deprecation shows up in every later build and hides the next real one.

Java 21 for adapter-platform-integration; `spi-for-java` targets Java 17. Fluent API
calls with more than one method call: one line per call (Spotless-enforced). Import
order: `java,javax,org,com,at.phactum`. Assembled strings: use `String#formatted`
instead of `+`-concatenation and text blocks (`"""`) for multi-line strings (e.g.
SQL) — better readability.

## Documentation conventions

- **Wiki** (`adapter-platform-integration.wiki/`) = user-facing docs. Update it when a
  feature changes user-visible behavior or configuration.
- **Module `README.md` files** = contributor/development docs explaining concepts, not
  just module listings. When implementing a feature, extend the affected module's
  README with the concept behind it.
- **Exception:** `spi-for-java/README.md` is user-facing.
- **`DECISIONS.md`** (every repository) = the numbered decisions the code cites, and the only
  citation target code is allowed: `see decision 7 in the repository's DECISIONS.md`, entries of
  that repository only. Read it before changing behaviour. Where a change would make an entry
  untrue, **ask before writing the change**; a decision is superseded rather than edited, keeps
  its number, and the successor gets the next free one. Each repository's `AGENTS.md` states it.
  Before you open a pull request, check that a number your branch hands out is still free,
  against `origin/main` AND against every open pull request (`bin/check-decision-numbers.sh`
  where the repository has it). A second branch claims the same number easily, and at the merge
  a `see decision 21` in a Java file can no longer be changed. Read each citation before you
  renumber: a branch may cite a number somebody else handed out, and that one stays.
- **`UPGRADE.md`** (every repository which has one) = the step from VanillaBP 1 to the 2.0
  release, and nothing else. An entry is owed where a version-1 application behaves differently or
  has to change something. A change between two snapshots of 2.0 earns no entry, however much work
  it was. What it earns instead is a wiki page where the end state belongs, a `DECISIONS.md` entry
  where several places rely on the reasoning, and nothing at all where it is neither. The file is
  organised per version line and then per topic, and no heading carries a date; the user-facing half
  is the wiki page `Migrating-from-version-1`, which wins where the two disagree.
  `process-engine-api-adapter` has no such file and gets none, because there was never a version-1
  release of it. Each repository's `AGENTS.md` states the rule.
- Versions: all artifacts are aligned to 2.0.0-SNAPSHOT (`spi-for-java`:
  1.2.0-SNAPSHOT; 1.2.0 is the version which added asynchronous task completion,
  `@WorkflowEnded`, `@WorkflowStartedByBpms`, `sendSignal` and `aggregateChanged`).
  User-facing documentation writes versions as `2.0`, without a patch digit and without
  `-SNAPSHOT`.

**A javadoc, README or wiki sentence which promises behaviour is part of the
behaviour.** Either a test fails when it stops being true, or the sentence says that it
is an assumption and what would disprove it. A story which changes behaviour re-reads
the claims about that behaviour before it is done. Name the test in the claim where it
is not obvious (`see FooTest#bar`), delete a sentence which promises nothing, and treat
a measurement as a statement about a measured past which needs its context (version,
setup, date) rather than a test. Both SPIs, the adapters' decisions and
all four wikis once for this; `adapter-platform-integration/CONTRIBUTING.md` carries the
rule for contributors.

## Configuration & error messages

Validate configuration as early as possible (Spring Boot: at startup, even for values
needed only later; Quarkus: build time / runtime init), let an unconfigured app still
boot, and make every startup message *guide* the developer to a complete configuration
(state the fix, name the property keys) so they need almost no documentation. This is a
VanillaBP core concept — see the `vanillabp-config-validation` skill. Never add lazy
"throw on first use" property checks.

## Known pitfalls (current state)

- `ProcessServiceBase` has no "not yet supported" stubs left: every
  operation of `ProcessService` is served by both platform beans, and the base
  declares them abstract, so a platform bean forgetting one does not compile. What a
  single BPMS cannot do is refused by ITS adapter, with a message naming the adapter.
- The election IS implemented and runs through the core's `WorkflowLocator`: the
  probes of `MigratableProcessService` take a `WorkflowScope` and an
  adapter answers for that scope only, everything else being `UNKNOWN_TO_BPMS`
  (`BPMS_UNAVAILABLE` must never fall back to the next adapter). The contract is in
  the type javadoc of `MigratableProcessService` and held by
  `ElectionScopeContractTest`.
- Workflow-level configuration (`vanillabp.workflow-modules.<id>.workflows.*`) works
  now; the former "not yet supported" rejection is gone and regression
  tests in `MigrationAdapterPropertiesTest` and `VanillaBpConfigurationBindingTest`
  keep it that way.
- Three SPI modules exist: business code implements interfaces from
  `io.vanillabp:vanillabp-integration-spi` (package `io.vanillabp.integration.spi`,
  e.g. `AggregatePersistenceAware`); adapters implement
  `io.vanillabp:vanillabp-adapter-spi`; an extension of the deployment pipeline
  implements `ExtensionWiringService` from `io.vanillabp:vanillabp-extension-spi`,
  which the adapter SPI extends and brings along. Never leak adapter-SPI types into
  business-facing modules.
- Two-phase workflow starts run through the `PhaseTwoOutbox` SPI: stores implement
  exactly one method `boolean schedule(PhaseTwoCall)`; the core builds the call from
  the `PhaseOperation` (START carries the elected adapter ID — persisted, used in
  phase two without re-election). An operation is defined once, in `PhaseOperation`,
  and an adapter contributes a `PhaseOperationHandler` per operation. Dispatch: outbox → core-owned `PhaseTwoRouter` →
  `MigrationProcessService` → adapter (process-service beans register with the
  router at bean creation, incl. a String→ID-type converter; conversion happens
  exactly once, in the router). Contract: unique idempotency key (duplicate = no-op
  returning false), DONE instead of delete + retention cleanup
  (`vanillabp.outbox.retention`), documented at-least-once residual window.
  Defaults: Spring+JPA = gruelbox-based (uniqueRequestId + retention threshold),
  Spring+MongoDB and Quarkus (JDBC/Agroal/JTA) = own implementations with
  STATUS/ADAPTER_ID/IDEMPOTENCY_KEY columns. Config: `vanillabp.outbox.*`.
