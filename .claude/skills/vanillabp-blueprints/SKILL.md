---
name: vanillabp-blueprints
description: Rules for writing and changing VanillaBP blueprints (vanillabp-blueprints/blueprints and the catalogue in vanillabp-blueprints/.github) - what a workflow module must bring, dependencies on support instead of adapters, API-first modules with client and server and their auto-configuration, where client keys live, frontends with a generated client, the shape of Business Cockpit blueprints, templates, endpoint paths, form endpoints and HTTP methods, access groups against feature roles, twin hashes, the local checks before a push, and the blueprint index. Use before creating or reviewing a blueprint, before writing an agent task for one, and before merging a change elsewhere (cockpit, platform) that the blueprints consume.
---

# Writing VanillaBP blueprints

Blueprints are small, complete example applications. Agents and people copy them, so a pattern
that is wrong in one blueprint spreads to every project built from it. The handbook is
`CONTRIBUTING.md` of `vanillabp-blueprints/blueprints`; this skill adds the rules that reviews
have asked for again and again.

Blueprints show VanillaBP topics only. Ordinary software problems (for example polling a
surrounding system) are left out. Where a real client library exists for a surrounding system,
use it instead of writing your own.

## 1. The workflow module brings everything

**Rule.** An application (or a library) is only a container for one or more workflow modules.
Adding the module as a Maven dependency must be enough. Routes, scans and configuration are
auto-configuration inside the module. Values such as the address of a module's UI are set per
workflow module, never application-wide. The application keeps only what belongs to a
deployment: the cockpit URL, credentials, the database.

**Why.** Think of a workflow module as a complete application which just cannot run alone. It
relies on nothing the hosting application provides, except shared resources such as the
`DataSource`. Several modules in one application must not get tangled through application code
or shared values; each module, for example, packs its own frontend bundle. The platform wiki page
`Workflow-modules.md` ("What is a workflow module?") says the same for users.

## 2. A module never depends on an adapter

**Rule.**

- Platform: a workflow module depends on `vanillabp-spring-boot-support` or
  `vanillabp-quarkus-support`. BPMS adapters (`camunda7-adapter-*`, `camunda8-adapter-*`,
  `operaton-*`, `cibseven-*`) appear only with `<scope>test</scope>`.
- Business Cockpit: a workflow module depends on the cockpit support library
  (`business-cockpit-spring-boot-support` on Spring Boot), which brings the cockpit SPI, not on
  `spi-for-java` directly. `businesscockpit-*-adapter-*` appear only in test scope.
- The application (also the `-application` part of a cockpit blueprint) brings the adapters.
  The one deliberate exception is `module-standalone`: there the application IS the module.

**Why.** A module runs in any application, whatever BPMS that application chooses. An adapter
in the module makes that choice for every application.

## 3. Every API is API-first: `<name>-api` with `client` and `server`

**Rule.** An interface to a surrounding system is a Maven module `<name>-api` (for example
`credit-rating-api`) that holds the OpenAPI YAML, with two submodules:

- `client`: generated Java classes for the caller, used by the application.
- `server`: generated Java classes for the provider, used by the simulator.
- With a callback there are two YAML files; `client` holds the client and the callback-service
  classes, `server` the other way round.

Business code uses only the generated client interface. Controllers implement the generated
service interfaces. No hand-written DTOs or REST templates for such an interface. Test code and
simulators also use generated classes, for example the client of the cockpit's official GUI API
(`apis/official-gui-api` in `vanillabp/business-cockpit`), not a hand-written REST client.

This holds for every API, including the module's own. One difference in where the file lives: an
API whose only client is the TypeScript of the module's own UI may keep its spec in the module,
next to the controller that implements it. The server interfaces are still generated.

The module that talks to the system is named after the system, not after the technique
(`sap-credit-rating-adapter`, `sign-now-e-signature-adapter`). `rest-adapter` is fine only in a
blueprint whose surrounding systems are made up, as in `module-simulator`.

