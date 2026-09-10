# Harbor 1.0.0-rc.5

Harbor 1.0.0-rc.5 prepares the remote MCP surface and review materials for an
initial public Plugins Directory submission.

## Changed

- Added specific titles and behavior descriptions for every public MCP tool.
- Added bounded input schemas and structured output schemas for all tools.
- Made the run tool's source access, durable writes, email side effect, and
  idempotency explicit.
- Removed internal tenant, source-post, delivery, and provider-message
  identifiers from public MCP responses while retaining customer-usable run ids.
- Updated the submission checklist with copy-ready listing content, current
  positive and negative review cases, annotation justifications, initial release
  notes, and the current plugin-commerce restriction.

This remains a release candidate while external publisher, reviewer-account,
legal, billing, and operational launch gates are completed.
