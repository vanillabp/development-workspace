---
name: vanillabp-testing
description: Testing strategy and concrete test patterns for VanillaBP — feature/acceptance tests (E2E) first for everything user-facing, integration tests for the rest, unit tests for edge cases; >90% coverage measured SEPARATELY per platform; adapters are tested primarily at the migration-adapter SPI boundary; always use test-utils (output suppression, coverage forwarding, free ports). Use whenever writing or reviewing tests in adapter-platform-integration or any adapter repository.
---

# VanillaBP testing strategy & patterns

## Test pyramid, inverted priority: features first

1. **Feature/acceptance tests (E2E) are the preferred kind** — one per feature and per
   user-visible variation of it (SPI usage AND configuration variants). A story is
   proven by its acceptance test, not by unit coverage: 100% unit coverage is worthless
   if the components don't work together.
2. **Integration tests** cover the rest — they usually produce good coverage on their
   own, leaving only edge cases.
3. **Unit tests** for edge cases and code paths practically never executed at runtime.

"User-facing" means everything the developer using VanillaBP touches: the
`spi-for-java` API, annotations, configuration keys and startup messages.

## Who is "the user"? Different per repo

- **adapter-platform-integration:** the user is the application developer → E2E means
  a booted application (Spring context / Quarkus app) exercising `ProcessService`,
  annotations and configuration, with the **dummy adapter** as the BPMS double.
- **Adapter repos:** the user is the **migration-adapter** — the adapter's job is to
  implement its SPI. Test primarily at that boundary (deployment pipeline calls,
  phase one/two, awareness) against the real BPMS (C7: embedded H2; C8: Testcontainers;
  PEA: the in-memory mock). A developer-level E2E test (via `ProcessService`) is
  needed only **exemplarily** (e.g. one start-to-finish flow) or where genuinely
  meaningful — most user-facing behavior is already covered by the platform
  integration's tests. Don't duplicate it per adapter.

## Coverage: >90%, strictly per platform

Target is **>90% line coverage, per platform, viewed separately**:

- `adapter-platform-integration/test-coverage-report/spring-boot` aggregates
  migration-adapter + Spring modules + Spring ITs; `.../quarkus` aggregates
  migration-adapter + Quarkus modules + Quarkus ITs. **A Spring E2E test must never be
  the reason Quarkus code counts as covered** — that's the whole point of the split.
- Adapter repos follow the same scheme: per-platform coverage reports (add them when a
  repo gains its second platform).
- JaCoCo setup (copy from adapter-platform-integration's parent pom): agent via
  `@{jacoco.agent}` in the surefire/failsafe `argLine`; test/IT packages excluded
  (`io/vanillabp/integration/test/**`, `.../it/**`); report modules list the covered
  artifacts as dependencies.

## Always use `test-utils` (`io.vanillabp:test-utils`)

- **`SuppressOutputExtension`** on EVERY test class
  (`@ExtendWith(SuppressOutputExtension.class)`): buffers stdout/stderr and prints it
  **only when the test fails** — build logs stay clean. Add
  `@SuppressBackgroundOutput` when background threads (Testcontainers, DB drivers)
  would print after the class finished. The extension is also a `ParameterResolver`:
  inject `CapturedOutput` to **assert log content** (exactly right for testing the
  guiding startup messages of `vanillabp-config-validation`).
- **`TestCoverageUtils.testCoverageJavaAgent(...)`**: forwards the JaCoCo agent into
  forked JVMs — mandatory for `QuarkusProdModeTest` (`setJVMArgs(...)`), otherwise the
  forked run produces no coverage.
- **`FreePortUtil`** for ports; **`TestJvmArgs`** (e.g. `quarkusProdModeTestDefaults()`)
  for standard forked-JVM args; **`SpringBootTestApplication`** to build Spring test
  apps with custom classpath resources (add/hide resources) WITHOUT extra Maven
  modules; `FullyQualifiedRepositoryBeanNameGenerator` for JPA test apps with
  repository name clashes.

## Established patterns (study real examples before writing new tests)

- **Spring, focused context:** `ApplicationContextRunner` with explicit
  `AutoConfigurations.of(...)` + `withUserConfiguration(...)` — boots exactly the
  configuration under test (example:
  `spring-boot-integration/integration-tests/main-integration-test/.../AdapterConfigurationTest`).
  Use for discovery/wiring/validation tests where a full boot would drag in unwanted
  lifecycles.
- **Spring, E2E:** `@SpringBootTest` with a real test application (JPA/H2, dummy
  adapter or real BPMS) — see the outbox ITs
  (`outbox-jpa-integration-test`, `outbox-mongo-integration-test`) for
  transaction/rollback/recovery test shapes (incl. context-restart recovery tests).
- **Quarkus, CDI-level:** `QuarkusUnitTest` (`@RegisterExtension`) with
  `.withApplicationRoot(jar -> jar.addAsResource("application.yaml").addClass(...))` —
  workflow-module marker files added via
  `addAsResource("workflow-module-descriptor/workflow-module", "META-INF/workflow-module")`.
- **Quarkus, E2E:** `QuarkusProdModeTest` with
  `.setJVMArgs(testCoverageJavaAgent(quarkusProdModeTestDefaults()))`, `.setRun(true)`,
  `quarkus.http.port` from `FreePortUtil`; the test application exposes small
  **`introspect/...` REST endpoints** that report internal state, asserted with
  RestAssured (example:
  `quarkus-integration/integration-tests/workflowmodule-integration-tests/.../MultipleWorkflowServicesTest`).
- **Test doubles:** the dummy adapters (both platforms) are THE test vehicle for
  platform features; listener hooks (`DummyAdapterPhaseTwoListener` /
  `DummyPhaseTwoListener`, `Recording*` test beans) observe and can fail dispatches to
  test retry paths. PEA's `InMemoryProcessEngine` records invocations incl.
  `ExecutionMode`.
- Real-BPMS tests: C7 embedded on H2 (cheap — use freely); C8 via Testcontainers with
  `@Testcontainers(disabledWithoutDocker = true)`; MongoDB via Testcontainers.

## Checklist for a story's test plan

1. One acceptance test per feature + per user-visible variation (SPI overload,
   config option, failure policy) — on BOTH platforms where the feature exists.
2. Adapter stories: assertions at the migration-adapter SPI boundary against the real
   BPMS/double; exemplary developer-E2E only once.
3. Rollback/idempotency/recovery shapes where transactions or at-least-once semantics
   are involved (copy the outbox IT shapes).
4. Startup-message tests assert message CONTENT (property keys!) via `CapturedOutput`.
5. Check the per-platform coverage reports afterwards; fill gaps with integration
   tests first, unit tests for the remaining edges. Target >90% per platform.
6. Every class: `SuppressOutputExtension`; forked JVMs: coverage forwarding.
