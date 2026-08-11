---
name: vanillabp-adapter-building
description: How to build a VanillaBP BPMS adapter repository — module layout, adapter SPI implementation, Spring Boot and Quarkus registration patterns, adapter id vs. type, configuration, build order and documentation conventions. Use when creating or extending an adapter (Camunda 7, Camunda 8, Process-Engine-API, ZenBPM) or when writing prompts for adapter work.
---

# Building a VanillaBP Adapter (Version 2)

Read `vanillabp-concepts` (architecture, glossary) and `vanillabp-bpms-characteristics`
(per-BPMS traits) first. This skill covers the mechanics common to all adapters.

## Repositories and workspace conventions

- Each adapter is an **own Git repository**, cloned as a sibling directory of
  `/workspaces/VanillaBP2` (like `adapter-platform-integration`). Initialize with
  `git init -b main`.
- The Camunda adapter repos will later **replace `main` of the existing GitHub repos**
  `vanillabp/camunda7-adapter` and `vanillabp/camunda8-adapter` (Camunda Community
  Hub; not under our control, no new repos possible there). Therefore: directory and
  artifact names must match those repos, and the Version-1 groupId
  `org.camunda.community.vanillabp` is kept.
- The Process-Engine-API adapter is a new repo (`process-engine-api-adapter`),
  groupId `io.vanillabp`.
- All adapter artifacts are versioned **2.0.0-SNAPSHOT** (aligned with
  adapter-platform-integration).
- After creating a new adapter repo, add it to the repository list in
  `/workspaces/VanillaBP2/CLAUDE.md`.

## Module layout (mirror of the platform split)

```
<adapter-repo>/
  pom.xml                  parent (packaging pom)
  core/                    platform-neutral: SPI implementations + BPMS client logic
  spring-boot/             Spring Boot auto-configuration (thin glue only)
  quarkus/
    runtime/               Quarkus extension runtime (producers, quarkus-extension.yaml)
    deployment/            Quarkus extension deployment (build steps)
```

Rules:

- **`core` is plain Java** — no Spring/Quarkus imports. It depends on
  `io.vanillabp.adapter:migration-adapter-spi` (adapter SPI),
  `io.vanillabp:vanillabp-integration-spi` (business SPI, transitively) and the BPMS
  client/engine artifact. All real behavior lives here.
- Platform modules only *construct and register* the core objects: read
  configuration, create beans. If you write BPMS logic in a platform module, move it
  to `core`.
- Camunda 7 exception: the embedded engine is Spring-centric; a Quarkus variant is
  deferred (Camunda's Quarkus extension is version-locked to older Quarkus releases
  and C7 is EOL) — the repo has `core/` + `spring-boot/` only.

## Dependencies (local Maven repo — build order matters)

```
io.vanillabp:spi-for-java:1.1.1-SNAPSHOT                     (user-facing annotations)
io.vanillabp:vanillabp-integration-spi:2.0.0-SNAPSHOT        (business SPI)
io.vanillabp.adapter:migration-adapter-spi:2.0.0-SNAPSHOT    (adapter SPI)
io.vanillabp:vanillabp-spring-boot-integration:2.0.0-SNAPSHOT   (spring-boot module)
io.vanillabp:vanillabp-quarkus-integration:2.0.0-SNAPSHOT       (quarkus runtime module)
io.vanillabp:vanillabp-quarkus-integration-deployment:2.0.0-SNAPSHOT (quarkus deployment module)
```

Build order: `spi-for-java` → `adapter-platform-integration` (`./mvnw install
verify`) → adapter repos (`mvn install verify`). Copy the Spotless setup
(`formatting_conventions.xml` + plugin config) from adapter-platform-integration so
formatting rules are identical.

## Adapter SPI to implement (in `core`)

Package `io.vanillabp.integration.adapter.spi` unless noted:

