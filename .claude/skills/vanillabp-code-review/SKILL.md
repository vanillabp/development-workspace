---
name: vanillabp-code-review
description: Review a VanillaBP diff against the rule that sources explain themselves: names which read like small sentences, comments which say why in their own words, English a second-language reader gets on the first pass, and no citation of anything a later change can invalidate. Use before submitting a pull request in spi-for-java, adapter-platform-integration or any adapter repository, and when reviewing somebody else's branch.
---

# Reviewing a VanillaBP change

*Last checked against decision 70 of `adapter-platform-integration`, decision 8 of `spi-for-java`, decision 23 of `camunda7-adapter`, decision 30 of `camunda8-adapter` and decision 12 of `process-engine-api-adapter`. A story which changes behaviour re-reads this skill and moves the anchor.*

This skill reviews the writing of a change: names, comments, the English they are written
in, and what they point at. Module placement, platform parity, SPI compatibility, build
commands and formatting are in `vanillabp-conventions`, and everything about tests is in
`vanillabp-testing`. Read those for the rules themselves. This one asks whether the change
explains itself to the next person who lands in it, and whether that person gets it on the
first pass.

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
citation target is a numbered entry in the SAME repository's `DECISIONS.md`, written in the
plain greppable form `see decision 7 in the repository's DECISIONS.md`.

Commit messages and pull-request descriptions may cite whatever they like. They are
records of a point in time themselves.

### 4. Every citation resolves

Read each `see decision <n>` in the diff against the `DECISIONS.md` of the repository
that file belongs to:

```bash
git diff origin/main...HEAD | grep -oiE 'decision [0-9]+' | sort -u
grep -n '^### [0-9]*\.' DECISIONS.md
```

A citation into another repository's log is the same fragile pointer as a story number and
does not count as resolving. A decision spanning several repositories gets an entry in
each, stating it from that repository's side.

### 5. A reworded message is followed where it is quoted

Read every message the diff rewrites: a startup finding, a validation message, any text a
developer reads.

The words of such a message stand in repositories this branch does not touch. An adapter
test boots an application and reads what the start said, to prove what its adapter
reported. A rewording turns those tests red days later, in somebody else's pull request.
Four assertions in three files of the Camunda 7 adapter went that way on 2026-09-27.

So every message the diff changed is looked for TWICE in each adapter clone:

```bash
for adapter in ../camunda7-adapter ../camunda8-adapter ../process-engine-api-adapter; do
  git -C "$adapter" grep -n "still run on version" -- '*.java'   # the words of the old sentence
  git -C "$adapter" grep -ni "version '" -- '*.java'             # the words around a placeholder
done
```

The first search reads the old sentence. The second one reads the words to the left and to
the right of every PLACEHOLDER in it, and it ignores upper and lower case. The values these
repositories put into a message are adapter ids, workflow module ids, BPMN process ids and
versions, so the second search runs four times: `adapter '`, `version '`, `process '` and
`workflow module '`.

One search is not enough. A test asserts a SHORT fragment with the values already in it. A
fragment which starts with stable words, such as `still run on version '1'`, is found by a
search for the sentence. A fragment whose value stands right behind the first word, such as
`adapter 'c7own'`, shares one single word with the old sentence, and no search for the
sentence finds it. A value which moves into the subject line of a finding takes the first
words of the sentence with it, and it often changes their case: `Adapter 'c7own'` became
`adapter 'c7own'`.

Neither search answers the question. They name the files to read, and nothing more. Both
forms of a message match the same search, and the old sentence may live on in a second
finding. `still run on version '%s'` is still the text of `reportOutfadedVersionInUse`,
while the finding beside it reads differently now. The answer comes from running the suites
the greps named against the changed platform. A scanner which normalises placeholders and
searches in both directions was tried on 2026-09-27 and could not tell the two apart
either.

A test which reads the phrase from the platform instead of writing it down again follows a
rewording by itself. Where a message is quoted that way, this check has nothing left to
read. The platform publishes such phrases as public constants beside the check which writes
them (decision 105 of `adapter-platform-integration`): `DeployedProcessVersionsCheck`
carries the words of its findings about held and faded-out versions, and `DeliveryRecords`
the words of the warning about a missing delivery log. For those findings, change the text
in the constant and nothing else; a rename of a constant is a build error in the adapters
instead of a search. The check still applies to every other message, and to every quote in a
wiki page, a README or an `UPGRADE.md` entry, constant or not.

