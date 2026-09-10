# Context-window resolution fidelity (WriterAgent)

**Author:** Eliyezer (via Chief)  
**From:** Eliyezer research pass (2026-09-10)  
**Status:** Research / design only — no product code in this PR  
**Scope:** Sidebar compaction denominator (`resolve_context_window`). **No product code changes in this pass.**

## Status / today

Sidebar compaction (PRs #712–#714: `plugin/chatbot/compaction.py`) needs a real context **denominator**. `tool_loop` passes `window=resolve_context_window(client)` into `compact_session`. **Ollama** uses live runtime `num_ctx` from cached `POST /api/show` (`parameters` / Modelfile only) — trained `model_info["*.context_length"]` is **never** a fallback (#570). **Everyone else** walks static `DEFAULT_MODELS[].context_length`, matching the current provider’s id (OpenRouter also via `openrouter_model_ids_equivalent` for `:nitro` / other dynamic suffixes). Custom endpoints get a second pass that matches `model_id` against **any** catalog id value (so `writeragent-mock` → 32768). Unknown → `None` → `compact_session` returns `reason="no_window"` (proactive **and** force compact skip); the feature stays inert. `model_fetcher` already hits `/v1/models` but keeps **ids only** — it discards provider `context_length` / `context_window` fields. Fidelity is therefore catalog-stale for hosted defaults and largely blind for LM Studio, bare llama.cpp / OpenAI-compat customs, and non-default model ids.

## Table

| Provider | Source-of-truth for context | What WA reads today | Gap | Proposed small fix |
|---|---|---|---|---|
| **Ollama** | Live `num_ctx` in `/api/show` `parameters` / Modelfile; trained length in `model_info.*.context_length` (different number) | Live `num_ctx` only via `query_ollama_runtime_num_ctx`; missing → `None` (no catalog fallback) | Correct for #570; if Modelfile omits `num_ctx`, compaction stays off even when trained length exists | **Keep as-is.** Optional later: surface “unknown window” in `/tokens` UI — do not revive trained fallback |
| **OpenRouter** | `GET /api/v1/models` → `context_length` (and `top_provider.context_length`) | Static `DEFAULT_MODELS` + `:nitro`/dynamic-suffix equivalence | Catalog can lag; non-default OR ids → `None`; `openrouter/free` hardcodes 131072 for a **router**, not a fixed model | Cache `context_length` when fetching OR `/v1/models`; `resolve_context_window` prefer cache, then catalog. Treat free-router as best-effort / opaque |
| **Together** | `GET /models` (array) → `context_length` | Catalog only (e.g. MiniMax M3 **1_000_000**, GPT-OSS rows) | Live API unused; Together docs currently show MiniMax M3 **524288** → catalog may already be stale | Same: harvest `context_length` from existing Together `/v1/models` parse path |
| **Groq** | `GET …/openai/v1/models` → `context_window` | Catalog only (`openai/gpt-oss-120b` / `20b`) | Field name differs (`context_window` ≠ `context_length`); unread | Normalize both keys when caching from `/v1/models` |
| **Google Gemini** | Native `models.get` → `inputTokenLimit` (+ separate `outputTokenLimit`); WA uses OpenAI-compat base | Catalog `1048576` for Gemini 3.1 rows | OpenAI-compat `/v1/models` may omit rich limits; native field unused | Prefer cached OpenAI-compat metadata if present; else catalog. **Do not** invent native Gemini client just for this |
| **DeepSeek / Mistral / Z.ai** | Provider model docs / their `/v1/models` (varies) | Catalog only (`deepseek-chat` 163840; Mistral Large 262144; `glm-5.2` 200000) | Non-default ids → `None`; no live harvest | Same optional `/v1/models` context cache when the endpoint already returns a length field |
| **Custom OpenAI-compat** (incl. mock) | Whatever the server puts on `/v1/models` (mock advertises `context_length: 32768`) | Any-id catalog match only (`writeragent-mock` → 32768); else `None` | Real custom servers that publish context are ignored | If `/v1/models` row for selected id has length, use it before giving up |
| **LM Studio** | Server `/v1/models` / load config (provider key `lmstudio`) | **Not** Ollama path (`provider == "ollama"` only). No LM Studio catalog rows → almost always `None` | Compaction inert on common local UX | Treat as OpenAI-compat: use cached `/v1/models` length when present; do **not** call Ollama `/api/show` |
| **llama.cpp** (llama-server) | Shared `n_ctx` (prompt + completion); often not on OpenAI `/v1/models` | Overflow **detection** strings only; no denominator probe | Unknown → inert compact; process-death path already avoids compact-and-retry | Prefer documented `/v1/models` length if exposed; otherwise leave `None`. **Do not** subtract `chat_max_tokens` from window |

### Catalog snapshot (`DEFAULT_MODELS` chat-relevant rows)

| Display | `context_length` | Provider ids |
|---|---|---|
| Free Models (Auto) | 131072 | `openrouter`: `openrouter/free` |
| DeepSeek V3 | 163840 | `deepseek`: `deepseek-chat` |
| DeepSeek V4 Flash | 163840 | `together`: `deepseek-ai/DeepSeek-V4-Flash-0731` |
| MiniMax M3 | 1000000 | `together`: `MiniMaxAI/MiniMax-M3` |
| GPT-OSS 120B | 131072 | `together` / `openrouter` (`…:nitro`) / `groq` |
| GPT-OSS 20B | 128000 | `together` / `groq` |
| Mistral Large 3 | 262144 | `openrouter` / `mistral` |
| Gemini 3.1 Flash Lite Preview / Lite / Pro | 1048576 | `google` + `openrouter` |
| GLM 5.2 | 200000 | `zai`: `glm-5.2` |
| WriterAgent Mock | 32768 | `mock`: `writeragent-mock` |

Audio/image-only rows omit `context_length` (expected). Offline sync helper: `scripts/sync_orca_openrouter_catalog.py` + `scripts/lib/orca_catalog.py` (curated merge, not runtime).

## Ranked small plan (least complexity)

1. **Extend the existing `/v1/models` parse** in `model_fetcher` to memoize per-endpoint `{model_id → context_tokens}`, accepting `context_length` **or** `context_window` (and ignore non-positive). No new network round-trip when Settings/sidebar already fetched the list.
2. **Teach `resolve_context_window` a thin fallback order:** (a) Ollama live `num_ctx` unchanged; (b) cached live metadata for `(endpoint, model_id)` with OpenRouter dynamic-suffix equivalence; (c) `DEFAULT_MODELS` as today; (d) `None`. Prefer optional params / small helpers on these surfaces — **no new tool, no microservice**.
3. **Keep offline catalog sync** (`sync_orca_openrouter_catalog`) as the hygiene path for default-dropdown fidelity; do not block runtime on it.
4. **Document free-router / unknown-id behavior:** `openrouter/free` and unlisted ids may remain approximate or `None`; inert compact is safer than a wrong large denominator.
5. **Tests only on the resolver + fetcher cache** (Ollama still no trained fallback; `:nitro` still matches; mock still 32768; Groq `context_window` harvested). Leave `compaction.py` policy (tiers, `GEN_RESERVE`, overflow retry) untouched.
6. *(Optional follow-up, still small)* LM Studio / custom: same cache path. Skip llama.cpp-specific `n_ctx` plumbing unless a length field appears on `/v1/models`.

## Non-goals

- Hermes **256k** (or any) universal fallback denominator  
- Subtracting `chat_max_tokens` / rewriting shared-`n_ctx` accounting for llama.cpp (keep `GEN_RESERVE`)  
- Rewriting compaction algorithm / thresholds / summarizer  
- New microservice, new MCP/tool, or native Gemini client solely for limits  
- Using Ollama **trained** `model_info.*.context_length` as compaction denominator (#570)

## Sources

**Code / docs (repo @ `25320212`)**

- `plugin/framework/default_models.py` — `DEFAULT_MODELS`, `resolve_model_id`  
- `plugin/chatbot/compaction.py` — `resolve_context_window`, `should_compact`, `compact_session` (`no_window`)  
- `plugin/chatbot/tool_loop.py` — callers with `window=resolve_context_window(client)`  
- `plugin/framework/client/model_fetcher.py` — `parse_ollama_runtime_num_ctx`, `query_ollama_*`, `/v1/models` id-only fetch  
- `plugin/framework/openrouter_model_id.py` — `:nitro` / dynamic vs static suffixes  
- `plugin/framework/client/provider_detection.py` — `ollama` vs `lmstudio` vs `custom`  
- `docs/chat/compaction-dev-plan.md` §5; `docs/chat/llm-hacks.md` (§ Ollama / #570); `docs/tests/mock-llm-sidebar.md`  
- `tests/chatbot/test_compaction.py` — resolver cases; `tests/framework/client/test_model_fetcher.py` — #570  
- PRs: #712 (module), #713 (wire), #714 (mock Packet K); issue #570  

**Provider docs (URLs)**

- OpenRouter models / `context_length`: https://openrouter.ai/docs/guides/overview/models  
- OpenRouter variants / suffixes FAQ: https://openrouter.ai/docs/faq  
- Ollama `/api/show`: https://docs.ollama.com/api-reference/show-model-details · https://github.com/ollama/ollama/blob/main/docs/api.md  
- Together models `context_length`: https://docs.together.ai/reference/models · context windows: https://docs.together.ai/learn/context-windows  
- Groq list models / `context_window`: https://console.groq.com/docs/api-reference · https://console.groq.com/docs/models  
- Google Gemini `inputTokenLimit`: https://ai.google.dev/api/models · https://ai.google.dev/gemini-api/docs/tokens  
