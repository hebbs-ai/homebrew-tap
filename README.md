# HEBBS Skill

Teaches AI agents how to use [HEBBS](https://hebbs.dev) — a local-first cognitive memory engine that stores, indexes, and retrieves knowledge.

## Install the skill

### OpenClaw

```bash
git clone https://github.com/hebbs-ai/hebbs-skill.git ~/.openclaw/skills/hebbs
```

Restart your OpenClaw session to pick up the skill.

### Claude Code

```bash
git clone https://github.com/hebbs-ai/hebbs-skill.git ~/.claude/skills/hebbs
```

### Claude.ai

1. Download this repo as a ZIP
2. Go to Settings > Capabilities > Skills > Upload the ZIP

## Install HEBBS

The skill requires `hebbs-server` and `hebbs-cli` binaries.

**macOS (Homebrew):**

```bash
brew install hebbs-ai/tap/hebbs
```

**Any platform (Linux, macOS):**

```bash
curl -sSf https://hebbs.ai/install | sh
```

## Start the server

```bash
brew services start hebbs
```

Or manually:

```bash
HEBBS_AUTH_ENABLED=false hebbs-server start --data-dir ~/.hebbs/data
```

The server listens on gRPC port 6380 and HTTP port 6381.

## Verify

```bash
hebbs-cli status --format json
```

## Links

- [HEBBS](https://hebbs.dev)
- [HEBBS GitHub](https://github.com/hebbs-ai/hebbs)
- [Homebrew Tap](https://github.com/hebbs-ai/homebrew-tap)
