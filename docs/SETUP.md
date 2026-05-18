# Quick Start Guide — AWS Cost Monitor

## Prerequisites
- AWS Account with billing access
- Python 3.8+
- Git

---

## Step-by-Step Setup (15 minutes)

### 1️⃣ Create AWS Credentials

**In AWS Console:**
1. Go to **IAM** → **Users** → **Create user**
   - Name: `cost-monitor-user`
   - No console access needed (programmatic only)

2. Attach policy: Search for `"AWSBillingReadOnlyAccess"`
   - This gives read-only access to Cost Explorer API

3. Create **Access Key**
   - Copy the `Access Key ID` and `Secret Access Key`
   - Store them safely (you'll only see the secret once!)

### 2️⃣ Create DynamoDB Table

```bash
# Using AWS CLI
aws dynamodb create-table \
  --table-name aws_cost_metrics \
  --attribute-definitions \
    AttributeName=date,AttributeType=S \
    AttributeName=service,AttributeType=S \
  --key-schema \
    AttributeName=date,KeyType=HASH \
    AttributeName=service,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

**Or via Console:**
1. DynamoDB → **Create table**
2. **Table name:** `aws_cost_metrics`
3. **Partition key:** `date` (String)
4. **Sort key:** `service` (String)
5. **Billing mode:** Pay-per-request
6. Click **Create**

### 3️⃣ Enable DynamoDB TTL (auto-cleanup)

```bash
aws dynamodb update-time-to-live \
  --table-name aws_cost_metrics \
  --time-to-live-specification AttributeName=ttl,Enabled=true \
  --region us-east-1
```

**Or via Console:**
1. DynamoDB → `aws_cost_metrics` table
2. **TTL** tab → **Manage TTL**
3. **Attribute name:** `ttl`
4. **Enable**

### 4️⃣ Clone & Setup Repo

```bash
# Clone your repo (or create fresh)
git clone https://github.com/yourusername/aws-cost-monitor.git
cd aws-cost-monitor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 5️⃣ Configure AWS Credentials

```bash
# Option A: AWS CLI (easiest)
aws configure
# Enter:
#   AWS Access Key ID: <paste from step 1>
#   AWS Secret Access Key: <paste from step 1>
#   Default region: us-east-1
#   Default output: json

# Option B: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1

# Option C: ~/.aws/credentials (advanced)
# Not recommended for this project (credential security risk)
```

### 6️⃣ Test the Script

```bash
# From repo root
python scripts/cost_analyzer.py
```

**Expected output:**
```
============================================================
AWS COST MONITOR - Data Collection Pipeline
============================================================
📊 Fetching costs from 2025-04-17 to 2025-05-17...
✅ Successfully fetched costs for 30 days

💾 Storing costs to DynamoDB...

✓ 2025-04-17: $  45.32 (7d avg: $  50.00, deviation:  -9.4%)
✓ 2025-04-18: $  48.90 (7d avg: $  50.00, deviation:  -2.2%)
🚨 ANOMALY! 2025-04-19: $  75.50 (7d avg: $  50.00, deviation: +51.0%)
...

📤 Exporting data to dashboard/data.json...
✅ Data exported successfully!
   📊 Days recorded: 30
   💰 Total (30d): $1,425.50
   📈 Daily avg: $47.52
   🚨 Anomalies detected: 2

============================================================
✅ Pipeline complete!
============================================================
```

### 7️⃣ View Dashboard Locally

```bash
# Navigate to dashboard folder
cd dashboard

# Start simple HTTP server
python -m http.server 8000

# Open browser
# http://localhost:8000
```

You should see:
- 📊 Line chart of daily costs
- 3 metric cards (Total, Daily Avg, Anomalies)
- Interactive chart that updates as you scroll

---

## 🚀 Automating Daily Runs (Optional)

### Option A: Cron Job (Mac/Linux)

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * cd /path/to/aws-cost-monitor && python scripts/cost_analyzer.py

# Verify
crontab -l
```

### Option B: AWS Lambda (Serverless)

```bash
# Create Lambda function
aws lambda create-function \
  --function-name cost-monitor \
  --runtime python3.9 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-role \
  --handler cost_analyzer.main \
  --zip-file fileb://deployment.zip

# Add CloudWatch trigger for daily execution
# (Advanced - requires more AWS IAM setup)
```

### Option C: GitHub Actions

Create `.github/workflows/daily-cost-sync.yml`:

```yaml
name: Daily Cost Sync

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: python scripts/cost_analyzer.py
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      - uses: actions/upload-artifact@v2
        with:
          name: dashboard-data
          path: dashboard/data.json
```

---

## 🧪 Test Without AWS (Local Mock Data)

If you don't have AWS credentials yet or want to test the dashboard:

```bash
# Generate mock cost data
python scripts/local_data_generator.py

# This creates:
# - mock_cost_data.json (realistic cost data)
# - dashboard/data.json (formatted for dashboard)

# View dashboard with mock data
cd dashboard
python -m http.server 8000
# http://localhost:8000
```

Perfect for testing before connecting to real AWS!

---

## ❌ Troubleshooting

### Error: "Invalid AWS credentials"
```
❌ Error fetching costs: An error occurred (UnrecognizedClientException) ...
```

**Solution:**
```bash
# Verify credentials are set
aws sts get-caller-identity

# If it fails, reconfigure
aws configure

# If still broken, check:
# - Access Key ID is correct
# - Secret Access Key is correct
# - User has AWSBillingReadOnlyAccess policy
# - Region is us-east-1 (Cost Explorer only available there)
```

### Error: "DynamoDB table not found"
```
❌ Error storing costs: Table aws_cost_metrics not found
```

**Solution:**
```bash
# Verify table exists
aws dynamodb describe-table --table-name aws_cost_metrics

# If missing, create it (see step 2 above)
aws dynamodb create-table ...
```

### Error: "No cost data available"
```
⚠️  No data found in DynamoDB
```

**Solution:**
- AWS takes 24 hours to generate cost data for a new account
- If you have a new account, run the script tomorrow
- Use mock data generator to test in the meantime

### Dashboard doesn't show chart
```
✅ Data exported successfully!
# But the chart is blank when you open the dashboard
```

**Solution:**
```bash
# Check that data.json was created
cat dashboard/data.json

# If it's empty or malformed:
# 1. Run local_data_generator.py to create mock data
# 2. Check browser console (F12) for JavaScript errors
# 3. Verify Chart.js CDN link in index.html
```

### Script takes too long (>60 seconds)
```bash
# Cost Explorer API can be slow. Optimize:
# 1. Reduce days parameter: fetch_aws_costs(days=7) instead of 30
# 2. Add IndexError handling for large responses
# 3. Implement request batching
```

---

## 📋 Checklist Before Submitting

- [ ] AWS credentials configured
- [ ] DynamoDB table created
- [ ] Script runs without errors: `python scripts/cost_analyzer.py`
- [ ] `dashboard/data.json` is generated
- [ ] Dashboard loads locally: `http://localhost:8000`
- [ ] Chart displays cost trend
- [ ] Anomalies are flagged
- [ ] README.md is complete & clear
- [ ] Repo is pushed to GitHub
- [ ] GitHub Pages enabled (if using static hosting)

---

## 💡 Pro Tips

1. **Run daily:** Set up cron or GitHub Actions to fetch costs every day. More historical data = better anomaly detection.

2. **Monitor the monitor:** Add CloudWatch alarms for when your script fails.

3. **Share results:** Schedule an email digest of the dashboard to your team every Friday.

4. **Cost optimization:** Once you have data, analyze which services drive most cost. EC2? RDS? Lambda?

5. **Interview story:** "I built this to save money. Found that our RDS was misconfigured and costing 3x more than needed. Fixed it, saved $1000/month."

---

## Next Steps

1. ✅ Get credentials working
2. ✅ Run script successfully once
3. ✅ View dashboard locally
4. ✅ Push to GitHub
5. ✅ Write LinkedIn post
6. ✅ Update resume
7. ✅ Practice explaining in interviews