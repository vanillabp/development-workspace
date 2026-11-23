---
name: vanillabp-camunda8
description: Contributor knowledge for the Camunda 8 adapter and the Camunda 8 extension of the Business Cockpit - release lines and which checks build them, traits of the Camunda Java client (enums in patches, the process-definition state filter, a worker which stops polling, the connection pool against the number of workers), listeners and cancelation on Camunda 8, how the cockpit extension takes its client, and where the protobuf pin belongs. Use before changing code in vanillabp/camunda8-adapter or vanillabp/business-cockpit-camunda8-adapter, before raising a Camunda client pin, and when a Camunda 8 test is slow, red on one line only, or fails at the cluster although it compiles.
---

# Camunda 8: what contributors need to know

This skill is about working ON the Camunda 8 adapter and its cockpit extension. What Camunda 8
does as a BPMS (eventual consistency, at-least-once job workers, the `end` listener on start
events, how the end of a workflow is reported) is in
[vanillabp-bpms-characteristics](../vanillabp-bpms-characteristics/SKILL.md). Read that first.
This skill does not repeat it.

The repositories:

- `vanillabp/camunda8-adapter`: the adapter. Its `README.md` explains the release lines in
  full, section "Release lines". Read it on `origin/main`, not in a local clone.
- `vanillabp/business-cockpit-camunda8-adapter`: the Business Cockpit extension for Camunda 8.

## 1. Release lines

**Rule.** A VanillaBP bugfix must be deliverable without a Camunda 8 cluster upgrade. So the
adapter is published once per Camunda minor (`2.x.y-8.8`, `2.x.y-8.9`, `2.x.y-8.10`), built from
one source tree with Maven profiles `line-<minor>`. A build without a profile is the current GA
line. The VanillaBP API must be the same on every line; `bin/api-identity.sh` checks it.

**Why.** A cluster upgrade is expensive, mostly for the organisation. Camunda promises that a
client works against clusters of its own version and newer, never older. So the client a build
was compiled against IS the lowest cluster that build accepts. The other direction was measured:
an adapter built on the 8.9 client against an 8.8 cluster got every job activation rejected.

For every Camunda 8 feature, check from which cluster version it exists. Where a line's cluster
cannot do something, the method is still there and fails with a message that names the line.
Code which differs per line lives in `core/src/main/java-line-<minor>`.

Which line is GA changes over time. Read the table in the README on `origin/main`; never state it
from memory.

### Traps when building lines

- Switching a line always needs `clean`. Classes compiled against one client have the owner of
  an inherited method burnt in. A stale `target/` fails at runtime with `NoClassDefFoundError`,
  not at compile time.
- The test cluster image is `camunda/camunda`, not `camunda/zeebe` (that image got no tags after
  8.9.11 and none for 8.10). Without secondary storage it needs `SPRING_PROFILES_ACTIVE=broker`.
  `ClusterUnderTest` in `test-support` does this for you.
- The image follows the pinned client (`camunda8.cluster.image` is built from
  `camunda8.version`), so client and cluster cannot drift apart in the tests.
- Consumers of the snapshots move with the lines. The default snapshot is the current GA line,
  so any cluster that runs against it, the blueprint CI included, must have at least that version.

### What the pull request checks build

Every pull request builds the whole line matrix (`checks.yaml` calls `line-matrix.yaml`). The
required check `line-pins-verified` reads only the GA lines. A preview line, built against an
alpha of the next minor, builds too but cannot block a pull request; when it breaks, a workflow
opens an issue instead. The nightly workflow "Release lines" runs the same matrix on `main`.

**Why.** A cluster bug in an alpha must not hold up anybody's pull request. Older rules said
"pull requests build only the GA line"; that is replaced, because the night then found what the
pull request had missed.

A red preview line: first find out whether it is a test fixture or a cluster bug. A cluster bug
gets an exclusion in the `line-*` profile with a link to the Camunda issue.

### Client pins

