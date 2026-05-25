/**
 * ReinforceTrade Dashboard — AJAX Auto-Refresh Frontend
 *
 * Polls /api/* endpoints every 3 seconds and renders:
 *   - Performance cards (win rate, Sharpe, drawdown, etc.)
 *   - Portfolio mini-cards
 *   - Positions table with sortable columns
 *   - Recent trades table
 */
(function () {
    "use strict";

    // ──────────────────────────────────────────────────────────────────
    // Configuration
    // ──────────────────────────────────────────────────────────────────
    var REFRESH_INTERVAL = 3000; // ms
    var API_BASE = ""; // relative to current origin

    // ──────────────────────────────────────────────────────────────────
    // DOM references
    // ──────────────────────────────────────────────────────────────────
    var $statusDot = document.querySelector(".status-dot");
    var $statusText = document.querySelector(".status-text");
    var $currentTime = document.getElementById("current-time");
    var $lastUpdate = document.getElementById("last-update");
    var $refreshCountdown = document.getElementById("refresh-countdown");

    // Cards
    var $cardWinRate = document.getElementById("card-win-rate");
    var $cardProfitFactor = document.getElementById("card-profit-factor");
    var $cardMaxDrawdown = document.getElementById("card-max-drawdown");
    var $cardSharpe = document.getElementById("card-sharpe");
    var $cardTotalTrades = document.getElementById("card-total-trades");
    var $cardTotalPnl = document.getElementById("card-total-pnl");

    // Portfolio
    var $portUnrealizedPnl = document.getElementById("port-unrealized-pnl");
    var $portRealizedPnl = document.getElementById("port-realized-pnl");
    var $portTotalPnl = document.getElementById("port-total-pnl");
    var $portPositionValue = document.getElementById("port-position-value");
    var $portActivePositions = document.getElementById("port-active-positions");

    // Tables
    var $positionsTbody = document.getElementById("positions-tbody");
    var $tradesTbody = document.getElementById("trades-tbody");

    // ──────────────────────────────────────────────────────────────────
    // State
    // ──────────────────────────────────────────────────────────────────
    var countdown = REFRESH_INTERVAL / 1000;
    var positionsData = [];
    var positionsSortKey = null;
    var positionsSortDesc = true;

    // ──────────────────────────────────────────────────────────────────
    // Helpers
    // ──────────────────────────────────────────────────────────────────
    function fmtCurrency(val) {
        if (val == null || isNaN(val)) return "$0.00";
        var num = Number(val);
        return (num >= 0 ? "$" : "-$") + Math.abs(num).toFixed(2);
    }

    function fmtPercent(val) {
        if (val == null || isNaN(val)) return "--%";
        return Number(val).toFixed(2) + "%";
    }

    function fmtNumber(val, decimals) {
        decimals = decimals != null ? decimals : 2;
        if (val == null || isNaN(val)) return "--";
        return Number(val).toFixed(decimals);
    }

    function fmtTime(isoStr) {
        if (!isoStr) return "--";
        var d = new Date(isoStr);
        return d.toLocaleTimeString("zh-CN", { hour12: false });
    }

    function setText(el, text) {
        if (el && el.textContent !== text) {
            el.textContent = text;
            el.classList.add("flash-update");
            setTimeout(function () {
                el.classList.remove("flash-update");
            }, 650);
        }
    }

    function setPnlText(el, val) {
        if (!el) return;
        var text = fmtCurrency(val);
        if (el.textContent !== text) {
            el.textContent = text;
            el.classList.add("flash-update");
            setTimeout(function () {
                el.classList.remove("flash-update");
            }, 650);
        }
        // Color class
        el.classList.remove("pnl-positive", "pnl-negative");
        if (val > 0) el.classList.add("pnl-positive");
        else if (val < 0) el.classList.add("pnl-negative");
    }

    function setConnectionStatus(connected) {
        if (!$statusDot || !$statusText) return;
        if (connected) {
            $statusDot.classList.remove("disconnected");
            $statusDot.classList.add("connected");
            $statusText.textContent = "已连接";
        } else {
            $statusDot.classList.remove("connected");
            $statusDot.classList.add("disconnected");
            $statusText.textContent = "已断开";
        }
    }

    // ──────────────────────────────────────────────────────────────────
    // Data fetching
    // ──────────────────────────────────────────────────────────────────
    function fetchAll() {
        var errors = 0;

        function handleError(endpoint) {
            errors++;
            console.warn("Dashboard: " + endpoint + " fetch failed");
        }

        // ── /api/performance ──────────────────────────────────────
        fetch(API_BASE + "/api/performance")
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (data) {
                var perf = data.performance || {};
                setText($cardWinRate, fmtPercent(perf.win_rate));
                setText($cardProfitFactor, fmtNumber(perf.profit_factor, 2));
                setText($cardMaxDrawdown, fmtPercent(perf.max_drawdown));
                setText($cardSharpe, fmtNumber(perf.sharpe_ratio, 2));
                setText($cardTotalTrades, String(perf.total_trades || 0));
                setPnlText($cardTotalPnl, perf.total_pnl);
            })
            .catch(function () {
                handleError("/api/performance");
            });

        // ── /api/positions ────────────────────────────────────────
        fetch(API_BASE + "/api/positions")
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (data) {
                var portfolio = data.portfolio || {};
                setPnlText($portUnrealizedPnl, portfolio.total_unrealized_pnl);
                setPnlText($portRealizedPnl, portfolio.total_realized_pnl);
                setPnlText($portTotalPnl, portfolio.total_pnl);
                setText($portPositionValue, fmtCurrency(portfolio.total_position_value));
                setText($portActivePositions, String(portfolio.active_positions || 0));

                positionsData = data.positions || [];
                renderPositionsTable();
                setConnectionStatus(true);
            })
            .catch(function () {
                handleError("/api/positions");
                setConnectionStatus(false);
            });

        // ── /api/metrics ──────────────────────────────────────────
        fetch(API_BASE + "/api/metrics")
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (data) {
                // MetricsCollector provides summary which we already get from /api/performance.
                // But it also provides recent_trades — use those as fallback.
                // We'll still call /api/trades explicitly for the trades table.
            })
            .catch(function () {
                handleError("/api/metrics");
            });

        // ── /api/trades ───────────────────────────────────────────
        fetch(API_BASE + "/api/trades")
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (data) {
                renderTradesTable(data.trades || []);
            })
            .catch(function () {
                handleError("/api/trades");
            });

        // Update timestamp
        var now = new Date();
        setText($lastUpdate, now.toLocaleTimeString("zh-CN", { hour12: false }));
        setText($currentTime, now.toLocaleDateString("zh-CN") + " " + now.toLocaleTimeString("zh-CN", { hour12: false }));
    }

    // ──────────────────────────────────────────────────────────────────
    // Render positions table
    // ──────────────────────────────────────────────────────────────────
    function renderPositionsTable() {
        if (!$positionsTbody) return;

        if (positionsData.length === 0) {
            $positionsTbody.innerHTML =
                '<tr class="empty-row"><td colspan="7">暂无持仓数据</td></tr>';
            return;
        }

        // Sorting
        var sorted = positionsData.slice();
        if (positionsSortKey) {
            sorted.sort(function (a, b) {
                var av = a[positionsSortKey];
                var bv = b[positionsSortKey];
                if (av == null) av = 0;
                if (bv == null) bv = 0;
                if (typeof av === "string") av = av.toLowerCase();
                if (typeof bv === "string") bv = bv.toLowerCase();
                if (av < bv) return positionsSortDesc ? -1 : 1;
                if (av > bv) return positionsSortDesc ? 1 : -1;
                return 0;
            });
        }

        var rows = sorted
            .map(function (pos) {
                var pnl = Number(pos.unrealized_pnl || 0);
                var pnlPct = Number(pos.pnl_percentage || 0);
                var pnlClass = pnl > 0 ? "pnl-positive" : pnl < 0 ? "pnl-negative" : "";
                var pctClass = pnlPct > 0 ? "pnl-positive" : pnlPct < 0 ? "pnl-negative" : "";

                return (
                    "<tr>" +
                    "<td>" +
                    escapeHtml(String(pos.symbol || pos.pair || "--")) +
                    "</td>" +
                    "<td>" +
                    escapeHtml(String(pos.side || "--")) +
                    "</td>" +
                    "<td>" +
                    fmtNumber(pos.size, 6) +
                    "</td>" +
                    "<td>" +
                    fmtCurrency(pos.entry_price) +
                    "</td>" +
                    "<td>" +
                    fmtCurrency(pos.current_price) +
                    "</td>" +
                    '<td class="' +
                    pnlClass +
                    '">' +
                    fmtCurrency(pnl) +
                    "</td>" +
                    '<td class="' +
                    pctClass +
                    '">' +
                    fmtPercent(pnlPct) +
                    "</td>" +
                    "</tr>"
                );
            })
            .join("");

        $positionsTbody.innerHTML = rows;
    }

    // ──────────────────────────────────────────────────────────────────
    // Render trades table
    // ──────────────────────────────────────────────────────────────────
    function renderTradesTable(trades) {
        if (!$tradesTbody) return;

        if (!trades || trades.length === 0) {
            $tradesTbody.innerHTML =
                '<tr class="empty-row"><td colspan="6">暂无交易记录</td></tr>';
            return;
        }

        var rows = trades
            .map(function (t) {
                var pnl = Number(t.pnl || t.realized_pnl || 0);
                var pnlClass = pnl > 0 ? "pnl-positive" : pnl < 0 ? "pnl-negative" : "";
                return (
                    "<tr>" +
                    "<td>" +
                    fmtTime(t.timestamp || t.time || t.filled_time) +
                    "</td>" +
                    "<td>" +
                    escapeHtml(String(t.symbol || t.pair || "--")) +
                    "</td>" +
                    "<td>" +
                    escapeHtml(String(t.side || "--")) +
                    "</td>" +
                    "<td>" +
                    fmtNumber(t.size || t.amount || t.quantity, 6) +
                    "</td>" +
                    "<td>" +
                    fmtCurrency(t.price || t.fill_price) +
                    "</td>" +
                    '<td class="' +
                    pnlClass +
                    '">' +
                    fmtCurrency(pnl) +
                    "</td>" +
                    "</tr>"
                );
            })
            .join("");

        $tradesTbody.innerHTML = rows;
    }

    // ──────────────────────────────────────────────────────────────────
    // Table sorting
    // ──────────────────────────────────────────────────────────────────
    function setupSorting() {
        var table = document.getElementById("positions-table");
        if (!table) return;
        table.addEventListener("click", function (e) {
            var th = e.target.closest("th");
            if (!th) return;
            var key = th.getAttribute("data-sort");
            if (!key) return;

            if (positionsSortKey === key) {
                positionsSortDesc = !positionsSortDesc;
            } else {
                positionsSortKey = key;
                positionsSortDesc = true;
            }
            // Update arrow indicators
            table.querySelectorAll("th").forEach(function (h) {
                var text = (h.textContent || "").replace(/\s*[▴▾]$/, "");
                h.textContent = text + " ▾";
            });
            th.textContent = (th.textContent || "").replace(/\s*[▴▾]$/, "") + (positionsSortDesc ? " ▴" : " ▾");
            renderPositionsTable();
        });
    }

    // ──────────────────────────────────────────────────────────────────
    // Countdown timer
    // ──────────────────────────────────────────────────────────────────
    function startCountdown() {
        setInterval(function () {
            countdown--;
            if (countdown <= 0) {
                countdown = REFRESH_INTERVAL / 1000;
                fetchAll();
            }
            if ($refreshCountdown) {
                $refreshCountdown.textContent = String(countdown);
            }
        }, 1000);
    }

    // ──────────────────────────────────────────────────────────────────
    // HTML escape
    // ──────────────────────────────────────────────────────────────────
    function escapeHtml(str) {
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // ──────────────────────────────────────────────────────────────────
    // Init
    // ──────────────────────────────────────────────────────────────────
    fetchAll();
    setupSorting();
    startCountdown();
})();