### 6. An overturned decision is asked about first, then superseded rather than edited

Read the diff of `DECISIONS.md`, next to the behaviour change in the same commit.

A logged decision is changed or replaced ONLY after asking the maintainer. An agent which
notices that its change contradicts an entry stops there and puts the question, before the
change is written. Rewriting an entry to fit the code you already wrote is the finding this
check exists for, and it is a finding even when the code is an improvement.

Once the answer is yes, the same commit updates the log: the old entry stays, marked as
superseded and naming the entry which replaced it, and the new decision takes the next free
number. Numbers are never reused and never renumbered, because a citation which shipped in
an older release still points at them. Editing an entry until its old text is gone breaks
every one of those.

A change which makes a decision untrue while the log stays untouched is a finding even when
the code itself is right. So is a new entry which nothing cites, or one whose reasoning fits
into a comment at the single place that needs it.

### 7. A number the branch hands out is still free

Read the `DECISIONS.md` diff once more, this time only for the numbers.

A number gets claimed while a branch is open, so the log on `origin/main` is only half the
answer. The open pull requests are the other half:

```bash
bin/check-decision-numbers.sh                  # where the repository has the script
```

By hand it is:

```bash
git fetch origin
git show origin/main:DECISIONS.md | grep -E '^#+ [0-9]+\. '
gh pr list --state open
gh pr diff <n> | grep -E '^\+#+ [0-9]+\. '       # gh pr diff takes no path argument
```

A taken number is a finding while the pull request does not exist yet. Once it is merged the
number is fixed on GitHub, and a `see decision 21` in a Java file cannot be changed there. The
fix is the next free number and every citation of it corrected.

Reviewing such a renumbering means reading each changed citation. A `see decision <n>` in the
branch can belong to somebody else's decision, and then the old number was the right one. A
search and replace over the whole branch is what this check is here for.

### 8. New comments say why, in words that stand alone

Read every comment the diff adds.

A comment repeating what the line already says is noise. A comment explaining why the
obvious solution is not the one taken is the reason comments exist. It has to be complete
where it stands, so "the same reason as above" and "see the other adapter" are findings:
both move.

Where a name could have carried the explanation, the name is the better fix. Look for that
before accepting a comment.

### 9. English a second-language reader gets on the first pass

Read every English sentence the diff adds or rewrites: comments and Javadoc, `README.md`,
`DECISIONS.md`, `UPGRADE.md`, `GAPS.md`, wiki pages, and the text of the pull request
itself.

Most people who read this code read English as a second language. A sentence they have to
read twice costs more than the sentence saved. The repository states the rule in the
section `How we write` of its `AGENTS.md`, and that section is what a finding points at.

What counts as a finding:

- a sentence with more than one subordinate clause, or one long enough that its subject and
  its verb are far apart;
- passive voice where somebody or something does the acting and could be named;
- a rare word where an everyday one says the same: `leverage` for `use`, `regarding` for
  `about`, `consequently` for `so`, `possesses` for `has`, `prior to` for `before`;
- three or more nouns stacked into one phrase, such as `adapter configuration property
  resolution order`;
- an abbreviation used before it is written out once, or a technical term introduced
  without saying what it means;
- a paragraph which says the same thing twice in different words.

Two greps find the common cases, and the rest is read:

```bash
git diff origin/main...HEAD | grep -E '^\+' | grep -oE '[^.!?]{160,}'
git diff origin/main...HEAD | grep -niE '^\+.*\b(leverage|utilize|regarding|consequently|possesses|facilitate|prior to|aforementioned|thereby|whilst|hereby|in order to)\b'
```

What is not a finding: an identifier, a configuration key, an artifact coordinate, the
headline of a decision log entry, or a quoted error message. None of those are rewritten
for the sake of language, because code and other repositories point at them. Neither is
text the diff leaves alone; this check reads what the branch writes, not what it inherits.

The fix is the rewritten sentence, not a note that the sentence is long.

### 10. What the change costs the next reader

Read the changed methods as a whole.

A method a reader has to scroll through twice to find out what it decides is worth
splitting even when nothing in it is wrong. There is no mechanical trigger for this one,
so report it only where it is obvious.

## Reporting

One line per finding: `path:line`, what is wrong, and the smallest fix. Order by check
number rather than by file. Where a check found nothing, say so instead of listing what is
fine.
