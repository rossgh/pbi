"""Construction-specific AI tools: each is a form that compiles into a prompt for the assistant."""

TOOLS = {
    "assistant": {
        "name": "Site Assistant",
        "icon": "💬",
        "summary": "Ask anything — codes, methods, scheduling, crew issues, supplier emails.",
        "fields": [],
    },
    "rfi": {
        "name": "RFI Writer",
        "icon": "❓",
        "summary": "Turn a field question into a clear, numbered Request for Information.",
        "fields": [
            {"name": "project", "label": "Project name / number", "type": "text"},
            {"name": "to", "label": "Addressed to (architect, engineer…)", "type": "text"},
            {"name": "location", "label": "Location / drawing / spec reference", "type": "text"},
            {"name": "issue", "label": "What's the problem or conflict?", "type": "textarea", "required": True},
            {"name": "proposal", "label": "Your suggested solution (optional)", "type": "textarea"},
            {"name": "impact", "label": "Schedule / cost impact if unanswered", "type": "text"},
        ],
    },
    "daily_report": {
        "name": "Daily Site Report",
        "icon": "📋",
        "summary": "Rough notes in, a clean daily log out — manpower, work done, delays, safety.",
        "fields": [
            {"name": "project", "label": "Project", "type": "text"},
            {"name": "date", "label": "Date", "type": "date"},
            {"name": "weather", "label": "Weather", "type": "text"},
            {"name": "crew", "label": "Crew / subs on site (headcount)", "type": "text"},
            {"name": "notes", "label": "Your rough notes for the day", "type": "textarea", "required": True},
        ],
    },
    "safety": {
        "name": "Safety Toolbox Talk & JHA",
        "icon": "🦺",
        "summary": "Job hazard analysis and a 5-minute toolbox talk for any task.",
        "fields": [
            {"name": "task", "label": "Task / activity", "type": "text", "required": True},
            {"name": "conditions", "label": "Site conditions (height, weather, confined space…)", "type": "textarea"},
            {"name": "crew_size", "label": "Crew size / experience", "type": "text"},
            {"name": "region", "label": "Jurisdiction (e.g. OSHA, HSE UK, WorkSafe)", "type": "text"},
        ],
    },
    "change_order": {
        "name": "Change Order Drafter",
        "icon": "🧾",
        "summary": "Document scope changes with justification, pricing breakdown and time impact.",
        "fields": [
            {"name": "project", "label": "Project", "type": "text"},
            {"name": "change", "label": "What changed and why?", "type": "textarea", "required": True},
            {"name": "labor", "label": "Labor (hours × rate)", "type": "text"},
            {"name": "materials", "label": "Materials / equipment costs", "type": "text"},
            {"name": "days", "label": "Schedule impact (days)", "type": "text"},
            {"name": "markup", "label": "Overhead & profit %", "type": "text"},
        ],
    },
    "delay": {
        "name": "Delay & Schedule Recovery",
        "icon": "⏱️",
        "summary": "Analyze a delay, draft the notice, and get a recovery plan.",
        "fields": [
            {"name": "project", "label": "Project", "type": "text"},
            {"name": "cause", "label": "Cause of delay", "type": "textarea", "required": True},
            {"name": "activities", "label": "Affected activities / critical path?", "type": "textarea"},
            {"name": "days", "label": "Estimated delay (days)", "type": "text"},
            {"name": "contract", "label": "Contract type / notice clause (if known)", "type": "text"},
        ],
    },
    "punch_list": {
        "name": "Punch List Organizer",
        "icon": "✅",
        "summary": "Paste walk-through notes; get a list grouped by trade, room and priority.",
        "fields": [
            {"name": "project", "label": "Project / area", "type": "text"},
            {"name": "items", "label": "Walk-through notes (one issue per line)", "type": "textarea", "required": True},
        ],
    },
    "estimate": {
        "name": "Material Estimator",
        "icon": "📐",
        "summary": "Quantity takeoff help — concrete, framing, drywall, paint, roofing.",
        "fields": [
            {"name": "scope", "label": "Describe the scope & dimensions", "type": "textarea", "required": True},
            {"name": "waste", "label": "Waste factor % (default 10)", "type": "text"},
            {"name": "prices", "label": "Known unit prices (optional)", "type": "textarea"},
        ],
    },
    "contract": {
        "name": "Contract & Spec Explainer",
        "icon": "📑",
        "summary": "Paste a clause or spec section; get plain-English meaning, risks and questions to ask.",
        "fields": [
            {"name": "text", "label": "Clause / spec text", "type": "textarea", "required": True},
            {"name": "role", "label": "You are the… (GC, sub, owner)", "type": "text"},
        ],
    },
    "email": {
        "name": "Client & Sub Communicator",
        "icon": "✉️",
        "summary": "Professional emails for tricky situations — late payment, defects, disputes.",
        "fields": [
            {"name": "recipient", "label": "Recipient (client, sub, supplier, inspector)", "type": "text"},
            {"name": "situation", "label": "Situation", "type": "textarea", "required": True},
            {"name": "tone", "label": "Tone", "type": "select", "options": ["Firm but friendly", "Formal", "Apologetic", "Urgent"]},
        ],
    },
}

