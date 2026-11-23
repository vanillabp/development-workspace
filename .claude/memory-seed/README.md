# Memory seed

This folder is a start memory for Claude Code. Each file is one lesson that came from a real
incident in this workspace. `MEMORY.md` is the index.

The rules of the workspace are in `AGENTS.md` and in the skills under `.claude/skills`. The lessons
here are the few that work best as memory: a short story of what went wrong, why it matters, and
what to do next time.

## How it gets into a workspace

`spawn-workspace` from `Phactum/dev-containers` copies these files into the shared project memory
on the host (`~/.claude/projects/<key>/memory`), but only when that memory is EMPTY or missing.
If the memory already holds a single note, nothing is copied and nothing is overwritten. This
`README.md` is not copied.

After that, the memory is yours. Claude Code adds its own notes as you work, in the language you
work in. The seed does not come back and is not updated in an existing memory.

## Changing a lesson

Change, add or remove a lesson here, in this folder, by a pull request to
`vanillabp/development-workspace`. Keep the format of the existing files: frontmatter with `name`,
`description` and `metadata.type`, then the fact, then `**Why:**` and `**How to apply:**`. Add
each new file to `MEMORY.md`. A change reaches new workspaces only; an existing memory keeps what
it has.
