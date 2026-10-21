import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime
import os
import json
from utils.logger import logger

class ReportGenerator:
    """
    Generates comprehensive backtest reports with visualizations.
    Provides transparency into multi-agent decision making process.
    """
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Set style for better looking charts
        plt.style.use('seaborn-v0_8-darkgrid')
        
    def generate_full_report(self, results: Dict[str, Any], strategy_name: str = "MultiAgentStrategy"):
        """
        Generate comprehensive HTML report with all metrics and visualizations.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = f"{self.output_dir}/report_{timestamp}"
        os.makedirs(report_dir, exist_ok=True)
        
        # Generate all plots
        self._plot_equity_curve(results, report_dir)
        self._plot_drawdown(results, report_dir)
        self._plot_trade_distribution(results, report_dir)
        self._plot_agent_signals(results, report_dir)
        self._plot_monthly_returns(results, report_dir)
        self._plot_cumulative_returns(results, report_dir)
        
        # Generate HTML report
        html_content = self._generate_html(results, strategy_name, timestamp)
        
        with open(f"{report_dir}/report.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Save JSON data
        json_path = f"{report_dir}/data.json"
        serializable_results = {k: v for k, v in results.items() 
                               if k not in ['trades', 'equity_curve', 'agent_signals_sample']}
        with open(json_path, "w") as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        logger.info(f"Full report generated at {report_dir}/report.html")
        return report_dir
    
    def _generate_html(self, results: Dict[str, Any], strategy_name: str, timestamp: str) -> str:
        """Generate HTML report content"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>ReinforceTrade Backtest Report - {strategy_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .summary {{ background: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px 20px; }}
        .metric-label {{ font-size: 12px; color: #7f8c8d; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-value.positive {{ color: #27ae60; }}
        .metric-value.negative {{ color: #e74c3c; }}
        .chart-container {{ margin: 20px 0; text-align: center; }}
        .chart-container img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .agent-signals {{ background: #e8f4f8; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #7f8c8d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ReinforceTrade Backtest Report</h1>
        <p><strong>Strategy:</strong> {strategy_name} | <strong>Generated:</strong> {timestamp}</p>
        
        <div class="summary">
            <h2>Performance Summary</h2>
            <div class="metric">
                <div class="metric-label">Total Return</div>
                <div class="metric-value {'positive' if results.get('total_return', 0) > 0 else 'negative'}">
                    {results.get('total_return_pct', 0):.2f}%
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value">
                    {results.get('win_rate_pct', 0):.1f}%
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value">
                    {results.get('sharpe_ratio', 0):.2f}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value negative">
                    {results.get('max_drawdown_pct', 0):.2f}%
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">
                    {results.get('total_trades', 0)}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value">
                    {results.get('profit_factor', 0):.2f}
                </div>
            </div>
        </div>
        
        <h2>Detailed Metrics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Initial Balance</td><td>${results.get('initial_balance', 0):,.2f}</td></tr>
            <tr><td>Final Balance</td><td>${results.get('final_balance', 0):,.2f}</td></tr>
            <tr><td>Total PnL</td><td>${results.get('total_pnl', 0):,.2f}</td></tr>
            <tr><td>Average Win</td><td>${results.get('avg_win', 0):,.2f}</td></tr>
            <tr><td>Average Loss</td><td>${results.get('avg_loss', 0):,.2f}</td></tr>
            <tr><td>Calmar Ratio</td><td>{results.get('calmar_ratio', 0):.2f}</td></tr>
        </table>
        
        <h2>Visualizations</h2>
        
        <div class="chart-container">
            <h3>Equity Curve</h3>
            <img src="equity_curve.png" alt="Equity Curve">
        </div>
        
        <div class="chart-container">
            <h3>Drawdown Analysis</h3>
            <img src="drawdown.png" alt="Drawdown">
        </div>
        
        <div class="chart-container">
            <h3>Trade Distribution</h3>
            <img src="trade_distribution.png" alt="Trade Distribution">
        </div>
        
        <div class="chart-container">
            <h3>Monthly Returns</h3>
            <img src="monthly_returns.png" alt="Monthly Returns">
        </div>
        
        <div class="chart-container">
            <h3>Cumulative Returns</h3>
            <img src="cumulative_returns.png" alt="Cumulative Returns">
        </div>
        
        <h2>Multi-Agent Signal Transparency</h2>
        <div class="agent-signals">
            <p>The following shows a sample of multi-agent decision making process:</p>
        </div>
        """
        
        # Add agent signals sample
        if 'agent_signals_sample' in results and results['agent_signals_sample']:
            html += "<table><tr><th>Timestamp</th><th>Environment Agent</th><th>Short-Term Agent</th><th>Trend Agent</th><th>Decision</th></tr>"
            for signal_data in results['agent_signals_sample'][:5]:
                signals = signal_data.get('signals', {})
                decision = signals.get('decision', {})
                analyses = signals.get('analyses', {})
                
                html += f"""
                <tr>
                    <td>{signal_data.get('timestamp', 'N/A')}</td>
                    <td>{analyses.get('EnvironmentAgent', {}).get('trend', 'N/A')}</td>
                    <td>{signals.get('ShortTermAgent', {}).get('signal', 'N/A')}</td>
                    <td>{signals.get('TrendAgent', {}).get('signal', 'N/A')}</td>
                    <td><strong>{decision.get('action', 'N/A')}</strong> (conf: {decision.get('confidence', 0):.2f})</td>
                </tr>
                """
            html += "</table>"
        
        html += f"""
        
        <div class="footer">
            <p>Generated by ReinforceTrade Multi-Agent Trading System</p>
            <p>This report provides transparent view into AI trading decisions.</p>
        </div>
    </div>
</body>
</html>
        """
        return html
    
    def _plot_equity_curve(self, results: Dict[str, Any], output_dir: str):
        """Plot equity curve"""
        equity_curve = results.get('equity_curve', [])
        if not equity_curve:
            return
            
        df = pd.DataFrame(equity_curve)
        initial_balance = results.get('initial_balance', 10000)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # Equity curve
        ax1.plot(df.index, df['equity'], label='Portfolio Value', color='#3498db', linewidth=2)
        ax1.axhline(y=initial_balance, color='red', linestyle='--', alpha=0.5, label='Initial Balance')
        ax1.fill_between(df.index, df['equity'], initial_balance, alpha=0.3, color='#3498db')
        ax1.set_title('Portfolio Equity Curve', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Equity ($)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Price overlay
        ax3 = ax1.twinx()
        ax3.plot(df.index, df['price'], color='orange', alpha=0.5, label='Asset Price')
        ax3.set_ylabel('Price ($)', color='orange')
        
        # Returns percentage
        returns = ((df['equity'] - initial_balance) / initial_balance * 100)
        ax2.fill_between(df.index, returns, 0, alpha=0.4, color='green', where=(returns > 0))
        ax2.fill_between(df.index, returns, 0, alpha=0.4, color='red', where=(returns <= 0))
        ax2.plot(df.index, returns, color='black', linewidth=1)
        ax2.set_title('Returns (%)')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Return (%)')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/equity_curve.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_drawdown(self, results: Dict[str, Any], output_dir: str):
        """Plot drawdown chart"""
        equity_curve = results.get('equity_curve', [])
        if not equity_curve:
            return
            
        df = pd.DataFrame(equity_curve)
        
        # Calculate drawdown
        rolling_max = df['equity'].cummax()
        drawdown = (df['equity'] - rolling_max) / rolling_max * 100
        
        plt.figure(figsize=(12, 5))
        plt.fill_between(df.index, drawdown, 0, alpha=0.4, color='red')
        plt.plot(df.index, drawdown, color='darkred', linewidth=1)
        plt.title('Portfolio Drawdown (%)', fontsize=14, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel('Drawdown (%)')
        plt.grid(True, alpha=0.3)
        
        # Add max drawdown line
        max_dd = results.get('max_drawdown_pct', 0)
        plt.axhline(y=-max_dd, color='red', linestyle='--', alpha=0.7, label=f'Max DD: {max_dd:.2f}%')
        plt.legend()
        
        plt.savefig(f"{output_dir}/drawdown.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_trade_distribution(self, results: Dict[str, Any], output_dir: str):
        """Plot trade distribution histogram"""
        trades = results.get('trades', [])
        if not trades:
            return
            
        returns = [t.get('return_pct', 0) for t in trades]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        # Histogram
        ax1.hist(returns, bins=30, alpha=0.7, color='#3498db', edgecolor='black')
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
        ax1.axvline(x=np.mean(returns), color='green', linestyle='--', linewidth=2, label=f'Mean: {np.mean(returns):.2f}%')
        ax1.set_title('Distribution of Trade Returns', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Return (%)')
        ax1.set_ylabel('Frequency')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Win/Loss pie chart
        wins = len([r for r in returns if r > 0])
        losses = len([r for r in returns if r <= 0])
        ax2.pie([wins, losses], labels=['Wins', 'Losses'], colors=['#27ae60', '#e74c3c'], autopct='%1.1f%%')
        ax2.set_title(f'Win Rate: {results.get("win_rate_pct", 0):.1f}%', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/trade_distribution.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_agent_signals(self, results: Dict[str, Any], output_dir: str):
        """Plot agent signal decisions over time"""
        signals = results.get('agent_signals_sample', [])
        if not signals:
            return
            
        # Extract signal data for visualization
        timestamps = []
        decisions = []
        confidences = []
        
        for signal_data in signals:
            timestamps.append(signal_data.get('timestamp', 0))
            decision = signal_data.get('signals', {}).get('decision', {})
            action = decision.get('action', 'hold')
            confidence = decision.get('confidence', 0)
            
            # Encode actions as numbers
            action_map = {'buy': 1, 'sell': -1, 'hold': 0}
            decisions.append(action_map.get(action, 0))
            confidences.append(confidence)
        
        plt.figure(figsize=(12, 5))
        
        colors = ['red' if d == -1 else 'green' if d == 1 else 'gray' for d in decisions]
        plt.scatter(range(len(decisions)), decisions, c=colors, s=[c*100 for c in confidences], alpha=0.6)
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        plt.title('Multi-Agent Trading Decisions', fontsize=14, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel('Decision (1=Buy, -1=Sell, 0=Hold)')
        plt.yticks([-1, 0, 1], ['Sell', 'Hold', 'Buy'])
        plt.grid(True, alpha=0.3)
        
        plt.savefig(f"{output_dir}/agent_signals.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_monthly_returns(self, results: Dict[str, Any], output_dir: str):
        """Plot monthly returns heatmap"""
        equity_curve = results.get('equity_curve', [])
        if not equity_curve or len(equity_curve) < 30:
            return
            
        df = pd.DataFrame(equity_curve)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('timestamp', inplace=True)
        
        # Calculate daily returns
        df['returns'] = df['equity'].pct_change()
        
        # Resample to monthly
        monthly_returns = df['returns'].resample('ME').apply(lambda x: (1 + x).prod() - 1) * 100
        
        if len(monthly_returns) > 0:
            plt.figure(figsize=(12, 6))
            colors = ['red' if r < 0 else 'green' for r in monthly_returns]
            plt.bar(range(len(monthly_returns)), monthly_returns, color=colors, alpha=0.7)
            plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            plt.title('Monthly Returns (%)', fontsize=14, fontweight='bold')
            plt.xlabel('Month')
            plt.ylabel('Return (%)')
            plt.xticks(range(len(monthly_returns)), 
                      [m.strftime('%Y-%m') for m in monthly_returns.index], 
                      rotation=45)
            plt.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            plt.savefig(f"{output_dir}/monthly_returns.png", dpi=150, bbox_inches='tight')
            plt.close()
    
    def _plot_cumulative_returns(self, results: Dict[str, Any], output_dir: str):
        """Plot cumulative returns"""
        equity_curve = results.get('equity_curve', [])
        if not equity_curve:
            return
            
        df = pd.DataFrame(equity_curve)
        initial = results.get('initial_balance', 10000)
        df['cumulative_return'] = (df['equity'] / initial - 1) * 100
        
        plt.figure(figsize=(12, 5))
        plt.plot(df.index, df['cumulative_return'], color='#3498db', linewidth=2)
        plt.fill_between(df.index, df['cumulative_return'], 0, alpha=0.3, color='#3498db')
        plt.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        plt.title('Cumulative Returns (%)', fontsize=14, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel('Cumulative Return (%)')
        plt.grid(True, alpha=0.3)
        
        # Add annotations
        final_return = results.get('total_return_pct', 0)
        plt.annotate(f'Final: {final_return:.1f}%', 
                    xy=(df.index[-1], df['cumulative_return'].iloc[-1]),
                    xytext=(10, 10), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        plt.savefig(f"{output_dir}/cumulative_returns.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def generate_summary_pdf(self, results: Dict[str, Any], output_path: str = "reports/summary.pdf"):
        """
        Generate a PDF summary report (if matplotlib backend supports it).
        """
        # This is a placeholder - PDF generation would require additional libraries
        logger.info("PDF generation requires additional setup (reportlab or weasyprint)")
        pass
