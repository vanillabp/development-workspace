---
name: vanillabp-testing
description: Testing strategy and concrete test patterns for VanillaBP — feature/acceptance tests (E2E) first for everything user-facing, integration tests for the rest, unit tests for edge cases; >90% coverage measured SEPARATELY per platform, gate at 85; adapters are tested primarily at the migration-adapter SPI boundary; always use test-utils (output suppression, coverage forwarding, free ports). Use whenever writing or reviewing tests in adapter-platform-integration or any adapter repository.
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
- **But DO duplicate it per platform, inside an adapter.** The exemplary end-to-end flow
  has to run on Spring Boot AND on Quarkus, against the real engine, because the adapter's
  neutral core being correct says nothing about a platform's glue ever calling it. This is
  deliberate duplication and it is the one place the rule above does not apply.

## Coverage: >90% of INSTRUCTIONS, strictly per platform

Target is **>90% instruction coverage, per platform, viewed separately**. The build breaks
at 85, the number `coverage.threshold.spring-boot` and `coverage.threshold.quarkus` hold in
every VanillaBP repository. That is the floor, not the target, and a report between 85 and
90 passes while still naming a gap somebody owes a test for. Neither number is edited to
make a build pass. Instructions,
not lines: it is the number JaCoCo's index page and therefore the README badge show, and
it does not move when code is only reformatted, while line coverage depends on the
compiler's line table.

- `adapter-platform-integration/test-coverage-report/spring-boot` aggregates
  migration-adapter + both SPI modules + Spring modules + Spring ITs; `.../quarkus`
  aggregates the same core plus the Quarkus modules and ITs. **A Spring E2E test must
  never be the reason Quarkus code counts as covered** — that's the whole point of the
  split.
- Adapter repos follow the same scheme: per-platform coverage reports (add them when a
  repo gains its second platform).
- **The number is a completeness signal for end-to-end tests, not a code-quality score**
  (Stephan, 2026-08-21). Every documented VanillaBP feature is exercised through EVERY
  platform, so that the parts working is never mistaken for the whole working; measuring
  the platform-neutral core separately per platform is what makes a missing run visible.
  The core lines a platform's tests never reach ARE the features that platform never runs.
- Which is why **the execution data of one platform must never be fed into the other's
  aggregate**, however tempting it looks when a number is low. It lifts the number and
  destroys the only thing it is good for. It has been proposed and
  rejected; the low Quarkus numbers of the three adapters are that signal working, not a
  bookkeeping defect.
- Reading the gap: compare `jacoco.csv` of both reports class by class. Where a class of
  the neutral core is high on one platform and low on the other, the difference names the
  features the second platform never runs, and that list is the work order.