**Why.** A blueprint had an external interface without a specification. Blueprints must be uniform
so that an agent learns one unambiguous pattern.

### The client module brings its auto-configuration

**Rule.** A `client` module configures its own REST client as auto-configuration: the
application adds the dependency, sets properties and injects the interface. On Spring Boot the
client is an HTTP service client (`@ImportHttpServices`), configured by the cockpit support
library from the package `io.vanillabp.cockpit.support.rest.httpservice` (timeouts, proxy, TLS,
retries, OAuth, a check of `base-url` at the start). Example on `origin/main`:
`CreditRatingClientAutoConfiguration` in `module-simulator`, registered in
`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`.

### Client keys belong to the module, never to `vanillabp`

**Rule.** Keys of a REST client live where the client is configured, for example
`credit-rating.client.*` or `loan-approval.cockpit.*`, never below `vanillabp.*`. A module names
the prefix of its group with an `HttpServiceGroupPrefix` bean.

**Why.** Two workflow modules in one application can use the same client of a surrounding
system and still need their own values (for example timeouts), because they use different parts
of that system. If a user wants the values shared, that is their own commons library. A test
with two modules and two groups with different values proves it.

## 4. Frontend blueprints

**Rule.**

- A frontend does not write its API client by hand. It reads the OpenAPI file of the backend and
  generates the client with `@hey-api/openapi-ts`, pinned to an exact version, configured in
  `openapi-ts.config.mjs` per frontend. This holds for React, Angular and Vue. In a split
  repository the file comes from a git submodule `backend` at a pinned commit; in the monorepo
  from the sibling directory (`scripts/fetch-openapi.mjs`).
- No Java in a frontend build. Build machines for Node often have only Node, so no
  `@openapitools/openapi-generator-cli` (a wrapper around a Java JAR) and no downloads during
  the build. The generator must be plain Node, or the client is made outside the Node build.
- Vue components that run as web components are named `*.ce.vue`. Otherwise their styles are not
  embedded into the custom element.

**Why.** Both points were missing in a Vue blueprint. The older generator `typescript-fetch` of
openapi-generator needs Java and was replaced.

## 5. Business Cockpit blueprints

**Rule.** A cockpit blueprint may contain a cockpit backend project, but no frontend beyond the
dev shell. Frontend features of a cockpit (avatar, rights overview, logout at the provider, and
similar) belong to the skill `business-cockpit-creator`, not to a blueprint.

A cockpit blueprint with a UI comes in parts, each a blueprint id of its own:

- `<id>-backend`: Maven, the API with its OpenAPI file and the workflow module,
- `<id>-frontend`: npm, the micro-frontends, the UI JAR and an nginx image,
- `<id>-application`: the application.

**Why.** Many companies have separate CI runner images for Maven and for npm. Blueprints stay small
and free of UI; the UI comes from the skill. The modules build against `@vanillabp/bc-module-kit`.
Call the frontend parts "micro-frontends" in texts for users.

### Templates

**Rule.** All Business Cockpit templates of a module, also those without a task such as
`task-fulltext-search.ftl`, live in
`src/main/resources/<workflow-module-id>/business-cockpit-templates/`. No other folder, and no
`template-loader-path` key: the cockpit finds them there without one.

**Why.** Reviews flagged scattered templates twice. Check every blueprint before review:

```bash
git ls-files '*.ftl' | grep -v business-cockpit-templates
```

## 6. Endpoints

### Paths: module name before `api`

**Rule.** A module's endpoints live below `/<module>/api/...`, for example
`/loan-approval/api/...`, not `/api/loan-approval/...`. The `workflow-module-uri` in the cockpit
ends with `/<module>`, so the path through the cockpit is `/wm/<module>/api/...` without a
repeated segment.

### Form endpoints carry the business id

**Rule.** A user-task form endpoint always has the business id of the case AND the task id in
its path, for example `/loan-approval/api/loan-requests/{loanRequestId}/assess-risk/{taskId}`.
The module checks that the task is open on that case and answers 404 otherwise. Never
`/api/user-tasks/{taskId}` alone.

