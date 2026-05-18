"""
LOCAL TEST DATA GENERATOR
Use this to test your dashboard locally WITHOUT AWS credentials.
Generates realistic mock cost data and stores in DynamoDB Local or SQLite.
"""

import json
import random
from datetime import datetime, timedelta
from decimal import Decimal

# For local testing, you can use either:
# 1. DynamoDB Local (docker run -d -p 8000:8000 amazon/dynamodb-local)
# 2. Simple JSON file (mock_data.json)

SERVICES = ['EC2', 'RDS', 'S3', 'Lambda', 'DynamoDB', 'CloudWatch', 'IAM']
REGIONS = ['us-east-1', 'ap-south-1', 'eu-west-1']


def generate_mock_costs(days=30):
    """
    Generate realistic mock AWS cost data for the last N days.
    Includes occasional spikes (anomalies) for demo purposes.
    
    Args:
        days (int): Number of days to generate
    
    Returns:
        list: List of daily cost records
    """
    records = []
    base_daily_cost = 50.0  # Base average daily cost
    
    for i in range(days, 0, -1):
        date = (datetime.now() - timedelta(days=i)).date().isoformat()
        
        # 10% chance of spike (anomaly for demo)
        if random.random() < 0.1:
            daily_total = base_daily_cost * random.uniform(1.5, 2.0)  # 50-100% spike
            is_anomaly = True
        else:
            # Normal variation
            daily_total = base_daily_cost * random.uniform(0.8, 1.2)
            is_anomaly = False
        
        # Create daily record with service breakdown
        day_record = {
            'date': date,
            'daily_total': round(daily_total, 2),
            'is_anomaly': is_anomaly,
            'services': {}
        }
        
        # Distribute cost across services
        remaining = daily_total
        for idx, service in enumerate(SERVICES[:-1]):
            service_cost = random.uniform(5, 20)
            day_record['services'][service] = round(service_cost, 2)
            remaining -= service_cost
        
        # Last service gets remainder
        day_record['services'][SERVICES[-1]] = round(remaining, 2)
        
        records.append(day_record)
    
    return records


def store_mock_to_json(output_file='mock_cost_data.json'):
    """
    Generate and save mock cost data to JSON file.
    Perfect for testing without AWS credentials.
    """
    print("Generating mock AWS cost data...")
    
    data = generate_mock_costs(days=30)
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Mock data saved to {output_file}")
    print(f"   Generated {len(data)} days of cost data")
    print(f"   Services: {', '.join(SERVICES)}")
    
    return data


def create_dashboard_data_from_mock(input_file='mock_cost_data.json', 
                                     output_file='dashboard/data.json'):
    """
    Convert mock cost data to dashboard format.
    Use this to test your HTML dashboard locally.
    """
    import os
    
    print(f"Converting {input_file} to dashboard format...")
    
    with open(input_file, 'r') as f:
        records = json.load(f)
    
    dates = [r['date'] for r in records]
    costs = [r['daily_total'] for r in records]
    anomalies = [r['is_anomaly'] for r in records]
    
    # Calculate summary
    total = sum(costs)
    daily_avg = total / len(costs) if costs else 0
    anomaly_count = sum(1 for a in anomalies if a)
    
    dashboard_data = {
        'dates': dates,
        'costs': costs,
        'anomalies': anomalies,
        'summary': {
            'total_30d': round(total, 2),
            'daily_avg': round(daily_avg, 2),
            'max_day': round(max(costs), 2),
            'anomaly_count': anomaly_count
        }
    }
    
    # Write output
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    print(f"✅ Dashboard data ready at {output_file}")
    print(f"\nSummary:")
    print(f"  📊 Total (30d): ${dashboard_data['summary']['total_30d']:.2f}")
    print(f"  📈 Daily avg: ${dashboard_data['summary']['daily_avg']:.2f}")
    print(f"  🚨 Anomalies: {dashboard_data['summary']['anomaly_count']}")


def store_mock_to_dynamodb_local(dynamodb_resource, table_name='aws_cost_metrics'):
    """
    Store mock data directly to DynamoDB Local (for advanced testing).
    
    Prerequisites:
    1. Start DynamoDB Local:
       docker run -d -p 8000:8000 amazon/dynamodb-local
    
    2. Create table:
       aws dynamodb create-table \
         --table-name aws_cost_metrics \
         --attribute-definitions AttributeName=date,AttributeType=S AttributeName=service,AttributeType=S \
         --key-schema AttributeName=date,KeyType=HASH AttributeName=service,KeyType=RANGE \
         --billing-mode PAY_PER_REQUEST \
         --endpoint-url http://localhost:8000
    
    Args:
        dynamodb_resource: boto3 DynamoDB resource
        table_name: DynamoDB table name
    """
    print("Storing mock data to DynamoDB Local...")
    
    table = dynamodb_resource.Table(table_name)
    records = generate_mock_costs(days=30)
    
    for record in records:
        date = record['date']
        daily_total = record['daily_total']
        
        # Store TOTAL
        table.put_item(Item={
            'date': date,
            'service': 'TOTAL',
            'cost': Decimal(str(daily_total)),
            'is_anomaly': record['is_anomaly'],
            'timestamp': datetime.now().isoformat()
        })
        
        # Store per-service breakdown
        for service, cost in record['services'].items():
            table.put_item(Item={
                'date': date,
                'service': service,
                'cost': Decimal(str(cost)),
                'timestamp': datetime.now().isoformat()
            })
    
    print(f"✅ Stored {len(records)} days of mock cost data to DynamoDB")


if __name__ == '__main__':
    # Quick start: generate mock data for dashboard testing
    store_mock_to_json()
    create_dashboard_data_from_mock()
    print("\n🎉 Ready to test your dashboard locally!")