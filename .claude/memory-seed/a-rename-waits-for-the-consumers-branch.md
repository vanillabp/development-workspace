---
name: a-rename-waits-for-the-consumers-branch
description: "A rename in test-utils or the SPI is merged only when the follow-up branch of every consumer exists and is confirmed; an announcement holds nothing back"
metadata:
  type: feedback
---

When you rename a class in `test-utils` or in the SPI, the merge publishes a snapshot. Other
repositories build against that snapshot. If their follow-up change is not ready before the merge,
their `main` breaks at once.

It happened like this: `FreePortUtil` was renamed to `OneFreePortPerJvm`. The commit message of the
rename even said that `business-cockpit` still needed a follow-up and that it had to be merged
before the snapshot went out. It was merged anyway. The people working on `business-cockpit` had no
branch yet, because they were waiting for the new snapshot. Both sides waited for each other, and
`business-cockpit` was red with `cannot find symbol` in three places.

**Why:** An announcement is not a predecessor. A line that only informs the other side does not
stop anything. The repositories are coupled only through the snapshot, so everything looks green
until the snapshot is published.

**How to apply:** Before you MERGE a rename in a shared artifact, name the follow-up branch of each
consumer and wait until someone confirms that it is ready, or prepare the follow-up there yourself.
Merge only after that, then merge the follow-ups right behind it. To see what a snapshot really
contains, run `unzip -l` on the jar and look for the class.
