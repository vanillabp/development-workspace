---
name: markdown-tables
description: Keep the markdown tables of a roadmap or any other repository document aligned after every edit, and repair the rows which break alignment. Use whenever a row is added, changed or removed in a markdown table, and whenever a table renders with a column it should not have.
---

# Markdown tables stay aligned

*Last checked on 2026-09-22 against `prompts/ROADMAP.md` and `prompts-businesscockpit/ROADMAP.md`.*

A table whose columns jump around is hard to read in an editor, and the jump appears the moment a
script inserts a row with its own idea of the column width. So after every edit of a table, the
table is aligned again.

## The rule

Every column is as wide as its longest entry, and every row uses that width. The separator row of
dashes uses the same width.

One exception, made on purpose: the LAST column is not padded. Status texts in these roadmaps run
from two hundred to over seven thousand characters, and padding every short row up to the longest
one buries the file in whitespace. The header and the separator of the last column follow the
header text instead.

## What breaks alignment

Four defects, all of them found in real roadmaps on 2026-09-22. The first two are about reading a
row, the last two are about the table as a whole.

**A pipe inside a code span.** `` `workflowModuleId|bpmnProcessId` `` carries a pipe which belongs
to the text. A splitter which does not know about backticks invents a column here, and when it
joins the cells again it writes spaces into the code.

**A raw pipe in the prose of a cell.** This one really does widen the row beyond its header. It is
repaired by escaping it as `\|`. Watch out for a half open code span around it: whether the pipe
counts depends on how the parser reads the span, which is reason enough to escape it.

**A row without its closing pipe.** It renders, and it counts one cell short. Add the pipe.

**A blank line in the middle of a table.** Everything below it renders as a second table without a
header. Remove the blank line.

And one which is not a formatting question at all: a header with fewer columns than its rows. That
happens when a column is added to newer rows only. Widen the header and give the older rows an
empty cell. Never invent a value to fill it, a gap says the truth and a number does not.

## Doing it

The script below aligns every table in a file. It is also here as `format_md_tables.py`.

```bash
python3 .claude/skills/markdown-tables/format_md_tables.py prompts/ROADMAP.md
```

A row without its closing pipe is repaired on the way, because that one can be told apart with
certainty: every row of a table ends with a pipe, so a row which does not is missing it. Counting
cells does not find it, since a trailing pipe is dropped anyway and an open row carries the same
number of cells as a closed one.

The other defects are reported, not guessed. A block whose rows disagree about the number of cells
is left exactly as it is, the message names the file and the first line of that block, and the exit
code is 1. That matters when the script runs in a hook or in a CI step, where nobody reads the
output: a table left alone must not look like success.

## Checking the result

Copy the file before the run and compare afterwards, with whitespace normalized and the escapes
undone. Two changes are allowed: whitespace, and a closing pipe which was added to a row that
lacked one. Everything else is a defect in the run, not in the file.

```bash
cp prompts/ROADMAP.md /tmp/roadmap.before
python3 .claude/skills/markdown-tables/format_md_tables.py prompts/ROADMAP.md
python3 - <<'EOF'
import re
norm = lambda s: re.sub(r'[ \t]+', ' ', re.sub(r'\|-+', '|-', s.replace('\\|', '|')))
before = norm(open('/tmp/roadmap.before').read())
after = norm(open('prompts/ROADMAP.md').read())
print('content unchanged:', before == after)
EOF
```

This check caught two wrong runs on 2026-09-22 before they reached the file: one which turned
`a|b` inside a code span into `a | b`, and one which read an escaped `\|` as a separator and so
took apart the row it had just repaired.

## Where this applies

`prompts/ROADMAP.md`, `prompts-blueprints/ROADMAP.md` and `prompts-businesscockpit/ROADMAP.md` are
shared files without git, so a broken table there cannot be undone by a checkout. Tables in a
repository document follow the same rule and are covered by the usual review.