The pin of each line is a property in the root POM, `camunda8.version.line-<minor>`. A client
patch stays inside the line (the minimum cluster is the minor, not the patch) and Renovate merges
it on its own. A minor is a new line: it waits for approval on the dependency dashboard and never
merges itself. A pin on a pre-release does not merge itself either.

## 2. Traits of the Camunda Java client

### New enum literals and interface methods arrive in patches

**Rule.** In all code compiled against `io.camunda:camunda-client-java`:

- every `switch` over a client enum has a `default`,
- never conclude completeness from `values()`,
- never implement a client interface yourself, also not as a test double (Mockito is safe).

Before a patch update, diff the classes, do not read the release notes:

```bash
gh api repos/camunda/camunda/compare/8.8.32...8.8.33
```

**Why.** Camunda does not count a new enum literal or a new interface method as breaking, so it
never documents them. Seen in practice: `ProcessDefinition.getHasStartForm()` (8.8.1),
`BatchOperationState.FAILED` (8.8.4), `UserTask.getProcessName()` (8.8.9), `ProcessDefinitionState`
with `getState()` (8.8.33). Patch pins merge themselves, so a missing `case` would only show at
runtime. For this reason every pull request that raises a pin gets a comment listing the new
members, and on a GA line a red check until `camunda8-client-read.properties` names the new
version. The README explains the steps. `Camunda8UnknownClientEnumsTest` holds what the adapter
does with a literal it has never seen.

A client downgrade inside a line is not supported for the same reason.

### The state of a process definition

- `state` on a process definition exists in the REST API only from cluster **8.8.33**. Older
  clusters answer a `filter.state` with `400 Request property [filter.state] cannot be parsed`,
  so the whole search fails instead of filtering.
- A second `filter()` call on a search request **replaces** the first. Set every criterion in
  one call. The Version 1 adapter set `state(ACTIVE)` and `tenantId` in two calls, lost the
  state criterion when a tenant was configured, and wired deleted definitions (fixed from
  1.10.0 on).
- The filter on `ACTIVE` is required, not cosmetic. When somebody deletes a process version,
  the document often stays in the search index with `state: DELETED`. On 8.10 a definition goes
  to `DRAINING` first, then `DELETED`, and stays in both.
- Version numbers count per tenant. A search without a tenant filter can return several
  definitions with the same version number.

### A worker stops polling while a handler runs

The client planned its next poll only when `remainingJobs <= 0`. A handler that does not return
stops its worker as soon as a poll comes back empty. Affected up to 8.8.36 and 8.9.17 and the
8.10 alphas; fixed in 8.8.37 and 8.9.18 and in 8.10.0. Reported to Camunda as SUPPORT-34723
(an older gateway finding with a different cause is SUPPORT-34287).

A second cause looks the same and hides the first: `DEFAULT_NUM_JOB_WORKER_EXECUTION_THREADS`
is 1, and the client runs handlers and planned polls on the same executor. The adapter separates
the two with `Camunda8Executor`, as wide as `worker-threads`. If you measure this with the bare
client, set `numJobWorkerExecutionThreads` to 8, otherwise you measure the default. Streaming
avoids the bug, because a streamed job does not count up `remainingJobs`.
`Camunda8KeepsAskingWhileAHandlerRunsIT` covers it.

### Connection pool against the number of workers

The client holds at most **100** HTTP connections by default (`DEFAULT_MAX_HTTP_CONNECTIONS`,
the same in the 8.8, 8.9 and 8.10 clients). The adapter opens one worker per process and kind,
and each worker keeps a REST activation request open. Above 100, the extra workers take turns,
and whatever one of them waits for arrives a full `request-timeout` (10 seconds) later.

**When a Camunda 8 test gets slow**, or a promise about things running at the same time or about
a redelivery fails, compare the number of workers with the pool first (the drain line of the log
says `... closed workers`). Do not blame the line.

