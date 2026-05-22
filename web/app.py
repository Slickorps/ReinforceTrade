"""
Flask application factory with REST API routes for trading metrics.

Endpoints:
    GET /api/metrics     - Real-time performance metrics (JSON)
    GET /api/positions   - Real-time position data (JSON)
    GET /api/performance - Performance statistics summary (JSON)
    GET /api/trades      - Recent trade history (JSON)
"""

from typing import Optional, Dict, Any, List
from flask import Flask, jsonify, request

from trading.order_manager import OrderManager
from trading.position_tracker import PositionTracker
from trading.performance_tracker import PerformanceTracker, MetricsCollector
from utils.logger import logger


# ──────────────────────────────────────────────────────────────────────
# Global registry  (injected by create_app or set externally)
# ──────────────────────────────────────────────────────────────────────
_registry: Dict[str, Any] = {
    "order_manager": None,
    "position_tracker": None,
    "performance_tracker": None,
    "metrics_collector": None,
}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _get_json_param(key: str, default: int = 50) -> int:
    """Extract integer query parameter with clamping."""
    try:
        val = int(request.args.get(key, default))
        return max(1, min(val, 500))
    except (ValueError, TypeError):
        return default


def _positions_to_dict(positions: List) -> List[Dict[str, Any]]:
    """Convert Position objects to JSON-safe dicts."""
    result = []
    for pos in positions:
        d = pos.to_dict() if hasattr(pos, "to_dict") else {}
        # Ensure numeric fields are serialisable
        for k in ("unrealized_pnl", "realized_pnl", "total_pnl", "pnl_percentage"):
            if k in d and d[k] is not None:
                d[k] = round(float(d[k]), 4)
        result.append(d)
    return result


# ──────────────────────────────────────────────────────────────────────
# Flask Application Factory
# ──────────────────────────────────────────────────────────────────────

