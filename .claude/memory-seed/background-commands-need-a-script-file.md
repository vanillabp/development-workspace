---
name: background-commands-need-a-script-file
description: "`nohup bash -c '...'` stops after the first command here and still reports exit code 0; background work with several steps goes into a script file"
metadata:
  type: feedback
---

A `nohup bash -c '<several commands>' &` dies in this harness after the first command. The output
stops without an error, and the task reports exit code 0. That looks like a successful run.

**Why:** This happened twice on one day, once during a measurement and once while generating two
API clients. Both times the second half of the work was missing, and nothing said so. Later, wait
jobs were started with `& disown` or `> /dev/null &` instead of `run_in_background`. They ran past
the harness, their output was lost, and one of them overwrote the control file of another wait job
that was still running.

**How to apply:** Put work with several steps into a script file in the scratchpad, `chmod +x` it,
then start it with `nohup <file> > <log> 2>&1 &`. Write a marker into the log after each step and
watch the log with a Monitor, so you can see where the run is. Start wait jobs ONLY with
`run_in_background`, and give each wait job its own state directory.
