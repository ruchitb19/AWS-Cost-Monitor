# Anomaly Detection Logic — Deep Dive

## The Problem
AWS bills can spike unexpectedly due to:
- Runaway EC2 instances
- Misconfigured DynamoDB autoscaling
- Unoptimized Lambda concurrency
- Forgotten databases

We need to **automatically flag suspicious spending patterns**.

---

## The Algorithm

### Core Logic
```
IF today's cost > (7-day average × 1.2) THEN flag as anomaly
```

**In English:**
- Calculate the average daily cost for the last 7 days
- Multiply by 1.2 (20% threshold)
- If today exceeds this, it's anomalous

### Example Walkthrough

**Scenario:** Last 7 days of costs
```
Day 1: $50
Day 2: $52
Day 3: $48
Day 4: $51
Day 5: $49
Day 6: $53
Day 7: $50
───────────
Average: $50.57
```

**Today (Day 8): $75**

Calculation:
```
Threshold = $50.57 × 1.2 = $60.68
Today's cost = $75

Is $75 > $60.68?  YES ✓
→ ANOMALY DETECTED 🚨
Deviation: ((75 - 50.57) / 50.57) × 100 = +48.4%
```

---

## Implementation Details

### Step 1: Query Historical Data
```python
def get_7day_average(current_date):
    """Get all TOTAL costs from DynamoDB for last 7 days"""
    response = table.query(
        KeyConditionExpression='service = TOTAL AND date BETWEEN :start AND :end'
    )
    # Returns: [Day1 cost, Day2 cost, ..., Day7 cost]
    average = sum(costs) / len(costs)
    return average
```

**Why DynamoDB query?**
- **Fast**: O(1) key lookup + range on date
- **Scalable**: Works for 100+ days of data
- **Flexible**: Easy to change from 7-day to 30-day average

### Step 2: Compare & Flag
```python
def detect_anomaly(daily_cost, current_date):
    avg_7day = get_7day_average(current_date)
    
    # Edge case: Skip if cost is tiny (startup phase)
    if daily_cost < $1:
        return False  # Not enough data to be meaningful
    
    # Edge case: Skip if no historical data
    if avg_7day == 0:
        return False  # Can't compare without baseline
    
    # Calculate threshold
    threshold = avg_7day × 1.2
    
    # Compare
    is_anomaly = daily_cost > threshold
    
    # Calculate how far off (for dashboard)
    deviation_pct = ((daily_cost - avg_7day) / avg_7day) × 100
    
    return {
        'is_anomaly': is_anomaly,
        'deviation_pct': deviation_pct,
        'avg_7day': avg_7day,
        'threshold': threshold
    }
```

### Step 3: Store Result
```python
# Store in DynamoDB
table.put_item(Item={
    'date': '2025-05-17',
    'service': 'TOTAL',
    'cost': 75.50,
    'is_anomaly': True,           # ← Anomaly flag
    'avg_7day': 50.57,            # ← For reference
    'deviation_pct': 48.4,        # ← For dashboard chart
    'timestamp': now()
})
```

---

## Why This Approach?

### ✅ Advantages
1. **Simple & interpretable** — No ML magic, easy to explain
2. **Low false positive rate** — 20% threshold filters noise but catches real issues
3. **Self-tuning** — Adapts to your baseline (if you normally spend $50/day, $60 is noticed; if $500/day, $600 is normal)
4. **Actionable** — Manager can see: *"Today was 48% above normal, investigate"*
5. **Production-ready** — Used by many cloud ops teams

### ⚠️ Limitations
1. **Doesn't account for weekly patterns** — If you have 2x spend on Fridays, Fridays will never trigger
2. **Slow to adapt** — Takes 7 days to "learn" a new baseline
3. **No seasonality** — Doesn't know about your end-of-month billing cycle

### 🚀 Improvements (for future)
```python
# More advanced options:

# Option A: Use 14-day or 30-day average instead of 7-day
def detect_anomaly(daily_cost, current_date):
    avg_30day = get_average(current_date, days=30)
    threshold = avg_30day × 1.3  # 30% threshold instead of 20%
    return daily_cost > threshold

# Option B: Account for day-of-week patterns
def detect_anomaly(daily_cost, current_date):
    day_of_week = datetime.fromisoformat(current_date).weekday()
    # Get average for same weekday (e.g., all Mondays)
    monday_average = get_average_for_weekday(day_of_week)
    threshold = monday_average × 1.2
    return daily_cost > threshold

# Option C: Statistical Z-score (more sophisticated)
def detect_anomaly(daily_cost, current_date):
    avg = get_7day_average(current_date)
    stddev = calculate_std_deviation(...)
    z_score = (daily_cost - avg) / stddev
    return z_score > 2  # Anything >2σ is anomaly (95% confidence)
```

---

## Interview Questions You'll Get (& Answers)

