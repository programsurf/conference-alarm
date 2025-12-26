# Conference Deadline Alert Bot

A GitHub Actions-powered bot that automatically fetches academic conference deadlines and sends daily notifications to Slack.

## Features

- Fetches conference deadline data from [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines)
- Converts all deadlines to KST (Korean Standard Time)
- Sends formatted notifications to Slack via webhook
- Runs daily at 9:00 AM KST via GitHub Actions
- Alternating notification modes:
  - **Odd days**: All conferences grouped by category
  - **Even days**: Target conferences only (focused view)

## Tracked Conferences

### AI/Vision
- CVPR, ICCV, ECCV, AAAI, IJCAI, ICML, NeurIPS, ICLR

### Security
- IEEE S&P, CCS, USENIX Security, NDSS, EUROCRYPT, CRYPTO, ASIACRYPT, CHES, ESORICS, DSN

### Network
- SIGCOMM, INFOCOM, NSDI, SIGMETRICS

### Data
- ICDM, BigData

## Target Conferences (Even-day Focus)

- CHES / TCHES
- EUROCRYPT
- ASIACRYPT
- USENIX Security
- IEEE S&P

## Urgency Indicators

| Emoji | Status | Days Remaining |
|-------|--------|----------------|
| :red_circle: | Urgent | ≤ 30 days |
| :yellow_circle: | Upcoming | 31-180 days |
| :green_circle: | Plenty of time | > 180 days |

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/alarm-bot.git
cd alarm-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Slack Webhook

1. Create a Slack Incoming Webhook in your workspace
2. Add the webhook URL as a GitHub repository secret:
   - Go to **Settings** → **Secrets and variables** → **Actions**
   - Create a new secret named `SLACK_WEBHOOK_URL`

### 4. Enable GitHub Actions

The workflow runs automatically once configured. You can also trigger it manually:
- Go to **Actions** → **Conference Deadline Alert** → **Run workflow**

## Local Testing

```bash
export SLACK_WEBHOOK_URL="your-webhook-url"
python conference_alert.py
```

## Requirements

- Python 3.11+
- requests
- beautifulsoup4
- PyYAML

## How It Works

1. Fetches YAML files from the ccfddl GitHub repository for each tracked conference
2. Parses deadline information including abstract and paper submission dates
3. Converts all times from their original timezone to KST
4. Filters conferences to show only current and next year deadlines
5. Formats and sends a Slack message with grouped deadline information

## License

MIT
