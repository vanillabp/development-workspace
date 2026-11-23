---
name: pkill-kills-its-own-shell
description: "`pkill -f <name>` inside a command that contains `<name>` kills its own shell; use the bracket trick"
metadata:
  type: feedback
---

`pkill -f <name>` matches the full command line of every process. If the command you run contains
`<name>` itself, the shell that runs it matches too, and `pkill` kills it.

**Why:** It happened in an earlier session of this workspace: a cleanup command with `pkill -f`
killed its own shell. This is the same trap as [[pgrep-wait-loop-matches-itself]], only it does
not hang, it ends the command.

**How to apply:** Write the pattern with the bracket trick, `pkill -f "[n]ame"`, so that it still
matches the process you want to stop but not your own command line. Before you kill anything, run
`pgrep -af "[n]ame"` and look at what would be hit.
