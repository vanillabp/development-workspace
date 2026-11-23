---
name: vanillabp-docs-and-wikis
description: How to write and change VanillaBP user documentation and the GitHub wikis of the vanillabp repositories - page structure, table of contents, titles and diagrams, how versions are written (2.0 in text, 2.0.0 in coordinates, which product versions the docs name before the release), and how to work with wiki branches (push at once, one worktree per worker, resolving conflicts in the same section, cherry-picking onto master). Use whenever you write or review a wiki page, a README for users, a skill text or a pull request text that names versions, and whenever you commit to a `<repo>.wiki` clone.
---

# Docs and wikis

Every repository of the `vanillabp` organisation that users work with has a GitHub wiki
(`<repo>.wiki`): the platform (`adapter-platform-integration`), each adapter, the Business
Cockpit and its adapters. The rules below hold for all of them, and for every page added later.
For the language itself (plain English for second-language readers, the humaniser checklist) see
the skill [humaniser](../humaniser/SKILL.md).

## 1. How a wiki page is built

**Write in layers.**

1. First paragraph: what the page is about, and what to do if you do not want to go deeper now.
2. Second paragraph: what people often need.
3. From the third on: the full explanation with background.

A newcomer must see how far to read the first time and where the reference part starts.

**A small table of contents at the top**, as a numbered list with anchor links. Each entry has the
heading and one short sentence that explains it. Models: `Spring-Boot-integration.md` in the
platform wiki and `Home.md` of the Camunda 7 adapter wiki.

```markdown
1. [Configure the adapters](#configure-the-adapters)<br>
   Each BPMS you use gets a section below `vanillabp.adapters`.
```

**No repeated title.** GitHub shows the page title itself. So the page does not start with a
heading that repeats it, not even in other words.

**Diagrams belong in.** Use Mermaid where GitHub renders it. Otherwise use a screenshot that links
to its source file. Diagrams for end users go into the wiki; diagrams for contributors go into the
`README.md` of the repository.

**One look across pages.** For example, no horizontal rules on one page when the others have none.

## 2. How versions are written

**In text, a version is `2.0`**, without a patch number and without `-SNAPSHOT`.

**In a dependency coordinate it is `2.0.0`.** A coordinate is not text: people copy it into a
build, where `2.0` resolves to nothing. That covers `<version>`, `implementation platform(...)`
and anything else a reader copies. The Camunda 8 adapter adds the cluster minor it was built
against, for example `2.0.0-8.10`. Where it helps to know which patches exist, link to Maven
Central instead of leaving the reader to fill in the number.

**Why.** The rule for text was once applied too widely, and the XML examples were set to `2.0`
as well. A reader who copies such an example gets a build that does not resolve.

### Which product versions the docs name before the release

Until the releases are out, every text (wikis, READMEs, skills, `AGENTS.md`, pull request texts,
upgrade notes) names **Business Cockpit 1.0** (`1.0.0`) and **VanillaBP 2.0**. This holds even
when the POM of the cockpit still says `0.9.0-SNAPSHOT`. Before the release, write "until 1.0.0
is released, build the snapshot of `main`", not "0.9.0-SNAPSHOT". The cockpit 1.0 is released
together with VanillaBP 2.0. Its migration starts from 0.4.3.

**Why.** An agent once derived "at least 0.9.0" from the POM and wrote it into a user text.

**Check:** search your text for `0\.9` before you commit.

## 3. Wiki branches

A wiki has no pull requests, and GitHub renders only `master`. So work happens on a branch of the
wiki repository, and the branch is merged onto `master` later.

### Push the branch at once

**Rule.** Push every wiki branch right after its first commit.

**Why.** A branch that exists only in a local clone dies with the dev container. Fourteen pages of
cockpit documentation were lost that way, because the branch was held back until the matching code
change was merged. A pushed branch next to `master` disturbs nobody.

### One worktree per worker

**Rule.** Two agents (or people) never work in the same `<repo>.wiki` clone at the same time.
Give each one a worktree, as for code:

```bash
git -C <repo>.wiki fetch origin
git -C <repo>.wiki worktree add -b wiki/<topic> /home/vscode/worktrees/<topic>-wiki origin/master
```

Name the worktree path in an agent's task and forbid the clone itself. If somebody works without a
worktree, they check before the push that the commit is where they think:

```bash
git -C <clone> branch --show-current
git log --oneline -1 <own-branch>
```

An empty own branch is the warning sign.

**Why.** One clone has one HEAD and one index. Agent B switched the clone to its branch while
agent A was working, and A's commit landed on B's branch while A's pushed branch stayed empty. A
small wiki commit on the wrong branch is easy to miss.

### Conflicts in the same section

Wiki branches of different changes collide often, and nearly always in the same way: two branches
add a NEW section at the same place on the same page, or both rewrite the summary line at the top.
Neither overwrites the other.

**Rule.**

- Keep both sides. Never pick one version.
- The order is usually in the text: the paragraph before refers to one of them as the "next
  section", and that one goes first.
- Tables: take all rows from both sides, and rewrite the paragraph after the table instead of
  picking one version. Otherwise the top of the page promises something the bottom does not hold.
- Afterwards check that phrases like "Both guardrails above" are still true with the added section.
- Merge branches in dependency order: a branch that was started on top of another goes after it.

### Merging onto `master`

Merge a wiki branch when the maintainer allowed it, and only once the code change it describes is
merged. Before that, the page would describe something that does not exist yet.

```bash
git -C <repo>.wiki fetch origin
git -C <repo>.wiki worktree add /home/vscode/worktrees/<topic>-master origin/master
cd /home/vscode/worktrees/<topic>-master
git cherry-pick -x <commit>...
git push origin HEAD:master
git push origin --delete wiki/<topic>
```

Do not check out `master` in a shared clone; use a worktree from `origin/master`.

**The order is the trap.** One branch can hold commits of several changes. Pick only the commits
whose code change is merged. Look at each commit before you cherry-pick it: a commit that
describes a method which does not exist yet stays on the branch.
