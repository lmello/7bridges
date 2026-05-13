# CHANGELOG

<!-- version list -->

## v1.0.0 (2026-05-13)

- Initial Release

## Unreleased

### Bug Fixes

- 400 errors, usage zeros, count_tokens 404, debug log bloat
  ([`f1ebd16`](https://github.com/sdkks/7bridges/commit/f1ebd16216b14d36aeca68a21b6c868dafc4e819))

- Add HEAD / handler for Claude Code connectivity check
  ([`efb1aa3`](https://github.com/sdkks/7bridges/commit/efb1aa3cc90491d21d6242c627cf12268616f6d2))

- Correct tool args serialization and thinking block handling
  ([`6cfa12a`](https://github.com/sdkks/7bridges/commit/6cfa12a68df952c0c6357be09a778698520550b3))

- Remove max_tokens ceiling, add validation error handler, PM2 memory cap
  ([`f26c376`](https://github.com/sdkks/7bridges/commit/f26c376ce04d71ba88e1335d027c87ba8ba5d96a))

- **config**: Add claude-opus-4-7 alias for Claude Code model selector
  ([`bf23233`](https://github.com/sdkks/7bridges/commit/bf2323341cfbb6ee97d46c578bdce9625d51eecb))

- **debug**: Correct timestamps and add useful timing metrics
  ([`06aca6b`](https://github.com/sdkks/7bridges/commit/06aca6b8c69988e3c533c0d30675d2279e996aa0))

- **tail-logs**: Auto-switch to newest debug log file on PM2 restart
  ([`557e36d`](https://github.com/sdkks/7bridges/commit/557e36d5f96be4b217f1e91ceaba584f0951fb3d))

- **translation**: Convert ToolResultBlock to OpenAI 'tool' role messages
  ([`d06d732`](https://github.com/sdkks/7bridges/commit/d06d73253a4a67d6a1ee1cb39bc4dba9722673b3))

### Build System

- Add PM2 config, Makefile targets, requirements lockfile
  ([`81acb9f`](https://github.com/sdkks/7bridges/commit/81acb9ff218aada1b9a3c28d4dbbcb8157eb25a7))

- Add pre-commit hooks with ruff, mypy, pytest
  ([`c273a51`](https://github.com/sdkks/7bridges/commit/c273a517dcb9ab14db07267e3259ccf127ec4de7))

- Enable BRIDGE_DEBUG by default in PM2 config
  ([`65510c9`](https://github.com/sdkks/7bridges/commit/65510c9b3fb1867a4f13cc60b885f49a77d00db9))

### Chores

- Clean up for open source
  ([`a86cb26`](https://github.com/sdkks/7bridges/commit/a86cb26c1f0c1354a041a77dfc9ba4607d856ab0))

- Ignore debug logs
  ([`477316e`](https://github.com/sdkks/7bridges/commit/477316eb30e777e3bf62b8de78f83992e6a8b43c))

- Remove SESSION_HANDOFF, add logs/.keep for directory structure
  ([`26f5357`](https://github.com/sdkks/7bridges/commit/26f5357ada065e9666fb1059bfe124f138ef783a))

- Rename pm2 process to 7bridges
  ([`e03bf92`](https://github.com/sdkks/7bridges/commit/e03bf923f535b8d7c2b24856530c9fe246295d0a))

### Documentation

- Add ARCHITECTURE.md with translation deep dive and mermaid diagrams
  ([`5278b04`](https://github.com/sdkks/7bridges/commit/5278b04037480a914b8f6c062bbbb8fcb589f0f5))

- Add CLAUDE.md and symlink AGENTS.md
  ([`117ccb0`](https://github.com/sdkks/7bridges/commit/117ccb0b3cf8903b115d2f7ce31ac906ae14f26c))

- Add debug logging docs and Makefile targets
  ([`d94562a`](https://github.com/sdkks/7bridges/commit/d94562a326d1425a1b7103033a88ba36e1fe873a))

- Add session handoff report
  ([`033e56f`](https://github.com/sdkks/7bridges/commit/033e56fc6151e3aedc9068b3bd2f325cf1ce5e3b))

- Rewrite README with motivation, vision, and usage
  ([`42ccc6c`](https://github.com/sdkks/7bridges/commit/42ccc6cb740af49496f4c79d184ba87a993d6ce9))

- Update README, CLAUDE.md, SESSION_HANDOFF with latest features
  ([`a887249`](https://github.com/sdkks/7bridges/commit/a8872492bfa900bfd4d7d8df3595735195f8720a))

- **agents**: Update CLAUDE.md with recent changes
  ([`34302f2`](https://github.com/sdkks/7bridges/commit/34302f22197b31772fb83622cb85cfdc05cb50f9))

- **readme**: Mention CLAUDE.md agentic development guide
  ([`ce50b85`](https://github.com/sdkks/7bridges/commit/ce50b8584d78fd9d1d36321712fd9a67202513fc))

### Features

- Add conventional commit validation and semantic-release
  ([`f37e215`](https://github.com/sdkks/7bridges/commit/f37e215adb3cb7869bc0cc0f415d69fcda8654ee))

- Add streaming translator and debug middleware
  ([`028efd1`](https://github.com/sdkks/7bridges/commit/028efd12d5029872528404b41aec1320a0384004))

- Agent inference test framework + live streaming smoke tests
  ([`002b590`](https://github.com/sdkks/7bridges/commit/002b590532b1315b96b95a9b36f9a925269c6b60))

- Complete Anthropic Messages API mapping with full test suite
  ([`06b35f6`](https://github.com/sdkks/7bridges/commit/06b35f676e976653a448ccb33b3dffad17cd2aca))

- HEAD handlers for all endpoints + comprehensive debug logging
  ([`0caff83`](https://github.com/sdkks/7bridges/commit/0caff83ca57f215e025b3eeb79d22653dcbcace7))

- Initial scaffolding for 7-bridges-of-claude
  ([`93a80df`](https://github.com/sdkks/7bridges/commit/93a80dff7068e792c37db5cca854663507b1092e))

- **config**: Add pattern-based model routing fallback
  ([`d151c66`](https://github.com/sdkks/7bridges/commit/d151c66163f9ff8b6d89da072de4663a6a725ba4))

- **debug**: Harden middleware with proper rebuild, errors, cleanup
  ([`fae181f`](https://github.com/sdkks/7bridges/commit/fae181f19d530f883545bd0b31856045036a7c2b))

### Refactoring

- **models**: Add _SIGNATURE_PLACEHOLDER constant for thinking blocks
  ([`aa0e8bc`](https://github.com/sdkks/7bridges/commit/aa0e8bc8667660e1d614f919da13e43abac92d88))

### Testing

- **agent-inference**: Add fixture prompts and baseline responses
  ([`0268946`](https://github.com/sdkks/7bridges/commit/02689461ad5ea4452358c1c2d0d6d71d88edd3c3))

- **streaming**: Add edge-case tests for interleaved thinking + tool calls
  ([`58405d4`](https://github.com/sdkks/7bridges/commit/58405d461f1ed8ada572c9b052c3f9482b5e0d07))
