#!/usr/bin/env python3
"""Aligns every markdown table of a file.

Each column gets the width of its longest entry. The last column is not padded,
because a status text runs to thousands of characters and padding every short
row up to it buries the file in whitespace; its separator follows the header
instead. The separator keeps the style of these files, dashes with no spaces
beside them.

A block whose rows disagree about the number of cells is left alone and
reported. Such a block has a row to repair, which is a different job: see the
skill next to this file.
"""
import re
import sys


def split_row(line):
    """Splits a table row at its separators, not at the pipes in its text.

    A pipe inside a code span belongs to the content, as in
    `workflowModuleId|bpmnProcessId`, and so does an escaped one, `\\|`.
    Splitting there invents a column and writes spaces into the code when the
    cells are joined again.
    """
    inner = line.strip()[1:]
    if inner.endswith('|'):
        inner = inner[:-1]
    cells, current, in_code = [], [], False
    for index, char in enumerate(inner):
        if char == '`':
            in_code = not in_code
        escaped = index > 0 and inner[index - 1] == '\\'
        if char == '|' and not in_code and not escaped:
            cells.append(''.join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append(''.join(current).strip())
    return cells


def is_separator(cells):
    return cells and all(re.fullmatch(r':?-{3,}:?', c) for c in cells)


def close_open_rows(block):
    """Adds the closing pipe to rows which lack it.

    Every row of a table ends with a pipe, so a row which does not is missing
    it. This is the one defect which can be told apart with certainty, and it
    is the most common one, so it is repaired rather than reported. Counting
    cells does not find it: the splitter drops a trailing pipe anyway, so an
    open row carries the same number of cells as a closed one.
    """
    return [l.rstrip() + ' |' if not l.rstrip().endswith('|') else l
            for l in block]


def format_block(block, path, first_line):
    block = close_open_rows(block)
    rows = [split_row(l) for l in block]
    counts = {len(r) for r in rows}
    if len(counts) != 1:
        print('%s:%d needs repair, rows carry %s cells'
              % (path, first_line, sorted(counts)))
        return block, False
    width = counts.pop()
    data = [r for r in rows if not is_separator(r)]
    widths = [max(len(r[c]) for r in data) for c in range(width)]
    # the last column is not padded, so its separator follows the header rather
    # than the longest status
    widths[-1] = max(len(data[0][-1]), 3) if data else 3
    out = []
    for row in rows:
        if is_separator(row):
            out.append('|' + '|'.join('-' * (widths[c] + 2) for c in range(width)) + '|')
            continue
        cells = [row[c].ljust(widths[c]) for c in range(width)]
        cells[-1] = row[-1]
        out.append('| ' + ' | '.join(cells) + ' |')
    return out, True


def main(path):
    lines = open(path).read().split('\n')
    result, block, start, left = [], [], 0, 0
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith('|'):
            if not block:
                start = number
            block.append(line)
            continue
        if block:
            out, aligned = format_block(block, path, start)
            result.extend(out)
            left += 0 if aligned else 1
            block = []
        result.append(line)
    if block:
        out, aligned = format_block(block, path, start)
        result.extend(out)
        left += 0 if aligned else 1
    open(path, 'w').write('\n'.join(result))
    if left:
        print('%s: %d table(s) left as they are, repair the rows named above'
              % (path, left))
    else:
        print('aligned', path)
    return left


if __name__ == '__main__':
    # a table left unaligned is reported through the exit code as well, so a
    # hook or a CI step does not mistake the message for success
    sys.exit(1 if sum(main(p) for p in sys.argv[1:]) else 0)
