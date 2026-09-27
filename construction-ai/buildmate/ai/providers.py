"""LLM provider abstraction. Picks Anthropic, OpenAI or Azure OpenAI from config; falls back to demo mode."""
from flask import current_app

from .demo import demo_reply

SYSTEM_PROMPT = """You are BuildMate, an expert AI assistant for construction companies — general contractors,
subcontractors, project managers, superintendents, estimators and safety officers.
You help with RFIs, daily reports, safety (JHAs, toolbox talks), change orders, delays and schedule
recovery, punch lists, quantity takeoffs, contract/spec interpretation, and professional communication.

Guidelines:
- Be practical and field-ready: use headings, numbered steps, checklists and tables in Markdown.
- Show calculations step by step and state assumptions. Round material quantities up to purchasable units.
- Put safety first. When codes or regulations vary by jurisdiction, say so and recommend confirming locally.
- For legal or structural-engineering questions, give useful guidance but recommend review by a licensed professional.
- Never invent project facts; use clear [placeholders] for anything the user didn't provide."""


def active_provider():
    cfg = current_app.config
    choice = cfg.get("AI_PROVIDER")
    if choice:
        return choice
    if cfg.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if cfg.get("AZURE_OPENAI_API_KEY") and cfg.get("AZURE_OPENAI_ENDPOINT"):
        return "azure"
    if cfg.get("OPENAI_API_KEY"):
        return "openai"
    return "demo"


def _system_for(user):
    parts = [SYSTEM_PROMPT]
    ctx = []
    if user.company:
        ctx.append(f"Company: {user.company.name} ({user.company.industry_focus})")
        if user.company.country:
            ctx.append(f"Region: {user.company.country}")
    if user.trade:
        ctx.append(f"User's role: {user.trade}")
    ctx.append(f"Preferred units: {user.units or 'imperial'}")
    parts.append("User context:\n" + "\n".join(ctx))
    return "\n\n".join(parts)


def generate_reply(user, tool_key, history):
    """history: list of {"role": "user"|"assistant", "content": str}. Returns (text, provider_name)."""
    provider = active_provider()
    cfg = current_app.config
    system = _system_for(user)

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=cfg["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=cfg["ANTHROPIC_MODEL"],
            max_tokens=cfg["AI_MAX_TOKENS"],
            system=system,
            messages=history,
        )
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        return text, provider

    if provider in ("openai", "azure"):
        import openai

        if provider == "azure":
            client = openai.AzureOpenAI(
                api_key=cfg["AZURE_OPENAI_API_KEY"],
                azure_endpoint=cfg["AZURE_OPENAI_ENDPOINT"],
                api_version=cfg["AZURE_OPENAI_API_VERSION"],
            )
            model = cfg["AZURE_OPENAI_DEPLOYMENT"]
        else:
            client = openai.OpenAI(api_key=cfg["OPENAI_API_KEY"])
            model = cfg["OPENAI_MODEL"]
        resp = client.chat.completions.create(
            model=model,
            max_tokens=cfg["AI_MAX_TOKENS"],
            messages=[{"role": "system", "content": system}] + history,
        )
        return resp.choices[0].message.content or "", provider

    return demo_reply(user, tool_key, history), "demo"