TOOL_INSTRUCTIONS = {
    "rfi": "Write a formal Request for Information. Include: RFI number placeholder, date, project, to/from, "
    "subject, references, a precise question, background, the contractor's proposed solution, requested "
    "response date, and impact statement. Keep the question unambiguous and answerable.",
    "daily_report": "Write a professional daily construction report. Sections: Summary, Weather, Manpower "
    "(by trade), Work Completed, Equipment, Deliveries, Delays/Issues, Safety Observations, Visitors/"
    "Inspections, Plan for Tomorrow. Only use facts from the notes; mark unknowns as 'N/A'.",
    "safety": "Produce (1) a Job Hazard Analysis table with steps, hazards, controls (by hierarchy of "
    "controls) and required PPE, and (2) a 5-minute toolbox talk script with 3 discussion questions. "
    "Reference relevant regulations for the jurisdiction where you are confident.",
    "change_order": "Draft a change order request: description of change, reason/justification, "
    "contract reference placeholder, itemized cost breakdown with subtotal, markup and total, schedule "
    "impact, and a signature block. Show arithmetic clearly.",
    "delay": "Analyze the delay: classify it (excusable/compensable/concurrent), note critical path impact, "
    "list documentation to collect, draft a formal delay notice letter, and give a practical recovery plan.",
    "punch_list": "Organize into a punch list table: #, Location, Trade, Description, Priority (High/Med/Low), "
    "Responsible party. Group by trade, then add a short summary with counts.",
    "estimate": "Do a quantity takeoff. State assumptions, show formulas and arithmetic step by step, apply "
    "the waste factor, round up to purchasable units, and list costs if prices were given. Use the user's "
    "preferred units.",
    "contract": "Explain the clause in plain English, highlight risks and obligations for the user's role, "
    "flag unusual or one-sided terms, and list questions to raise before signing. Note that this is not legal advice.",
    "email": "Write a clear, professional email with a subject line. Be concise, factual, and propose next steps.",
}


def build_prompt(tool_key, data):
    tool = TOOLS[tool_key]
    lines = [f"Task: {tool['name']}", TOOL_INSTRUCTIONS.get(tool_key, ""), "", "Details provided:"]
    for f in tool["fields"]:
        val = (data.get(f["name"]) or "").strip()
        if val:
            lines.append(f"- {f['label']}: {val}")
    return "\n".join(lines).strip()


def missing_required(tool_key, data):
    return [f["label"] for f in TOOLS[tool_key]["fields"] if f.get("required") and not (data.get(f["name"]) or "").strip()]


def title_for(tool_key, data):
    tool = TOOLS[tool_key]
    for key in ("project", "task", "recipient", "scope", "issue", "change", "cause", "situation", "text", "items", "notes"):
        val = (data.get(key) or "").strip()
        if val:
            snippet = val.splitlines()[0][:60]
            return f"{tool['name']}: {snippet}"
    return tool["name"]
