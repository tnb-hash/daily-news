"""
Daily news brief generator.

Pipeline: Grok (X + Web Agent Tools search) -> Claude (synthesis) -> Resend (email).
All editorial content (topics, prompts) lives in prompts.py — edit that, not this.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import markdown
import resend
from anthropic import Anthropic
from openai import OpenAI

from prompts import TOPICS, GROK_SYSTEM_PROMPT, NEWSLETTER_SYSTEM_PROMPT


def collect_topic(client: OpenAI, topic: dict) -> dict:
    """One Grok call using the Agent Tools API (x_search + web_search)."""
    today_iso = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d")
    user_input = (
        f"Today's date is {today_iso}. Only return news from the past 24 hours.\n\n"
        + topic["query"]
    )
    response = client.responses.create(
        model="grok-4.3",
        input=[
            {"role": "system", "content": GROK_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        tools=[
            {"type": "x_search"},
            {"type": "web_search"},
        ],
        timeout=180,
    )
    return {
        "name": topic["name"],
        "content": response.output_text or "",
    }


def synthesize_newsletter(client: Anthropic, topic_results: list) -> str:
    """Single Claude call: take 4 topic dumps, output a finished newsletter."""
    today_pst = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d (%A)")
    parts = [f"本日: {today_pst} サンフランシスコ時刻\n\n以下、生のトピックブリーフィング:\n"]
    for r in topic_results:
        parts.append(f"\n=== {r['name']} ===\n{r['content']}")
    parts.append("\n\nシステムプロンプトのルールに従って、日本語ニュースレターを生成してください。")
    user_content = "\n".join(parts)

    msg = client.messages.create(
        model="claude-sonnet-4-6",
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
body{{font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;max-width:680px;margin:24px auto;padding:0 16px;color:#222;line-height:1.7;font-size:15px}}
h1,h2,h3{{line-height:1.4}}
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
<div class="footer">自動生成 — Grok Live Search (X + Web) より収集、Claude にて編集。</div>
</body></html>"""


def send_email(html: str):
    resend.api_key = os.environ["RESEND_API_KEY"]
    today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    resend.Emails.send(
        {
            "from": os.environ["EMAIL_FROM"],
            "to": [os.environ["EMAIL_TO"]],
            "subject": f"AIブリーフ — {today}",
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
