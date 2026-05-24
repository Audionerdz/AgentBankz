from typing import Any

from deepagents.middleware.subagents import SubAgent


GMAIL_ZAPIER_USAGE_GUIDE = """
Mandatory rules for Gmail/Zapier:
- Never use action="search". That action does not exist for Gmail in Zapier.
- To search or read emails, use execute_zapier_read_action with app="gmail", action="message", and params={"query": "..."}.
- To send emails, use execute_zapier_write_action with app="gmail", action="message", and params with to, subject, and body.
- To delete emails, use execute_zapier_write_action with app="gmail", action="delete_email", and params={"message_id": "..."}.
- For attachments, use execute_zapier_read_action with app="gmail", action="attachment".
- If you don't know the exact parameters, first call list_enabled_zapier_actions with app="gmail" and action set to the real key.
- Use only exact action keys returned by list_enabled_zapier_actions; do not translate names like search, send, read, or delete into invented action keys.
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
