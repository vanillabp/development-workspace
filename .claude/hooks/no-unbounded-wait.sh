#!/usr/bin/env bash
#
# PreToolUse hook for the Bash tool: denies commands that poll in a loop without a
# guaranteed end.
#
# Every hanging shell we have seen had the same shape: a `while` or `until` loop with a
# `sleep` in it, waiting for a condition that never became true, usually because it watched
# a file that some OTHER job was supposed to write. Such a loop does not fail. It waits
# forever, and the session looks busy while nothing happens.
#
# Denied:  a while/until loop that contains sleep.
# Allowed: the same loop wrapped in `timeout <seconds>`, or a loop bounded by `seq`.
#
# Reads the hook payload on stdin and answers with a PreToolUse permission decision.
# Without jq it lets every command pass. It keeps no state, so running it twice (for
# example once from the project settings and once from the user's own settings) is
# harmless: both runs give the same answer.

set -o pipefail

command -v jq >/dev/null 2>&1 || exit 0

payload="$(cat)"
command="$(printf '%s' "${payload}" | jq -r '.tool_input.command // ""' 2>/dev/null)"

has_loop() { printf '%s' "${command}" | grep -qE '(^|[;&|)[:space:]])(while|until)[[:space:]]'; }
has_sleep() { printf '%s' "${command}" | grep -qE '(^|[;&|[:space:]])sleep[[:space:]]'; }
is_bounded() { printf '%s' "${command}" | grep -qE '(^|[;&|[:space:]])(timeout|seq)[[:space:]]'; }

if has_loop && has_sleep && ! is_bounded; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Unbounded polling loop. A while/until loop with sleep has no guaranteed end, and loops like this have left shells hanging before.\n1. Waiting for a job YOU started with run_in_background? Then do not wait at all: the completion notification is the signal.\n2. Waiting for something the harness cannot see (CI, a cluster, a remote queue)? Bound it: timeout 900 bash -c '"'"'until <condition>; do sleep 30; done'"'"'. Exit code 124 means it gave up. That is a result to report, not a reason to start the same loop again.\n3. Watch an artifact of the job itself (its log and the marker it writes), never the output file of another wait task."
    }
  }'
fi

exit 0
