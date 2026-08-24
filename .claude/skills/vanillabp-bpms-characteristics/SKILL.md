---
name: vanillabp-bpms-characteristics
description: Traits of the BPMS supported by VanillaBP adapters (Camunda 7, Camunda 8, Process-Engine-API, ZenBPM) and their consequences for implementing adapter features — use when writing or implementing adapter code or feature prompts, when deciding what is BPMS-specific vs. generic, or when reasoning about transactions, idempotency, eventual consistency or BPMS migration.
---

# BPMS Characteristics (VanillaBP Version 2)

## The one rule that shaped Version 2

**Generic mechanisms live in `adapter-platform-integration`, never in an adapter.**
In Version 1, concepts like the transaction outbox and eventual-consistency handling
were implemented inside the specific adapters (where they conceptually belong at first
glance). That broke the *migration feature*: switching a running application from one
BPMS to another (or running two BPMS side by side) only works if two-phase commits,
adapter election, retries and idempotency are handled uniformly by the migration
adapter. That is why `PhaseTwoOutbox`, `WorkflowAwareness`
and the deployment-failure policy exist in the core. Adapters only contribute the
BPMS-specific behavior behind these SPIs.

Consequence when implementing a feature: first ask "which part of this is the same for
every BPMS?" — that part goes into `migration-adapter` (and its platform glue). Only
the remainder goes into the adapters, implemented against the adapter SPI.

## Two-phase commit: what phase one may and may not do

Every operation that mutates a *remote* BPMS (start, complete task, correlate message,
...) is split into two phases by the `PhaseTwoOutbox`, because the remote engine cannot
join the local DB transaction. The precise rule for **phase one** (which runs *inside*
the still-uncommitted local transaction) is often stated too strongly as "must not
contact the cluster" — that is wrong. The real rule:

- **Phase one MUST NOT perform any action that *advances* the BPMN process** (create an
  instance, complete/cancel a task, correlate/publish a message, ...). Such an action
  would race the still-uncommitted local transaction: if the transaction later rolls
  back, the BPMS has already moved on → ghost progress / inconsistency. The advancing
  action is always deferred to phase two (after commit, via the outbox).
- **Phase one MAY contact the cluster for a *non-advancing* check** whose only purpose
  is to **abort the local transaction early** when it is already clear the phase-two
  action cannot succeed — failing fast instead of committing and only then discovering
  in phase two that the action is impossible (which would leave a stale outbox entry).
  - Example — completing a service task: phase one verifies the task still exists by
    **extending/resetting the job's worker timeout** (a non-advancing operation). If it
    succeeds, the task is there and the transaction may commit; if not, abort now.
  - **Refinement (from the V1 Camunda 8 adapter):** run this check in a **pre-commit
    transaction synchronization** (right before commit), not at the start of phase one.
    This minimizes the window between the check and the phase-two action and therefore
    the number of *stale outbox entries* (entries scheduled for an action that became
    impossible between check and dispatch).
- **Starting a workflow is the degenerate case: phase one has nothing to check against
  the cluster.** There is no pre-existing state to validate; if the cluster is
  unavailable, the phase-two start just waits in the outbox until it is reachable. So a
  start adapter's phase one only resolves the aggregate id and verifies configuration.
- **A phase-two failure is repeated unless the adapter says it cannot help.** The
  outbox retries until the entry is blocked, which is what makes an operation losing a
  concurrency conflict survivable. Where the BPMS will answer the same way every time
  (Camunda 7 rejecting an invalid command, an API which cannot do what was asked), the
  adapter answers `false` to `MigratableProcessService.isPhaseTwoFailureRepeatable`
  (default `true`). The core then wraps the failure in a
  `PhaseTwoPermanentFailure` and every store blocks that entry after ONE attempt.
  Keep the list of permanent cases short: repeating is the safe default.

  What each adapter answers today:

  | Adapter | Permanent | Everything else |
  |---|---|---|
  | Camunda 7 | `BadUserRequestException` (a task id which does not exist, an argument the engine rejects) | repeated, `OptimisticLockingException` being the case two-phase exists for |
  | Camunda 8 | HTTP `400`/`403`/`405`/`501` and the gRPC `INVALID_ARGUMENT`/`PERMISSION_DENIED`/`UNIMPLEMENTED`, plus `NumberFormatException` on a task key | repeated, deliberately including `404` (eventual consistency), `401` (expired token), `409`, `429`, `5xx` |
  | Process-Engine-API | `UnsupportedOperationException` - what the API cannot do at all (signal without `SignalApi`, pushing a changed aggregate) | repeated: the API has no typed exceptions, so "refused" and "unreachable" are indistinguishable |

  What phase one can ASK differs the same way: Camunda 7 asks its embedded engine for
  free, Camunda 8 runs non-advancing checks against the cluster (job timeout update, empty
  user-task update) as a PRE-COMMIT synchronization, and the Process-Engine-API uses
  `ExecutionMode.PREFLIGHT_CHECK` where a command lets it (an `open class` - the final
  `data class` commands `CorrelateMessageCmd` and `SendSignalCmd` do not, which is why
  correlation and signals have no preflight there). For a message correlation Camunda 8
  asks the MODEL instead of the cluster: a message no deployed model of the workflow module
  declares fails in phase one, because the cluster would buffer the publication until its
  time-to-live passed and nothing would ever correlate.

