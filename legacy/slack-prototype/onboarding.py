"""Onboarding wizard — triggered after OAuth install.

DMs the installing user with a 3-step flow:
1. What data sources? (buttons)
2. Paste the key / connect the account
3. Which channel should the morning data post to?

Then saves the config per workspace and confirms.
"""

WELCOME_MSG = {
    "text": "Welcome to Harbor — your data runner.",
    "blocks": [
        {"type": "header", "text": {"type": "plain_text", "text": "Harbor is installed 🚢"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "Three quick things and your data starts arriving tomorrow morning.\n\n"
                    "*Step 1 of 3 — Where does your data live?*"}},
        {"type": "actions", "block_id": "source_select", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "beehiiv"},
             "action_id": "source_beehiiv", "value": "beehiiv"},
            {"type": "button", "text": {"type": "plain_text", "text": "Mailchimp"},
             "action_id": "source_mailchimp", "value": "mailchimp"},
            {"type": "button", "text": {"type": "plain_text", "text": "ConvertKit"},
             "action_id": "source_convertkit", "value": "convertkit"},
            {"type": "button", "text": {"type": "plain_text", "text": "Other / skip"},
             "action_id": "source_other", "value": "other"},
        ]}
    ]
}

STEP2_KEY = {
    "text": "Paste your API key",
    "blocks": [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "*Step 2 of 3 — Connect your account*\n\n"
                    "The v0.8 alpha does not accept production API keys in Slack. "
                    "Use the secure connection flow when it is enabled."}},
        {"type": "input", "block_id": "api_key_input",
         "element": {"type": "plain_text_input", "action_id": "api_key_value",
                     "placeholder": {"type": "plain_text", "text": "Paste key here"}},
         "label": {"type": "plain_text", "text": "Development only — do not paste a production key"}},
        {"type": "input", "block_id": "pub_id_input",
         "element": {"type": "plain_text_input", "action_id": "pub_id_value",
                     "placeholder": {"type": "plain_text", "text": "pub_xxxx (from your ESP settings)"}},
         "label": {"type": "plain_text", "text": "Publication ID"}},
    ]
}

STEP3_CHANNEL = {
    "text": "Where should the data land?",
    "blocks": [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "*Step 3 of 3 — Where should the morning data post?*\n\n"
                    "Pick a channel. Harbor will post there every morning at 6am.\n"
                    "Invite @Harbor to the channel first."}},
        {"type": "input", "block_id": "channel_input",
         "element": {"type": "channels_select", "action_id": "channel_value",
                     "placeholder": {"type": "plain_text", "text": "Pick a channel"}},
         "label": {"type": "plain_text", "text": "Channel"}},
    ]
}

DONE_MSG = {
    "text": "Harbor is ready.",
    "blocks": [
        {"type": "header", "text": {"type": "plain_text", "text": "You're set 🚢"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "Harbor will pull your data every morning and post it to your channel at 6am.\n\n"
                    "Try it now: `/harbor pull email-performance`\n\n"
                    "— Harbor"}},
    ]
}
