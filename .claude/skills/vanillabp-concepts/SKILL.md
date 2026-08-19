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
- **Election cache** (`WorkflowAdapterCache`, business SPI): remembers which adapter
  holds a workflow, so the next operation skips the probing walk. Entries are HINTS —
  losing one costs an extra walk (and, on an eventually consistent BPMS, the
  visibility window), never correctness. The in-memory default is bounded and
  expiring, sized by `vanillabp.workflow-adapter-cache.max-entries` / `.time-to-live`
  (10.000 / 1 h); a cluster shares elections by providing its own bean. What the cache
  does is counted in `WorkflowAdapterCacheStatistics` (published as Micrometer meters
  `vanillabp.workflow.adapter.cache.*` where Micrometer is present, optional on both
  platforms), and hints lost to eviction pressure produce a guiding WARN at most once
  per hour.
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
- **`TransactionRunner` / `TransactionRunnerAware<A>` (story 70):** the transaction
  VanillaBP wraps around everything it does with one aggregate (delivery lookup,
  `loadById`, handler, `save`, delivery record, outbox entry). Lives in the business SPI,
  so an application whose aggregates are stored in a system the platform does not manage
  (event store, ledger, message producer, an API) contributes its own unit of work -
  either as a plain bean serving every aggregate, or attributed per aggregate through the
  aware bean, whose named class may be an interface all aggregates of a workflow module
  implement (most specific wins, a tie ends the boot). Resolution order: aware bean,
  application bean, platform runner (Spring: a unique `PlatformTransactionManager`;
  Quarkus: JTA, always there), nothing - which ends the boot where the first-priority
  adapter needs a two-phase commit. The platform also reports what the transaction COVERS
  (`TransactionCoverage`), which is how a MongoDB aggregate without a
  `MongoTransactionManager` and a MongoDB deployment without a replica set are named at
  startup; `vanillabp.transactions.unguarded-aggregate-writes` accepts the weaker
  behaviour deliberately.
- **`AggregatePersistenceAware<A>`:** persistence abstraction
  (`getAggregateClass`, `save`, `getAggregateId`). Lives exactly once in the
  business SPI `io.vanillabp:vanillabp-integration-spi` (package
  `io.vanillabp.integration.spi`), provided transitively by both support modules.
  The implementation with the most specific generic aggregate type wins
  (inheritance-distance metric in `AggregatePersistenceResolver`). An application
  implementation always beats the platform defaults: Spring Data on Spring Boot,
  and on Quarkus a Panache repository, a Panache active record (JPA or MongoDB) or
  a Spring Data repository, picked at build time per aggregate
  (`DefaultAggregatePersistenceResolver`).
- **`PhaseTwoOutbox` / `PhaseTwoCall` / `PhaseTwoRouter`:** adapter-SPI contract
  for crash-safe phase-two dispatch of two-phase BPMS calls. Stores implement
  exactly one method `boolean schedule(PhaseTwoCall)` (enlist in local
  transaction); typed default methods (`scheduleStartWorkflow(module, process,
  aggregateId, adapterId)`) build the immutable `PhaseTwoCall` record via
  `PhaseTwoCall.of(operation, ...)` (a store rebuilding a call from a persisted
  entry uses `forDispatch(name, ...)`; the aggregate ID travels as String only).
  Operations are entries of the `PhaseTwoOperationRegistry`: persisted NAME +
  idempotency-key derivation (`PhaseTwoOperation`, core operations as constants) +
  dispatch (`PhaseTwoOperationDispatch`, registered at startup). The core registers
  its seven operations in the router; an EXTENSION registers namespaced ones
  (`my-extension:NOTIFY`, enforced) and gets their calls in its own handler, without
  adapter election. An unregistered operation at dispatch = guiding error, entry
  stays in the store. Contract: unique idempotency key enforced by the store (duplicate
  schedule = no-op, returns false; START key = module|process|aggregateId), DONE
  instead of delete (async cleanup after `vanillabp.outbox.retention`, default
  7 days), documented at-least-once residual window. Dispatch goes through the
  core-owned `PhaseTwoRouter` (registry (module, process) →
  `MigrationProcessService` + platform-registered `Function<String,Object>` ID
  converter, registered at bean creation); START uses the persisted adapter ID,
  future operations probe adapters. Default implementations per
  platform/persistence; config `vanillabp.outbox.*`.
