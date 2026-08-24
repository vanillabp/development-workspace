---
name: vanillabp-configuration-model
description: Where VanillaBP configuration lives and how it is resolved — one adapter instance per configured adapter id (multiple of the same BPMS type allowed, the basis of the migration feature), canonical per-adapter location `vanillabp.adapters.<id>.*`, and adapter-specific properties resolvable at four levels (task > workflow > workflow-module > adapter) with the most specific value winning. Use whenever creating adapter beans, reading adapter configuration, or adding any adapter-specific property (e.g. Camunda 8 job timeout).
---

# VanillaBP configuration model (Version 2)

## One instance per adapter id — never "the first"

`vanillabp.prioritized-adapters` and `vanillabp.adapters` map **adapter ids** to
configuration. An adapter id names one *instance* of a BPMS; its `type` (in
`vanillabp.adapters.<id>.type`) names which BPMS adapter serves it. **The same BPMS type
may be configured under several ids** — e.g. two Camunda 8 adapters, one on-prem and one
SaaS, each with its own connection config. The migration adapter then performs each
action against the adapters in `prioritized-adapters` order (new workflows start in the
first; existing workflows are located by probing). This multiplicity IS the migration
feature — do not collapse it.

Consequence for adapter wiring: an adapter must create **one runtime object per
configured adapter id of its type**, not one shared object using the first id.

- `MigratableProcessService` — one per configured adapter id (each carries its own
  `adapterId` and its own BPMS client/config).
- `AdapterDeploymentService` — likewise one per configured adapter id.

Pattern (Spring): iterate `properties.getAdapters()` for entries whose type equals this
adapter's type, and register one **element** bean per id — NEVER a bean of type
`List<AdapterDeploymentService<...>>` (List beans break collection injection as soon as
a second adapter type is present — review finding B1; the platform collects element
beans via `ObjectProvider` streams), and an adapter registers ONE element bean per
configured id of its type, named after that id.
Pattern (Quarkus): element beans likewise; the platform's collection point
additionally flattens beans of type `List<MigratableProcessService>`, the shape the
runtime config produces for several ids.

## Where the primary per-adapter config lives: `vanillabp.adapters.<id>.*`

The primary configuration of an adapter instance is **always** at
`vanillabp.adapters.<id>.*`, modeled ONCE in the core:
`MigrationAdapterProperties.adapters` is a `Map<String, AdapterConfigProperties>`
(platform keys `type`, `deployment-failure`; each adapter adds its own keys to the
same section). The *keys* differ per BPMS, but the *location is always the same* — do
not invent a parallel namespace.

**Wrong (what the C8 skeleton currently does):** a separate flat namespace like
`camunda8-adapter.<id>.rest-address`. **Right:** `vanillabp.adapters.<id>.rest-address`
etc., contributed via the adapter-owned OVERLAY of the shared prefix:

- **Spring** binds the core POJOs directly (thin
  `@ConfigurationProperties("vanillabp")` subclass `VanillaBpConfigurationProperties`);
  an adapter adds a second `@ConfigurationProperties("vanillabp")` overlay class with
  only its own keys — same-prefix classes coexist, unknown keys are ignored.
