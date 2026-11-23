---
name: a-test-which-does-not-know-the-clock
description: "Platform tests run in Europe/Vienna; a time window in production code turns a test into a time bomb that is red only at night"
metadata:
  type: project
---

The root POM of `adapter-platform-integration` passes `-Duser.timezone=Europe/Vienna` to Surefire
AND Failsafe. The outbox housekeeping has a default window from 04:00 to 05:00. Unless a zone is
configured, it uses the JVM's time zone. In summer time that is 02:00 to 03:00 UTC.

Because of this, EVERY open pull request of the repository failed one night, seven of them, all at
`MongoIndexesOfAnApplicationManagingItsOwnSchemaTest`. The runs were between 02:15Z and 02:53Z. The
housekeeping claimed its storage, and on MongoDB an upsert creates the collection it writes to. The
same code was green in the evening. The test promised that no INDEX is created, but it checked that
no collection exists at all.

**Why:** A test that does not know a time window of the production code is red at night and green
during the day. That looks like a flaky test, but it is a clock. A Renovate pull request that failed
the same way proved that no feature change was the cause.

**How to apply:** When a failure hits all branches and `main` was green, first compare the time of
the runs with the time windows in the production code. A test that lives next to such a window
keeps the window under its own control, as `MongoOutboxRetentionTest` already does.
