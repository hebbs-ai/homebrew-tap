# HEBBS Skill for Claude

Teaches Claude how to use [HEBBS](https://hebbs.dev) — a local-first cognitive memory engine that stores, indexes, and retrieves knowledge.

## Install

### Claude.ai

1. Download or clone this repo
2. Zip the `hebbs/` folder
3. Go to Settings > Capabilities > Skills > Upload the ZIP

### Claude Code

```bash
# Clone into your skills directory
git clone https://github.com/hebbs-ai/hebbs-skill.git ~/.claude/skills/hebbs-skill
```

### OpenClaw

The skill is discoverable via OpenClaw's skill registry. OpenClaw will auto-install HEBBS via Homebrew if needed.

## Prerequisites

HEBBS must be installed and the server must be running.

**Install:**

```bash
brew install hebbs-ai/tap/hebbs
```

Or:

```bash
curl -sSf https://hebbs.ai/install | sh
```

**Start the server:**

```bash
hebbs-server
```

## What the skill enables

- **Remember** facts, decisions, preferences, and observations
- **Recall** relevant context using similarity, temporal, causal, or analogical strategies
- **Reflect** to consolidate raw memories into higher-order insights
- **Forget** outdated or irrelevant memories
- **Prime** context at the start of conversations

## Links

- [HEBBS](https://hebbs.dev)
- [HEBBS GitHub](https://github.com/hebbs-ai/hebbs)
- [Homebrew Tap](https://github.com/hebbs-ai/homebrew-tap)