- **`TaskDeliveryLog` / `TaskDelivery` / `TaskDeliveryLogAware` (story 51):** the
  INBOUND counterpart of the outbox - durable memory of the task deliveries the core
  processed, so a redelivery of work an at-least-once BPMS never learned the result of
  reports the recorded outcome instead of running the `@WorkflowTask` method again. The
  identity comes from the adapter
  (`TaskInvocationContext.getDeliveryId()`: C8 job key, PEA task id, C7 none - it
  delivers in its own transaction, so a redelivery proves nothing was committed) and is
  qualified by `TaskDeliveryKey` (adapter|module|process|event|deliveryId, hashed above
  512 chars). The record is written in the HANDLER's transaction (a rolled-back delivery
  leaves none and runs again), carries the `WorkflowTaskOutcome` incl. BPMN error code,
  and is resolved per aggregate (`TaskDeliveryLogResolver`, mirroring the outbox
  resolver). Switch: adapter-scoped `deduplicate-deliveries` (default true, resolvable
  per module/workflow/task); `MigratableProcessService.deliversTasksAtLeastOnce()`
  decides only whether a missing log is worth a startup WARN. Stores: own table
  `VANILLABP_TASK_DELIVERY` (shared SQL in the core's `JdbcTaskDeliveryStore`) resp.
  collection `vanillabp-task-deliveries`, settings shared with `vanillabp.outbox.*`
  (create-schema, retention). Deliberately NOT gruelbox on Spring/JPA: gruelbox
  dispatches calls, a delivery record is read back.
- **Two writers on one workflow aggregate (story 59):** a BPMN process holding more
  than one token has two branches writing the same aggregate - one in the transaction
  VanillaBP owns for its task, one in the transaction the application opens around its
  API call - and a persistence layer writing the whole record loses what the branch
  committing first wrote. VanillaBP does not resolve it, it makes it visible: adapters
  report the elements producing a second token during `wireBpmn`
  (`WorkflowTaskInvoker#reportConcurrentTokenElements`), the core warns once per BPMN
  process where the aggregate has no version attribute (`ConcurrentTokenCheck`, matching
  the annotation by its SIMPLE name so JPA and Spring Data are covered without a
  dependency), and a version conflict in a commit the core owns is named by one guiding
  ERROR and rethrown UNCHANGED (`AggregateWrite#inTransaction`, classification through
  the platform's `TransactionRunner#isConcurrentModification`). Deliberately NO retry
  inside the framework: the BPMS retries and ends in an incident, and a handler may have
  called a remote API before the commit failed. Where the BPMS owns the transaction (C7
  embedded) VanillaBP never sees the conflict. The delivery record of story 51 rolls back
  with the aggregate, so the retried delivery runs the handler again - which is the
  boundary between the two stories, documented on the wiki page `Workflow-aggregates`.
- **Workflow-ended notification:** optional `@WorkflowEnded` method (spi-for-java,
  value record `WorkflowEnd`); adapter SPI `…adapter.spi.workflowend`
  (`WorkflowEndedInvoker`, implemented by `WorkflowTaskRegistry`). Adapters ask
  `workflowEndedHandlerExists` while wiring and attach a listener ONLY where a method
  exists. C7: END execution listener at the process scope, in the engine TX,
  COMPLETED vs. TERMINATED via delete reason; C8: `end` execution listener on the
  process element plus worker, COMPLETED only; PEA: not possible, WARN (gap 17).
  At-least-once; a deleted aggregate is skipped, not an error.
- **Signals:** `ProcessService.sendSignal(name)` is a BROADCAST (no aggregate, no
  election). It fans out over the deployment union of the workflow module; embedded
  BPMS broadcast in phase one, remote ones via the `SEND_SIGNAL` outbox operation
  (adapter id persisted per entry, NO idempotency key). Adapter SPI:
  `sendSignalPhaseOne`/`sendSignalPhaseTwo` (defaults throw guiding). Deliberately no
  instance-targeted variant - Camunda 8 cannot do it. SCOPE = the workflow module of
  the calling process service (own client + tenant per adapter, module prefix applied
  in `use-prefix`); crossing module boundaries is the application's job.
- **`aggregateChanged` (story 44):** `ProcessService.aggregateChanged(aggregate)` pushes
  the values shared per the sync model at the workflow's GLOBAL scope,
  `aggregateChanged(aggregate, taskId)` in the scope the task RUNS in (process,
  embedded subprocess, or ONE iteration of a multi-instance embedded subprocess - never
  the task's own scope) and deliberately NOT additionally globally. Shape mirrors
  `correlateMessage` (save, probe `awarenessOfWorkflow`, phase one embedded / outbox
  remote); core operation `AGGREGATE_CHANGED` WITHOUT idempotency key, because the
  values are read at dispatch time. Adapter SPI
  `aggregateChangedPhaseOne`/`aggregateChangedPhaseTwo` (defaults throw guiding). C7
  writes `setVariables`/`setVariablesLocal` and thereby makes conditional events work
  (technical marker variable `vanillabpAggregateChanged` when nothing is shared); C8
  sends `SetVariables` and NEEDS secondary storage (query API translates aggregate id
  into instance/element keys); PEA cannot do it at all (gap 18).
- **BPMS-initiated start:** a workflow started by the BPMS itself (timer, signal or
  conditional start event) has no aggregate yet, so the core builds one: adapter SPI
  `io.vanillabp.integration.adapter.spi.workflowstart` (`BpmsInitiatedStartInvoker`,
  implemented by `WorkflowTaskRegistry`, plus spec/context/result types); adapters
  report their start events during `wireBpmn` and notify at runtime. ID rules: the
  BPMS' own identity of the start (remote: instance key) > a timer's trigger time >
  generated > left to the persistence layer. Optional application hook
  `@WorkflowStartedByBpms` (spi-for-java) building or enriching the aggregate. C7:
  execution listener on the start event, business key set from the aggregate; C8:
  injected `zeebe:executionListener` (eventType `end`, `start` is rejected there);
  PEA: deployment fails guiding (gap 16).
- **Process version (`version` attribute, story 48):** `@WorkflowTask`,
  `@WorkflowStartedByBpms` and `@WorkflowEnded` carry `version`, matched against the
  version of the deployed process DEFINITION as the BPMS counts it (C7/C8: integers
  upwards per process id) - never a business version. Core: `VersionRange` (parse once,
  `matches`, `overlaps`) plus `ProcessVersions` (catalogs per module/process) in package
  `workflowtask`, used by all three registries. Formats: `*`, `3`, `1-3`, `>3`/`>=3`,
  `<3`/`<=3`, and a version TAG (`camunda:versionTag` / `zeebe:versionTag`) anywhere a
  number may stand; ranges over tags use `..` (a tag may contain `-`). Numbers cost
  nothing (compared to the reported version); a TAG is placed through the adapter SPI
  `spi.version.ProcessVersionCatalog` (base class `CachingProcessVersionCatalog`),
  registered per process in `wireBpmn` and warmed by
  `WorkflowTaskInvoker.resolveProcessVersions(module)` at the END of `deployResources`,
  with an on-demand BPMS query for a version this node never deployed (rolling
  deployment). Duplicate detection = real OVERLAP of the ranges (disjoint ranges are
  legitimate), checked at registration and again after the tags were resolved. C7 reports
  the version everywhere (cached per definition id) and can be asked for tags; C8 ships it
  with every job, tags need the query API; PEA only reports the tag of the current task
  where the engine supplies it (gap 19).
- **`WorkflowAwareness`:** enum (`ACTIVE`, `COMPLETED`,
  `UNKNOWN_TO_BPMS`, `BPMS_UNAVAILABLE`) returned by
  `MigratableProcessService.awarenessOfTask/awarenessOfWorkflow` (the workflow probe
  takes the aggregate persistence: the aggregate-ID variable is named after the
  aggregate's ID attribute) — the basis for
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
  `PhaseTwoCall`, `PhaseTwoOperation`, `PhaseTwoOperationRegistry`,
  `PhaseTwoOperationDispatch`, `ExtensionWiringService`,
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
