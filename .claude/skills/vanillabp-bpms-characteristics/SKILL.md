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

Embedded BPMS (Camunda 7) do everything in phase one within the shared transaction;
phase two is a no-op. This section is about *remote* BPMS (Camunda 8, Process-Engine-API
treated as remote, ZenBPM).

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
- `needsTwoPhaseCommitForStartingWorkflows()` = **false**: starting a workflow happens
  completely in phase one within the local transaction; phase two is a no-op. No
  outbox involved.
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
  are version-locked to EOL platform releases). The full analysis incl. a PROVEN
  Quarkus recipe lives in `prompts/analysis-c7-plain-engine-RESULT.md`. Key facts:
  Spring = `camunda-engine-spring-6` wiring sharing the app's DataSource +
  `PlatformTransactionManager`, `SpringJobExecutor` deferred to
  `startWorkflowProcessing`; Quarkus = engine-shipped
  `JakartaTransactionProcessEngineConfiguration` + Agroal + Narayana, **mandatory**
  schema-ops `JakartaTransactionInterceptor` (Agroal has no deferred enlistment) and
  engine classloader = Quarkus runtime TCCL (JobExecutor threads otherwise fail on
  delegate classes). **JVM-mode only — no native image** (decided; engine stack is
  reflection-heavy).
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
| Joins local TX | yes | no | `SYNC` mode may | no |
| Two-phase start | no | yes | yes | yes |
| Eventual consistency | no | yes | possible | expected |
| Task delivery | synchronous / job executor | polling workers, at-least-once | Task Subscription API | REST (tbd) |
| Idempotent handlers needed | no | yes | yes | yes |
| Module isolation | tenant ID | tbd (variable/tenant) | not expressible (gap) | tbd |
| Client artifact | `org.camunda.bpm:camunda-engine` 7.24.x | `io.camunda:camunda-client-java` 8.8.x | `dev.bpm-crafters.process-engine-api:process-engine-api` | REST (openapi) |

## Checklist for every adapter feature

1. What is generic? → implement in `migration-adapter` (+ platform glue), not here.
2. Which `ExecutionMode`/phase does each call belong to (in-TX vs. after-commit)?
3. Is the operation delivered at-least-once? → make the handler idempotent and name
   the idempotency key.
4. Can the BPMS answer "unknown" reliably, or only eventually? → map to
   `UNKNOWN_TO_BPMS` vs. `BPMS_UNAVAILABLE` correctly (wrong mapping breaks election).
5. Does the feature work per workflow module (tenant/namespace)? If not expressible:
   document the gap (PEA: `GAPS.md`).