1. `AdapterDeploymentService<BPMN, PC> extends ExtensionWiringService<BPMN, PC>` —
   one instance **per configured adapter id** (not per type!):
   - `getAdapterId()` / `getAdapterType()` — id from configuration, type is a
     constant (e.g. `"camunda7"`).
   - `getModelType()` / `getProcessContextType()` — the adapter's BPMN model class
     and its processing-context class (an adapter-own accumulator, threaded through
     the pipeline).
   - Pipeline, called by the core `DeploymentService` per workflow module:
     `readBpmn(moduleId, filename, inputStream, isVanillaBpBpmn)` → list of
     (bpmnProcessId → model) entries (one BPMN file may contain several processes;
     throw `BpmnParseException` on parse errors) →
     `prepareBpmn(moduleId, existingContext, filename, bpmnProcessId, model)` →
     `wireBpmn(moduleId, filename, bpmnProcessId, model, context)` →
     `deployResources(moduleId, context)` →
     `startWorkflowProcessing(moduleId, context)` /
     `stopWorkflowProcessing(moduleId, context)` (graceful shutdown, reverse order).
2. `MigratableProcessService<A>` — the per-adapter runtime the core
   `MigrationProcessService` delegates to:
   - `getAdapterId()`
   - `needsTwoPhaseCommitForStartingWorkflows()` — embedded/in-TX engines: false;
     remote engines: true (routes starts through the `PhaseTwoOutbox`).
   - `startWorkflowPhaseOne(aggregatePersistence, aggregate)` — inside the local
     transaction (embedded: do everything; remote: validate only).
   - `startWorkflowPhaseTwo(workflowAggregateId)` — after commit, dispatched via
     outbox → core-owned `PhaseTwoRouter` → `MigrationProcessService` (uses the
     adapter ID persisted with the outbox entry — no re-election). Must be
     idempotent (key: moduleId + bpmnProcessId + aggregateId).
   - `awarenessOfWorkflow(aggregateId)` / `awarenessOfTask(aggregateId, taskId)` —
     return `WorkflowAwareness`; `BPMS_UNAVAILABLE` only for infrastructure
     failures (it suppresses fallback election), `UNKNOWN_TO_BPMS` only after a
     *successful* query found nothing.

Skeleton stage: methods that are not implemented yet throw
`UnsupportedOperationException("<method> is implemented in a later story")` — never
silently do nothing (silent stubs hide wiring bugs in later stories).

## Registration: Spring Boot (template: dummy adapter)

Template to study:
`adapter-platform-integration/spring-boot-integration/integration-tests/dummy-adapter/`
— three auto-configuration classes listed in
`src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`:

1. **Adapter announcement** — must be built *before* the platform validates
   configured adapter types:
   ```java
   @AutoConfiguration(before = SpringBootMigrationAdapterAutoConfiguration.class)
   public class Camunda7AdapterConfiguration extends AdapterConfigurationBase {
     public static final String ADAPTER_TYPE = "camunda7";
     @Override public String getAdapterType() { return ADAPTER_TYPE; }
   }
   ```
   (Do not declare other beans in this class — it must be constructible early.)
2. **Deployment service** — `@AutoConfiguration(after =
   SpringBootMigrationAdapterAutoConfiguration.class)`, registering the adapter's
   `AdapterDeploymentService` as an **individual element bean**. NEVER register a
   bean of type `List<AdapterDeploymentService<...>>` — Spring's collection
   injection only collects element beans, so List beans break as soon as a second
   adapter type is on the classpath (= the migration scenario; review finding B1).
   The platform collects all element beans via `ObjectProvider` streams. Until the
   adapter-config-model story (26d) introduces per-id element beans, build the one
   instance for the first configured adapter id of this adapter's type.
3. **Process service** — an element bean of the adapter's
   `MigratableProcessService` implementation (the platform injects all of them into
   every `ProcessServiceSpringBean`). Same rule: element beans only. The election
   fails startup fast if any prioritized adapter id has no matching process
   service.

## Registration: Quarkus (template: dummy adapter)

Template:
`adapter-platform-integration/quarkus-integration/integration-tests/dummy-adapter/`
— an own Quarkus extension (runtime + deployment):

