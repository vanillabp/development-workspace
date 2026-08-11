---
name: vanillabp-config-validation
description: How VanillaBP validates configuration and writes error/log messages — a core UX principle. Validate as early as possible (Spring Boot = at startup, even for values needed only later), let an unconfigured app still boot, and make every startup message guide the developer step by step to a complete configuration so they need to read almost no documentation. Use whenever writing configuration handling, property validation, startup checks, or any user-facing error/log message in adapters or platform integrations.
---

# Configuration validation & self-guiding errors (a VanillaBP core concept)

VanillaBP wants a developer to be able to start an **unconfigured or partially
configured** application and be led to a working setup purely by the messages emitted
on each boot — reading as little documentation as possible. Configuration errors are
not failures to punish, they are a guided setup dialog spread across restarts.

Three rules follow from this.

## 1. Validate as early as possible

Check configuration **at the earliest point where the check is possible**, not at the
point where the value is first used.

- **Spring Boot:** validate **at startup** (auto-configuration / a transformer / an
  `EnvironmentPostProcessor` / a `SmartInitializingSingleton`), even for values that are
  only needed much later at runtime. The developer should learn about a gap when the app
  boots, not hours later when a specific code path finally runs.
- **Quarkus:** validate at **build time** (build steps) what is knowable then; validate
  the rest at **runtime init** (a `StartupEvent` observer / recorder). Same intent.

**Anti-pattern (do not do this):** lazy `requireProperty(...)` / `validateConfigured()`
that only throws when a method first touches the property. Example currently in the tree:
`Camunda8AdapterConfiguration.requireProperty` is evaluated on first use, so a missing
Camunda 8 connection property surfaces only when a workflow is first started — it should
be surfaced at startup for every configured `camunda8` adapter id. (Aligning this is a
later refinement; new code must not add more lazy checks.)

## 2. Still let the app boot — guide, don't just crash

An unconfigured application should be **startable**. Each restart emits the next
actionable message, and the developer converges on a complete configuration one step at
a time. Prefer:

- Report **all** currently-detectable gaps in one boot (or at least the next actionable
  one), so the developer does not fix-restart-discover-one-more in a long loop.
- Hard-fail the boot only when continuing is genuinely pointless (e.g. the *primary*
  adapter cannot start any workflow). This ties into the existing
  `vanillabp.adapters.<id>.deployment-failure` = `fail` | `warn` policy — a
  non-primary adapter that is misconfigured may `warn` and let the app run
  (migration scenario) rather than block boot.

## 3. Messages state the fix, not just the defect

Do not only report *what* is missing — where you can, tell the developer *how* to fix it:
the exact property keys to add, with a concrete pattern. Sometimes a value really is just
missing and a short "missing X" is right; but whenever a solution can be named, name it.

Reference example (`SpringBootMigrationAdapterTransformer`) — reports the defect **and**
the remedy:

```
Unconfigured VanillaBP workflow modules were found in classpath:
  %s
Add property keys '%s.workflow-modules.*' to configure them.
```

Message-writing checklist:

- Name the concrete thing (workflow module id, adapter id, BPMN process id, property
  key) — never a vague "configuration error".
- When a fix exists, show the property key(s) to add, ideally with the pattern (`<id>`,
  `.workflow-modules.*`) so the developer can generalize.
- Keep it copy-pasteable: the developer should be able to act from the log line alone.
- Match the severity to rule 2: a guiding hint that still lets the app boot is a
  `WARN` with instructions; a genuine boot-blocker is an exception whose message still
  explains the remedy.

## Why this is a core concept, not a nicety

"Business code is written only against the SPI, guided by convention" is VanillaBP's
promise; the configuration side mirrors it — convention-over-configuration plus
self-documenting startup so onboarding needs almost no manual. Treat a missing or
unhelpful startup message as a real defect, the same as a missing validation.

Related: `vanillabp-conventions` (development rules), `vanillabp-adapter-building`
(adapter config keys, `deployment-failure` policy), `vanillabp-concepts` (workflow-module
configuration, BPMS election).
