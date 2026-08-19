# Humaniser Skill for Claude Code

A Claude Code skill that strips AI tells out of your writing. Point it at a draft, and it rewrites the parts that make text sound like ChatGPT wrote it.

## What it does

When you trigger `/humaniser`, Claude reads the text you give it and:

- Identifies twenty-five patterns common to AI-generated writing
- Rewrites the problematic sections in a more natural voice
- Audits its own rewrite for tells it missed the first time
- Returns a final version after the self-audit

It works from Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) guide, maintained by the WikiProject AI Cleanup volunteers who spend their days reverting AI-generated articles. They know what to look for better than anyone.

## When to use it

- You have a draft that you need to sound like you wrote it
- You want to finish a blog post, article, email, or piece of documentation without readers clocking it as AI output
- You've used Claude or another model to generate a first draft and want to make it publishable
- You're reviewing someone else's writing and want a second opinion on whether it reads as human

Don't bother for code comments, commit messages, or anything short and functional where voice doesn't matter.

## What it catches

Twenty-five patterns across five groups:

- **Content patterns**: promotional language, vague attributions, superficial -ing analyses, undue emphasis on significance and legacy
- **Language and grammar**: overused AI vocabulary, copula avoidance, negative parallelisms, rule of three, elegant variation, false ranges
- **Style**: em dash overuse, boldface spam, inline-header vertical lists, title case headings, emojis, curly quotes
- **Communication artefacts**: "I hope this helps", knowledge cutoff disclaimers, sycophantic openers, chat residue
- **Filler and hedging**: excessive hedging, generic positive conclusions, hyphenated word pair overuse, filler phrases

The full catalogue with before/after examples lives in `SKILL.md`.

## The self-audit pass

Most humaniser tools produce one pass and stop. This one does the pass, then prompts itself: "What makes the below so obviously AI generated?" It answers honestly, then does a second pass on the tells it caught the first time round. You get the cleaner version, not the first draft.

That second pass is the difference between output you can publish and output that still smells machine-made.

## A note on soul

Removing AI tells is half the job. The other half is adding voice. Clean prose with no opinions, no rhythm variation, no first person, no admitted uncertainty still reads like a press release. The skill pushes for actual personality: short sentences next to longer ones, stated opinions, specific emotional detail, the occasional tangent. There's a whole section on this in `SKILL.md`, and it's the bit I care about most.

## Installation

Copy `SKILL.md` into your Claude Code skills directory:

```
~/.claude/skills/humaniser/SKILL.md
```

Claude Code will detect and register the skill automatically.

## Usage

Point it at a file:

```
/humaniser path/to/draft.md
```

Or paste text directly:

```
/humaniser
[paste your text]
```

The skill will:

1. Produce a draft rewrite
2. Audit that rewrite with the question "What makes the below so obviously AI generated?"
3. Produce a final version after the audit
4. Optionally summarise the changes it made

## A note on naming

The skill is called `/humaniser` because I write in British English. The internal skill file still references "humanize" and "humanized" in places because those are lifted straight from the Wikipedia source. That's deliberate. Rename the folder and command if you prefer American spelling; the skill itself doesn't care.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition loaded by Claude Code |
| `README.md` | This file |

## Licence

MIT. Do what you like with it.

## Credit

The pattern catalogue is based on [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup. They did the hard work of documenting this stuff. This skill wraps it in a form you can actually use.