- `runtime/src/main/resources/META-INF/quarkus-extension.yaml` with
  `dependencies: [vanillabp]`.
- Deployment module build steps:
  - produce a `FeatureBuildItem`
  - produce `VanillaBpMigratableProcessServiceBuildItem.builder()
    .adapterType("...").migratableProcessServiceBeanClass(<runtime class name>)
    .build()` — announces the adapter type and its process-service bean to the
    VanillaBP extension.
  - register the runtime producer via `AdditionalBeanBuildItem`
    (`.setUnremovable()`).
- Runtime module: an `@ApplicationScoped` producer creating the core
  `MigratableProcessService` (resolve the adapter id from
  `MigrationAdapterProperties.getAdapters()` by type) and, later, the deployment
  services.

## Registration pitfalls (verified while building the C7/C8/PEA skeletons)

- **Configuration shape:** `vanillabp.adapters` binds to a
  `Map<String, AdapterConfigProperties>` in the CORE model (story 19: the tree is
  modeled once, in `MigrationAdapterProperties`; Spring binds the core POJOs
  directly, Quarkus maps its `@ConfigMapping` interface onto them via a generated
  MapStruct `toCore()`). The shorthand `vanillabp.adapters.<id>: <type>`
  does NOT bind — always use `vanillabp.adapters.<id>.type: <type>` (the adapter id
  is the map key, the type a sub-property). The id→type view is
  `MigrationAdapterProperties.adapterTypes()` (type defaults to the id).
- **Adapter config OVERLAY (story 19, consumed by 26d):** adapters contribute their
  own keys (connection settings etc.) to the SAME tree
  (`vanillabp.adapters.<id>.<key>` — never a parallel namespace) by binding an
  adapter-owned overlay of the `vanillabp` prefix:
  - Spring: a second `@ConfigurationProperties("vanillabp")` class in the adapter's
    spring-boot module (same-prefix classes coexist; unknown keys are ignored by
    JavaBean binding). Run the configuration processor for IDE metadata.
  - Quarkus: a RUN_TIME `@ConfigRoot @ConfigMapping(prefix = "vanillabp")` in the
    adapter's runtime module (reference: the platform's Quarkus dummy adapter,
    `DummyAdapterOverlayProperties`). The blanket
    `withMappingIgnore("vanillabp.**")` is GONE — a key no registered mapping
    knows fails the startup (typo detection; Quarkus is stricter than Spring,
    accepted). Therefore EVERY key an adapter reads/writes must be modeled in its
    overlay mapping.
  - **Adapter-id-set rule (decision 9):** the authoritative id set is ALWAYS the
    platform's core properties (`adapterTypes()`); overlay maps are per-known-id
    lookups only, NEVER iterated to discover ids (Spring env-var overrides can
    materialize phantom map entries; overlay-only ids are invisible to
    validation).
- **Quarkus capability contract:** an adapter extension MUST declare, in its runtime
  `META-INF/quarkus-extension.yaml`, a provided capability
  `io.vanillabp.adapter.<adapterType>` (suffix EQUALS the adapter type, e.g.
  `io.vanillabp.adapter.camunda8`). The VanillaBP Quarkus integration hard-validates
  this — it is independent of the artifact groupId. The extension `name` can be
  anything (convention `vanillabp-<type>`).
- **Skeleton smoke tests / deployment lifecycle:** the core deployment runs
  unconditionally at context start — Spring's deployment `SmartLifecycle` (and the
  Quarkus `StartupEvent` path) call `deployResources`/`startWorkflowProcessing` for
  every (workflow module × prioritized adapter) **even with zero BPMN files**. A
  skeleton whose pipeline methods throw therefore cannot complete a full boot. Two
  proven ways to still test adapter *discovery*:
  - Spring: `@SpringBootTest` with
    `spring.autoconfigure.exclude=<the platform's DeploymentAutoConfiguration>`, or an
    `ApplicationContextRunner` that does not activate the deployment lifecycle; assert
    the deployment-service list bean and the `MigratableProcessService` bean resolve
    with the expected adapter id/type.
  - Quarkus: a skeleton that wires no deployment service boots fine (the JDBC outbox
    stays inactive without a datasource, so a two-phase adapter needs neither).
  A test also needs a `META-INF/workflow-module` marker — startup enforces "at least
  one workflow module".