def create_app(
    *,
    order_manager: Optional[OrderManager] = None,
    position_tracker: Optional[PositionTracker] = None,
    performance_tracker: Optional[PerformanceTracker] = None,
    metrics_collector: Optional[MetricsCollector] = None,
) -> Flask:
    """
    Create and configure the Flask monitoring application.

    All arguments are optional and can be set later via
    ``set_registry()`` or the dedicated setter functions below.
    """
    app = Flask(__name__)

    # ── Inject dependencies ───────────────────────────────────────
    if order_manager is not None:
        _registry["order_manager"] = order_manager
    if position_tracker is not None:
        _registry["position_tracker"] = position_tracker
    if performance_tracker is not None:
        _registry["performance_tracker"] = performance_tracker
    if metrics_collector is not None:
        _registry["metrics_collector"] = metrics_collector

    # ── CORS helper ───────────────────────────────────────────────
    @app.after_request
    def _add_cors_headers(response):
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault(
            "Access-Control-Allow-Headers", "Content-Type, Authorization"
        )
        response.headers.setdefault(
            "Access-Control-Allow-Methods", "GET, OPTIONS"
        )
        return response

    # ── Routes ────────────────────────────────────────────────────

    @app.route("/api/metrics", methods=["GET"])
    def api_metrics():
        """
        GET /api/metrics?limit=50

        Returns real-time performance metrics from MetricsCollector
        (win rate, profit factor, Sharpe, max drawdown, etc.).
        """
        collector: Optional[MetricsCollector] = _registry.get("metrics_collector")
        if collector is None:
            return jsonify({"error": "MetricsCollector not configured"}), 503

        try:
            summary = collector.get_summary()
            trades = collector.get_completed_trades_dict(
                _get_json_param("limit", 50)
            )
            return jsonify({
                "summary": summary,
                "recent_trades": trades,
                "timestamp": _now_iso(),
            })
        except Exception as exc:
            logger.error(f"/api/metrics error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/positions", methods=["GET"])
    def api_positions():
        """
        GET /api/positions

        Returns all currently open positions with real-time PnL.
        """
        pt: Optional[PositionTracker] = _registry.get("position_tracker")
        if pt is None:
            return jsonify({"error": "PositionTracker not configured"}), 503

        try:
            positions = pt.get_all_positions() if hasattr(pt, "get_all_positions") else []
            portfolio = pt.calculate_portfolio_value() if hasattr(pt, "calculate_portfolio_value") else {}
            return jsonify({
                "positions": _positions_to_dict(positions),
                "portfolio": {
                    "total_unrealized_pnl": round(float(portfolio.get("total_unrealized_pnl", 0.0)), 4),
                    "total_realized_pnl": round(float(portfolio.get("total_realized_pnl", 0.0)), 4),
                    "total_pnl": round(float(portfolio.get("total_pnl", 0.0)), 4),
                    "total_position_value": round(float(portfolio.get("total_position_value", 0.0)), 4),
                    "active_positions": portfolio.get("active_positions", 0),
                },
                "timestamp": _now_iso(),
            })
        except Exception as exc:
            logger.error(f"/api/positions error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/performance", methods=["GET"])
    def api_performance():
        """
        GET /api/performance

        Returns comprehensive performance summary from PerformanceTracker.
        """
        tracker: Optional[PerformanceTracker] = _registry.get("performance_tracker")
        if tracker is None:
            return jsonify({"error": "PerformanceTracker not configured"}), 503

        try:
            summary = tracker.get_performance_summary()
            # Round floats for cleaner output
            for key in summary:
                if isinstance(summary[key], float):
                    summary[key] = round(summary[key], 4)
            return jsonify({
                "performance": summary,
                "timestamp": _now_iso(),
            })
        except Exception as exc:
            logger.error(f"/api/performance error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/trades", methods=["GET"])
    def api_trades():
        """
        GET /api/trades?limit=100

        Returns recent trade history from OrderManager.
        Fallback to MetricsCollector if OrderManager unavailable.
        """
        limit = _get_json_param("limit", 100)

        om: Optional[OrderManager] = _registry.get("order_manager")
        trades: List[Dict[str, Any]] = []

        if om is not None:
            try:
                orders = om.get_order_history() if hasattr(om, "get_order_history") else []
                # Return only filled orders, newest first
                filled = [
                    o.to_dict() if hasattr(o, "to_dict") else o
                    for o in orders
                    if (hasattr(o, "status") and str(o.status).lower() in ("filled", "closed"))
                ]
                trades = filled[-limit:][::-1]
            except Exception as exc:
                logger.warning(f"OrderManager.get_order_history() failed: {exc}")

        # Fallback: use MetricsCollector trade records
        if not trades:
            collector: Optional[MetricsCollector] = _registry.get("metrics_collector")
            if collector is not None:
                trades = collector.get_completed_trades_dict(limit)

        return jsonify({
            "trades": trades,
            "count": len(trades),
            "timestamp": _now_iso(),
        })

    @app.route("/api/health", methods=["GET"])
    def api_health():
        """Health-check endpoint."""
        return jsonify({
            "status": "ok",
            "services": {
                "order_manager": _registry["order_manager"] is not None,
                "position_tracker": _registry["position_tracker"] is not None,
                "performance_tracker": _registry["performance_tracker"] is not None,
                "metrics_collector": _registry["metrics_collector"] is not None,
            },
            "timestamp": _now_iso(),
        })

    logger.info("Flask web application created (6 routes)")
    return app


# ──────────────────────────────────────────────────────────────────────
# Registry helpers (for external injection after app creation)
# ──────────────────────────────────────────────────────────────────────

def set_order_manager(om: OrderManager) -> None:
    """Register OrderManager instance."""
    _registry["order_manager"] = om


def set_position_tracker(pt: PositionTracker) -> None:
    """Register PositionTracker instance."""
    _registry["position_tracker"] = pt


def set_performance_tracker(tracker: PerformanceTracker) -> None:
    """Register PerformanceTracker instance (also sets MetricsCollector)."""
    _registry["performance_tracker"] = tracker
    if tracker is not None and hasattr(tracker, "collector"):
        _registry["metrics_collector"] = tracker.collector


def set_metrics_collector(mc: MetricsCollector) -> None:
    """Register MetricsCollector instance."""
    _registry["metrics_collector"] = mc


def get_registry() -> Dict[str, Any]:
    """Return a copy of the current registry (read-only)."""
    return dict(_registry)


# ──────────────────────────────────────────────────────────────────────
# Internal
# ──────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()