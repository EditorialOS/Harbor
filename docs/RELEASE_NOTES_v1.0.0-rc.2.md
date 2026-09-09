# Harbor 1.0.0-rc.2

This release candidate fixes the ChatGPT dashboard discovered during live
acceptance testing. The dashboard now completes the MCP Apps initialization
handshake before receiving its tenant-scoped tool result, while retaining the
ChatGPT compatibility fallback.

All Harbor 1.0.0-rc.1 product, infrastructure, security, billing, and
operational changes remain included. Harbor is still a release candidate until
the unchecked gates in `docs/LAUNCH_CHECKLIST.md` are completed with real
evidence.
