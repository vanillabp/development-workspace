---
name: vanillabp-code-review
description: Review a VanillaBP diff against the rule that sources explain themselves: names which read like small sentences, comments which say why in their own words, and no citation of anything a later change can invalidate. Use before submitting a pull request in spi-for-java, adapter-platform-integration or any adapter repository, and when reviewing somebody else's branch.
---

# Reviewing a VanillaBP change

This skill reviews the writing of a change: names, comments, and what they point at.
Module placement, platform parity, SPI compatibility, build commands and formatting are
in `vanillabp-conventions`, and everything about tests is in `vanillabp-testing`. Read
those for the rules themselves. This one asks one question only: does the change explain
itself to the next person who lands in it?

## What to review

The diff of the branch against `main`:

```bash
git fetch origin main
git diff origin/main...HEAD
```

Read the changed hunks plus enough of their surroundings to judge whether a name or a
comment carries. Report a finding only where a reader arriving at that line for a bugfix,
without knowing the rest of the repository, would be left guessing.

## The checks

Each check names what it reads, so it can be run against a branch mechanically.

### 1. Names read like small sentences

Read the identifiers the diff introduces or renames: methods, local variables, fields,
parameters, test classes, test methods.

A method name says what the method does, and a method body together with its comments
reads like a small story. `whatIsReportedWhileBooting` is a name; `handleResult` is not.
A test class says which behaviour is under test, so `Camunda7OldProcessVersionsIT` passes
and `Story57Test` does not.

### 2. Variables are named after what they stand for, not after what they are

Read every declaration in the diff whose name contains its own type in camel case, or a
filler like `data`, `result`, `value`, `list`, `map`, `obj`, `tmp`.

An instance of `WorkflowService` is `workflow`, not `workflowService`. A type name inside
the identifier is the tell to look for. The one exception is a place where two instances
of the same type stand for different things and the type is all that separates them, and
even there the better fix is usually to name the roles.

### 3. Nothing ephemeral is cited

Read every comment, Javadoc, README section, `UPGRADE.md` entry, POM comment, workflow
YAML comment and BPMN comment the diff touches. The grep finds most of them:

```bash
git diff origin/main...HEAD | grep -niE '^\+.*\b(story|prompt|issue|ticket)s? ?#?[0-9]+'
```

Code must not point at a story number, a prompt file, an issue or pull-request number, a
chat transcript or a person. All of those record a conversation at a point in time, and a
later change can overturn what they say without anything noticing. The one sanctioned
citation target is a numbered entry in the decision log of the SAME repository's
`README.md`, written in the plain greppable form
`see decision 7 in the repository's README.md`.

Commit messages and pull-request descriptions may cite whatever they like. They are
records of a point in time themselves.

### 4. Every citation resolves

Read each `see decision <n>` in the diff against the `## Decision log` section of the
README belonging to that file's repository:

```bash
git diff origin/main...HEAD | grep -oiE 'decision [0-9]+' | sort -u
grep -n '^### [0-9]*\.' README.md
```

A citation into another repository's log is the same fragile pointer as a story number and
does not count as resolving. A decision spanning several repositories gets an entry in
each, stating it from that repository's side.

### 5. An overturned decision is superseded, not edited

Read the diff of `README.md` in the decision-log section, next to the behaviour change in
the same commit.

Where the change makes a logged decision untrue, the same commit updates the log: the old
entry stays, marked as superseded and naming the entry which replaced it, and the new
decision takes the next free number. Numbers are never reused and never renumbered.
Editing an entry until the old text is gone breaks every citation which pointed at it,
the ones in older releases included.

A change which makes a decision untrue while the log stays untouched is a finding even
when the code itself is right.

### 6. New comments say why, in words that stand alone

Read every comment the diff adds.

A comment repeating what the line already says is noise. A comment explaining why the
obvious solution is not the one taken is the reason comments exist. It has to be complete
where it stands, so "the same reason as above" and "see the other adapter" are findings:
both move.

Where a name could have carried the explanation, the name is the better fix. Look for that
before accepting a comment.

### 7. What the change costs the next reader

Read the changed methods as a whole.

A method a reader has to scroll through twice to find out what it decides is worth
splitting even when nothing in it is wrong. There is no mechanical trigger for this one,
so report it only where it is obvious.

## Reporting

One line per finding: `path:line`, what is wrong, and the smallest fix. Order by check
number rather than by file. Where a check found nothing, say so instead of listing what is
fine.
