from typing import Any

from deepagents.middleware.subagents import SubAgent


GMAIL_ZAPIER_USAGE_GUIDE = """Mandatory rules for Gmail/Zapier:

## Parameter requirements

execute_zapier_read_action and execute_zapier_write_action both have 5 REQUIRED parameters:
  app (string)         — e.g. "gmail"
  action (string)      — action key from list_enabled_zapier_actions
  instructions (string) — natural language description of the operation
  params (object)      — dict keyed by param names for the specific action
  output (string)      — what data you want from the results (e.g. "sender, subject, date, body, message_id")

You MUST include ALL 5 parameters every time you call these tools.

## Gmail action reference

Read actions (via execute_zapier_read_action):
  action="message"    — Find Email. params={"query": "gmail_search_query"}
                        Use Gmail search operators: from:, subject:, label:, in:inbox,
                        newer_than:7d, rfc822msgid:<id>, is:unread, etc.
  action="attachment" — Get Attachment by Filename. params={"message_id": "...", "attachment_filename": "..."}

Write actions (via execute_zapier_write_action):
  action="message"          — Send Email. params={"to": "...", "subject": "...", "body": "..."}
  action="delete_email"     — Delete Email. params={"message_id": "..."}
  action="archive_email"    — Archive Email. params={"message_id": "..."}
  action="draft_v2"         — Create Draft. params={"subject": "...", "body": "..."}
  action="draft_v2_reply"   — Create Draft Reply. params={"body": "...", "thread_id": "..."}
  action="reply_to_message" — Reply to Email. params={"body": "...", "thread_id": "..."}
  action="add_label"        — Add Label. params={"message_id": "...", "new_label_ids": "..."}
  action="remove_label"     — Remove Label. params={"message_id": "...", "label_ids": "..."}
  action="label"            — Create Label. params={"name": "..."}

## Rules

- Never use action="search". That action does not exist for Gmail in Zapier.
- To read a specific email by message_id, use action="message" with params={"query": "rfc822msgid:<message_id>"}
- To get the full email body, set output="full body content, sender, subject, date, all headers"
- If you don't know the exact parameters, first call list_enabled_zapier_actions with app="gmail"
- Use only exact action keys from list_enabled_zapier_actions; do not invent action keys
""".strip()


def build_gmail_subagents(zapier_tools: list[Any], model: str) -> list[SubAgent]:
    subagents: list[SubAgent] = []

    for tool in zapier_tools:
        name = tool.name if hasattr(tool, "name") else tool.__name__
        subagents.append(
            SubAgent(
                name=f"gmail_{name}",
                description=f"Agent specialized in the Gmail operation '{name}' via Zapier.",
                system_prompt=(
                    f"You are a Gmail expert agent. Your only task is to invoke the "
                    f"'{name}' tool when the orchestrator requests it. Execute it with the exact "
                    f"parameters you receive. Do not invent values or modify the request.\n\n"
                    f"{GMAIL_ZAPIER_USAGE_GUIDE}"
                ),
                model=model,
                tools=[tool],
            )
        )

    return subagents
