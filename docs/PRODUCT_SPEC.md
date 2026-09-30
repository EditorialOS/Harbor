# Harbor — production product slice

## What the customer buys

A Harbor workspace with installable workers. The first worker is Newsletter Intelligence: connect a real newsletter account once and receive a daily intelligence brief based on current performance and recent baseline behavior.

Harbor's primary product is its web workspace and scheduled service. ChatGPT,
Codex, email, and future surfaces are optional interfaces over the same Harbor
account; none is required to operate the product.

The product is not a dashboard that happens to run a script. Harbor is the persistent worker environment. Newsletter Intelligence is worker #1.

## Customer experience

1. Create Harbor account/workspace.
2. Harbor provisions the tenant's private Sprite computer.
3. Customer connects Kit or another supported newsletter source securely.
4. Customer selects morning delivery time and output surface.
5. Harbor validates the live connection.
6. Newsletter Intelligence is enabled.
7. Harbor runs automatically on schedule.
8. Customer may optionally invoke the same worker from ChatGPT/Codex or another
   supported surface.

No customer sees a filesystem path, cron expression, environment variable, or Python command.

## First commercial promise

"Connect your newsletter. Harbor watches performance and gives you the useful part every morning: what changed, what matters, and what to test next."

## Worker ladder

- Newsletter Intelligence
- Competitive / public-source intelligence
- Social intelligence
- Research worker
- SEO worker
- Brand worker
- Alex content-agency worker

All workers use the same Harbor tenancy, Sprite, connector, scheduling, and output infrastructure.

## Commercial boundary

The first pilot is successful when one customer runs on Fly with real source
data for at least one week without manual source-code edits or daily operator
intervention. Public directory distribution is not a v1 launch dependency.
