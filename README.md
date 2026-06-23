# Daily News Brief

A personal AI-powered daily newsletter. Collects fresh news from X and the web via Grok Live Search, has Claude synthesize a 15-minute reading brief, and emails it to you every morning.

## Architecture

```
GitHub Actions cron (07:00 PDT)
  -> Grok 4 Fast (X + Web live search, 5 topics in parallel)
  -> Claude Sonnet 4.5 (editorial synthesis)
  -> Resend (HTML email)
  -> Inbox
```

## Setup

### 1. Get API keys

| Service   | Where                                  | Notes                                |
|-----------|----------------------------------------|--------------------------------------|
| xAI       | https://console.x.ai/                  | Add ~$10 credit; use pay-as-you-go.  |
| Anthropic | https://console.anthropic.com/         | Standard API key.                    |
| Resend    | https://resend.com/api-keys            | Free 3,000 emails/month.             |

### 2. Resend sender setup

The fastest path: use Resend's shared dev domain. Set `EMAIL_FROM` to `onboarding@resend.dev`. Messages may land in spam — fine if `EMAIL_TO` is your own Gmail with a filter.

For clean delivery: verify your own domain on Resend and use `brief@yourdomain.com`.

### 3. Create GitHub repo and push these files

```bash
git init
git add .
git commit -m "initial commit"
gh repo create daily-news --public --source=. --push
```

### 4. Set GitHub Secrets

In `Settings → Secrets and variables → Actions → New repository secret`, add:

- `XAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `RESEND_API_KEY`
- `EMAIL_FROM` — e.g. `onboarding@resend.dev`
- `EMAIL_TO` — e.g. `you@gmail.com`

### 5. Trigger the first run

Go to `Actions` tab → `Daily News Brief` → `Run workflow`. Check the logs and your inbox.

## Cost estimate

Roughly **$5–10 / month** at one run/day:
- Grok 4 Fast search: ~$0.05/day (4 calls + X search tool fees)
- Claude Sonnet 4.5 synthesis: ~$0.15/day
- Resend / GitHub Actions: free tier

## Customization

- **Topics**: edit `TOPICS` in `news.py`.
- **Editorial style**: edit `NEWSLETTER_SYSTEM_PROMPT` in `news.py`.
- **Schedule**: edit the cron in `.github/workflows/daily-news.yml`. UTC. [crontab.guru](https://crontab.guru/).
- **Strict PST year-round**: change cron to `0 15 * * *`.
- **Add evening edition**: add a second cron line, e.g. `'0 1 * * *'` for ~5 PM PST.
