---
name: vanillabp-ci-and-github
description: How to read and wait for GitHub Actions runs of the VanillaBP repositories without false results, and the CI traps seen so far. Covers checks per head SHA, finding the main run of a merge, the GitHub API limit, concurrency groups, stacked pull requests, HTTP 429 from Maven Central, mixed snapshots and the Maven cache in the blueprints CI, the names of the nightly workflows, Renovate's automerge rules and pushes into a wiki. Use whenever you wait for, judge or re-run a CI run, merge a pull request, or write a script which does any of that.
---

# CI and GitHub in the VanillaBP repositories

Most CI mistakes so far were not red builds. They were wait jobs which reported "green" for a run
that had not started yet, or for the run before it. The first three sections are about that.

All commands use the `gh` CLI. Always pass the repository with `-R <owner>/<repo>`.

## Reading the checks of a pull request

Wait for the runs of the head commit, not for the list of checks. Right after a push, the check
list of a pull request still shows the old state, or only part of the new one:

- A list with one registered check and nothing pending passes `all(.bucket != "pending")`. The
  list then grows to its full length.
- A list with only green checks can miss the build itself. A run that waits in its concurrency
  group has no check run yet.
- "no checks reported" is not "nothing failed". A merge script once merged a pull request this
  way, with no run on its last commit.

So ask for the runs of the head SHA, and count them against the workflows you expect. You know
that number from the workflows in `.github/workflows` which start on `pull_request`.

```bash
head=$(gh pr view <nr> -R <repo> --json headRefOid --jq .headRefOid)
gh run list -R <repo> --commit "$head" --json workflowName,status,conclusion
# done when: number of runs >= expected workflows AND every status is "completed"
```

A run in state `pending` or `queued` has not started. That is neither a failure nor a result.

A merge script first waits until at least one check line exists, then merges only if every line
is `pass` or `skipping`. Before you merge by hand, look at `gh run list -R <repo> --branch <branch>`
for the head SHA.

After a new push to an open pull request, cancel the run of the old head if its workflow does not
do that itself. Otherwise two full builds run side by side.

## Finding the run on `main` after a merge

`gh run list --branch main --limit 1` right after `gh pr merge` returns the run of the PREVIOUS
merge. GitHub creates the new run a few seconds later. Find the run by the merge commit:

```bash
sha=$(gh pr view <nr> -R <repo> --json mergeCommit --jq .mergeCommit.oid)
gh run list -R <repo> --commit "$sha" --json workflowName,status,conclusion
```

- Use the full SHA. `--commit` with a short SHA returns nothing.
- Never type or copy a SHA into a script. Get it with a command (`gh pr view` as above, or
  `git rev-parse origin/main`). Two wait jobs once reported "no run" for 18 minutes because of a
  SHA that was typed in, while both runs were going.
- An empty answer means "the run does not exist yet", not "done".
- A repository often starts several workflows on the same commit. All of them must be done.

## The GitHub API limit

The limit is 5000 requests per hour per user. It counts all sessions, agents and wait jobs of
that user together. Six to eight wait jobs at once once used it up within the hour. After that,
no run could be read, and no agent could call `gh` any more.

- Never use `gh run watch` in a wait job. It asks every 3 seconds.
- `gh pr checks --watch` only with `--interval 60` or more.
- Better: one wait job for everything, which asks for a list of pull requests and merge SHAs every
  two minutes. Give it an end, for example with `timeout`.
- When calls start to fail, look at the budget:
  `gh api rate_limit --jq .resources.core`.

## Concurrency groups

GitHub keeps at most one waiting run per concurrency group. A newer run of the same group replaces
the waiting one, which then ends as `cancelled` without ever starting a job. Such a cancelled run is
a replaced waiting place, not a failure.

Every repository publishes snapshots only from `main`. In `business-cockpit`, the workflow
"Publish snapshots" has one group for `main` and one shared by the runs started by hand. So only a
newer push to `main` can replace a waiting run of `main`. The pull-request build has a group per
pull request. To publish a snapshot from a branch there, start "Publish snapshots" by hand on that
branch.

## Stacked pull requests

When pull request B has the branch of pull request A as its base, deleting A's branch after the
merge does not move B to `main`. GitHub closes B, and `gh pr reopen` fails while the base branch is
missing. The right order:

```bash
gh pr edit <B> -R <repo> --base main
git push origin --delete <branch-of-A>
```

If the branch is already gone: push it again at the merged commit
(`git push origin <sha>:refs/heads/<branch-of-A>`), reopen B, change its base to `main`, then delete
the branch. Afterwards merge `main` into B, because the new base has commits B does not have.

## HTTP 429 from Maven Central

Maven Central answers runners with 429 and a `Retry-After` of about half an hour. The limit counts
per outgoing IP address, so all users of a GitHub runner share it. Requests during the block make
it longer, up to a day, and repeated bursts up to 30 days. The resolver of Maven 3.9 does not wait
at all when `Retry-After` is longer than its maximum interval (600 seconds by default).