Camunda 7 used to do everything in phase one within the shared transaction. Since story
63 it uses the same two-phase path as every other BPMS: an operation which loses a
concurrency conflict cannot be repeated inside the caller's transaction (every engine
command joins it, so a failing one leaves it rollback-only), and repeating just the
engine part in a transaction of its own would advance the process while the application
rolls back. Being embedded, its phase one asks MORE than a remote one can: the task's
existence, a waiting message subscription, a deployed message start event - exactly and
for free, from the caller's own transaction.

**Being embedded is no reason to share less.** Every BPMS evaluates the
expressions of its models against ITS OWN variables, an embedded engine included - so
Camunda 7 pushes the shared values like every other adapter, at every point the adapter
talks to the engine, the completion of a `@WorkflowTask` method included (a gateway right
behind a service task decides on what that task computed). Reading the aggregate live was
the older approach and it made models unportable: they worked on Camunda 7 and took the
default flow everywhere else. What remains of it is a migration fallback for workflows
started before the upgrade, removed in 2.1. Consequences for an adapter of the C7 family:
the values are written INSIDE the engine's transaction (the handler ran there), nested
values need a serialization format the application configures, and any
`ProcessEnginePlugin` bean of the application has to reach the engine the adapter builds -
otherwise no dataformat can be installed.

**An embedded engine also limits where the aggregate may live:** Camunda 7
needs a relational database, and its engine transaction can never cover a workflow
aggregate stored anywhere else - MongoDB, an event store, a ledger. Such an application
is legal, but the engine and the aggregate commit separately, and no configuration
changes that. A remote BPMS has no such tie: there the aggregate's store decides which
transaction VanillaBP opens, and the phase-two outbox entry rides it.

## BPMN modification at deployment is engine-specific

VanillaBP does not deploy the user's BPMN as-is: during the deployment pipeline
(`prepareBpmn`/`wireBpmn`) the adapter **modifies the model according to well-known
best practices — and those are engine-specific**. Examples:

- **Camunda 7:** set `asyncAfter` on service tasks, so the transaction ends when the
  task completes. This aligns embedded-engine behavior with remote BPMS, and avoids the
  anti-pattern of running several service tasks in one transaction (whose scope would be
  engine-specific and surprising).
- **Camunda 7 AND Camunda 8:** inject task listeners and execution listeners at
  deployment to enable various VanillaBP features.

This is the deep reason why **BPMS-specific adapters are necessary even where a generic
Process-Engine-API adapter exists**: the PEA deploys opaque resources and cannot express
these engine-specific rewrites. Long-term vision: BPMS adapters *extend* the generic PEA
adapter and add only these specifics (parsing/modification, listeners). Today that is
not realistic — PEA implementations lag behind or are not clean enough — so the Camunda
adapters are implemented natively; **only the ZenBPM adapter is planned on the PEA
base** for now.

## Camunda 7 (embedded, synchronous)

- Engine runs **inside the application's JVM** and uses the **same database and the
  same DB transaction** as the business code. Calls are synchronous.
- Version: **7.24 is the final feature release** (Oct 2025, LTS; community edition
  EOL — no further community releases). Pin 7.24.x.
- `needsTwoPhaseCommitForStartingWorkflows()` = **true** (for every
  adapter id): every progressing operation is scheduled through the phase-two outbox and
  runs after the commit, so it can be repeated when it loses a conflict. An outbox is
  therefore mandatory for Camunda 7. What phase one still does is ASK - a task which is
  gone, a message nobody waits for and an unknown message start event still fail
  synchronously, where the application made the call - a wrong correlation id
  included, since the id the waiting execution expects is a local variable phase one
  can read.
