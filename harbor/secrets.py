"""Secret reference resolution.

v0.8 ships only an environment-backed resolver. The interface deliberately
allows a managed secret store (Vault, AWS Secrets Manager, etc.) to replace it
without changing workers or connectors.
"""
from __future__ import annotations

import os


class SecretError(RuntimeError):
    pass


def resolve(secret_ref: str | None, *, required: bool = False) -> str | None:
    if not secret_ref:
        if required:
            raise SecretError("secret reference is required")
        return None
    if secret_ref.startswith("env:"):
        name = secret_ref[4:]
        value = os.environ.get(name)
        if required and not value:
            raise SecretError(f"environment secret '{name}' is not set")
        return value
    raise SecretError(
        f"unsupported secret_ref '{secret_ref}'. v0.8 supports env:NAME; "
        "add a managed secret backend before production multi-tenant rollout."
    )