**Why.** It looks like a line problem and is not one. 8.10 reaches the limit first only because
it adds a cancel listener per process: the Spring Boot test module opens 85 workers on 8.9 and
115 on 8.10. With 115 workers a test took 10412 ms with 100 connections and 215 ms with 256. The
Spring Boot test module therefore sets `max-http-connections: 256` in `camunda8-it.yaml`. Do not
put comments into that YAML: Spotless formats it through Jackson and drops them. The adapter
warns at startup when its workers take the whole pool (`Camunda8WorkerConnections`).

## 3. Listeners and cancelation

- Camunda 8 accepts a `cancel` execution listener **only on the `process` element**, from 8.10
  on. On a service task or end event the deployment fails with HTTP 400 ("The 'cancel' event type
  is only supported on the 'process' element"). The client still has
  `ZeebeExecutionListenerEventType.cancel`, so such code compiles and fails only at the cluster.
  Source: https://docs.camunda.io/docs/next/components/concepts/execution-listeners/
- A design that wrote one cancel listener per served listener was built and then removed for
  this reason. It turned the nightly line red and every Renovate pin pull request with it.
  Use the current state: the process-level cancel listener (`Camunda8CancelListeners` on the
  8.10 line) reports a canceled instance.
- The cancelation of a single task is derived, not delivered. Whenever the cluster hands the
  application a job of a workflow, the adapter checks the other open tasks of that process
  instance and reports the ones the cluster no longer has as `CANCELED`. The README section
  "Task cancellation arrives at the next wake-up, not at the moment" has the details.
- A listener somebody modelled is served only behind `allow-listeners`, and its method hears
  `CREATED` when it fires. Decision 27 in the adapter's `DECISIONS.md` explains why.

**Rule.** A Camunda 8 feature that you only see in the client library is proven only when a
cluster has accepted it. Line-specific code of a preview line never reaches a cluster in a
required check, so run the matrix for it before the merge.

## 4. The cockpit extension

- **Start events.** The extension does not use a `start` execution listener on the process.
  That listener runs before the start variables exist, so the aggregate id is missing and the
  extension cannot load the aggregate. It puts an `end` listener on every start event instead,
  like the adapter does for `@WorkflowStartedByBpms`. The `end` listener on the process stays.
  The task listeners stay byte-identical to Version 1; the start events are the one deliberate
  difference (decision 1 of that repository).
- **The client comes from the adapter.** Every line of `business-cockpit-camunda8-adapter`
  takes the Camunda client through `vanillabp/camunda8-adapter` of the same line
  (`camunda8-adapter.version.line-<minor>` in the POM). Nothing in that repository may manage
  `io.camunda:camunda-client-java`.
- **New clients are still read.** `client-api-changes.yaml` runs every morning, compares
  `camunda8-client-read.properties` with the adapter's pins and opens or updates a pull request
  from the branch `client-api-read` with the report of new enum literals and interface methods.
  It never merges itself: a person's merge means "read". When the report finds something, read
  the named packages and change the code before you merge. The bot pull request gets no CI run
  (it is opened with `GITHUB_TOKEN`); it only changes data.

## 5. The protobuf pin belongs to Camunda 8

**Rule.** Pin `protobuf-java` only in the Camunda 8 adapter repositories
(`camunda8-adapter`, `business-cockpit-camunda8-adapter`). Never in `business-cockpit-bom`,
the blueprints, or another repository. If somebody proposes a pin elsewhere, point to the
Camunda 8 adapter.

**Why.** The Camunda 8 client always brings generated gRPC code. Protobuf 4 gencode checks the
runtime in every static initializer (`RuntimeVersion.validateProtobufGencodeVersion()`), and the
class does not load if the runtime is OLDER than the gencode. A newer runtime is fine. So the
rule is "runtime >= gencode of the client", not "exactly this version". Our own generated code
runs on the version the Spring Boot BOM brings. A pin elsewhere would fix a version that only the
Camunda client needs.

In `camunda8-adapter` the number is the gencode version of the newest pinned client, written
before the Spring Boot BOM import, and `Camunda8ProtobufPinTest` checks it against the client of
the line. Renovate is off for `com.google.protobuf`; the pin moves when a client pin moves.