- Permanent phase-two failures: a `BadUserRequestException` (an operation the engine
  refuses as invalid, e.g. a task id which never existed) is reported as NOT repeatable,
  so its outbox entry is blocked right away instead of after ten attempts. Everything
  else, the optimistic-locking conflict above all, stays repeatable.
- The INBOUND direction is unchanged: the engine delivers tasks inside its OWN
  transaction, so aggregate changes and engine state still commit together there, and
  `deliversTasksAtLeastOnce()` stays `false`.
- No eventual consistency: engine queries (awareness, task state) read the local DB
  and are authoritative. `BPMS_UNAVAILABLE` practically cannot occur.
- Asynchronous continuations (async-before/after, timers) run on the engine's **job
  executor** — still in-JVM, still same DB.
- Exceptions thrown by `@WorkflowTask` methods roll back the shared transaction —
  business data and engine state stay consistent automatically.
- Workflow-module isolation: use the **workflow module ID as Camunda tenant ID**
  (Version-1 behavior) to avoid BPMN process ID clashes between modules.
- The 1:1 aggregate relation maps naturally to the Camunda 7 **business key**.
- **Platform wiring uses the plain engine, never Camunda's starter/extension** (both
  are version-locked to EOL platform releases). Both recipes are implemented and
  commented in the adapter itself — `Camunda7EngineHolder` for Spring Boot,
  `Camunda7QuarkusEngineHolder` for Quarkus; read those before changing the wiring.
  What they do:
  - Spring: `camunda-engine-spring-6` wiring sharing the application's DataSource and
    `PlatformTransactionManager`, with `SpringJobExecutor` deferred to
    `startWorkflowProcessing`.
  - Quarkus: the engine-shipped `JakartaTransactionProcessEngineConfiguration` on
    Agroal plus Narayana, `transactionsExternallyManaged(true)`, and two settings
    which are not optional — the schema-ops `JakartaTransactionInterceptor`, because
    Agroal has no deferred enlistment, and the engine classloader set to the Quarkus
    runtime TCCL, because JobExecutor threads otherwise fail to load delegate classes.
  - **JVM mode only, no native image.** The engine stack (MyBatis, JUEL, scripting,
    reflective delegate instantiation, XML parsers) is reflection-heavy, Camunda never
    supported native, and neither fork claims to.
