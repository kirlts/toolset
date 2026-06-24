# OpenCode Go Model Discovery

> When asked about available models from the OpenCode Go provider, do NOT rely solely on the models injected into your system prompt (which may be capped). Query the actual API endpoint.

## Endpoint

```
GET https://opencode.ai/zen/go/v1/models
Authorization: Bearer <OPENCODE_GO_API_KEY>
```

## Full Model List (as of June 2026)

20 models available:

| Model | Type | Vision? |
|---|---|---|
| deepseek-v4-flash | Text | ❌ |
| deepseek-v4-pro | Text | ❌ |
| mimo-v2-pro | Text | ❌ |
| **mimo-v2-omni** | **Multimodal** | **✅ Best candidate** |
| mimo-v2.5-pro | Text | ❌ |
| mimo-v2.5 | Text | ❌ |
| qwen3.7-max | Text | ❌ |
| qwen3.7-plus | Text | ❌ |
| qwen3.6-plus | Text | ❌ |
| qwen3.5-plus | Text | ❌ |
| glm-5.2 | Text (may have vision) | ? |
| glm-5.1 | Text | ❌ |
| glm-5 | Text | ❌ |
| kimi-k2.7-code | Code | ❌ |
| kimi-k2.6 | Text | ❌ |
| kimi-k2.5 | Text | ❌ |
| minimax-m3 | Text | ❌ |
| minimax-m2.7 | Text | ❌ |
| minimax-m2.5 | Text | ❌ |
| hy3-preview | Text | ❌ |

## Cross-Reference

- **toolset repo** `infrastructure/kilo.jsonc` — Provider config that maps model names to the provider
- **config.yaml** `model.default` — The model used for main agent tasks
- **config.yaml** `auxiliary.vision` — The model used for vision tasks (separate from main model)

## Configuring Vision

To enable vision with OpenCode Go:

```yaml
auxiliary:
  vision:
    provider: opencode-go
    model: mimo-v2-omni
    base_url: "https://opencode.ai/zen/go/v1"
```

This uses the same `OPENCODE_GO_API_KEY` as the main model. The `mimo-v2-omni` model supports multimodal (text + image) input.
