# Customer onboarding

This is the customer-facing setup for Newsletter Intelligence. It requires no
terminal, JSON, SSH, or Sprite knowledge.

1. Open the Harbor web address and choose **Create workspace**.
2. Enter your email address. Harbor emails a one-time verification code.
3. Enter the code, workspace name, time zone, report hour, and delivery choice.
4. Choose a monthly plan and complete Stripe's hosted Checkout when billing is
   enabled. Harbor then creates the private workspace computer automatically.
5. Connect a supported source. For beehiiv, open **Settings → Integrations →
   API**, copy an active API key, and paste it into **Connect beehiiv**. Harbor
   sends it directly to Fly's encrypted connector service and does not save it.
   When Kit is enabled, choose **Connect Kit** and complete Kit's hosted consent
   screen; no API key is pasted into Harbor.
6. If the source shows more than one publication, choose the newsletter to analyze.
   If more than one source is connected, choose the **Report source** in the
   schedule. Manual runs use the same selected source; **All connected sources**
   produces a combined report.
7. Confirm the workspace shows **Ready**, **Connected**, and the desired next
   report time. Choose **Run Newsletter Intelligence** for the first report.
8. Confirm the run completes and the report arrives at the configured email.
9. In ChatGPT, connect the Harbor app and sign in with the same Harbor account.

If a step fails, Harbor shows the failure in the workspace. Retrying does not
duplicate a completed run or delivery. Never send a beehiiv, Stripe, Fly, or
Harbor secret by email or chat.

Before public onboarding, Harbor's operator must configure a verified Resend
sending domain. The Resend testing sender can deliver only to the provider
account owner and is not a general customer email service.