- **Camunda 7 + Spring Boot 4:** `camunda-bpm-spring-boot-starter:7.24.0` targets
  Spring Boot 3.5.x (via `camunda-parent`) and is incompatible with the VanillaBP-2
  baseline (Boot 4.1). Depend on `org.camunda.bpm:camunda-engine` directly and wire
  the embedded engine yourself; do not fight the starter.

## C7-family portability rules (Operaton / CIB seven readiness)

The Camunda 7 adapter stays Camunda-7-only, but every line of it must stay **trivially
copyable** to the forks Operaton (`org.operaton.bpm.*`) and CIB seven
(`org.cibseven.bpm.*`) — both renamed all packages; the copy will be generated with
OpenRewrite later (roadmap 26g). Rules for ALL C7 adapter code:

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

## Configuration validation

Validate an adapter's configuration **at startup** for every configured adapter id of
its type (Spring auto-config / Quarkus startup), not lazily on first use, and emit
messages that tell the developer which property keys to add. An unconfigured adapter
should still let the app boot (guided, incremental setup). This is a VanillaBP core
concept — see the `vanillabp-config-validation` skill. (The current Camunda 8 skeleton
validates lazily via `requireProperty`/`validateConfigured` on first use — a known
inconsistency to align in a later story; do not copy that pattern.)

## Adapter id vs. adapter type — why two names

`vanillabp.adapters.<id>` configures an adapter *instance* of a *type*
(`getAdapters()` yields id → type). The same BPMS type may be configured twice with
different ids — the central migration scenario (e.g. old on-prem Camunda 8 cluster
and new SaaS cluster side by side, or two engine versions). Consequences:

- Never treat the adapter type as a singleton: **one `MigratableProcessService` AND
  one `AdapterDeploymentService` (and any BPMS client) per configured adapter id** —
  build them by iterating `properties.getAdapters()` for your type, not via
  `findFirst()`. (The current skeletons wrongly build a single process service from
  the first id — a rework story.)
- Adapter-specific configuration lives at `vanillabp.adapters.<id>.*` (the canonical
  location — `AdapterConfiguration`), NOT a parallel flat namespace. Scope-specific
  properties (per module/workflow/task, e.g. Camunda 8 job timeout) resolve
  most-specific-wins across four levels. See the `vanillabp-configuration-model`
  skill. (The dummy adapter's test-only `dummy-adapter.two-phase-commit` flag is a
  test toggle, not a template for real adapter config.)

## Testing

- Core logic: plain JUnit 5 + Mockito in `core`.
- Spring: integration tests booting a real context (see
  `spring-boot-integration/integration-tests/*` for style); no real BPMS needed for
  skeleton tests — assert the context boots with the adapter configured and the
  adapter type/id is resolved.
- Quarkus: `QuarkusUnitTest` in the deployment module (style:
  `quarkus-integration/integration-tests/*` and the dummy adapter's deployment
  tests). Suppress build logs via `SuppressOutputExtension` from
  `test-utils`.
- Real-BPMS tests: Camunda 7 runs embedded (H2) → real engine in tests is cheap.
  Camunda 8 tests use `io.camunda:camunda-process-test-java` (Testcontainers-based,
  needs Docker). PEA tests run against the in-memory mock module.

## Documentation conventions

- **Adapter repo root `README.md` is user-facing** (like in Version 1 and like
  `spi-for-java`): dependency coordinates, configuration, BPMS-specific behavior.
- Module `README.md` files are contributor documentation (concepts, design
  decisions) — same rule as in adapter-platform-integration.
- The PEA adapter additionally maintains `GAPS.md`: features that cannot be
  implemented via the Process-Engine-API (or need PEA/VanillaBP extensions), found
  during mock-first development.
