---
name: pgrep-wait-loop-matches-itself
description: "A wait loop with `pgrep -f <pattern>` finds its own `bash -c` command line and never ends; write the pattern with the bracket trick"
metadata:
  type: feedback
---

A wait loop like
`timeout 1200 bash -c 'until ! pgrep -f "org.codehaus.plexus.classworlds.launcher.Launcher"; do sleep 10; done'`
never ends on its own: `pgrep -f` finds the loop's own `bash -c` command line, which contains the
pattern.

**Why:** A sub-agent hung in exactly this loop for 20 minutes, although no Maven build was running.

**How to apply:** Write the pattern with the bracket trick:
`pgrep -f "[o]rg.codehaus.plexus.classworlds.launcher.Launcher"`. The regex still matches the Maven
process, but no longer the loop's own command line. This applies to every `pgrep -f` condition in
an `until` or `while` loop. Use such a loop to run the Maven builds of several agents one after
the other; for long Docker integration tests set the timeout to 3600 seconds. See also
[[pkill-kills-its-own-shell]].
