---
name: vanillabp-conventions
description: Development rules for implementing VanillaBP Version 2 features — use before writing or changing code in spi-for-java or adapter-platform-integration, covering module placement, compatibility constraints, build/test commands, formatting and documentation conventions.
---

# VanillaBP Development Conventions (Version 2)

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

## Testing conventions

Strategy and patterns live in the `vanillabp-testing` skill — read it before writing
any test. Core points: feature/acceptance tests (E2E) first for everything
user-facing; integration tests for the rest; unit tests for edge cases; **>90%
coverage per platform, measured separately** (Spring tests must not cover Quarkus
code); adapters test primarily at the migration-adapter SPI boundary; every test class
uses `test-utils` (`SuppressOutputExtension` etc.). Platform tests use the **dummy
adapter** (and, for Spring, the dummy extension) instead of a real BPMS; MongoDB/C8
tests use Testcontainers. Quarkus log suppression: see
`quarkus-integration/README.md`, section "Logging during tests".

## Build & verify

```bash
# Build order matters: spi-for-java before adapter-platform-integration.
cd spi-for-java && mvn install verify
cd adapter-platform-integration && ./mvnw install verify   # install, NOT package:
                                                           # Quarkus ITs load modules
                                                           # from the local Maven repo

# Single unit test / single integration test
mvn test -pl <module-path> -Dtest=TestClassName
mvn verify -pl <module-path> -Dit.test=ITClassName

# Formatting (Spotless fails the build on violations)
mvn spotless:apply
```

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
- Versions: all artifacts are aligned to 2.0.0-SNAPSHOT (`spi-for-java`:
  1.1.1-SNAPSHOT).

## Configuration & error messages

Validate configuration as early as possible (Spring Boot: at startup, even for values
needed only later; Quarkus: build time / runtime init), let an unconfigured app still
boot, and make every startup message *guide* the developer to a complete configuration
(state the fix, name the property keys) so they need almost no documentation. This is a
VanillaBP core concept — see the `vanillabp-config-validation` skill. Never add lazy
"throw on first use" property checks.

## Known pitfalls (current state)

- `ProcessService` operations beyond `startWorkflow` (message correlation,
  complete/cancel tasks, viewer/history) throw `UnsupportedOperationException`
  ("not yet supported by VanillaBP 2") from the shared core base
  `ProcessServiceBase` — they are upcoming feature stories.
- The fallback election for existing workflow instances is NOT implemented yet:
  `MigratableProcessService.awarenessOfTask/awarenessOfWorkflow` exist as SPI
  (enum `WorkflowAwareness` with `ACTIVE`/`COMPLETED`/`UNKNOWN_TO_BPMS`/
  `BPMS_UNAVAILABLE`; `BPMS_UNAVAILABLE` must never trigger fallback to the
  next adapter) but the core does not call them yet.
- Workflow-level configuration (`vanillabp.workflow-modules.<id>.workflows.*`) is
  rejected at startup ("not yet supported") — implement it before removing the
  rejection in both platform transformers.
- Two SPI modules exist: business code implements interfaces from
  `io.vanillabp:vanillabp-integration-spi` (package `io.vanillabp.integration.spi`,
  e.g. `AggregatePersistenceAware`); adapters implement
  `io.vanillabp.adapter:migration-adapter-spi`. Never leak adapter-SPI types into
  business-facing modules.
- Two-phase workflow starts run through the `PhaseTwoOutbox` SPI: stores implement
  exactly one method `boolean schedule(PhaseTwoCall)`; typed default methods build
  the call (START carries the elected adapter ID — persisted, used in phase two
  without re-election). Dispatch: outbox → core-owned `PhaseTwoRouter` →
  `MigrationProcessService` → adapter (process-service beans register with the
  router at bean creation, incl. a String→ID-type converter; conversion happens
  exactly once, in the router). Contract: unique idempotency key (duplicate = no-op
  returning false), DONE instead of delete + retention cleanup
  (`vanillabp.outbox.retention`), documented at-least-once residual window.
  Defaults: Spring+JPA = gruelbox-based (uniqueRequestId + retention threshold),
  Spring+MongoDB and Quarkus (JDBC/Agroal/JTA) = own implementations with
  STATUS/ADAPTER_ID/IDEMPOTENCY_KEY columns. Config: `vanillabp.outbox.*`.
