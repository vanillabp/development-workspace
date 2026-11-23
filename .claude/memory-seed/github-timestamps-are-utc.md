---
name: github-timestamps-are-utc
description: "GitHub timestamps are UTC, the container clock may not be; a two hour offset makes a healthy run look stuck"
metadata:
  type: feedback
---

Everything `gh` prints (`createdAt`, `startedAt`, `updatedAt`, log lines) is in UTC. The clock of a
dev container can run in local time, for example CEST, which is two hours ahead. Then a run that
started three minutes ago looks like a run that has hung for two hours.

**Why:** A publish run was cancelled because its step "Publish package" seemed to run for two
hours. It had run for three minutes and was healthy. The cancel destroyed a good run and cost a
restart. A sub-agent disproved the mistake with `date; date -u` in one line.

**How to apply:** Before you say anything about how long a run takes, use `date -u`, not `date`.
Better, compute the duration from the fields of the run (`updatedAt` minus `createdAt`) instead of
comparing with your own clock. If you declare a run stuck, name the computed duration and the
duration of earlier runs of the same workflow. Check your own measurement before you cancel
anything, the same way you check what an agent reports.