- JaCoCo setup (copy from adapter-platform-integration's parent pom): agent via
  `@{jacoco.agent}` in the surefire/failsafe `argLine`; test/IT packages excluded
  (`io/vanillabp/integration/test/**`, `.../it/**`); report modules list the covered
  artifacts as dependencies.
- **A module producing a `jacoco.exec` has to be listed in the aggregate of its
  platform.** Forgetting one is invisible: everything covered ONLY by its tests counts
  as missed, and the number then asks for tests which already exist. Seven modules of
  `adapter-platform-integration` had slipped through that way once.
- **The gate:** every repository builds `test-coverage-report/coverage-gate` last. It
  reads the two published reports, breaks the build below `coverage.threshold` (root POM,
  in percent) and compares every module producing a `jacoco.exec` against the two
  aggregates. JaCoCo's own `check` goal cannot do this: it judges one module's classes
  against one execution-data file, while both numbers come from aggregated reports.
  Reading the published report is what keeps report and gate from disagreeing.
- A module whose data belongs to no report is a decision, not an oversight: name it in
  the gate's list of exceptions together with the reason. The same holds for a
  production module left out of the aggregates (the Quarkus `ProcessServiceIdeProducer`
  is one: an unselected CDI alternative which exists for IDE analysis and can never run).

## Always use `test-utils` (`io.vanillabp:test-utils`)

- **`SuppressOutputExtension`** on EVERY test class
  (`@ExtendWith(SuppressOutputExtension.class)`) except the one documented below, and as the **FIRST** class-level
  extension, above `@Testcontainers`: JUnit registers declarative extensions in the order
  they are written, so a Testcontainers extension listed first starts its container, and
  logs it, before anything captures output (2208 debug lines of the Docker
  client in a green build). Both rules are enforced by the `coverage-gate` module of every
  repository via `TestClassConventions`. What starts even earlier than the first callback
  — Docker detection from an `ExecutionCondition`, an image pull, the Ryuk reaper — no
  extension reaches; that needs a `logback-test.xml` holding `org.testcontainers`, `tc`
  and `com.github.dockerjava` at `WARN`.
- **The one exemption: `@PrintsWhenPassing`.** A class whose printed line IS its result
  carries that annotation with the reason instead of the suppression, and
  `TestClassConventions` leaves it alone. VanillaBP has exactly one such class, the
  `CoverageGateTest` of each repository: it measures both platforms against the gate and
  against the rule, and that measurement belongs in the log of a green build, where
  somebody who has just written tests can read whether the gap got smaller. Anything else,
  a mock that warns or a container that boots, is noise and gets suppressed. A second
  exemption needs a reason of the same shape, which is why the annotation demands one in
  writing. In the Quarkus test modules the level stays at
  `INFO` — a record a level drops reaches no handler and therefore no capture, so a red
  build would replay nothing. What those modules cannot capture is the boot of an
  application: Quarkus logs it into a log context of its own, in the Quarkus extension's
  `beforeAll`. For a FORKED application (prod-mode tests of the adapters) that is a dozen
  lines per class and stays visible; for an application booted IN the test JVM (platform,
  pea) it was 311 lines per module, which is why those modules keep
  `redirectTestOutputToFile` and their workflow uploads the reports when a build fails. It buffers stdout/stderr and prints it
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
- **Quarkus, CDI-level:** `QuarkusExtensionTest` (`@RegisterExtension`) with
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
- **A real engine or cluster needs `@DirtiesContext` on the class, plus its own database
  respectively container.** Spring caches every test context until the JVM exits, and all
  IT classes of a module share one Surefire fork: a context which outlives its test keeps
  working — C7's job executor polls the database the next classes use, C8's job workers
  poll a gateway Testcontainers already stopped. That accumulation is what made the
  seventh Zeebe container of `camunda8-adapter` run into test timeouts, and what let two
  C7 engines fish each other's jobs. Classes deliberately SHARING one context (identical
  `@SpringBootTest`, no `@DynamicPropertySource`) stay without the annotation — it would
  rebuild their context between classes.
- **A test scenario gets its own workflow module id.** VanillaBP registers the
  `@WorkflowService` classes of a workflow module from the CLASSPATH, and all tests of one
  Maven module share one classpath. Two scenarios using the same module id therefore
  register each other's workflow services, and every context is asked for the persistence
  of aggregates it never heard of - that ENDS the startup instead of
  failing at the first task, which is how the Camunda 8 adapter's 19 IT classes went red at
  once. So a new scenario brings its own module id, its own `resources-location` and its own
  BPMN resources, and its configuration file configures only that module. Do
  not answer the symptom with a persistence double for the other scenario's aggregate
  class: that couples the two, and the next aggregate breaks a test nobody touched.
- **A test application which never persists says so**, with an
  `AggregatePersistenceAware<Object>` bean whose methods throw (the platform's
  `NoPersistenceForTheSampleAggregate` is the pattern; the Camunda 8 adapter's smoke
  application and the Process-Engine-API adapter's `TestPersistenceConfiguration` follow
  it). It sits at the greatest inheritance distance, so a double or a repository for a
  specific aggregate still wins. A `SpringDataUtil` stub whose `getRepository` throws is
  NOT enough any more: that throw is exactly what the startup check reports.
- **Shared test beans are reset by the test which changed them** (`@AfterEach`), not only
  in the next class's `@BeforeEach`. Surefire and Failsafe run `alphabetical` (parent POM)
  so a runner's order matches the local one, but a left-behind window or stub answer still
  poisons whoever comes next — the platform's `TaskOperationsDispatchTest` waited 300 s per
  test for exactly that reason.

## Checklist for a story's test plan

1. One acceptance test per feature + per user-visible variation (SPI overload,
   config option, failure policy) — on BOTH platforms where the feature exists.
2. Adapter stories: assertions at the migration-adapter SPI boundary against the real
   BPMS/double; exemplary developer-E2E only once.
3. Rollback/idempotency/recovery shapes where transactions or at-least-once semantics
   are involved (copy the outbox IT shapes).
4. Startup-message tests assert message CONTENT (property keys!) via `CapturedOutput`.
5. Check the per-platform coverage reports afterwards; fill gaps with integration
   tests first, unit tests for the remaining edges. Target >90% per platform, build breaks at 85.
6. Every class: `SuppressOutputExtension` (only `CoverageGateTest` is exempt, via
   `@PrintsWhenPassing`); forked JVMs: coverage forwarding.
7. A new test scenario: its own workflow module id, and an owner for every aggregate its
   context registers (see the two rules above).
