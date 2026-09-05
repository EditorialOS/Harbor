# Harbor on ChatGPT / Codex

This directory is a product surface, not a separate Harbor runtime.

The intended production bundle is:

- **Skill:** workflow guidance for Harbor workers.
- **Remote MCP app:** authenticated Harbor product verbs backed by the Fly control plane.
- **Plugin/listing:** distribution layer once Harbor's remote MCP endpoint, tenant authentication, privacy/terms, and production connection flow are live.

Do not point a public ChatGPT/Codex integration at the local file-config MCP adapter. Production tenant resolution must come from authenticated Harbor identity, never a caller-supplied filesystem path.
