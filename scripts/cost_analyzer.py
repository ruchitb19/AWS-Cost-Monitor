import boto3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from botocore.exceptions import ClientError
from decimal import Decimal
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Configure logging (production-ready)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AWSCostMonitor:
    """
    Production-ready AWS Cost Monitor combining best practices from both approaches:
    - Proper OOP architecture (Document 1)
    - Detailed anomaly metrics with deviation_pct (Document 2)
    - TTL-based auto-cleanup (Document 2 enhancement)
    - Structured logging for CloudWatch (production pattern)
    """
    
    def __init__(self, region='ap-south-1', table_name='aws_cost_metrics'):
        """Initialize AWS clients and DynamoDB table"""
        try:
            self.ce_client = boto3.client('ce', region_name=region)
            self.dynamodb = boto3.resource('dynamodb', region_name=region)
            self.table = self.dynamodb.Table(table_name)
            logger.info(f"Initialized AWSCostMonitor with table: {table_name}")
        except ClientError as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise

    def fetch_aws_costs(self, days=30) -> Dict:
        """Fetch AWS costs from Cost Explorer API."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        try:
            logger.info(f"Fetching costs from {start_date} to {end_date}")
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'REGION'}
                ]
            )
            logger.info(f"Successfully fetched costs for {len(response['ResultsByTime'])} days")
            return response
        except ClientError as e:
            logger.error(f"Cost Explorer API call failed: {e}")
            raise

    def get_historical_average(self, days: int = 7) -> float:
        """Query DynamoDB for historical daily costs."""
        try:
            end_date = datetime.now().date()
            total = 0.0
            count = 0
            for i in range(days + 1):
                target_date = (end_date - timedelta(days=i)).isoformat()
                resp = self.table.get_item(Key={'date': target_date, 'service': 'TOTAL'})
                if 'Item' in resp:
                    total += float(resp['Item']['cost'])
                    count += 1
            
            if count == 0:
                logger.warning(f"No historical data found for last {days} days")
                return 0.0
            
            average = total / count
            logger.info(f"Historical average cost ({days} days): ${average:.2f}")
            return average
        except ClientError as e:
            logger.error(f"Failed to query historical data: {e}")
            return 0.0

    def detect_anomaly(self, daily_cost: float, threshold_multiplier: float = 1.2) -> Dict:
        """
        Detect anomaly with detailed metrics.
        
        Returns dict with:
        - is_anomaly: boolean
        - daily_cost: float (actual cost)
        - avg_7day: float (7-day average)
        - deviation_pct: float (percentage above/below average)
        - threshold: float (alert threshold)
        """
        historical_avg = self.get_historical_average(days=7)
        
        if historical_avg == 0:
            logger.info("Skipping anomaly detection - no historical data")
            return {
                'is_anomaly': False,
                'daily_cost': daily_cost,
                'avg_7day': 0.0,
                'deviation_pct': 0.0,
                'threshold': 0.0
            }
        
        threshold = historical_avg * threshold_multiplier
        is_anomaly = daily_cost > threshold
        deviation_pct = ((daily_cost - historical_avg) / historical_avg) * 100
        
        if is_anomaly:
            logger.warning(
                f"ANOMALY DETECTED: Daily cost ${daily_cost:.2f} "
                f"exceeds threshold ${threshold:.2f} (+{deviation_pct:.1f}%)"
            )
        else:
            logger.info(f"Daily cost ${daily_cost:.2f} is normal (+{deviation_pct:.1f}% vs avg)")
        
        return {
            'is_anomaly': is_anomaly,
            'daily_cost': daily_cost,
            'avg_7day': historical_avg,
            'deviation_pct': deviation_pct,
            'threshold': threshold
        }

    def store_cost_data(self, cost_data: Dict) -> Tuple[int, int]:
        """
        Parse and store cost data in DynamoDB.
        
        Features:
        - Individual service/region costs
        - Daily aggregate with anomaly detection
        - TTL for automatic 90-day cleanup
        - Deviation metrics for analytics
        """
        items_stored = 0
        errors = 0
        ttl = int((datetime.now() + timedelta(days=90)).timestamp())
        
        try:
            for result in cost_data['ResultsByTime']:
                date = result['TimePeriod']['Start']
                daily_cost = 0.0
                
                # Store individual service costs
                for group in result['Groups']:
                    try:
                        cost = float(group['Metrics']['UnblendedCost']['Amount'])
                        service = group['Keys'][0]
                        region = group['Keys'][1]
                        daily_cost += cost
                        
                        try:
                            self.table.put_item(
                                Item={
                                    'service': service,
                                    'date': date,
                                    'region': region,
                                    'cost': Decimal(str(cost)),
                                    'timestamp': datetime.now().isoformat(),
                                    'ttl': ttl
                                },
                                ReturnConsumedCapacity='NONE'
                            )
                            items_stored += 1
                        except ClientError as e:
                            logger.error(f"Failed to store {service}-{region} cost: {e}")
                            errors += 1
                    except (ValueError, KeyError) as e:
                        logger.error(f"Failed to parse cost group: {e}")
                        errors += 1
                
                # Detect anomaly with detailed metrics
                anomaly_result = self.detect_anomaly(daily_cost)
                
                # Store daily aggregate
                try:
                    self.table.put_item(
                        Item={
                            'service': 'TOTAL',
                            'date': date,
                            'region': 'ALL',
                            'cost': Decimal(str(daily_cost)),
                            'is_anomaly': anomaly_result['is_anomaly'],
                            'avg_7day': Decimal(str(anomaly_result['avg_7day'])),
                            'deviation_pct': Decimal(str(anomaly_result['deviation_pct'])),
                            'timestamp': datetime.now().isoformat(),
                            'ttl': ttl
                        },
                        ReturnConsumedCapacity='NONE'
                    )
                    items_stored += 1
                    
                    # Log summary
                    status = "🚨 ANOMALY" if anomaly_result['is_anomaly'] else "✓"
                    logger.info(
                        f"{status} {date}: ${daily_cost:.2f} "
                        f"(7d avg: ${anomaly_result['avg_7day']:.2f}, "
                        f"deviation: {anomaly_result['deviation_pct']:+.1f}%)"
                    )
                except ClientError as e:
                    logger.error(f"Failed to store daily total for {date}: {e}")
                    errors += 1
            
            logger.info(f"Cost storage completed: {items_stored} items stored, {errors} errors")
            return items_stored, errors
        except Exception as e:
            logger.error(f"Unexpected error during cost storage: {e}")
            return items_stored, errors

    def export_to_json(self, output_file='dashboard/data.json') -> bool:
        """Query DynamoDB and export cost data to JSON for dashboard."""
        try:
            data = {
                'generated_at': datetime.now().isoformat(),
                'dates': [],
                'costs': [],
                'anomalies': [],
                'deviations': [],
                'summary': {}
            }
            
            response = self.table.scan(
                FilterExpression='service = :service',
                ExpressionAttributeValues={':service': 'TOTAL'}
            )
            
            while True:
                items = response.get('Items', [])
                logger.info(f"Retrieved {len(items)} items from DynamoDB")
                
                for item in sorted(items, key=lambda x: x['date']):
                    data['dates'].append(item['date'])
                    data['costs'].append(float(item['cost']))
                    data['anomalies'].append(item.get('is_anomaly', False))
                    data['deviations'].append(float(item.get('deviation_pct', 0)))
                
                if 'LastEvaluatedKey' not in response:
                    break
                    
                response = self.table.scan(
                    FilterExpression='service = :service',
                    ExpressionAttributeValues={':service': 'TOTAL'},
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
            
            # Calculate summary
            if data['costs']:
                data['summary'] = {
                    'total_cost': round(sum(data['costs']), 2),
                    'daily_average': round(sum(data['costs']) / len(data['costs']), 2),
                    'max_cost': round(max(data['costs']), 2),
                    'min_cost': round(min(data['costs']), 2),
                    'anomalies_detected': sum(1 for a in data['anomalies'] if a)
                }
            
            import os
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Successfully exported data to {output_file}")
            return True
        except ClientError as e:
            logger.error(f"Failed to export data: {e}")
            return False

def main():
    """Main execution function"""
    try:
        monitor = AWSCostMonitor(region='ap-south-1', table_name='aws_cost_metrics')
        
        logger.info("Starting AWS cost monitoring job...")
        costs = monitor.fetch_aws_costs(days=30)
        items_stored, errors = monitor.store_cost_data(costs)
        export_success = monitor.export_to_json('dashboard/data.json')
        
        logger.info(f"Job completed - Stored: {items_stored}, Errors: {errors}, Export: {export_success}")
        print("✅ AWS cost monitoring completed successfully")
        
    except Exception as e:
        logger.error(f"Cost monitoring job failed: {e}")
        print("❌ Cost monitoring failed - check logs for details")
        raise

if __name__ == '__main__':
    main()