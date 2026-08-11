---
name: vanillabp-concepts
description: Glossary and architecture of VanillaBP Version 2 — use when working on any VanillaBP feature, when terms like workflow module, workflow aggregate, migration adapter, adapter SPI, extension, BPMS election or two-phase start appear in a task, or when deciding in which module code belongs.
---

# VanillaBP Concepts (Version 2)

VanillaBP applies hexagonal architecture to business processing: business code is
written only against the SPI (`spi-for-java`), never against BPMS APIs. All workflow
state lives in a *workflow aggregate* — process variables are not used directly.

## Architecture (dependency flow)

```
Business code
    │ uses
spi-for-java                      (annotations + interfaces; Java 17; user-facing)
    │ brought to life by
Platform integration              (spring-boot-integration / quarkus-integration)
    │ delegates to
migration-adapter                 (platform-neutral core, plain Java)
    │ orchestrates
BPMS adapters                     (implement the migration-adapter SPI; separate repos)
```

**Rule of thumb: implement features in `migration-adapter` (plain Java, no platform
dependencies).** Platform integrations only do platform-specific work: loading
configuration, scanning/analyzing business code, creating beans. This way features
reach Spring Boot, Quarkus and future platforms (Jakarta EE) from one code base.

## Glossary

- **Process vs. workflow:** *Process* = the BPMN model. *Workflow* = one running
  instance of it. Use the terms strictly this way.
- **Workflow module:** BPMN model(s) + their implementation for one use case, packaged
  as its own Maven module (JAR). Declared by a marker file `META-INF/workflow-module`
  whose *content* is the workflow module ID. Purpose: encapsulation, avoiding BPMN name
  clashes, visibility scopes in the BPMS (e.g. tenant ID). Every application consists
  of at least one workflow module; without a marker file the whole app is the *global*
  module.
- **Workflow module configuration:** per-module config files named after the module ID
  (`loan-approval.yaml`, `loan-approval-<profile>.properties`, ...). They override
  `application.*` properties. Spring Boot: merged via an `EnvironmentPostProcessor`;
  Quarkus: generated config sources with ordinals 251 (properties) / 256 (YAML).
- **Workflow aggregate:** a DDD aggregate with a 1:1 relation to one workflow instance,
  holding all data the workflow needs. BPMN expressions (JUEL/FEEL) reference aggregate
  attributes. Best practice: intention-revealing boolean getters instead of raw
  attributes, to decouple BPMN from the data model. JPA is not mandatory.
- **`@SyncWithBPMS` / `@NoSyncWithBPMS`:** fine-grained control over which parts of the
  aggregate are synchronized with the BPMS (default: everything). Documented in the
  wiki; **not implemented yet** (planned as its own story).
- **Adapter:** a BPMS-specific implementation of the migration-adapter SPI. Exactly one
  adapter per BPMS in use. Adapters live in separate repositories (none in this
  workspace yet — they will be rebuilt from scratch).
