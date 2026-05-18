fetch('data.json')
    .then(r => r.json())
    .then(data => {
        // Calculate metrics
        const totalCost = data.costs.reduce((a, b) => a + b, 0);
        const dailyAvg = (totalCost / data.dates.length).toFixed(2);
        const anomalyCount = data.anomalies.filter(a => a).length;

        document.getElementById('monthly-cost').textContent = `$${totalCost.toFixed(2)}`;
        document.getElementById('daily-avg').textContent = `$${dailyAvg}`;
        document.getElementById('anomaly-count').textContent = anomalyCount;

        // Draw chart
        const ctx = document.getElementById('costChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.dates,
                datasets: [{
                    label: 'Daily Cost ($)',
                    data: data.costs,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: true },
                    title: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Cost ($)' }
                    }
                }
            }
        });
    });