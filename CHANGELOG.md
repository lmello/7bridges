# CHANGELOG

<!-- version list -->

## v1.15.1 (2026-05-30)

### Bug Fixes

- Add DocumentBlock for PDF/document content blocks from Claude Code
  ([`211b50b`](https://github.com/sdkks/7bridges/commit/211b50be13c819ff3a8032df14a0d15225a53dbc))


## v1.15.0 (2026-05-29)

### Features

- **mimo**: Add Xiaomi MiMo OpenAI-compatible backend with prompt caching
  ([`f0eaa78`](https://github.com/sdkks/7bridges/commit/f0eaa78))

## v1.14.0 (2026-05-28)

### Documentation

- Update example to use 4096 tokens for vision fallback
  ([`b4c0a0c`](https://github.com/sdkks/7bridges/commit/b4c0a0c874311beb3ee3bd628673daf7ce868118))

- **vision**: Document caching, parallel processing, and Ollama lifecycle
  ([`9303aba`](https://github.com/sdkks/7bridges/commit/9303abad8bbdb7824c322503c0abf699db15c5b8))

### Features

- **dashboard**: Add cache visualization and server-side chart filtering
  ([`c78b7be`](https://github.com/sdkks/7bridges/commit/c78b7be6d8eb39541b40427496d1a8540dcda0bc))


## v1.13.0 (2026-05-28)

### Bug Fixes

- **ollama**: Add logging, keep_alive, and cancellation to vision fallback
  ([`b51f94b`](https://github.com/sdkks/7bridges/commit/b51f94bcaa85afd74954259568fa29cfd40a14ba))

### Features

- **vision**: Change default VL model to gemma4:e4b, fix soft reject bug
  ([`b5176e2`](https://github.com/sdkks/7bridges/commit/b5176e20095db3720bbd691cbdc96e4848c2c6aa))

- **vision**: Parallel VL calls, persistent cache, and context prompts
  ([`798e730`](https://github.com/sdkks/7bridges/commit/798e730525cbc2ab487139d994b8bb8c2d650dc9))

- **vision**: Parameterize Ollama ctx window and remove keep_alive for VL
  ([`c3273e0`](https://github.com/sdkks/7bridges/commit/c3273e0f2860fe5b4004f3f6e0e96e8470ce63e8))


## v1.12.0 (2026-05-27)

### Features

- Add per-backend/model pricing overrides in config.py with fallback
  ([`fa3ee33`](https://github.com/sdkks/7bridges/commit/fa3ee335de528b4f71307cd1ac1df01aedae7b54))

- Per-model pricing, log rotation, cache keys, and historical data
  ([`fa3ee33`](https://github.com/sdkks/7bridges/commit/fa3ee335de528b4f71307cd1ac1df01aedae7b54))


## v1.11.2 (2026-05-27)

### Bug Fixes

- **dashboard**: Resolve three rendering and interaction bugs
  ([`634d989`](https://github.com/sdkks/7bridges/commit/634d9894088d7b1106cb5372298b6477e4fa1338))


## v1.11.1 (2026-05-27)

### Bug Fixes

- **ollama**: Prevent hangs with HTTP timeout and stream cancellation cleanup
  ([`c17ea02`](https://github.com/sdkks/7bridges/commit/c17ea02ece0ca54a2249e0445d8ee919570f60ab))

### Documentation

- **dashboard**: What's new
  ([`5f81a4d`](https://github.com/sdkks/7bridges/commit/5f81a4dd701ab2bdbc35eab656e1c35cd4c9448f))


## v1.11.0 (2026-05-27)

### Bug Fixes

- **dashboard**: Use local timezone for chart labels and table timestamps
  ([`3d76782`](https://github.com/sdkks/7bridges/commit/3d76782412ce9542d72d4b2a268bd5dd04069649))

### Features

- **dashboard**: Add errors/hour chart and configurable time window
  ([`f481e08`](https://github.com/sdkks/7bridges/commit/f481e08b870aae1eb57034bb40286a1fb1aa4a70))


## v1.10.0 (2026-05-27)

### Features

- **dashboard**: Add favicon and configurable auto-refresh
  ([`901ccc8`](https://github.com/sdkks/7bridges/commit/901ccc8b2ae6f4757335f38b9663e52aae7145e4))


## v1.9.0 (2026-05-27)

### Features

- **logging**: Add universal usage logging, cost estimation, and web dashboard
  ([`671003a`](https://github.com/sdkks/7bridges/commit/671003ac83d0c7f26362c1bb92e7248dd23efb5e))


## v1.8.0 (2026-05-27)

### Bug Fixes

- **ci**: Prevent backtick command injection in release workflow
  ([`144749e`](https://github.com/sdkks/7bridges/commit/144749e3c929f9bf03d57a2e61242075d0d6b9be))

- **docs,backend**: Address PR #2 review comments
  ([`412fc0b`](https://github.com/sdkks/7bridges/commit/412fc0b1c2e0feddac463fb622cd66442d6396c2))

### Continuous Integration

- Add PR checks workflow for lint and test on pull requests
  ([`8d32de0`](https://github.com/sdkks/7bridges/commit/8d32de02bffcbcb397fa39ff8af38b21483e61a0))

### Documentation

- Add issue/PR templates and contributing guide
  ([`f60a5b0`](https://github.com/sdkks/7bridges/commit/f60a5b0e510c0dec140b2fb4632890c10686cc2b))

- **readme**: Add per-bridge thinking and context window notes
  ([`fb0a48f`](https://github.com/sdkks/7bridges/commit/fb0a48fe80f53c1a11f40fa8dd771a70892c5244))

### Features

- **dev**: Add start-debug target for pm2-based debug sessions
  ([`2e951d9`](https://github.com/sdkks/7bridges/commit/2e951d978507908de26f58df5e898633eeea8ec2))


## v1.7.0 (2026-05-22)

### Bug Fixes

- **fireworks**: Use Anthropic-compatible thinking object instead of SiliconFlow params
  ([`0ab9750`](https://github.com/sdkks/7bridges/commit/0ab97506bc47db3615b5a41ca6b6c5d6e4ba3a1a))

- **fireworks**: Use reasoning_effort string for MiniMax M2.7 instead of thinking object
  ([`217d507`](https://github.com/sdkks/7bridges/commit/217d5074522f5e651959b5192077928c48a05c85))

### Documentation

- Add Fireworks AI bridge and models to README
  ([`b0c870f`](https://github.com/sdkks/7bridges/commit/b0c870fe07bc200a08873f6e6a928833eb5580a2))

### Features

- **fireworks**: Add Fireworks AI backend with Kimi K2.6 and MiniMax M2.7
  ([`25e2721`](https://github.com/sdkks/7bridges/commit/25e2721bf4b2da5d19dc461a070101b6259fb760))


## v1.6.0 (2026-05-22)

### Bug Fixes

- **ci**: Check only commit subject line for conventional format
  ([`846f81d`](https://github.com/sdkks/7bridges/commit/846f81dcbac5a5f06b059e5d17a938bc8ad54430))

- **ci**: Exclude live-API tests from pre-commit hook
  ([`a32e923`](https://github.com/sdkks/7bridges/commit/a32e9231e677aa144687645aff9e04fb94f9a4b7))

### Features

- **debug**: Log enable_thinking and thinking_budget in outgoing requests
  ([`7c57027`](https://github.com/sdkks/7bridges/commit/7c5702791cd113418937cc397021510f79538be4))


## v1.5.0 (2026-05-22)

### Features

- **siliconflow**: Add Kimi K2.6 and GLM 5.1 models with accurate specs
  ([`68568cd`](https://github.com/sdkks/7bridges/commit/68568cdb649db672e60e5d5f314beeb7619c3369))

- **siliconflow**: Add SiliconFlow bridge with MiniMax-M2.5 support
  ([`561d511`](https://github.com/sdkks/7bridges/commit/561d511a7e18979241ffc7e2dea89fe3b05f32c1))


## v1.4.0 (2026-05-22)

### Bug Fixes

- **stream**: Handle upstream errors mid-stream with SSE error event
  ([`3c14f27`](https://github.com/sdkks/7bridges/commit/3c14f276e5864d8653dd8e3729c4768a95ba5ef4))

### Documentation

- Expand vision fallback docs with separate API call explanation
  ([`9f94ccd`](https://github.com/sdkks/7bridges/commit/9f94ccdde8111622887bb9038bb1456af335d518))

### Features

- **debug**: Log outgoing requests and wire up DeepSeek thinking/effort passthrough
  ([`591a838`](https://github.com/sdkks/7bridges/commit/591a8380fa8cee6f51324b7063dbbb68b15d4464))


## v1.3.0 (2026-05-18)

### Bug Fixes

- **ollama**: Add from err to chained exceptions (B904)
  ([`69c5359`](https://github.com/sdkks/7bridges/commit/69c53594d94ebc114be34a1f122ca9d2bdb4cd12))

- **ollama**: Resolve mypy type errors from ollama SDK type stubs
  ([`62a8857`](https://github.com/sdkks/7bridges/commit/62a8857bde5a0e3923673fe89ecdf1dd38284e62))

### Features

- Vision fallback — give blind models eyes via VL backend
  ([`09a9ebf`](https://github.com/sdkks/7bridges/commit/09a9ebfd476f08e27f851f248ec3e261d8434699))


## v1.2.0 (2026-05-16)

### Documentation

- **ollama**: Document BFS tree inversion test for each model
  ([`2cc143e`](https://github.com/sdkks/7bridges/commit/2cc143e0b24ace4509dc2cadac1ae2e90daa9ef6))

- **ollama**: Fix table formatting, correct gemma4 to MoE architecture
  ([`9a9046b`](https://github.com/sdkks/7bridges/commit/9a9046b0bfa6379f6a654303012f125ccc36b52d))

### Features

- **ollama**: Introduce Ollama support
  ([`fb06653`](https://github.com/sdkks/7bridges/commit/fb066537bf98d76d309dda677d08b7890f36cb57))


## v1.1.0 (2026-05-16)

### Bug Fixes

- **ollama**: Graceful stream end on SDK parse errors
  ([`6a7e5a4`](https://github.com/sdkks/7bridges/commit/6a7e5a46f90976e26f87e0bc8e5cbad9539dae47))

- **ollama**: Use "300s" keep_alive default with time unit suffix
  ([`cee4de2`](https://github.com/sdkks/7bridges/commit/cee4de2945c398816528d3ba36332d46f923c5e9))

- **streaming**: Emit initial tool call args, prevent arg concatenation
  ([`fe7ace1`](https://github.com/sdkks/7bridges/commit/fe7ace1d5d740a0b5df6c237aeea713e9ad602f0))

### Chores

- **ollama**: Bump haiku context window to 128k
  ([`16bae14`](https://github.com/sdkks/7bridges/commit/16bae14c44a4fd1f43f8678f8ca75b314e4dc5e0))

- **ollama**: Revert haiku context to 64k
  ([`57d9e88`](https://github.com/sdkks/7bridges/commit/57d9e8850f396b9337857d0c867a0fe77747fb1f))

- **ollama**: Switch haiku default to qwen3.5:9b
  ([`eb4e23a`](https://github.com/sdkks/7bridges/commit/eb4e23afb82368ee697cbc11d4fe1b9edb5282d8))

- **ollama**: Sync .envrc.example haiku context to 64k
  ([`f64d135`](https://github.com/sdkks/7bridges/commit/f64d1353c62d6edd802b7c11fcdb9e92a3607abb))

### Documentation

- **ollama**: Add dense/MoE type and activated params to model table
  ([`83be6fe`](https://github.com/sdkks/7bridges/commit/83be6fe71ec292129f67240f808fce0cd0b1daa9))

- **ollama**: Add OLLAMA_MODELS.md with capabilities and quirks
  ([`240223b`](https://github.com/sdkks/7bridges/commit/240223b2b170f191b6cfcf85e2a9c83e4fb764e4))

- **readme**: Add Ollama bridge section with setup and usage
  ([`ffd7628`](https://github.com/sdkks/7bridges/commit/ffd762858784dc0db0d015eec117b0c957131184))

- **readme**: Explain ollama aliases as local analogues for Anthropic tiers
  ([`6e2241c`](https://github.com/sdkks/7bridges/commit/6e2241c9cc1b190557672594ae0f42b8444b5665))

- **readme**: Link to OLLAMA_MODELS.md for full capabilities
  ([`cafa5d6`](https://github.com/sdkks/7bridges/commit/cafa5d63707a1856f18e04b14387bdd23ac4a70c))

- **readme**: Mention Apple Silicon M2 Pro 32GB as test hardware
  ([`2fafedf`](https://github.com/sdkks/7bridges/commit/2fafedff9f6fc34e339a083df297312a419e3a94))

### Features

- **ollama**: Add Ollama backend bridge using ollama-python SDK
  ([`380b5c3`](https://github.com/sdkks/7bridges/commit/380b5c3f5d5ce32d905fcc3b1ef9537a4454fb47))

- **ollama**: Add ollama-gemma (gemma4:26b, 64k), document gpt-oss write quirk
  ([`bdcddc0`](https://github.com/sdkks/7bridges/commit/bdcddc084e7fe0b5f753e761afd08fcf92fc65e0))

- **ollama**: Add ollama-nemo mapping to nemotron-3-nano:4b (64k ctx)
  ([`97fc16d`](https://github.com/sdkks/7bridges/commit/97fc16d8c6b3431c6b1a3a5413a14faac81b5233))

- **ollama**: Add ollama-sonnet/haiku aliases, debug logging, error hardening
  ([`766c0c6`](https://github.com/sdkks/7bridges/commit/766c0c6fb55380cdb668021e06a5fa156ef702ee))

- **ollama**: Replace ollama-nemo with ollama-gpt-oss (gpt-oss:20b, 64k)
  ([`5d98bc8`](https://github.com/sdkks/7bridges/commit/5d98bc89010ff8002d8da7584ba63fcefbf93f90))


## v1.0.1 (2026-05-15)

### Bug Fixes

- **config**: Add Claude 3.5-era fallback pattern for statusline model
  ([`2d881b1`](https://github.com/sdkks/7bridges/commit/2d881b1ada955ae55d212d95ef94ceb34f591e34))

### Documentation

- **readme**: Add vision support note for DeepSeek vs Kimi
  ([`cb7cd88`](https://github.com/sdkks/7bridges/commit/cb7cd88d5e595c17947737ce938b7717dbb750f3))


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
