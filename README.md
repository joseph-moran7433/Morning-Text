# Morning Text — Formation Weather & Uniform Advisory

Every morning, someone checks the weather and translates it into a uniform
call and a set of safety precautions — reactively, one day at a time. This
project automates that: it pulls a real forecast, runs it through the
Army's actual heat-category and cold-injury thresholds, and texts a
7-day-ahead advisory to your phone every night, with zero manual effort.

## Sample output

```
WX/UNIFORM
Tue: 34-61°F | IPFU+fleece/gloves | low risk
Wed: 30-58°F | IPFU+fleece/gloves | low risk
Thu: 28-55°F | IPFU+fleece/gloves | low risk
Fri: 45-72°F | IPFU+fleece/gloves | low risk
Sat: 50-78°F | IPFU+jacket | low risk
Sun: 52-91°F | IPFU+jacket | Cat 5 black
Mon: 48-75°F | IPFU+jacket | low risk

Heads up: Sun trending black — hydrate
```

Note: the uniform call is based on the **morning low** (0630 PT is the
coldest part of the day), while heat category uses the **afternoon high**
(the actual midday training risk) — see `build_daily_summaries()` in
`advisory.py` for the reasoning.

## What it's built on

- **Weather data:** [National Weather Service API](https://api.weather.gov)
  (`api.weather.gov`) — free, public, no API key required.
- **Heat category logic:** the Army Public Health Command's official
  Work/Rest & Water Consumption table (Heat Categories 1–5, WBGT-based).
  WBGT is approximated from temperature + humidity since we don't have a
  live solar-radiation reading — see the caveat in `heat_category.py`.
- **Uniform / cold injury logic:** the Army PT Uniform Weather Chart, and
  cold-injury inspection thresholds (25°F: inspect cold weather clothing,
  0°F: inspect for cold injuries).

## Project layout

```
advisory.py               # main script: fetch → compute → format → send
heat_category.py          # WBGT approximation + heat category table
uniform_chart.py          # temp → PT uniform mapping + cold risk
requirements.txt
.github/workflows/daily.yml   # runs advisory.py every night, free, no server needed
```

## Setup

### 1. Create a Gmail App Password (used to send, not your real password)
Go to https://myaccount.google.com/apppasswords, generate one, and save it
somewhere safe — you'll paste it into a GitHub secret, never into code.

### 2. Find your carrier's email-to-SMS address
- Verizon: `yournumber@vtext.com`
- AT&T: `yournumber@txt.att.net`
- T-Mobile: `yournumber@tmomail.net`
(search "[your carrier] email to text gateway" if not listed here)

### 3. Add GitHub Actions secrets
In your repo: **Settings → Secrets and variables → Actions → New repository secret**
Add three:
| Name | Value |
|---|---|
| `EMAIL_FROM` | your Gmail address |
| `EMAIL_APP_PASSWORD` | the app password from step 1 |
| `EMAIL_TO` | your carrier's gateway address from step 2 |

### 4. Push this project to your repo
```bash
cd morning-text
git init
git add .
git commit -m "Initial commit: formation weather & uniform advisory"
git branch -M main
git remote add origin https://github.com/joseph-moran7433/Morning-Text.git
git push -u origin main
```

### 5. Test it
Go to the **Actions** tab in your repo → "Daily Morning Text" → **Run workflow**
to trigger it manually and confirm the text arrives. Once that works, it'll
run automatically every night at the scheduled time with zero further effort.

## Known limitations (good talking points for the presentation)

- WBGT is approximated from temperature/humidity only — no solar radiation
  term, since that requires a physical sensor a weather API can't provide.
  A real unit would calibrate this against an actual WBGT meter.
- Uniform temperature bands are a reasonable approximation, not a
  copy of any one unit's exact SOP.
- GitHub Actions cron is UTC and doesn't auto-adjust for daylight saving.
