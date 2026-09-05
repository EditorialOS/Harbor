# Alex worker — v3 adapter scaffold

Harbor now has a first-class slot for Alex, but this build does **not** pretend the supplied Minimal AI OS v2.0 / Alex-Final v2.1 kernel is already the reconciled v3 kernel.

The v3 architecture requires three concrete changes before `alex` is runnable:

1. Reconcile the live Cowork v2.4 improvements back into `Alex-Final.md` and the skill registry.
2. Align gate behavior with the persistent Gate API's 8-criterion contract.
3. Move per-client brand context, queue, batches and learnings behind the Context API and use tenant config rather than hardcoded folder/service IDs.

The uploaded kernel is preserved under `kernel-source/` as source material for that reconciliation pass.
