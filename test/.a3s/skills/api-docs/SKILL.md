---
name: api-docs
description: Generate OpenAPI documentation from code
triggers:
  - "generate docs"
  - "document api"
  - "openapi"
---

When asked to generate API documentation:
1. Read all handler files to understand the API surface
2. Extract route definitions, parameters, and response types
3. Generate OpenAPI 3.0 YAML format
4. Write to docs/openapi.yaml