### Q: "Why 1.2? Why not 1.5 or 1.1?"
**Your answer:**
> Great question. 1.2 (20% threshold) is a sweet spot for our use case:
> - **Too sensitive (1.1)**: You'd get false alarms every day
> - **Too loose (1.5)**: You'd miss real issues
> 
> For a fresher project, 1.2 is reasonable. In production, I'd **tune it by looking at your actual cost distribution** — graph your daily costs, see what the natural variance is, then set threshold accordingly. Ideally, you'd alert on maybe 5-10 anomalies per year, not 100 per month.

### Q: "What if someone scales up infrastructure on purpose?"
**Your answer:**
> Perfect edge case. The 7-day average would *eventually* catch up (if scale-up was permanent, days 8-14 would be high, so by day 15 the baseline is higher). But yes, for **expected planned increases**, you'd want:
> - A **change management system** that pre-flags "we're launching Campaign X, expect 3x costs"
> - Or a **whitelist**: mark certain days as "known spike, don't flag"
> 
> For this MVP, I focused on catching unexpected issues. Planned changes are a nice-to-have.

### Q: "How would you test this logic?"
**Your answer:**
> I'd write **unit tests** with mock data:
> ```python
> def test_anomaly_detection():
>     # Setup: 7 days at $50, then day 8 at $75
>     create_mock_7day_baseline(50)
>     
>     result = detect_anomaly(75, 'day-8')
>     assert result['is_anomaly'] == True
>     assert result['deviation_pct'] == 50.0  # 50% above baseline
>     
> def test_no_anomaly_within_threshold():
>     create_mock_7day_baseline(50)
>     result = detect_anomaly(55, 'day-8')  # Only 10% above
>     assert result['is_anomaly'] == False
> ```
> 
> And I'd use the `local_data_generator.py` to generate realistic mock data and visually inspect anomaly flags.

### Q: "How do you handle the first 7 days when there's no history?"
**Your answer:**
> Good catch. The code has a guard:
> ```python
> if avg_7day == 0.0:
>     return False  # Can't compare without baseline
> ```
> 
> So for the first 7 days, **nothing gets flagged as anomalous** — we're just collecting baseline data. This is intentional; you need at least 7 days of history to have a meaningful baseline. In production, you might set a flag like `is_learning_phase: true` to indicate the system isn't ready yet.

### Q: "How does this scale if you monitor 50 AWS accounts?"
**Your answer:**
> The anomaly detection logic itself is independent of scale. What changes is the data collection:
> 
> **Current approach (1 account):**
> - 1 Python script → 1 Cost Explorer API → 1 DynamoDB table
> 
> **Scaled approach (50 accounts):**
> - 50 Python scripts (or 1 script that assumes roles across 50 accounts)
> - → 50 Cost Explorer API calls
> - → Single centralized DynamoDB table (master account)
> 
> Anomaly detection works the same. You'd just have more rows in DynamoDB.
> The query `get_7day_average()` would still be fast because of the hash key + range key design.

---

## Code Walkthrough (For Interview Prep)

When interviewer asks "Walk me through the code":

```python
def detect_anomaly(daily_cost, current_date, anomaly_threshold=1.2):
    """
    Line 1: Three inputs
    - daily_cost: Today's total AWS spend (e.g., 75.50)
    - current_date: Date string (e.g., "2025-05-17")
    - anomaly_threshold: Multiplier (default 1.2 = 20%)
    
    Line 2: Return a dict with useful info
    """
    
    # Guard 1: If cost is negligible, don't bother
    if daily_cost < 1.0:
        return {'is_anomaly': False, ...}
    
    # Query DynamoDB for last 7 days of TOTAL costs
    avg_7day = get_7day_average(current_date)
    
    # Guard 2: If no history, can't compare
    if avg_7day == 0.0:
        return {'is_anomaly': False, ...}
    
    # The core logic: calculate threshold
    threshold_amount = avg_7day * anomaly_threshold
    
    # Is today above threshold?
    is_anomaly = daily_cost > threshold_amount
    
    # Calculate percentage deviation (for visualization)
    deviation_pct = ((daily_cost - avg_7day) / avg_7day) * 100
    
    # Return rich object with all the info
    return {
        'is_anomaly': is_anomaly,
        'daily_cost': daily_cost,
        'avg_7day': avg_7day,
        'threshold_amount': threshold_amount,
        'deviation_pct': deviation_pct
    }
```

---

## Testing Without AWS

Use `local_data_generator.py`:
```bash
python local_data_generator.py
# Generates mock_cost_data.json with realistic costs + anomalies
# Then creates dashboard/data.json for your HTML to display
```

This lets you test the full pipeline (collect → analyze → visualize) without AWS credentials.

---

## Summary for Your Resume

**Resume bullet:**
> Implemented automated cost anomaly detection using statistical analysis: 
> compares daily spend against 7-day rolling average with 20% threshold. 
> Flags cost spikes for investigation, demonstrating understanding of DevOps 
> observability and metrics-driven decision making.

**What you learned:**
- Time-series data analysis
- Threshold-based alerting
- Edge case handling (insufficient data, zero baselines)
- Balancing sensitivity vs false positives