"""Offline 'demo mode' replies so the app is useful before an AI key is configured.

These are rule-based templates — not an LLM — but they produce real, usable drafts from the user's input.
"""
import re
from datetime import date

from .tools import TOOLS

BANNER = (
    "> **Demo mode** — no AI provider is configured, so this draft was generated from built-in templates. "
    "Set `ANTHROPIC_API_KEY` (or an OpenAI / Azure OpenAI key) for full AI answers.\n\n"
)


def _fields_from_prompt(tool_key, prompt):
    labels = {f["label"]: f["name"] for f in TOOLS[tool_key]["fields"]}
    data, current = {}, None
    for line in prompt.splitlines():
        m = re.match(r"^- (.+?): (.*)$", line)
        if m and m.group(1) in labels:
            current = labels[m.group(1)]
            data[current] = m.group(2)
        elif current and line and not line.startswith("- "):
            data[current] += "\n" + line
    return data


def _v(data, key, placeholder):
    return (data.get(key) or "").strip() or f"[{placeholder}]"


def _numbers(text):
    return [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.?\d*", text or "")]


# --- per-tool generators ------------------------------------------------------

def _rfi(d, user):
    return f"""## Request for Information — RFI #[000]

| | |
|---|---|
| **Project** | {_v(d, 'project', 'Project name / no.')} |
| **Date** | {date.today():%B %d, %Y} |
| **To** | {_v(d, 'to', 'Architect / Engineer of Record')} |
| **From** | {user.display_name}{', ' + user.company.name if user.company else ''} |
| **Reference** | {_v(d, 'location', 'Drawing / spec section / grid line')} |
| **Response needed by** | [Date — allow 5–7 working days] |

### Question
{_v(d, 'issue', 'Describe the conflict')}

Please clarify the intended design so work can proceed as specified.

### Contractor's proposed solution
{_v(d, 'proposal', 'None proposed — awaiting design direction')}

### Impact if unanswered
{_v(d, 'impact', 'Potential schedule and cost impact to be assessed')}

### Attachments
- [Marked-up drawing / photo]

Sign-off: `______________________`
"""


def _daily(d, user):
    notes = [n.strip("-• ").strip() for n in (d.get("notes") or "").splitlines() if n.strip()]
    issues = [n for n in notes if re.search(r"delay|late|wait|rain|problem|issue|short|broke|fail|stopp", n, re.I)]
    safety = [n for n in notes if re.search(r"safety|ppe|incident|near miss|injur|hazard|toolbox", n, re.I)]
    work = [n for n in notes if n not in issues and n not in safety]
    bullets = lambda xs: "\n".join(f"- {x}" for x in xs) or "- N/A"  # noqa: E731
    return f"""## Daily Construction Report

**Project:** {_v(d, 'project', 'Project')}  ·  **Date:** {_v(d, 'date', date.today().isoformat())}  ·  **Prepared by:** {user.display_name}

### Weather
{_v(d, 'weather', 'N/A')}

### Manpower
{_v(d, 'crew', 'N/A')}

### Work completed
{bullets(work)}

### Delays / issues
{bullets(issues)}

### Safety observations
{bullets(safety)}

### Plan for tomorrow
- [Next activities]
"""


HAZARDS = [
    (r"height|roof|ladder|scaffold|elevat|lift|mewp", "Falls from height", "Guardrails / fall-arrest harness tied off to rated anchor; inspect ladders & scaffold tags; 3 points of contact"),
    (r"excavat|trench|dig", "Cave-in / struck by spoil", "Shoring, sloping or trench box > 5 ft (1.5 m); spoil 2 ft back; locate utilities before digging; competent person inspection daily"),
    (r"electri|wiring|panel|power", "Electric shock / arc flash", "Lockout/tagout, verify zero energy, GFCI on temporary power, qualified persons only"),
    (r"concrete|pour|slab|cement", "Chemical burns, strains, pump line whip", "Alkali-resistant gloves & boots, eye protection, team lifting, clear hose area"),
    (r"weld|cut|grind|torch|hot work", "Fire, burns, fumes, eye injury", "Hot-work permit, fire watch 30+ min after, extinguisher at hand, welding screen, ventilation"),
    (r"crane|rigging|hoist|lift", "Struck by / dropped load", "Lift plan, certified rigger & signaler, inspect slings, exclusion zone under load"),
    (r"confined|tank|manhole|vault", "Oxygen deficiency / toxic atmosphere", "Permit-required entry, gas testing, ventilation, attendant & rescue plan"),
    (r"demoli|asbestos|lead|silica|saw", "Dust / silica / hazardous materials", "Survey for asbestos/lead first, wet cutting or vacuum extraction, respirators per exposure plan"),
]


def _safety(d, user):
    text = " ".join(d.values())
    found = [h for h in HAZARDS if re.search(h[0], text, re.I)]
    found += [(None, "Slips, trips & falls on same level", "Housekeeping, cord management, clear walkways, adequate lighting"),
              (None, "Manual handling strains", "Mechanical aids, team lifts, correct lifting technique")]
    rows = "\n".join(f"| {i} | {h[1]} | {h[2]} |" for i, h in enumerate(found, 1))
    task = _v(d, "task", "Task")
    return f"""## Job Hazard Analysis — {task}

**Conditions:** {_v(d, 'conditions', 'Normal site conditions')}  ·  **Crew:** {_v(d, 'crew_size', 'N/A')}  ·  **Jurisdiction:** {_v(d, 'region', 'Confirm local regulations')}

| # | Hazard | Controls (elimination → engineering → admin → PPE) |
|---|---|---|
{rows}


**Minimum PPE:** hard hat, safety glasses, hi-vis vest, safety-toe boots, gloves suited to the task.

## 5-Minute Toolbox Talk: {task}

1. **Why it matters** — Every hazard above has caused serious injuries on sites like ours. Today we're doing *{task}*.
2. **What we'll do** — Walk through the controls in the table. Nobody starts until their area is set up correctly.
3. **Stop-work authority** — Anyone can stop the job if something looks wrong. No blame.
4. **Emergency** — Muster point: [location]. First aider: [name]. Nearest hospital: [address].

**Discussion questions**

- What's changed on site since yesterday that could affect this task?
- Which step worries you most, and why?
- Where is the nearest extinguisher / first-aid kit / eyewash?

Attendance sign-off: `______________________`
"""


def _change_order(d, user):
    labor_nums = _numbers(d.get("labor"))
    labor = labor_nums[0] * labor_nums[1] if len(labor_nums) >= 2 else (labor_nums[0] if labor_nums else 0.0)
    materials = sum(_numbers(d.get("materials")))
    markup_pct = (_numbers(d.get("markup")) or [15.0])[0]
    subtotal = labor + materials
    markup = subtotal * markup_pct / 100
    total = subtotal + markup
    labor_line = f"{labor_nums[0]:g} h × ${labor_nums[1]:,.2f}" if len(labor_nums) >= 2 else "lump sum"
    return f"""## Change Order Request — CO #[000]

**Project:** {_v(d, 'project', 'Project')}  ·  **Date:** {date.today():%B %d, %Y}  ·  **Submitted by:** {user.display_name}

### Description of change
{_v(d, 'change', 'Describe change')}

### Reason / justification
[Owner request / design change / unforeseen condition — reference RFI or directive no.]

### Cost breakdown
| Item | Basis | Amount |
|---|---|---|
| Labor | {labor_line} | ${labor:,.2f} |
| Materials & equipment | {_v(d, 'materials', 'itemize')} | ${materials:,.2f} |
| **Subtotal** | | **${subtotal:,.2f}** |
| Overhead & profit | {markup_pct:g}% | ${markup:,.2f} |
| **Total requested** | | **${total:,.2f}** |

### Schedule impact
{_v(d, 'days', '0')} calendar day(s) extension requested.

### Approval
| Owner | Contractor |
|---|---|
| Signature / date: | Signature / date: |
"""


def _delay(d, user):
    return f"""## Delay Analysis — {_v(d, 'project', 'Project')}

**Cause:** {_v(d, 'cause', 'Cause')}
**Affected activities:** {_v(d, 'activities', 'Identify from schedule')}
**Estimated delay:** {_v(d, 'days', 'TBD')} day(s)

### Classification (confirm against your contract: {_v(d, 'contract', 'contract type')})
- **Excusable & compensable** — owner-caused (design changes, late approvals, site access).
- **Excusable, non-compensable** — neither party's fault (unusually severe weather, force majeure).
- **Non-excusable** — contractor-caused; recovery at your cost.

### Documentation to collect now
- Dated photos, daily reports, weather records, correspondence, RFIs, delivery tickets
- Schedule update showing as-planned vs. impacted critical path

### Draft delay notice
> Dear [Owner/Architect],
> In accordance with [clause no.], we hereby give notice of a delay to the Works caused by: {_v(d, 'cause', 'cause')}.
> The event was first identified on [date] and is currently expected to affect the completion date by approximately {_v(d, 'days', '[x]')} day(s).
> We are taking all reasonable steps to mitigate and will submit a detailed time impact analysis within [x] days.
> Regards, {user.display_name}

### Recovery options
1. Re-sequence non-dependent work to run in parallel
2. Add a second shift or weekend work on critical activities
3. Increase crew size on critical path; pre-fabricate off-site where possible
4. Expedite long-lead materials; confirm alternates with the design team
"""


TRADE_WORDS = [
    ("Painting", r"paint|touch.?up|scuff|stain"), ("Drywall", r"drywall|gyp|nail pop|tape|patch"),
    ("Electrical", r"outlet|switch|light|electric|breaker|cover plate"), ("Plumbing", r"leak|faucet|toilet|drain|plumb|sink"),
    ("HVAC", r"hvac|vent|diffuser|thermostat|duct"), ("Doors & Hardware", r"door|hinge|lock|handle|strike"),
    ("Flooring", r"floor|tile|carpet|grout|baseboard"), ("Carpentry", r"trim|cabinet|casing|shelf|millwork"),
    ("Glazing", r"window|glass|glazing"),
]


def _punch(d, user):
    items = [l.strip("-•*0123456789.) ").strip() for l in (d.get("items") or "").splitlines() if l.strip()]
    rows = []
    for i, it in enumerate(items, 1):
        trade = next((t for t, rx in TRADE_WORDS if re.search(rx, it, re.I)), "General")
        prio = "High" if re.search(r"leak|safety|hazard|broken|not working|exposed|missing", it, re.I) else "Medium" if re.search(r"crack|damage|loose", it, re.I) else "Low"
        rows.append((trade, i, it, prio))
    rows.sort(key=lambda r: (r[0], {"High": 0, "Medium": 1, "Low": 2}[r[3]]))
    table = "\n".join(f"| {r[1]} | {r[0]} | {r[2]} | {r[3]} | [Sub] | ☐ |" for r in rows)
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    return f"""## Punch List — {_v(d, 'project', 'Project')}

| # | Trade | Item | Priority | Responsible | Done |
|---|---|---|---|---|---|
{table}

**Summary:** {len(rows)} items — {summary or 'none'}.
"""


def _estimate(d, user):
    metric = user.units == "metric"
    return f"""## Quantity Takeoff Worksheet

**Scope:** {_v(d, 'scope', 'Scope')}
**Waste factor:** {_v(d, 'waste', '10')}%

### Formulas
| Material | Formula |
|---|---|
| Concrete | L × W × T → {'m³' if metric else 'ft³ ÷ 27 = yd³'}, then × (1 + waste) |
| Drywall | wall area ÷ sheet area ({'2.88 m²' if metric else '32 ft² for 4×8'}), subtract large openings |
| Paint | area × coats ÷ coverage ({'≈10 m²/L' if metric else '≈350 ft²/gal'}) |
| Studs | wall length ({'mm' if metric else 'in'}) ÷ spacing + 1, + 2 per corner, + 2–3 per opening |
| Blocks | wall area ÷ block face ({'0.08 m²' if metric else '0.89 ft² for 8×16'}) |

Open the **Calculators** page for instant, exact numbers — or configure an AI key and I'll run the full takeoff from your description.
"""


RISK_TERMS = [
    (r"pay[- ]if[- ]paid", "Pay-if-paid", "You only get paid if the owner pays the GC — shifts owner-insolvency risk to you. Push for pay-when-paid with a time limit."),
    (r"pay[- ]when[- ]paid", "Pay-when-paid", "Timing of payment is tied to owner payment. Ask for a maximum number of days."),
    (r"indemnif|hold harmless", "Indemnification", "Check whether you indemnify for the other party's own negligence (broad form). Limit to your proportional fault."),
    (r"liquidated damages|\bLDs?\b", "Liquidated damages", "Fixed daily amount for late completion. Verify rate, cap, and that excusable delays extend the date."),
    (r"no damages for delay", "No damages for delay", "You get time but not money for owner-caused delays. Negotiate exceptions for active interference."),
    (r"termination for convenience", "Termination for convenience", "Other party can end the contract anytime. Ensure you recover costs + profit on work done and demobilization."),
    (r"retain|retention", "Retainage", "Portion of each payment withheld. Check %, reduction at 50% complete, and release timing."),
    (r"waive|waiver", "Waiver", "Watch for lien or claim waivers — only waive for amounts actually received."),
    (r"consequential", "Consequential damages", "Seek a mutual waiver of consequential damages."),
    (r"notice.{0,40}(days|hours)", "Notice deadline", "Missing a notice deadline can forfeit claims. Calendar it and send notices in writing."),
    (r"warrant", "Warranty", "Confirm duration, start date (substantial completion?), and exclusions."),
]


def _contract(d, user):
    text = d.get("text") or ""
    found = [(name, why) for rx, name, why in RISK_TERMS if re.search(rx, text, re.I)]
    risks = "\n".join(f"- **{n}** — {w}" for n, w in found) or "- No common high-risk terms detected by the keyword scan. Read carefully for scope, schedule and payment terms."
    return f"""## Clause Review (you are: {_v(d, 'role', 'party')})

### Flagged terms
{risks}

### Questions to raise before signing
1. What exactly triggers each obligation, and what's the deadline?
2. Is liability capped? Is it mutual?
3. How are changes, delays and disputes handled — and who pays?

_This is general information, not legal advice. Have a construction attorney review significant contracts._
"""


def _email(d, user):
    return f"""**Subject:** {_v(d, 'situation', 'Subject').splitlines()[0][:70]}

Hi {_v(d, 'recipient', 'Name')},

I'm writing regarding {_v(d, 'situation', 'the situation').rstrip('.')}.

To keep the project on track, could we [proposed next step] by [date]? I'm happy to jump on a call or meet on site to work through the details.

Thanks for your help,
{user.display_name}
{user.job_title or ''}{' · ' + user.company.name if user.company else ''}
{user.phone or ''}

_Tone requested: {_v(d, 'tone', 'Firm but friendly')}_
"""


FAQ = [
    (r"concrete|slab|footing", "**Concrete:** volume = L × W × T. In imperial, ft³ ÷ 27 = yd³. Add 5–10% waste. Typical slab-on-grade is 4 in (100 mm); garage 5–6 in. Cure ≥ 7 days moist; full strength at 28 days."),
    (r"rfi", "**RFIs:** keep one question per RFI, cite drawing/spec references, propose a solution, and state the response date and impact. Try the **RFI Writer** tool."),
    (r"safety|osha|ppe|hazard|fall", "**Safety:** fall protection is required at 6 ft (1.8 m) in US construction. Run a JHA before non-routine work and a daily toolbox talk. Try the **Safety Toolbox Talk & JHA** tool."),
    (r"delay|behind|schedule", "**Schedule slip:** give written notice fast (check your contract's notice clause), document everything, and focus recovery on the critical path. Try **Delay & Schedule Recovery**."),
    (r"change order|extra work|scope", "**Change orders:** never proceed on extra work without written direction. Price labor, material, equipment, markup and time. Try **Change Order Drafter**."),
    (r"pay|invoice|retain", "**Payment issues:** send a polite written reminder citing the contract payment terms, then a formal notice. Know your lien deadlines. Try **Client & Sub Communicator**."),
]


def _assistant(history, user):
    q = history[-1]["content"] if history else ""
    hits = [a for rx, a in FAQ if re.search(rx, q, re.I)]
    body = "\n\n".join(hits) if hits else (
        "I can help with RFIs, daily reports, safety JHAs & toolbox talks, change orders, delay notices, "
        "punch lists, material takeoffs, contract clauses and professional emails. Pick a tool from the "
        "**AI Tools** menu, or ask about concrete, safety, delays, change orders or payment."
    )
    return f"Thanks, {user.display_name.split()[0]}. Here's what I can tell you in demo mode:\n\n{body}"


GENERATORS = {
    "rfi": _rfi, "daily_report": _daily, "safety": _safety, "change_order": _change_order, "delay": _delay,
    "punch_list": _punch, "estimate": _estimate, "contract": _contract, "email": _email,
}


def demo_reply(user, tool_key, history):
    user_turns = [m for m in history if m["role"] == "user"]
    if tool_key in GENERATORS and len(user_turns) == 1:
        data = _fields_from_prompt(tool_key, user_turns[0]["content"])
        return BANNER + GENERATORS[tool_key](data, user)
    return BANNER + _assistant(history, user)
