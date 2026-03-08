default_model = "anthropic/claude-sonnet-4-6"
providers {
  name     = "anthropic"
  api_key  = "cr_f3cc3848c18a4a63338bb1fade6ab3e50be86f63d688ad02da93bacaea01bc93"          # default for all models
  base_url = "https://claude-code.club/api"      # default base URL

  models {
    id        = "claude-opus-4-6"
    name      = "Claude Opus 4.6"
    tool_call = true
    # inherits provider api_key and base_url
  }
  models {
    id        = "claude-sonnet-4-6"
    name      = "Claude Sonnet 4.6"
    tool_call = true
    # inherits provider api_key and base_url
  }
}
providers {
  name    = "openai"
  api_key = "sk-team-key..."

  models {
    id        = "gpt-4o"
    name      = "GPT-4o"
    tool_call = true
    # inherits provider api_key
  }

  models {
    id        = "gpt-4o-mini"
    name      = "GPT-4o Mini"
    api_key   = "sk-personal-key..."   # different key for this model
    tool_call = true
  }
}