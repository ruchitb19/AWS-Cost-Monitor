# AWS Cost Monitor 📊

## Problem
AWS bills can surprise you. Need automated visibility into spending patterns & anomalies.

## Solution
Python + AWS Cost Explorer API → DynamoDB → HTML Dashboard

### What it does:
- ✅ Fetches last 30 days of AWS costs (daily granularity)
- ✅ Stores cost trends in DynamoDB
- ✅ Detects spending anomalies (>20% above 7-day avg)
- ✅ Visualizes trends with interactive charts
- ✅ Shows cost by service & region

## Tech Stack
- **Backend**: Python, boto3, DynamoDB
- **Frontend**: HTML5, Chart.js (zero build tools)
- **Cloud**: AWS (Cost Explorer API, DynamoDB, IAM)
- **Hosting**: GitHub Pages (static HTML)

## Quick Start

### Prerequisites
```bash
pip install boto3
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### Run
```bash
cd scripts/
python cost_analyzer.py
```

This fetches costs and generates `dashboard/data.json`

### View Dashboard
```bash
cd dashboard/
python -m http.server 8000
# Open http://localhost:8000
```

## Key Learnings
- AWS Cost Explorer API pagination
- DynamoDB query patterns & TTL
- Anomaly detection (simple statistical method)
- Data visualization best practices

## Next Steps
- Add Lambda trigger for automated daily runs
- Integrate with SNS for email alerts
- Add budget thresholds & forecasting
- Multi-account support

## Interview Talking Points
- How you detected anomalies
- Why DynamoDB over RDS
- Scaling considerations for multi-account setups
- Cost optimization strategies you'd implement