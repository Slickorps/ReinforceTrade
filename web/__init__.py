"""
Web monitoring dashboard module for ReinforceTrade.

Provides Flask-based REST API and dashboard frontend for real-time
trading metrics, positions, performance, and trade history visualization.
"""

from web.app import create_app

__all__ = ["create_app"]