# API-Specific Provider Configuration

This document explains how to configure which providers to use for each API endpoint in SentinelShield.

## Overview

The system now supports configuring different providers for different API endpoints. This allows you to:
- Use only specific providers for each API endpoint
- Prevent unnecessary model downloads for unused providers
- Optimize performance by using lightweight providers where appropriate

## Configuration

The configuration is defined in `sentinelshield/core/config.py` in the `Settings` class:

```python
api_configs: Dict[str, APIConfig] = {
    "/v1/prompt-guard": APIConfig(providers=["llama_prompt_guard_2"]),
    "/v1/general-guard": APIConfig(providers=["dummy"]),
}
```

## Current Configuration

### `/v1/prompt-guard`
- **Providers**: `llama_prompt_guard_2` only
- **Purpose**: Specialized prompt moderation using Llama Prompt Guard 2 model
- **Rules**: Uses both whitelist and blacklist rules

### `/v1/general-guard` (formerly `/v1/moderate`)
- **Providers**: `dummy` only
- **Purpose**: General content moderation using lightweight dummy provider
- **Rules**: Uses blacklist rules only

## Adding New API Endpoints

To add a new API endpoint with specific providers:

1. Add the configuration to `sentinelshield/core/config.py`:
```python
api_configs: Dict[str, APIConfig] = {
    "/v1/prompt-guard": APIConfig(providers=["llama_prompt_guard_2"]),
    "/v1/general-guard": APIConfig(providers=["dummy"]),
    "/v1/new-endpoint": APIConfig(providers=["llama_guard_4_12b", "dummy"]),
}
```

2. Create a new router file in `sentinelshield/api/routers/`
3. Use `build_orchestrator(api_path="/v1/new-endpoint")` in your router

## Available Providers

- `dummy`: Lightweight provider for testing (blocks text containing "bad")
- `llama_prompt_guard_2`: Llama Prompt Guard 2 model for prompt moderation
- `llama_guard_4_12b`: Llama Guard 4 12B model for general moderation

## Benefits

1. **Selective Loading**: Only providers configured for any API endpoint will be loaded
2. **Performance**: Each API endpoint uses only the providers it needs
3. **Resource Efficiency**: Prevents unnecessary model downloads
4. **Flexibility**: Easy to configure different provider combinations per endpoint

## Example Usage

```bash
# Use prompt-guard with llama_prompt_guard_2
curl -X POST "http://localhost:8000/v1/prompt-guard" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Hello, how are you?"}'

# Use general-guard with dummy provider
curl -X POST "http://localhost:8000/v1/general-guard" \
     -H "Content-Type: application/json" \
     -d '{"text": "This is a test message"}'
``` 