- **Quarkus** keeps its `@ConfigMapping` interface (mapped onto the core by a
  generated MapStruct `toCore()`); an adapter adds a RUN_TIME
  `@ConfigRoot @ConfigMapping(prefix = "vanillabp")` overlay (reference:
  `DummyAdapterOverlayProperties` of the platform's dummy adapter). There is NO
  blanket `withMappingIgnore` any more — every key must be known to some registered
  mapping, so typos under `vanillabp.*` fail the Quarkus startup (stricter than
  Spring, accepted).
- **Adapter-id-set rule:** ids are ALWAYS derived from the platform's core
  properties (`MigrationAdapterProperties.adapterTypes()`); overlay maps are
  per-known-id lookups only, never iterated to discover ids.

**Environment-variable limitation (both platforms):** env vars can only OVERRIDE
map entries (adapters, workflow modules) already declared in a configuration file —
they cannot INTRODUCE a new entry whose id contains dashes/dots (the binder cannot
reconstruct the id from the variable name). A `VANILLABP_*` variable addressing an
unknown id fails the startup with a guiding message
(`MigrationAdapterProperties.validateEnvironmentVariableUsage`).

## Not everything under `vanillabp.*` belongs to an adapter

Some sections configure the PLATFORM and carry no adapter id:
`vanillabp.outbox.*` (the phase-two outbox), `vanillabp.workflow-adapter-cache.*`
(the election cache's bounds), `vanillabp.transactions.*` (whether writes to
a workflow-aggregate store which VanillaBP's transaction demonstrably does not cover are
`accepted` or `rejected`, the latter being the default which ends the startup) and
`vanillabp.delivery.*` (`release-on-workflow-end`, whether a workflow which
ended deletes the records of its processed task deliveries instead of leaving them to
`vanillabp.outbox.retention`; default `false`, because switching it on makes every
deployed process of the module carry the listener reporting the end). The last two are
also the pattern for a platform-wide property with a per-module override: the same
type sits under `vanillabp.workflow-modules.<id>.transactions.*` respectively
`vanillabp.workflow-modules.<id>.delivery.*`, the module's value wins where it is set,
and the resolution lives in the core
(`MigrationAdapterProperties.acceptsUnguardedAggregateWrites`,
`MigrationAdapterProperties.releasesDeliveryRecordsOnWorkflowEnd`) rather than in either
platform. They follow the same rule as everything else — modeled
ONCE in the core (`PhaseTwoOutboxProperties`, `WorkflowAdapterCacheProperties`,
`TransactionsProperties`, `DeliveryProperties`),
validated in the core's `validateProperties`, bound directly on Spring Boot and mapped
from the `@ConfigMapping` interface by the generated `toCore()` on Quarkus (where the
`@WithDefault` values are pinned against the core's defaults by a test, because they
are necessarily written twice). Put a new platform-wide property here, never into
`vanillabp.adapters.<id>.*`.

**Quarkus trap: never `@Inject` a `@ConfigMapping` interface.** A bean
injecting it turns the mapping into a STATIC-INIT mapping, and SmallRye then validates
the whole `vanillabp.*` tree at static init - before the adapter extensions registered
their RUN_TIME overlays. Every adapter-specific key fails the startup with
`SRCFG00050: ... does not map to any root`, and the message points at the adapter's
key, not at the injection which caused it. Read the mapping instead:
`ConfigProvider.getConfig().unwrap(SmallRyeConfig.class).getConfigMapping(QuarkusMigrationAdapterProperties.class)`.

## Adapter-specific properties resolve at four levels (most specific wins)

Some adapter properties are not global to the adapter but vary by scope. Examples:
**Camunda 8 job timeout is task-specific**, and so is the CORE's
`deduplicate-deliveries` (whether a repeated task delivery is answered from
the record instead of running the handler again; default `true`, and a single expensive
task may be treated differently from the rest) and `outfaded-versions` /
`outfaded-versions-in-use` (which versions of a process this application does
not serve any more, written in the grammar of the `version` attribute, and what happens
when workflows still run on one; per workflow, because a version is a property of ONE
process, and per adapter, because every BPMS counts its own versions). Such a property may be set at any of four
levels, and the **most specific configured value wins**:

```
task            most specific   (per BPMN task)
  workflow                      (per BPMN process / workflow)
    workflow-module             (per workflow module)
      adapter     least specific (vanillabp.adapters.<id>.*)
```

Concrete key shape (from the properties model — `WorkflowModuleProperties` and
`WorkflowProperties` both extend `AdaptersConfigurationProperties` and carry an
`adapters` map; a `tasks` level is added when task-scoped config is implemented):

```
vanillabp.adapters.<id>.<key>                                                # adapter level (base)
vanillabp.workflow-modules.<mod>.adapters.<id>.<key>                         # per module
vanillabp.workflow-modules.<mod>.workflows.<wf>.adapters.<id>.<key>          # per workflow
vanillabp.workflow-modules.<mod>.workflows.<wf>.tasks.<task>.adapters.<id>.<key>  # per task (future)
```

Resolution walks from most specific to least specific and takes the first value present.
Precedent already in the codebase: BPMS election
(`getPrioritizedAdaptersFor(module, workflow)`) resolves per level — reuse that
mechanism rather than inventing a new one. Whether "most specific wins" applies
per-property or per-block: per-block for grouped settings, per-property for scalars
(the removed `resilience` block worked per-block) — confirm against
`MigrationAdapterProperties` when implementing.

## Checklist when adding an adapter-specific property

1. Is it global to the adapter instance, or scope-specific (module/workflow/task)? If
   scope-specific, make it resolvable at all applicable levels, most specific wins.
2. Put it under `vanillabp.adapters.<id>.*` (base) — never a parallel namespace.
3. Validate it at startup with a guiding message (see `vanillabp-config-validation`).
4. Both platforms: Spring binding + Quarkus runtime config.

Related: `vanillabp-adapter-building` (adapter wiring, id vs. type),
`vanillabp-config-validation` (when to validate + message UX), `vanillabp-concepts`
(workflow-module configuration, BPMS election).
