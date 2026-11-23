# AGENTS.md

Rules for coding agents (and people) who work in the VanillaBP development workspace. Each rule
comes with a short reason. Topic details live in the skills under `.claude/skills`, listed at the
end. `README.md` explains how to clone and build.

## Repositories

The workspace holds the active VanillaBP repositories as git submodules (see `.gitmodules`):

- API and platform: `spi-for-java`, `adapter-platform-integration`.
- BPMS adapters: `camunda7-adapter`, `camunda8-adapter`, `process-engine-api-adapter`,
  `operaton-adapter`, `cibseven-adapter`.
- Business Cockpit: `business-cockpit` and its adapters `business-cockpit-*`.
- Blueprints: `blueprints` and `blueprints-organisation-page` (organisation `vanillabp-blueprints`).
- Shared configuration: `renovate-config`.
- Most repositories have a GitHub wiki, checked out as `<repo>.wiki`.

Old versions (1.x) of the adapters lived in the Camunda Community Hub. Now the repositories of the
`vanillabp` organisation are the ones that count.

`business-cockpit-angular-ui` is legacy. Do not change it, not even to fix a red build. You may read
it to look up old code.

## Where to find work

- The issues of each repository. Users report bugs and wishes there.
- The public GitHub projects of the `vanillabp` organisation:
  [platform](https://github.com/orgs/vanillabp/projects/2),
  [Camunda 7 adapter](https://github.com/orgs/vanillabp/projects/3),
  [Camunda 8 adapter](https://github.com/orgs/vanillabp/projects/4),
  [Process Engine API adapter](https://github.com/orgs/vanillabp/projects/5).
- A red build on `main` or in a nightly run, see [Red builds first](#red-builds-first).

## How a change runs

This is the default. Work this way without being asked.

1. The main session plans and checks. Sub-agents do the work, one per change, several in parallel
   when they do not touch the same files.
2. Each agent works in its own worktree and writes to its own log directory, see
   [Worktrees and agents](#worktrees-and-agents).
3. Build and test only the area of the change, with its new and its old tests. The full build runs
   in CI, see [Build locally or in CI](#build-locally-or-in-ci).
4. Finished changes for one repository collect on one shared branch, one commit per change, and go
   to `main` as one pull request. Why: seven single pull requests in one adapter once cost about
   6.5 hours of CI for less than two hours of work.
5. Before the pull request, check numbers you add against `main` and open pull requests, see
   [DECISIONS.md](#decisionsmd).
6. Whoever depends on the change follows in the same change: adapters after the platform snapshot,
   then blueprints and wikis, see [Scope of a change](#scope-of-a-change).
7. No agent waits for CI. It pushes and ends its turn. The main session keeps one wait job per pull
   request. Why: this frees the agent at once and saves a wake-up per change.
8. The `main` run after a merge does not block the next change. Wait for it only when the next work
   needs the published snapshot.
9. Open one pull request in every repository the change touches, in the order of the dependency
   chain. Fix what turns red until all is green. Merge only when the maintainer allowed it.
10. A change is done when the `main` run after the merge is green. Read its conclusion, see
    [Waiting](#waiting-for-builds-and-ci).
11. Finish one batch completely before you start the next. You may prepare the next batch while a
    build runs, as long as you still know which work belongs to which build.
12. Pull requests are opened by the main session, also for branches an agent only pushed.
13. A pull request which changes `.github/workflows` may fail to merge with a token that lacks the
    `workflow` scope. Try it and check with `gh pr view <n> --json state,mergeCommit`. If GitHub
    refuses, give the maintainer one list of such pull requests.
14. A branch pushed only as a backup must not cost CI. The `push` triggers run on `main` only and
    the builds run on `pull_request`. If that changes, cancel the run the push started.
15. Before you report done: remove the worktree and the branch, check running processes and
    containers, see [Clean up](#clean-up).

## Worktrees and agents

- Never work in the submodule clone itself. Create a worktree from `origin/main`:
  `git -C <repo> worktree add -b <branch> /home/vscode/worktrees/<name> origin/main`.
  Why: a branch switch in a shared clone confuses every other agent who uses it.
- Keep worktrees under `/home/vscode/worktrees`, not in `/tmp`. In the DevContainer `/tmp` is a
  tmpfs: it uses the same memory as builds and clusters, and it dies with the container.
- Give every agent its own log directory. Why: two agents once wrote to the same build log, and one
  cut off the other's log in the middle of a run.
- An agent which starts a long build in the background ends its turn without a result. The main
  session then puts a monitor on the agent's log (the filter matches success and failure) and wakes
  the agent with the measured lines, not just "done". The agent has not seen the log.
- Sub-agents cannot write report files; the harness refuses them. Ask an agent to return the file
  content after a clear marker line, and let the main session write the file. Code and other
  repository files are written by the agents.

## Build locally or in CI

- Locally, build only the modules the change touches, with their tests. Commit, push and open the
  pull request; CI runs the full build with Testcontainers. Why: otherwise every run takes 20 to 30
  minutes twice, once locally and once in CI.
- A local full build is still worth it when the core of the change is real cluster or engine
  behaviour. A red integration test costs two CI rounds there.
- A red pull request build is the accepted price. It is no reason to go back to local full builds.
- Never run two Maven builds at the same time, and only one test cluster at a time. Memory is shared.
- When the shared `~/.m2` may be stale, build against the published snapshots with
  `-Pvanillabp-snapshots` and an own `-Dmaven.repo.local`. Do not `mvn install` while other agents
  build. Details: skill `vanillabp-maven-builds`.

## Waiting for builds and CI

1. A job you started with `run_in_background`: do not wait at all. Its completion notification is
   the signal. No loop, no status check, no reading its output file. A wait loop for a job the
   harness already watches is always a mistake.
2. A loop only for state the harness cannot see (a CI run, a cluster, a remote queue), and only
   with a guaranteed end: `timeout 900 bash -c 'until <condition>; do sleep 30; done'`. Exit code
   124 means it gave up. Report that; do not start the same loop again. Interval: 30 s for jobs over
   10 minutes, 10 s for jobs over a minute or without an estimate, 5 s below.
3. To see progress of a long run, use the Monitor tool on the job's log, not chains of `sleep` and
   `grep`. One monitor per run, then end the turn. The filter must match the failures too
   (for example `'Tests run:|ERROR|BUILD FAILURE|=== .* DONE'`). Silence is not success.
4. Wait on what the job itself writes: its log and the marker in it. Never on the output file of
   another wait job. Why: a loop once ran for hours because the marker was in a different file. If
   something already waits for a job, do not wait for it a second time.
5. Check what runs with `pgrep -af "<term>"` and `docker ps`, not with `jobs`. Every Bash call gets
   its own shell, so `jobs` always shows nothing.
6. Stop what you started (test clusters, containers, servers) in the same turn, after the task.
7. Read the result of a CI run with `gh run view <id> --json conclusion`. Why: a wait job once
   ended with exit 0 while the run had failed. An exit code is a guess, the conclusion is the answer.
   A wrapper like `cmd > log; echo "EXIT=$?" >> log` reports the exit code of `echo`.
8. Watch the jobs of a matrix one by one and look at a red job at once. The other jobs may run on.
   The same holds for several pull requests: watch each, and start the analysis when the first
   turns red. Why: the Camunda 8 lines take from one to over forty minutes.
9. Stop a run early when it clearly goes wrong (wrong test selection, a hanging container, an error
   already in the log). Why: a 40-minute run which fails after two minutes costs the full time.

The hook `.claude/hooks/no-unbounded-wait.sh` rejects a `while`/`until` loop with `sleep` and without
`timeout`. The hook is the safety net, not the rule. More on reading checks: skill
`vanillabp-ci-and-github`.

## Pull requests and order across repositories

- Every change goes on its own branch and through a pull request to `main`, in every repository,
  `blueprints` included. Never push to `main` directly.
- Delete the branch when you merge (`gh pr merge <n> --delete-branch`). With stacked pull requests,
  first move the base of the follow-up pull request to `main`, or deleting the branch closes it.
- GitHub wikis have no pull requests. See skill `vanillabp-docs-and-wikis`.
- Before you push to an existing pull request branch, read `gh pr view <n> --json state`. If it is
  merged, start a new branch from `origin/main`, cherry-pick the commit and open a new pull request.
  Why: a push to a merged branch still starts a green CI run and looks like success, but the commit
  never reaches `main`.
- Order across repositories: platform first, merge, wait for the snapshot, then the adapters, then
  the blueprints. Prepare and push the adapter commits, but hold back the pull request (or open it as
  a draft) and say what it waits for. Why: adapter CI reads the published snapshot and turns red
  against the old one, although the code is right.
- A rename in the SPI or in `test-utils` is merged only when the follow-up branches of all
  consumers exist and are confirmed. An announcement holds nothing up. Why: until the snapshot is
  published, everything looks green; after it, every consumer is red. Check a published snapshot
  with `unzip -l` on the jar. If you must build locally in between, adapt the consumer only in your
  worktree and keep that out of your commit.

## Scope of a change

- A change of the SPI or of behaviour also updates `blueprints`, `AGENTS.md`, `README.md` and the
  wikis in the same change. Before you call it done, grep the blueprints for removed or renamed
  names; the `UPGRADE.md` entry of the platform is the list to search for. Why: a rename once left
  a blueprint behind and turned the nightly build red.
- A change to a BPMS adapter also checks its Business Cockpit counterpart
  (`business-cockpit-camunda8-adapter`, `business-cockpit-camunda7-adapter`,
  `business-cockpit-process-engine-api-adapter`) and fixes it there too, in the same change.

## DECISIONS.md

- Every framework repository keeps a `DECISIONS.md`. It is the only thing code may cite, in the form
  `see decision N in the repository's DECISIONS.md`, and only the log of its own repository. Never
  cite issue, pull request or other planning numbers in code. Why: a citation is read years later,
  and a renumbered or rewritten entry makes it wrong without any error.
- Read `DECISIONS.md` before you change behaviour. Add an entry only when several places depend on
  it; otherwise write a comment at the one place. Mark a new entry as a proposal in the pull request.
- Never rewrite, replace or renumber an entry. If a change makes an entry untrue, ask first. An
  outdated entry stays, keeps its number and names its successor.
- Agents working in parallel write a new decision to `DECISIONS.pending/<change>.md`, without a
  number, with a list of the places which cite it. The main session moves the entries into
  `DECISIONS.md` when it builds the pull request branch, numbers them in commit order, fixes the
  citations and deletes `DECISIONS.pending/`. Why: two agents who both append to the end of the file
  always collide.
- Before a pull request, `git fetch origin`, read the highest number on `origin/main` and check each
  open pull request (`gh pr diff <n> -- DECISIONS.md`). If your number is taken, change it and every
  `see decision <n>` that means your entry.

## Verify, do not trust

- An agent's report is a claim. Check the one number, class name or file that carries a finding with
  a command (`grep`, `git show`). Where an agent names a rule ("the cluster drops ...", "the last
  release is ..."), check the source.
- Check every statement about the state of a repository against `origin/main` after `git fetch`:
  `git grep <pattern> origin/main -- <path>` or `git show origin/main:<file>`. The submodule clones
  lag behind `main`, so a working tree is no proof. Where an agent names a commit, check its branch.
- For a comparison, ask what else differed besides the one variable.
- A number from cut-off output is no number. A code comment and a decision entry that cite each
  other are no proof either.
- An agent who corrects its own mistake is welcome. Write the correction and its reason down.

## Red builds first

- A red `main` or nightly run goes before new work, even if only a flaky test or a 429 from Maven
  Central caused it. Why: people who see a red badge do not tell a test problem from a code problem.
- Make a flaky test robust; do not retry it.
- This does not apply to `business-cockpit-angular-ui`.

## Clean up

- Remove only the containers you started, by name or id. Never `docker ps -q | xargs docker rm -f`.
  Why: it removes the test clusters of other agents, and their runs fail like test failures.
- Testcontainers cleans up by itself. Find what is left with `docker ps --filter name=<prefix>`.
- Before the final report, read `docker ps` and `pgrep -af "<term>"`, stop what is yours and name
  what still runs.
- After the merge, `git worktree remove --force` and delete the local branch. Otherwise
  `gh pr merge --delete-branch` fails on the branch still in use.

## Texts, commits and reports

- Write plain English for readers who have English as a second language: short sentences, common
  words, one thought per sentence, active voice. This holds for code comments, commit messages, pull
  requests, `README.md`, `DECISIONS.md`, wikis and questions.
- Run every text through the `humaniser` skill before you commit it. No dashes as punctuation, no
  bold labels at the start of list items, no forced lists of three, no promotional words.
- Every commit made with an AI agent carries a `Co-Authored-By:` trailer for the agent. Never remove
  it, also not to satisfy a CLA check.
- Always name pull requests and issues with their repository, for example `camunda7-adapter#161`,
  never just `#161`. Why: with many repositories, a bare number is ambiguous.
- Feedback on one file applies to every file of the set. After each pass, grep all files for the
  old statement and fix every hit.
- Do not stop and wait for an answer. Write the question into the issue, pull request or agent brief
  together with the default you assume, and go on with that default.

## Skills and maintenance

- There are two collections. User skills (for people who build applications with VanillaBP) live in
  `vanillabp/skills` and follow the agentskills.io standard. Contributor skills (for work on
  VanillaBP itself) live in `.claude/skills` of this repository and change through a pull request
  here.
- A skill refers only to public sources: code, tests, `README.md`, `DECISIONS.md`, wikis and
  blueprints. No private paths, no planning numbers, no private or customer projects. Grep for them
  before you finish.
- Contributor skills: `vanillabp-concepts`, `vanillabp-conventions`, `vanillabp-adapter-building`,
  `vanillabp-bpms-characteristics`, `vanillabp-configuration-model`, `vanillabp-config-validation`,
  `vanillabp-testing`, `vanillabp-code-review`, `vanillabp-maven-builds`, `vanillabp-ci-and-github`,
  `vanillabp-dev-environment`, `vanillabp-camunda8`, `vanillabp-blueprints`,
  `vanillabp-business-cockpit`, `vanillabp-docs-and-wikis`, `markdown-tables`, `humaniser`,
  `security-audit`.
- `.claude/memory-seed/` holds lessons from past incidents as a start memory for new workspaces.
- Every change that alters a rule also updates this file, the skills and the memory seed in this
  repository, in the same pull request.
