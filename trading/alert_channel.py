"""
Alert management system for handling and distributing trading alerts.
Provides alert channels for different output destinations (console, file, etc.)
and an extensible interface for adding new channels (Webhook, Telegram, etc.).
"""
from typing import Dict, Any, List, Optional, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from pathlib import Path

from trading.monitor import MonitorEvent
from utils.logger import logger


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """
    Represents an alert to be distributed through alert channels.

    Contains all necessary information for different alert channel types.
    """
    title: str
    message: str
    severity: AlertSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    event_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_monitor_event(cls, event: MonitorEvent) -> "Alert":
        """
        Create an Alert from a MonitorEvent.

        Args:
            event: The MonitorEvent to convert

        Returns:
            Alert instance
        """
        return cls(
            title=event.event_type.value.replace("_", " ").title(),
            message=event.message,
            severity=AlertSeverity(event.severity),
            source=event.source,
            event_type=event.event_type.value,
            data=event.data,
            timestamp=event.timestamp
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization"""
        return {
            'title': self.title,
            'message': self.message,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'event_type': self.event_type,
            'data': self.data
        }

    def format_for_console(self) -> str:
        """Format alert for console output"""
        severity_colors = {
            AlertSeverity.INFO: "",
            AlertSeverity.WARNING: "[WARN]",
            AlertSeverity.ERROR: "[ERROR]",
            AlertSeverity.CRITICAL: "[CRITICAL]"
        }
        prefix = severity_colors.get(self.severity, "[INFO]")
        return f"{prefix} [{self.source}] {self.title}: {self.message}"

    def format_for_file(self) -> str:
        """Format alert for file logging"""
        return (
            f"[{self.timestamp.isoformat()}] "
            f"[{self.severity.value.upper()}] "
            f"[{self.source}] "
            f"{self.title}: {self.message}"
        )

    def format_for_webhook(self) -> Dict[str, Any]:
        """Format alert as JSON for webhook delivery"""
        return self.to_dict()


class AlertChannel(ABC):
    """
    Abstract base class for alert channels.

    Implementations define how alerts are delivered (console, file, webhook, etc.)
    """

    def __init__(self, name: str, enabled: bool = True):
        """
        Initialize alert channel.

        Args:
            name: Channel name for identification
            enabled: Whether the channel is initially enabled
        """
        self.name = name
        self._enabled = enabled
        self._sent_count: int = 0
        self._error_count: int = 0

    @property
    def enabled(self) -> bool:
        """Check if channel is enabled"""
        return self._enabled

    def enable(self) -> None:
        """Enable the channel"""
        self._enabled = True
        logger.debug(f"Alert channel '{self.name}' enabled")

    def disable(self) -> None:
        """Disable the channel"""
        self._enabled = False
        logger.debug(f"Alert channel '{self.name}' disabled")

    @abstractmethod
    def send_alert(self, alert: Alert) -> bool:
        """
        Send an alert through this channel.

        Args:
            alert: The Alert to send

        Returns:
            True if sent successfully, False otherwise
        """
        ...

    def get_statistics(self) -> Dict[str, Any]:
        """Get channel statistics"""
        return {
            'name': self.name,
            'type': self.__class__.__name__,
            'enabled': self._enabled,
            'sent_count': self._sent_count,
            'error_count': self._error_count
        }


class ConsoleAlertChannel(AlertChannel):
    """
    Alert channel that outputs alerts to the console.

    Uses the project's logger to output formatted alert messages.
    """

    def __init__(self, name: str = "console", enabled: bool = True):
        super().__init__(name, enabled)

    def send_alert(self, alert: Alert) -> bool:
        """
        Send alert to console via logger.

        Args:
            alert: The Alert to display

        Returns:
            True if logged successfully
        """
        try:
            message = alert.format_for_console()

            # Route by severity to appropriate log level
            if alert.severity == AlertSeverity.CRITICAL:
                logger.critical(message)
            elif alert.severity == AlertSeverity.ERROR:
                logger.error(message)
            elif alert.severity == AlertSeverity.WARNING:
                logger.warning(message)
            else:
                logger.info(message)

            self._sent_count += 1
            return True

        except Exception as e:
            logger.error(f"Console alert channel failed: {e}")
            self._error_count += 1
            return False


class FileAlertChannel(AlertChannel):
    """
    Alert channel that writes alerts to a dedicated alerts log file.

    Creates a separate log file for alerts, distinct from the main application log.
    """

    def __init__(self, file_path: str = "logs/alerts.log",
                 name: str = "file", enabled: bool = True):
        """
        Initialize file alert channel.

        Args:
            file_path: Path to the alerts log file
            name: Channel name
            enabled: Whether the channel is initially enabled
        """
        super().__init__(name, enabled)
        self.file_path = file_path

        # Ensure directory exists
        log_dir = Path(file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    def send_alert(self, alert: Alert) -> bool:
        """
        Write alert to the alerts log file.

        Args:
            alert: The Alert to write

        Returns:
            True if written successfully
        """
        try:
            message = alert.format_for_file()

            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(message + '\n')

            self._sent_count += 1
            return True

        except Exception as e:
            logger.error(f"File alert channel failed: {e}")
            self._error_count += 1
            return False


class AlertManager:
    """
    Central alert management system.

    Manages multiple alert channels, routes alerts to appropriate channels
    based on severity, and provides alert history and statistics.
    """

    def __init__(self, max_alert_history: int = 1000):
        """
        Initialize AlertManager.

        Args:
            max_alert_history: Maximum number of alerts to keep in memory
        """
        self._channels: Dict[str, AlertChannel] = {}
        self._alert_history: List[Alert] = []
        self._max_alert_history = max_alert_history
        self._lock = Lock()

        # Statistics
        self._total_alerts: int = 0
        self._total_sent: int = 0
        self._total_failed: int = 0

        # Severity counters
        self._severity_counts: Dict[str, int] = {
            'info': 0,
            'warning': 0,
            'error': 0,
            'critical': 0
        }

        logger.info("AlertManager initialized")

    # ── Channel Management ────────────────────────────────────────

    def add_channel(self, channel: AlertChannel) -> None:
        """
        Register an alert channel.

        Args:
            channel: AlertChannel instance to add
        """
        with self._lock:
            self._channels[channel.name] = channel
        logger.info(f"Alert channel added: '{channel.name}' ({type(channel).__name__})")

    def remove_channel(self, name: str) -> bool:
        """
        Remove an alert channel by name.

        Args:
            name: Channel name to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if name in self._channels:
                del self._channels[name]
                logger.info(f"Alert channel removed: '{name}'")
                return True
            return False

    def get_channel(self, name: str) -> Optional[AlertChannel]:
        """Get an alert channel by name"""
        with self._lock:
            return self._channels.get(name)

    def get_channels(self) -> Dict[str, AlertChannel]:
        """Get all registered alert channels"""
        with self._lock:
            return dict(self._channels)

    def enable_channel(self, name: str) -> bool:
        """Enable a specific channel"""
        channel = self.get_channel(name)
        if channel:
            channel.enable()
            return True
        return False

    def disable_channel(self, name: str) -> bool:
        """Disable a specific channel"""
        channel = self.get_channel(name)
        if channel:
            channel.disable()
            return True
        return False

    # ── Alert Dispatch ────────────────────────────────────────────

    def send_alert(self, alert: Alert) -> int:
        """
        Dispatch an alert to all enabled channels.

        Args:
            alert: The Alert to dispatch

        Returns:
            Number of channels that successfully sent the alert
        """
        with self._lock:
            # Store in history
            self._alert_history.append(alert)
            if len(self._alert_history) > self._max_alert_history:
                self._alert_history.pop(0)

            # Update counters
            self._total_alerts += 1
            severity_key = alert.severity.value
            if severity_key in self._severity_counts:
                self._severity_counts[severity_key] += 1

            # Get enabled channels
            channels = list(self._channels.values())

        # Dispatch to all enabled channels
        sent_count = 0
        for channel in channels:
            if not channel.enabled:
                continue

            try:
                if channel.send_alert(alert):
                    sent_count += 1
            except Exception as e:
                logger.error(f"Alert channel '{channel.name}' send failed: {e}")
                self._total_failed += 1

        with self._lock:
            self._total_sent += sent_count

        return sent_count

    def handle_event(self, event: MonitorEvent) -> int:
        """
        Handle a MonitorEvent by converting it to an Alert and dispatching it.

        This method is designed to be called by TradeMonitor.

        Args:
            event: The MonitorEvent to handle

        Returns:
            Number of channels that successfully sent the alert
        """
        alert = Alert.from_monitor_event(event)
        return self.send_alert(alert)

    def alert_info(self, title: str, message: str,
                   source: str = "system", data: Optional[Dict[str, Any]] = None) -> int:
        """Send an info-level alert"""
        alert = Alert(
            title=title,
            message=message,
            severity=AlertSeverity.INFO,
            source=source,
            data=data or {}
        )
        return self.send_alert(alert)

    def alert_warning(self, title: str, message: str,
                      source: str = "system", data: Optional[Dict[str, Any]] = None) -> int:
        """Send a warning-level alert"""
        alert = Alert(
            title=title,
            message=message,
            severity=AlertSeverity.WARNING,
            source=source,
            data=data or {}
        )
        return self.send_alert(alert)

    def alert_error(self, title: str, message: str,
                    source: str = "system", data: Optional[Dict[str, Any]] = None) -> int:
        """Send an error-level alert"""
        alert = Alert(
            title=title,
            message=message,
            severity=AlertSeverity.ERROR,
            source=source,
            data=data or {}
        )
        return self.send_alert(alert)

    def alert_critical(self, title: str, message: str,
                       source: str = "system", data: Optional[Dict[str, Any]] = None) -> int:
        """Send a critical-level alert"""
        alert = Alert(
            title=title,
            message=message,
            severity=AlertSeverity.CRITICAL,
            source=source,
            data=data or {}
        )
        return self.send_alert(alert)

    # ── Data Access ───────────────────────────────────────────────

    def get_alert_history(self, count: int = 10,
                          severity: Optional[str] = None) -> List[Alert]:
        """
        Get recent alerts, optionally filtered by severity.

        Args:
            count: Maximum number of alerts to return
            severity: Optional severity filter ('info', 'warning', 'error', 'critical')

        Returns:
            List of recent Alert objects
        """
        with self._lock:
            alerts = list(self._alert_history)

        if severity:
            alerts = [a for a in alerts if a.severity.value == severity]

        return alerts[-count:]

    def get_alert_history_dict(self, count: int = 10,
                               severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent alerts as dictionaries for serialization"""
        return [a.to_dict() for a in self.get_alert_history(count, severity)]

    def get_statistics(self) -> Dict[str, Any]:
        """Get alert manager statistics"""
        with self._lock:
            channels_stats = {
                name: ch.get_statistics()
                for name, ch in self._channels.items()
            }

            return {
                'total_alerts': self._total_alerts,
                'total_sent': self._total_sent,
                'total_failed': self._total_failed,
                'severity_counts': dict(self._severity_counts),
                'active_channels': len(self._channels),
                'alert_history_size': len(self._alert_history),
                'channels': channels_stats
            }

    def clear_history(self) -> int:
        """Clear alert history. Returns number of alerts cleared."""
        with self._lock:
            count = len(self._alert_history)
            self._alert_history.clear()
        logger.info(f"Cleared {count} alerts from history")
        return count

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"AlertManager(alerts={stats['total_alerts']}, "
            f"channels={stats['active_channels']}, "
            f"sent={stats['total_sent']})"
        )