---
name: vanillabp-business-cockpit
description: Contributor rules for the VanillaBP Business Cockpit repositories (vanillabp/business-cockpit and the business-cockpit-*-adapter extensions) - delivered MongoDB changesets are append-only, a report to the cockpit is built at the event and not at dispatch, the module kit is only the minimum UI contract, which of the two public cockpit skills does what, and the Spring MVC 7 order of RouterFunctionMapping. Use before changing cockpit server code, a cockpit extension, the module kit or one of the cockpit skills.
---

# Business Cockpit: contributor view

This skill is for people who change the cockpit itself. If you want to connect a workflow module
or build a cockpit of your own, use the public skills instead (section 4).

## 1. Delivered changesets are append-only

**Rule.** Never change a delivered changeset of the cockpit (`*/model/changesets/V*.java`). That
covers the body, the class name, the package, the method name and `order`. Also do not add
Javadoc, constructors or imports there. A correction is a NEW changeset. Formatting by Spotless is
allowed.

Only the maintainer can decide to correct an old body. That decision needs a reason in
`DECISIONS.md`. Tell every agent that touches cockpit code that changeset classes are off limits.

**Why.** The aim is safe upgrades: an upgrade must not fail at startup or quietly do something
else. `mongodb-changesets` (by Phactum) knows a changeset only by `ClassName#methodName`. It has no
hash check like Liquibase. So a changed body never runs on a database that already has the
changeset, and a renamed one runs twice.

## 2. A report is built at the event

**Rule.** A report to the Business Cockpit is built when the EVENT happens, in the listener, and
travels as the payload of the outbox entry. Do not read the BPMS again when the report is sent.

Three things matter when you extend this:

- Schedule reports with `PhaseTwoOutbox.scheduleReplacingWhatIsStillWaiting`, not with
  `schedule`. Otherwise, when entries pile up, the oldest state wins. The registration of a
  module stays on plain `schedule`.
- The `businessId` is the `@Id` attribute of the workflow aggregate, on every path and every
  release line.
- A failure in the listener SHOULD be visible. On Camunda 7 and Camunda 8 it becomes an incident.

**Why.** What a BPMS knows about a user task (due date, assignee, candidates) is only a copy; the
truth is in the application. When the report was built at dispatch time, a report that waited
while the cockpit server was down carried the state of some later moment. Auditing was not the
answer, because the normal application keeps none.

## 3. The module kit is only the minimum contract

**Rule.** The contract between a cockpit user interface and a workflow module exists once per
cockpit, as packages the skill `business-cockpit-creator` generates for that cockpit. Those
packages do not take in `@vanillabp/bc-module-kit` (repository
`vanillabp/business-cockpit-module-kit`), but they must cover it as their minimum, with the same
names and behaviour.

The minimum is exactly what the kit has:

- the four data entries `UserTaskList`, `WorkflowList`, `UserTaskForm` and `WorkflowPage`, with
  their export names,
- the area `all`,
- the manifest and its check `bc-check-entries`,
- the event protocol and `defineBcElement`.

Everything else differs from one organisation to the next: the `Header` entry, the page areas
`body`, `information` and `actions`, the `Pages` entry. Do not put constants of one organisation
into the kit. A cockpit ignores unknown entries and areas without an error; without areas it
shows `all`.

**Why.** The kit exists so that the Business Cockpit blueprints work without a generated
cockpit. The test UIs in React, Angular and Vue are not delivered.

## 4. Two public cockpit skills, two jobs

| Skill | Where | Job |
|-------|-------|-----|
| `business-cockpit` | `vanillabp/skills` | A map: says the cockpit exists and where the answers are (wiki, cockpit blueprints, the creator skill). Not a manual. |
| `business-cockpit-creator` | `vanillabp/business-cockpit`, folder `skills/` | Says exactly how to generate a Business Cockpit. Not how a workflow module joins one. |

How a workflow module integrates with the cockpit is shown by the Business Cockpit blueprints and
the cockpit wiki. Put that content there, not into either skill.

**Why.** Whoever installs the VanillaBP skills should learn that the cockpit exists. Whoever has to
build a cockpit needs the creator.

## 5. Spring MVC 7: `RouterFunctionMapping` has order -1

**Rule.** In a servlet (Spring MVC 7) cockpit backend, do not register a catch-all gateway route
such as `/**` as a bean of type `RouterFunction`. Put it into a `RouterFunctionMapping` of its own
with an order after the controllers.

**Why.** Spring MVC puts every `RouterFunction` bean into one shared `RouterFunctionMapping`, and
that mapping has order `-1`: it is asked before the controllers. A route `/**` there swallows every
GET of the GUI API, whatever `@Order` it has. A working configuration from the WebFlux era (cockpit
0.4.x) does not help: there the order was 1. The creator skill shows the fix in
`references/backend.md`, section "The route to the user interface".
