"""
Daily news brief generator.

Pipeline: Grok (X + Web live search) -> Claude (synthesis) -> Resend (email).
Run via GitHub Actions cron. All secrets from environment variables.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import markdown
import resend
from anthropic import Anthropic
from openai import OpenAI


# ---------- Topic queries ----------
# Each topic becomes one Grok call with X + Web live search.
TOPICS = [
    {
        "name": "AI Security",
        "query": (
            "Find the most important AI security news from the last 24 hours. "
            "Cover: model jailbreaks, prompt injection incidents, AI-related "
            "cyberattacks, vulnerability disclosures in AI products, leaked "
            "model weights, and AI safety incidents at major labs. "
            "Skip generic hype and opinion pieces. "
            "Return 3 to 5 items, each with a source URL."
        ),
    },
    {
        "name": "Silicon Valley Startups",
        "query": (
            "Find notable Silicon Valley startup news from the last 24 hours: "
            "Series A or later funding rounds, product launches, acquisitions, "
            "founder or executive moves, and notable shutdowns. "
            "Focus on AI infrastructure, AI applications, fintech, and developer tools. "
            "Return 5 to 7 items, each with a source URL and round size if applicable."
        ),
    },
    {
        "name": "Frontier AI Models",
        "query": (
            "Find updates from the last 24 hours about frontier AI models: "
            "Claude (Anthropic), Gemini (Google), ChatGPT and GPT models (OpenAI), "
            "Grok (xAI), Llama (Meta), and other major labs. "
            "Include new releases, feature launches, pricing changes, benchmark "
            "results, and notable capability demos. "
            "Return 3 to 5 items, each with a source URL."
        ),
    },
    {
        "name": "AI Markets and Investment",
        "query": (
            "Find AI-related market and investment news from the last 24 hours: "
            "stock moves of NVDA, MSFT, GOOGL, META, AMZN, AMD, TSM, ORCL on AI catalysts, "
            "major VC funding announcements, M&A in the AI sector, AI regulation, "
            "and AI capex or datacenter news. "
            "Also include Bitcoin treasury or BTC market structure news if relevant. "
            "Skip altcoin and memecoin news. "
            "Return 3 to 5 items, each with a source URL."
        ),
    },
]


# ---------- Editorial style ----------
NEWSLETTER_SYSTEM_PROMPT = """You are the editor of a daily AI and tech brief for one specific reader.

About the reader:
- Senior network engineer relocating from Tokyo to San Francisco for business development.
- Technically deep (graduate-level CS, networking specialty). Skip basic explanations; cover mechanisms, not concepts.
- Bitcoin maximalist. Ignore altcoin and memecoin pumps. Bitcoin treasury moves and BTC market structure ARE relevant.
- English learner. Use professional but simple English. Avoid idioms, slang, and literary phrasing.
- Has 15 minutes maximum to read.

Your job:
Take the raw topic briefings below and produce ONE polished newsletter in Markdown.

Rules:
1. Open with "## TL;DR" containing 3 to 5 bullets — the must-read items of the day.
2. Then 4 sections in this order: "## AI Security", "## Silicon Valley Startups", "## Frontier AI Models", "## AI Markets & Investment".
3. Per section: 3 to 5 items, ranked by importance. One item = 1 to 2 plain sentences + source link in [title](url) format.
4. Drop items that are filler, restatements of older news, or hype without substance.
5. Prefix items with "**[BREAKING]**" if they happened in the last 6 hours.
6. End with "## What to watch next" — a single sentence prediction.
7. Aim for ~15 minute reading time. Be concise.
8. No horizontal rules (---), no bold inside sentences, no emoji.
9. Output Markdown only — no preamble like "Here is your newsletter".
"""


# ---------- Pipeline steps ----------
def collect_topic(client: OpenAI, topic: dict) -> dict:
    """One Grok call with X + Web live search for one topic."""
    response = client.chat.completions.create(
        model="grok-4-fast-reasoning",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a real-time news researcher. Use the search tools to find "
                    "current information from X and the web. Return concise factual "
                    "summaries with source URLs. Never invent facts."
                ),
            },
            {"role": "user", "content": topic["query"]},
        ],
        extra_body={
            "search_parameters": {
                "mode": "on",
                "sources": [{"type": "x"}, {"type": "web"}],
                "max_search_results": 15,
                "return_citations": True,
                "from_date": datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d"),
            }
        },
        timeout=180,
    )
    msg = response.choices[0].message
    # Citations live on the response object (xAI extension)
    citations = getattr(response, "citations", None) or []
    return {
        "name": topic["name"],
        "content": msg.content or "",
        "citations": citations,
    }


def synthesize_newsletter(client: Anthropic, topic_results: list) -> str:
    """Single Claude call: take 4 topic dumps, output a finished newsletter."""
    today_pst = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%A, %B %d, %Y")
    parts = [f"Today: {today_pst} (San Francisco time)\n\nRaw topic briefings:\n"]
    for r in topic_results:
        parts.append(f"\n=== {r['name']} ===\n{r['content']}")
        if r["citations"]:
            parts.append("\nCitations:\n" + "\n".join(r["citations"]))
    parts.append("\n\nNow produce the newsletter following the rules in the system prompt.")
    user_content = "\n".join(parts)

    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        system=NEWSLETTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return msg.content[0].text


def md_to_email_html(md_content: str) -> str:
    """Wrap Markdown -> HTML output in an email-friendly shell with inline CSS."""
    body_html = markdown.markdown(md_content, extensions=["extra", "sane_lists"])
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;max-width:680px;margin:24px auto;padding:0 16px;color:#222;line-height:1.6;font-size:15px}}
h1,h2,h3{{line-height:1.3}}
h1{{font-size:20px;border-bottom:1px solid #eee;padding-bottom:8px}}
h2{{font-size:17px;margin-top:32px;border-bottom:1px solid #f0f0f0;padding-bottom:4px}}
h3{{font-size:15px}}
a{{color:#0066cc;text-decoration:none}}
a:hover{{text-decoration:underline}}
code{{background:#f4f4f4;padding:2px 5px;border-radius:3px;font-size:90%}}
ul,ol{{padding-left:24px}}
li{{margin-bottom:6px}}
.footer{{margin-top:40px;padding-top:16px;border-top:1px solid #eee;color:#999;font-size:12px}}
</style></head><body>
{body_html}
<div class="footer">Generated automatically. Sources via Grok Live Search (X + Web).</div>
</body></html>"""


def send_email(html: str):
    resend.api_key = os.environ["RESEND_API_KEY"]
    today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    resend.Emails.send(
        {
            "from": os.environ["EMAIL_FROM"],
            "to": [os.environ["EMAIL_TO"]],
            "subject": f"Daily Brief — {today}",
            "html": html,
        }
    )


def main():
    grok = OpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
    )
    claude = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("Collecting topics from Grok...")
    results = []
    for topic in TOPICS:
        print(f"  - {topic['name']}")
        results.append(collect_topic(grok, topic))

    print("Synthesizing newsletter with Claude...")
    md_content = synthesize_newsletter(claude, results)

    print("Sending email via Resend...")
    send_email(md_to_email_html(md_content))

    print("Done.")


if __name__ == "__main__":
    main()