**Why.** The task id alone is enough technically. With the business id from the client, a form
cannot complete the task of another case by mistake, and both values are at hand for messages
and exceptions.

### HTTP methods

What the blueprints on `origin/main` do today:

- Endpoints that a person calls, start, status and also completing a task in a blueprint
  without a UI, are GET, so they can be used from a browser. Example: `module-simulator` has
  `GET /loan-approval/api/{loanRequestId}/prepare-contract/{taskId}`.
- Endpoints that a UI calls may use other methods, because the UI calls them and not a person.
  A form has two: GET reads what the form shows, POST takes what the user entered and completes
  the task (`cockpit-user-task-backend`, `UserTaskFormController`).
- The API of a surrounding system keeps the methods its own spec defines (for example the
  e-signature envelope and its callback are POST in `module-simulator`).

## 7. Access group and feature roles are different things

**Rule.** `WorkflowModuleDetailsProvider#getAccessibleToGroups` returns every group that may see
the module at all, usually one access group (for example `LOAN_APPROVAL_USERS`). Feature roles
that show or hide a button (for example `LOAN_OFFICERS`) imply the access group through a group
hierarchy. Test with a user who sees the module but not the button.

**Why.** Using one group for both mixes two decisions, and a user without the feature role would
not see the module at all. Some existing blueprints still use one group; new work keeps them
apart. The cockpit wiki page `Security.md` explains group hierarchies.

## 8. Before a push: twin hashes and local checks

The blueprint CI runs the full matrix on every push and takes about an hour. Bundle related
changes into one pull request and avoid follow-up pushes. Before you push, run the repository
checks locally and build the blueprints you touched.

The checks in `bin/` on `origin/main`: `check_bpmn_covers.py`, `check_default_profiles.py`,
`check_delta_tables.py`, `check_docs_structure.py`, `check_enforcer_rule.py`,
`check_foreign_decisions.py`, `check_index_consistency.py`, `check_module_resources.py`,
`check_scoping_modes.py`, `check_spi_readme_links.py`, `check_table_paths.py`,
`check_twin_diff.py`. Several of them read the index; fetch it first:

```bash
curl -fsSLO https://raw.githubusercontent.com/vanillabp-blueprints/.github/main/blueprints.yaml
python3 bin/check_index_consistency.py blueprints.yaml
```

### Twin hashes

Every blueprint exists for Spring Boot and Quarkus. `check_twin_diff.py` compares the two and
accepts only differences listed in `<group>/<blueprint-id>/twin-diff-allow.txt`, each with a
hash of the difference and a reason. When the text of an allowed difference changes, its hash
changes and the check turns red.

- After `bin/sync_harness.py` (which copies the test harness into every blueprint), also run
  `python3 -I bin/check_twin_diff.py blueprints.yaml`. Run it after Spotless, not before.
- If the reason stays the same, replace only the old hash with the new one (the check prints it,
  `--update` writes it) and keep the reason.

**Why.** One small change to the shared harness changed 37 entries at once.

### Changes elsewhere that the blueprints consume

Before you merge a pull request in the cockpit or the platform that changes an OpenAPI spec or a
simulator path, search the blueprints for the affected method or path, and have the blueprint fix
ready before that pull request merges. A removed header once removed a parameter from the
generated client, and the blueprint `main` turned red.

## 9. The index and the organisation page

The catalogue is `blueprints.yaml` in `vanillabp-blueprints/.github`; `profile/README.md`, the
organisation page, is rendered from it.

- A new blueprint needs an entry in `blueprints.yaml`, otherwise the page does not show it.
- Nobody writes a platform status by hand. The split job of the monorepo sets it to `available`
  (with `bin/set_platform_status.py`) once the blueprint is pushed into its own repository. The
  one status a person writes is `not-applicable`, with a one-sentence reason.
- After changing the catalogue, run and commit the rendered page:

```bash
pip install pyyaml jsonschema
bin/validate_index.py
bin/render_index.py
```