- **Migration adapter:** the platform-neutral meta-adapter ("an adapter aware of other
  adapters"). Selects the BPMS per workflow via prioritized adapter lists and enables
  migrations (on-prem→SaaS, version upgrades, BPMS switch). Must itself handle eventual
  consistency of remote BPMS — otherwise fallback election ("try Camunda 7 if the
  instance is not in Camunda 8") is impossible.
- **BPMS election:** configuration `vanillabp.prioritized-adapters`, overridable per
  workflow module and per workflow; most specific non-empty value wins. New workflows
  always start in the first adapter; existing instances are located by asking adapters
  in priority order (`MigratableProcessService.isTaskActive` → true/false/null).
- **Two-phase start / transaction outbox:** workflow start is split into
  `startWorkflowPhaseOne` (inside the local DB transaction) and
  `startWorkflowPhaseTwo` (after commit, scheduled via the `PhaseTwoOutbox` SPI
  within the same transaction). Prevents ghost workflows with remote BPMS; embedded
  BPMS do everything in phase one. Dispatch chain (as short as possible):
  outbox store → core-owned `PhaseTwoRouter` → `MigrationProcessService` → adapter.
  For START the adapter elected in phase one IS persisted with the outbox entry
  and used in phase two (stale entries after config changes yield a guiding
  error); future probing operations carry no adapter ID.
- **Extension:** an integration that plugs into deployment/wiring in addition to the
  BPMS adapter (e.g. the VanillaBP Business Cockpit). Entry point:
  `ExtensionWiringService` (own `wireBpmn` + `startWorkflowProcessing`, ordered by
  `getOrder()`, filtered by matching model/context types). An extension may define its
  own SPI (e.g. `@UserTaskDetailsProvider` of the Business Cockpit); such SPI lives in
  the extension's `wireBpmn` implementation, never in the VanillaBP core.
- **Platform integration:** the thin platform-specific layer (Spring Boot / Quarkus)
  that brings the SPI to life and delegates to the migration adapter.
- **Processing context (`PC`):** adapter-specific object accumulated across all BPMN
  files of a workflow module during the deployment pipeline
  (`readBpmn` → `prepareBpmn` → `wireBpmn` → `deployResources` →
  `startWorkflowProcessing`).
- **`AggregatePersistenceAware<A>`:** persistence abstraction
  (`getAggregateClass`, `save`, `getAggregateId`). Lives exactly once in the
  business SPI `io.vanillabp:vanillabp-integration-spi` (package
  `io.vanillabp.integration.spi`), provided transitively by both support modules.
  The implementation with the most specific generic aggregate type wins
  (inheritance-distance metric in `AggregatePersistenceResolver`).
- **`PhaseTwoOutbox` / `PhaseTwoCall` / `PhaseTwoRouter`:** adapter-SPI contract
  for crash-safe phase-two dispatch of two-phase BPMS calls. Stores implement
  exactly one method `boolean schedule(PhaseTwoCall)` (enlist in local
  transaction); typed default methods (`scheduleStartWorkflow(module, process,
  aggregateId, adapterId)`) build the immutable `PhaseTwoCall` record (operation
  enum with persisted idempotency-key derivation rules; aggregate ID travels as
  String only). Contract: unique idempotency key enforced by the store (duplicate
  schedule = no-op, returns false; START key = module|process|aggregateId), DONE
  instead of delete (async cleanup after `vanillabp.outbox.retention`, default
  7 days), documented at-least-once residual window. Dispatch goes through the
  core-owned `PhaseTwoRouter` (registry (module, process) →
  `MigrationProcessService` + platform-registered `Function<String,Object>` ID
  converter, registered at bean creation); START uses the persisted adapter ID,
  future operations probe adapters. Default implementations per
  platform/persistence; config `vanillabp.outbox.*`.
- **`WorkflowAwareness`:** enum (`ACTIVE`, `COMPLETED`,
  `UNKNOWN_TO_BPMS`, `BPMS_UNAVAILABLE`) returned by
  `MigratableProcessService.awarenessOfTask/awarenessOfWorkflow` — the basis for
  the (not yet implemented) fallback election. `BPMS_UNAVAILABLE` means retry
  later, never fall back.
- **Deployment-failure policy:** `vanillabp.adapters.<id>.deployment-failure` =
  `fail` (default) | `warn` (non-first-priority adapter may fail deployment
  without preventing boot). Retry/backoff configuration (`vanillabp.resilience.*`)
  was removed ("optimize late") - it returns per adapter with the first consumer
  (story 22).
- **Dummy adapter:** log-only adapter in each platform's integration-tests; template
  for adapter authors and test double for infrastructure tests without a real BPMS.

## Where things live

- `spi-for-java/` — user-facing API: `@WorkflowService`, `@WorkflowTask`, `@TaskId`,
  `@TaskEvent`, `@TaskParam`, multi-instance annotations, `ProcessService<A>`
  (start, correlate messages, complete/cancel tasks, viewer/history API).
- `adapter-platform-integration/migration-adapter/business-spi/` — business SPI
  (`io.vanillabp:vanillabp-integration-spi`): `AggregatePersistenceAware`.
- `adapter-platform-integration/migration-adapter/spi/` — adapter SPI:
  `AdapterDeploymentService<BPMN, PC> extends ExtensionWiringService`,
  `MigratableProcessService` (awareness methods), `PhaseTwoOutbox`,
  `PhaseTwoCall`, `PhaseTwoOperation`, `ExtensionWiringService`,
  `BpmnParseException`, `WorkflowAwareness`.
- `adapter-platform-integration/migration-adapter/runtime/` — core runtime:
  `DeploymentService`, `MigrationProcessService`, `PhaseTwoRouter`,
  `MigrationAdapterProperties`.
- `adapter-platform-integration/spring-boot-integration/` — auto-configurations,
  `ProcessServiceSpringBean`, `SpringDataUtil` (JPA/MongoDB), `spring-boot-support`.
- `adapter-platform-integration/quarkus-integration/` — extension
  (deployment = build steps + Gizmo bean generation, runtime =
  `ProcessServiceBaseCdiBean`), `quarkus-support`.
- `adapter-platform-integration.wiki/` — user-facing documentation (concepts,
  configuration, platform guides). Module `README.md` files = contributor/development
  documentation.

Full analysis incl. implementation status: `/workspaces/VanillaBP2/ANALYSE.md`.
