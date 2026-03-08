# a3s-code configuration
# Format: "provider_name/model_id"

# default_model = "openai/model--zhipuai--glm-4.7"
default_model = "openai/kimi-k2.5"
providers {
  name     = "anthropic"
  api_key  = "cr_327e6516e9f13a1efc3934264f207d24929f12a1e52c607ab50c56e8ddc0ba07"
  base_url = "https://hk.claude-code.club/api/v1"

  models {
    id           = "claude-opus-4-5-20251101"
    name         = "Claude Opus 4.5 (20251101)"
    family       = "claude-opus"
    attachment   = true
    reasoning    = true
    tool_call    = true
    temperature  = true
    release_date = "2025-11-01"

    modalities {
      input  = ["text", "image", "pdf"]
      output = ["text"]
    }

    cost {
      input       = 5.0
      output      = 25.0
      cache_read  = 0.5
      cache_write = 6.25
    }

    limit {
      context = 200000
      output  = 64000
    }
  }

  models {
    id           = "claude-sonnet-4-20250514"
    name         = "Claude Sonnet 4 (20250514)"
    family       = "claude-sonnet"
    attachment   = true
    reasoning    = false
    tool_call    = true
    temperature  = true
    release_date = "2025-05-14"

    modalities {
      input  = ["text", "image", "pdf"]
      output = ["text"]
    }

    cost {
      input       = 3.0
      output      = 15.0
      cache_read  = 0.3
      cache_write = 3.75
    }

    limit {
      context = 200000
      output  = 64000
    }
  }
}

providers {
  name = "openai"

  models {
    id          = "kimi-k2.5"
    name        = "KIMI K2.5"
    family      = "kimi"
    api_key     = "sk-G6exg5ITTg5WseU091BKayWz9TX4S4LtPBfU58AtR3UctZ18"
    base_url    = "http://35.220.164.252:3888/v1"
    attachment  = false
    reasoning   = false
    tool_call   = true
    temperature = true

    modalities {
      input  = ["text"]
      output = ["text"]
    }

    limit {
      context = 256000
      output  = 8192
    }
    }
    models {
        id          = "model--zhipuai--glm-4.7"
        name        = "GLM-4.7 (GPUStack)"
        family      = "glm"
        api_key     = "gpustack_e7c6c8513314b5ca_fd0789fbffb7e22b9ab1b38c10ba0e77"
        base_url    = "http://s-20260120181355-dlb77.ailab-safeag.pjh-service.org.cn/v1"
        attachment  = false
        reasoning   = false
        tool_call   = true
        temperature = true

        modalities {
        input  = ["text"]
        output = ["text"]
        }

        limit {
        context = 131072
        output  = 8192
        }
    }
}