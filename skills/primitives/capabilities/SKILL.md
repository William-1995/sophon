---
name: capabilities
description: |
  Introduce Sophon and list available capabilities.
  Call ONLY when the user explicitly asks: "what can you do", "who are you", "list skills", "你有什么能力", "你能做什么", etc.
  Do NOT call for: greetings (hi, hello, 你好), small talk, cancelled runs, or when the user has not explicitly asked about your identity or capabilities. When in doubt, do not call.
metadata:
  type: primitive
  dependencies: ""
---

## Tools

### list
Return a short introduction of Sophon and the list of all available skills (name + description) shown to the user. No arguments needed.
