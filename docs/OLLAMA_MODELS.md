# Ollama Known Working Models

Models tested and confirmed working with the 7 Bridges Ollama backend. All models support tool calling (Read, Write, Edit, Bash) and run locally on Apple Silicon M2 Pro with 32 GB unified memory. Capabilities determined via `ollama show <model>`.

| Alias | Model | Params | Activated | Type | Architecture | Quant | Native Context | Vision | Tools | Thinking |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ollama-sonnet` | `qwen3.6:35b-a3b-coding-nvfp4` | 35.1B | ~3B | MoE | qwen3_5_moe | nvfp4 | 262,144 | ✅ | ✅ | ✅ |
| `ollama-haiku` | `qwen3.5:9b` | 9.7B | 9.7B | Dense | qwen35 | Q4_K_M | 262,144 | ✅ | ✅ | ✅ |
| `ollama-gpt-oss` | `gpt-oss:20b` | 20.9B | — | MoE | gptoss | MXFP4 | 131,072 | ❌ | ✅ | ✅ |
| `ollama-gemma` | `gemma4:26b` | 25.8B | 25.8B | Dense | gemma4 | Q4_K_M | 262,144 | ✅ | ✅ | ✅ |

## ollama-sonnet — qwen3.6:35b-a3b-coding-nvfp4

Qwen 3.6 35B MoE (Mixture of Experts) with nvfp4 quantization. 35.1B total parameters, only ~3B activated per token ("a3b" in the model name). Heaviest model in the roster, tuned for coding tasks. Reliable tool use, strong reasoning, handles large conversations well. The 32k context window we configure is conservative — the native limit is 256k.

**Why "sonnet":** Qwen 3.6 35B hits a sweet spot for local inference — smaller than cloud-scale models but capable enough for complex multi-turn agentic workflows. Roughly analogous to Claude Sonnet in the capability/performance tradeoff.

## ollama-haiku — qwen3.5:9b

Qwen 3.5 9B dense model at Q4_K_M quantization. All 9.7B parameters active on every token — no expert routing overhead. Fast, lightweight, capable of tool use. Good for quick tasks, simple edits, and low-latency interactions. The 64k context window fits comfortably in 32 GB memory.

**Why "haiku":** 9B parameters at Q4_K_M is the local equivalent of a fast, efficient model — quick responses, moderate capability, suitable for straightforward coding and refactoring tasks.

## ollama-gpt-oss — gpt-oss:20b

GPT-OSS 20B MoE at MXFP4 quantization. 20.9B total with a subset activated per token (exact activated count not published). No vision support, but handles tools and thinking. Intermediate size between haiku and sonnet. Native context of 128k; we run at 64k for memory headroom.

**Known quirk:** ~50% failure rate on first-time `Write` tool calls — the model sometimes emits the tool call with incomplete parameters. Subsequent retries almost always succeed as the model corrects itself. `Edit` and `Read` calls are reliable from the first attempt.

## ollama-gemma — gemma4:26b

Gemma 4 26B dense model at Q4_K_M quantization. All 25.8B parameters active on every token. Full capabilities — vision, tools, thinking. 256k native context; runs at 64k. Google's open model, good all-rounder for local agentic use.