- Never answer a 429 with a re-run. Make fewer requests instead of more attempts.
- The blueprints repository sets in `.github/maven/settings.xml` that the resolver waits out the
  block once (`aether.connector.http.retryHandler.*`, at most two repeats, at most 35 minutes). Its
  repository filters ask each remote repository only for the group ids listed for it.
- The organisation variable `VANILLABP_SNAPSHOTS_FROM=github-packages` makes the builds read the
  VanillaBP snapshots from GitHub Packages instead of Maven Central.
- To diagnose, raise only the log level of `ServiceUnavailableRetryExec` to trace. Never log the
  headers: the `Authorization` header would end up in a public log.

## The blueprints CI

**Pull requests build Camunda 7 only.** The other engines run on `main` and in the nightly build.
A break on another engine shows up there.

**Mixed snapshots.** An `AbstractMethodError` or `NoSuchMethodError` in a VanillaBP class, on a
blueprint which did not change, usually means that the blueprint jobs resolved while a snapshot of
the platform or an adapter was being published. They got a new module next to an old one. Compare
the times:

```bash
gh run view <publish-run> -R <repo> --json createdAt,updatedAt
```

If they overlap with the blueprint run, wait for the publish to end and run
`gh run rerun <blueprint-run> -R vanillabp-blueprints/blueprints --failed`. Search the blueprint
only when the re-run is red again. Locally, the same symptom comes from a stale `~/.m2`, see the
skill `vanillabp-maven-builds`.

**The Maven cache.** GitHub keeps 10 GB of Actions cache per repository. Each run of "Build" saves
its own Maven cache, keyed by the run id, about 2.3 GB today. With `main` and several pull requests
running at once, the cache of a running build gets evicted. Its matrix jobs then restore an older
cache, fetch the rest from Maven Central, and fail with `Failed to resolve` or 429. That looks
like a problem of Maven Central, but it is not.

- Run at most two blueprint pull-request builds at the same time. Leave review pull requests that
  will not be merged soon without a run, or cancel their run.
- On `Failed to resolve` in the matrix, first check which cache the job got: the warning "The
  Maven cache of this run is gone", or "Cache hit for restore-key" in the cache step.

## Nightly workflows

Scheduled runs often start hours late. Look at them with
`gh run list -R <repo> --event schedule --limit 5`, or by name with `--workflow "<name>"`.

| Repository                          | Scheduled workflows                                                                                                                                                           |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `vanillabp-blueprints/blueprints`   | "Nightly build" (opens an issue when red), "Build the cockpit applications", "Build the cockpit application with the user interface behind a proxy" (these two open no issue) |
| `business-cockpit`                  | "Nightly build", "Chain check" (runs last and checks the others)                                                                                                              |
| `camunda7-adapter`                  | "Nightly against the platform snapshot"                                                                                                                                       |
| `process-engine-api-adapter`        | "Nightly against the platform snapshot"                                                                                                                                       |
| `cibseven-adapter`                  | "Nightly against the platform snapshot", "Nightly against the next CIB seven", "Sync from the Camunda 7 adapter"                                                              |
| `operaton-adapter`                  | "Nightly against the platform snapshot", "Nightly against the next Operaton"                                                                                                  |
| `camunda8-adapter`                  | "Release lines"                                                                                                                                                               |
| `business-cockpit-camunda8-adapter` | "Release lines", "Client API changes"                                                                                                                                         |
| other `business-cockpit-*-adapter`  | "Nightly build"; the CIB seven one also "Sync from the Camunda 7 extension"                                                                                                   |
| `adapter-platform-integration`      | "Weekly load run"                                                                                                                                                             |

A workflow which opens no issue fails silently, so check it yourself. A red nightly is often an
outage of Maven Central or the network. Re-run such runs one after another
(`gh workflow run "<name>" -R <repo>`), not all at once.

## Renovate

The shared preset is `vanillabp/renovate-config`. Its `README.md` says what merges itself:

- every patch, the BPMS, Spring Boot and Quarkus included,
- tools and test libraries (JUnit, Mockito, Testcontainers, Maven plugins, Spotless, JaCoCo,
  Lombok) also for a minor,
- GitHub Actions for a minor, a patch and a digest.

A minor or major of a client or engine (Camunda 7, Camunda 8, Operaton, CIB seven, the Process
Engine API) and a minor of Spring Boot or Quarkus never merge themselves. Renovate proposes them,
and a person decides. Do not set `automerge: true` for such updates. When somebody says "an upgrade
merges on a green build", patches are meant. A minor automerge for two engines was once switched
on because of exactly this misunderstanding, and had to be taken back.

## Pushing into a wiki from a workflow

The `GITHUB_TOKEN` of a run cannot push into a wiki, not even the wiki of its own repository. A
workflow which writes a wiki page ("Wiki line table" in `camunda8-adapter`) uses the token of a
user account, stored as an organisation secret. That account needs write access to the target
repository. A 403 (`Permission to ...wiki.git denied`) means: check the role of that account in
the target repository, not the token. A green run proves nothing until it had something to push.
