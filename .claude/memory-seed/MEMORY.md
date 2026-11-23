# Memory Index

## Lessons from incidents
- [A rename waits for the consumer's branch](a-rename-waits-for-the-consumers-branch.md): an announcement holds nothing back
- [A test which does not know the clock](a-test-which-does-not-know-the-clock.md): red only at night, check the time windows first
- [Background commands need a script file](background-commands-need-a-script-file.md): `nohup bash -c` stops after the first command
- [GitHub timestamps are UTC](github-timestamps-are-utc.md): compute durations from the run, not from your clock
- [pgrep wait loop matches itself](pgrep-wait-loop-matches-itself.md): bracket trick, `[o]rg.codehaus...`
- [pkill kills its own shell](pkill-kills-its-own-shell.md): bracket trick, `pkill -f "[n]ame"`