- **C7 forks (Camunda 7 is EOL):** Operaton (`org.operaton.bpm`, community) and CIB
  seven (`org.cibseven.bpm`, commercial LTS) — both **renamed all Java packages** (no
  drop-in, no bridge jar), but the APIs port by mechanical package rename and both
  accept the legacy `camunda:` BPMN namespace (verified by probes on both platforms).
  Decided strategy: the adapter stays Camunda-7-only, written portably (see
  `vanillabp-adapter-building`); fork adapters are generated later by **OpenRewrite**
  copy. A `camunda7 → operaton/cibseven` switch is a REAL VanillaBP migration: two
  embedded engines side by side with **separate schemas/datasources per adapter id**
  (a low-level in-place DB swap affects all instances at once and is out of
  VanillaBP's scope).

## Camunda 8 (remote, eventually consistent)

- **Remote service** (SaaS or self-managed cluster), accessed via
  `io.camunda:camunda-client-java` (8.8.x; the old `zeebe-client-java` is deprecated,
  removal announced for 8.10). Use the **plain Java client**, NOT Camunda's Spring
  SDK — platform wiring and configuration are done by VanillaBP itself (same
  reasoning as for the Process-Engine-API below).
- `needsTwoPhaseCommitForStartingWorkflows()` = **true**: the engine cannot join the
  local DB transaction. The actual `CreateProcessInstance` happens in phase two,
  dispatched through the `PhaseTwoOutbox`. **For starting a workflow, phase one does
  nothing against the cluster** — if the cluster is down, the phase-two start waits in
  the outbox until it is reachable (see the two-phase rules above; other operations
  like completing a task DO use a phase-one check).
- **Eventual consistency:** a started instance may not be visible to queries
  immediately (exported data lags behind the engine). Awareness implementations must
  distinguish carefully: gateway unreachable → `BPMS_UNAVAILABLE` (never triggers
  fallback election); a successful query that finds nothing → `UNKNOWN_TO_BPMS`.
  Answering `UNKNOWN_TO_BPMS` for a workflow which exists is NOT a bug to hide, it is
  what the read model knows — report a `workflowVisibilityDelay()` instead (Camunda 8:
  `workflow-visibility-timeout`, 10s), and the core keeps asking while it has a reason
  to believe this BPMS holds the workflow.
- **The aggregate-ID variable is named after the aggregate's ID attribute**, so every
  lookup needs that name from the persistence of the call at hand. Camunda 8 stores
  variables as JSON, so the filter value carries quotes (`"\"4711\""`). Both were
  real defects once, and each made every probe find nothing.
- **At-least-once job workers:** service tasks are pulled by polling workers; a job
  may be delivered again after a timeout or crash. `@WorkflowTask` handlers are
  therefore called at least once → task completion must be **idempotent** (keyed by
  aggregate state, not by call count).
- No business key: the workflow-aggregate ID travels as a process variable; no other
  process variables are used (aggregate attribute sync is the `@SyncWithBPMS` story).
- Strict idempotency of phase-two workflow starts needs a core-side
  `WorkflowInstanceRegistry` (planned story) — C8 itself offers no cheap
  "instance already exists for this aggregate" check due to the query lag.

## Process-Engine-API (BPMS-agnostic, bpm-crafters)

- `dev.bpm-crafters.process-engine-api:process-engine-api` (Kotlin, 100%
  Java-compatible; 1.7+, verify latest on Maven Central). A second BPMS-agnostic API
  besides VanillaBP, but **lower-level**: command/API-oriented instead of
  aspect-oriented.
- API surface (each an own interface, Java package `dev.bpmcrafters.processengineapi`
  — note the artifact groupId has a hyphen, the package does not): `deploy.DeploymentApi`,
  `process.StartProcessApi`, `correlation.CorrelationApi`, `correlation.SignalApi`,
  `task.TaskSubscriptionApi`, `task.ServiceTaskCompletionApi`,
  `task.UserTaskCompletionApi`, `task.UserTaskModificationApi`,
  `decision.EvaluateDecisionApi`. Commands are `ExecutionModeAware`; several APIs
  extend `MetaInfoAware` + `RestrictionAware` (mostly Java-`default` methods).
  `DeploymentApi` deploys opaque `NamedResource`s — there is no BPMN model type
  (consumers parse BPMN themselves).
- **`ExecutionMode`** (FQN `dev.bpmcrafters.processengineapi.ExecutionMode`; issue
  bpm-crafters/process-engine-api#281, released in 1.6):
  every command method takes an `ExecutionMode` — `DEFAULT` (adapter decides,
  usually async), `ASYNC` (fire via `CompletableFuture`, no transaction awareness),
  `SYNC` (execute in the caller's thread/transaction: embedded engines join the DB
  transaction, remote engines write an outbox entry), `PREFLIGHT_CHECK` (validate
  only, optimistic fast-fail, no execution). This maps directly onto VanillaBP's
  two-phase pattern: **phase one ≈ `PREFLIGHT_CHECK`, phase two ≈ `SYNC`**.
- The VanillaBP adapter uses **only the pure Java/Kotlin API artifact** — none of the
  existing platform-specific PEA implementations (their platform binding and
  configuration philosophy differs from VanillaBP's).
- **Mock-first strategy:** the PEA implementation is fully mocked (an own in-memory
  fake module). Purpose: discover, feature by feature, where either VanillaBP or the
  Process-Engine-API needs extensions. Findings are collected in the adapter repo's
  `GAPS.md`. Known upfront: several VanillaBP features cannot be expressed through
  PEA at all (e.g. module-as-tenant semantics, viewer/history API) — a real
  BPMS-specific adapter built *on top of* the PEA adapter would be slimmer but still
  needs BPMS-specific escape hatches.
- Treat it like a remote BPMS: `needsTwoPhaseCommitForStartingWorkflows()` = true,
  so the generic outbox path is exercised.

## ZenBPM (future)

- New BPMS by pbinitiative with a plain **REST API**
  (<https://github.com/pbinitiative/zenbpm/blob/main/openapi/api.yaml>). Adapter
  planned later; expect remote-BPMS traits (two-phase start, eventual consistency,
  polling or callback-based task delivery).
- **Decided:** the ZenBPM adapter will be built **on the Process-Engine-API adapter**
  (the first — and currently only — PEA-based BPMS adapter), adding the BPMS-specific
  parts on top (see "BPMN modification at deployment").

## Cheat sheet

| Trait | Camunda 7 | Camunda 8 | PEA | ZenBPM |
|---|---|---|---|---|
| Location | in-JVM | remote | depends (treat remote) | remote |
| Joins local TX | inbound yes (task delivery), outbound no | no | `SYNC` mode may | no |
| Aggregate sync default | `FULL` (it used to be `NONE` plus a live read) | `FULL` | `FULL` | `FULL` |
| Two-phase start | yes | yes | yes | yes |
| Eventual consistency | no | yes | possible | expected |
| Task delivery | synchronous / job executor | polling workers, at-least-once | Task Subscription API | REST (tbd) |
| Idempotent handlers needed | no | yes | yes | yes |
| Sees a version conflict of the aggregate | no while delivering (engine owns the TX) | yes | yes | yes |
| Failed task ends in | retry by job executor, then incident | retries counted down, then incident | the engine's business | tbd |
| Identity of a delivery | none needed (delivery in engine TX) | job key | task id | tbd |
| Module isolation | tenant ID | tbd (variable/tenant) | not expressible (gap) | tbd |
| Client artifact | `org.camunda.bpm:camunda-engine` 7.24.x | `io.camunda:camunda-client-java` 8.8.x | `dev.bpm-crafters.process-engine-api:process-engine-api` | REST (openapi) |

## Checklist for every adapter feature

1. What is generic? → implement in `migration-adapter` (+ platform glue), not here.
2. Which `ExecutionMode`/phase does each call belong to (in-TX vs. after-commit)?
3. Is the operation delivered at-least-once? → make the handler idempotent and name
   the idempotency key. INBOUND (BPMS → application) that means two answers:
   `deliversTasksAtLeastOnce()` and an identity per delivery
   (`TaskInvocationContext.getDeliveryId()`), stable across a redelivery and different
   for a new task instance - the core then skips the handler of a repeated delivery and
   reports the recorded outcome. Where the BPMS delivers inside the application's
   transaction, both answers are "no" and that is the complete answer.
4. Can the BPMS answer "unknown" reliably, or only eventually? → map to
   `UNKNOWN_TO_BPMS` vs. `BPMS_UNAVAILABLE` correctly (wrong mapping breaks election),
   and report a `workflowVisibilityDelay()` where "unknown" may just mean "not yet".
5. Does the feature work per workflow module (tenant/namespace)? If not expressible:
   document the gap (PEA: `GAPS.md`).


## Starting a workflow the BPMS decides on

A timer, signal or conditional start event starts a process without the application.
What each BPMS offers to notice it:

- **Camunda 7:** an execution listener on the start event, running in the engine's own
  transaction. The aggregate and the process instance commit together, so a failure
  rolls both back and there is no repeated notification to guard against. The
  aggregate's ID becomes the instance's BUSINESS KEY. The engine does not tell the
  listener a timer's scheduled time.
- **Camunda 8:** execution listeners exist since 8.6, but the cluster REJECTS event
  type `start` on a start event ("Execution listeners of type 'start' are not
  supported by start events", verified against 8.8.31). An `end` listener on the start
  event works and still gates the transition. Its job completion carries the
  aggregate-ID variable. The cluster does not report a timer's scheduled time either,
  so the stable identity is the PROCESS INSTANCE KEY - it survives a retried listener
  job, which a remote BPMS can always produce. Conditional events do not exist in
  Camunda 8 at all.
- **Process-Engine-API:** nothing. The API reports tasks, not starts, so such a
  process is rejected while deploying (GAPS.md 16).

The lesson generalizes: where a BPMS can repeat a notification after the aggregate was
committed, the aggregate's ID has to be derived from something the BPMS itself keeps
stable; where notification and aggregate share one transaction, the meaningful value
(the trigger time) can be used.


## Signals

- **Camunda 7:** `RuntimeService.createSignalEvent(name)` with tenant handling, inside
  the caller's transaction. It CAN target a single execution (`executionId`), which
  VanillaBP deliberately does not expose - no other BPMS can.
- **Camunda 8:** `BroadcastSignal` (8.3+), after the commit. No payload, no message id
  equivalent, so no deduplication.
- **Process-Engine-API:** `SignalApi.sendSignal(SendSignalCmd)` exists (1.5+), so the
  adapter can serve signals; the command carries a payload supplier which VanillaBP
  leaves empty.

The asymmetry that matters: only an embedded engine can make the broadcast part of the
application's transaction. Everywhere else the outbox does it, and the at-least-once
residual has no cure because a signal carries no key.


## Pushing a changed aggregate

- **Camunda 7:** `RuntimeService.setVariables(processInstanceId, ...)` /
  `setVariablesLocal(<scope execution>, ...)`, inside the caller's transaction. The
  task-scoped write goes to the scope the task RUNS in, found by walking the execution
  tree upwards: skip the execution of an activity's own scope (boundary events,
  multi-instance instance - the model tells which activity has one) and skip the
  multi-instance BODY (recognizable by its local `nrOfInstances`). Note the tree shape:
  for a multi-instance subprocess the iteration's SCOPE execution is the one the task
  executes on, while `item`/`loopCounter` live on the concurrent execution above it.
  Conditional events (intermediate, boundary, event subprocess) are evaluated ONLY when
  a variable of their scope or of a PARENT scope changes - `createConditionEvaluation()`
  is for conditional START events and does not help here. Since this adapter shares nothing by default, an empty
  push would be no change at all: VanillaBP writes `vanillabpAggregateChanged` (the
  push time) so the variable event happens. Verified by an IT: the conditional event
  fires only after the push, and a task-scoped push leaves the siblings and the process
  scope untouched.
- **Camunda 8:** `newSetVariablesCommand(key)` with `local(false)` for the process
  instance and `local(true)` for the element instance of the scope the task runs in,
  after the commit. The keys are NOT derivable without the query API: a process instance
  is found by the aggregate-ID variable, the task's element instance via job search by
  job key (a VanillaBP task id IS the job key). The API has no parent link on an element
  instance (only an `elementInstanceScopeKey` FILTER), so the scope around a task is
  found by walking down from the process instance. So the feature requires secondary storage, and the adapter says so. NOTE
  variable filters carry JSON values - a String has to be searched WITH quotes, which
  the client does not add (getting this wrong made EVERY probe answer
  UNKNOWN_TO_BPMS on clusters with secondary storage, and no test noticed because the
  test clusters had none). One encoder `Camunda8VariableFilters` serves every search.
  When writing Camunda 8 tests, ask which cluster the test needs: without secondary
  storage the awareness probe is the optimistic FALLBACK, not the query.
- **Process-Engine-API:** payload modification exists for TASKS only
  (`UserTaskModificationApi` + `ChangePayloadModifyTaskCmd`), never for a running
  instance - gap 18, both phases throw guiding.

Conditional events are the asymmetry worth remembering: Camunda 7 has them and needs a
variable change to look at them, Camunda 8 has none at all.

Camunda 7 EL pitfall found here: `Camunda7TaskConnectable.applies` matches by ELEMENT id
too, so every expression evaluated while an execution sits at a wired task used to resolve
to that task's behavior. The resolver now prefers a workflow-aggregate attribute unless the
name IS a task definition, asking the core via `workflowAggregateHasProperty` (class-level,
no aggregate loaded).


## The end of a workflow

- **Camunda 7:** an END execution listener at the PROCESS scope, inside the engine's
  transaction. `PvmExecutionImpl#getDeleteReason()` is what distinguishes a cancelled
  or terminated instance from one which reached an end event, and the current
  activity id names that end event.
- **Camunda 8:** an `end` execution listener on the PROCESS element is accepted
  (verified against 8.8.31 - unlike `start` on a start event, which is rejected). It
  runs for COMPLETED instances only: a cancelled instance is removed without running
  end listeners, so the adapter cannot report a cancellation and says so.
- **Process-Engine-API:** nothing. Task subscriptions are all the API offers, so the
  adapter warns instead of pretending (GAPS.md 17).

The rule this confirms: what a BPMS cannot tell apart, an adapter reports as the
weaker fact rather than inventing the distinction.

## The version of a deployed process

What `@WorkflowTask(version = ...)` and its siblings are matched against, per BPMS:

- **Camunda 7:** counts a definition's version upwards per process id, and every
  execution names its definition id. The adapter resolves the version ONCE per definition
  id and caches it (a repository query per task execution would be paid by every
  workflow). `camunda:versionTag` is on the definition, so the definition query answers
  which version carries which tag, and `deployWithResult()` already reports what was just
  deployed.
- **Camunda 8:** every `ActivatedJob` carries `getProcessDefinitionVersion()`, so numbers
  cost nothing on any cluster. The version TAG is NOT on the job: it needs
  `newProcessDefinitionSearchRequest`, i.e. a cluster with secondary storage. Without it
  the adapter says so once and specifications naming a tag match nothing. The deploy
  command reports the version, the tag is read from the model (`zeebe:versionTag`).
- **Process-Engine-API:** no version number anywhere, and no query for the versions of a
  process. `TaskInformation.meta` may carry `processDefinitionVersionTag`
  (`CommonRestrictions`), which the adapter reports as the version - so an exact tag works
  where the engine supplies it and nothing else does (GAPS.md 19).

The rule this confirms again: an adapter reports what its BPMS knows and nothing more; a
missing version matches every method, which keeps applications not using the attribute
untouched.


## The versions a BPMS still holds

The `version` attribute asks what version a delivery belongs to. The startup check asks
the other direction: which
versions does the BPMS still HOLD, what do their models look like, and how many workflows
run on them - because the application only ever brings its newest model, and the older
versions are what its methods have to keep serving.

- **Camunda 7:** all three, with the engine at hand. `RepositoryService` lists the
  definitions of a process and hands out the model of any of them
  (`getBpmnModelInstance`), `RuntimeService` counts the instances of a definition. Note
  the deployment case: an engine which deploys nothing because the resources are unchanged
  reports no definitions, so the adapter has to query the latest version itself - otherwise
  the check would only run on a boot which changed a model.
- **Camunda 8:** all three, but only through the query API (secondary storage): the
  definition search finds the version, `newProcessDefinitionGetXmlRequest` returns its
  model, and the process instance search counts what runs on it. Without secondary storage
  the adapter answers `null` and the core says once that this BPMS cannot tell.
- **Process-Engine-API:** none of it (GAPS.md 19 and 20), and since it reports no deployed
  version either, the core skips the check for it entirely.

The SPI shape follows the usual rule: the two questions are `default null` on
`ProcessVersionCatalog`, so an adapter answers what its BPMS knows and switches off what it
cannot. Reading the model is the adapter's job, deciding whether a method serves it is the
core's - and both adapters build the task specs of an old model with the same extraction
they use in `wireBpmn`, so the two directions cannot drift apart.

## A failed transaction, and what the BPMS makes of it

A workflow with more than one token has two branches writing the same workflow aggregate.
With a version attribute on the aggregate that collision is an exception in the commit
instead of a lost write, and the exception surfaces where VanillaBP commits: a
`@WorkflowTask` method, a workflow the BPMS started on its own, the `@WorkflowEnded`
notification. The core recognizes it by asking the platform
(`TransactionRunner#isConcurrentModification`), logs one guiding ERROR and rethrows it
UNCHANGED. **VanillaBP never retries it** - a handler may have called a remote API before the
commit failed, so a quiet retry would repeat that call and hide the failure at once.

What happens next is the BPMS' answer, and it is the same answer it gives for any handler
that throws:

- **Camunda 7:** the job executor retries the job as configured (three times by default,
  `camunda:failedJobRetryTimeCycle` per task) and creates an incident when the attempts are
  used up. The engine delivers tasks INSIDE its own transaction, so the conflict fails that
  transaction and VanillaBP does not even see it - the guiding message stays out here, and
  the incident is what the developer gets.
- **Camunda 8:** the job is reported as failed, the cluster counts its retries down,
  redelivers it and raises an incident once they are exhausted. VanillaBP owns the
  transaction, so the message is logged before the job is failed.
- **Process-Engine-API:** VanillaBP owns the transaction and reports the conflict; what the
  engine behind the API does with the failed task is that engine's business.

Two consequences for adapter work:

- **A handler has to survive repetition, and the delivery record does not change that.** The
  delivery record is written in the handler's transaction, so a run which failed on a
  conflict leaves none and the redelivery runs the handler again. Idempotency of side effects
  stays the application's job.
- **Reading the model is the adapter's job here as well.** An adapter reports the elements
  which can put a second token into a running workflow
  (`WorkflowTaskInvoker#reportConcurrentTokenElements`: non-interrupting boundary event,
  forking parallel or inclusive gateway, parallel multi-instance activity, non-interrupting
  event subprocess); the core decides what it means and warns once per BPMN process where the
  aggregate has no version attribute. An adapter without a model (PEA) reports nothing, and
  the hint stays silent rather than being guessed.
