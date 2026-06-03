-- ============================================================================
-- Intelligent Strategy Trading — PostgreSQL Stored Procedures
--
-- This script provides:
--   1. Backtest result aggregation statistics
--   2. Trade flow analysis reports
--   3. Risk indicator calculation functions
--   4. Utility helper functions
--
-- Compatible with PostgreSQL 13+
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- Helper: ensure uuid-ossp extension for UUID generation
-- ────────────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ────────────────────────────────────────────────────────────────────────────
-- Helper: ensure tablefunc extension for crosstab (pivot) queries
-- ────────────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "tablefunc";


-- ============================================================================
-- SCHEMA: trading
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS risk;


-- ============================================================================
-- TABLES (idempotent creation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.backtest_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_name   VARCHAR(128) NOT NULL,
    symbol          VARCHAR(32) NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    initial_capital NUMERIC(20, 4) NOT NULL,
    final_capital   NUMERIC(20, 4),
    total_return    NUMERIC(10, 6),
    sharpe_ratio    NUMERIC(10, 6),
    max_drawdown    NUMERIC(10, 6),
    win_rate        NUMERIC(6, 4),
    total_trades    INTEGER,
    winning_trades  INTEGER,
    losing_trades   INTEGER,
    params_json     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trading.trade_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_id     UUID REFERENCES trading.backtest_results(id) ON DELETE CASCADE,
    strategy_name   VARCHAR(128) NOT NULL,
    symbol          VARCHAR(32) NOT NULL,
    side            VARCHAR(8) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    entry_price     NUMERIC(20, 6) NOT NULL,
    exit_price      NUMERIC(20, 6),
    quantity        NUMERIC(20, 6) NOT NULL,
    entry_time      TIMESTAMPTZ NOT NULL,
    exit_time       TIMESTAMPTZ,
    pnl             NUMERIC(20, 6),
    pnl_pct         NUMERIC(10, 6),
    fee             NUMERIC(20, 6) DEFAULT 0,
    slippage        NUMERIC(20, 6) DEFAULT 0,
    tags            TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk.daily_risk_metrics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_id     UUID REFERENCES trading.backtest_results(id) ON DELETE CASCADE,
    calc_date       DATE NOT NULL,
    equity          NUMERIC(20, 4) NOT NULL,
    daily_return    NUMERIC(10, 6),
    rolling_var_95  NUMERIC(10, 6),
    rolling_var_99  NUMERIC(10, 6),
    rolling_cvar_95 NUMERIC(10, 6),
    drawdown        NUMERIC(10, 6),
    volatility_21d  NUMERIC(10, 6),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (backtest_id, calc_date)
);

CREATE INDEX IF NOT EXISTS idx_trade_records_backtest
    ON trading.trade_records(backtest_id);
CREATE INDEX IF NOT EXISTS idx_trade_records_strategy
    ON trading.trade_records(strategy_name);
CREATE INDEX IF NOT EXISTS idx_trade_records_entry_time
    ON trading.trade_records(entry_time);
CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy
    ON trading.backtest_results(strategy_name);
CREATE INDEX IF NOT EXISTS idx_daily_risk_backtest
    ON risk.daily_risk_metrics(backtest_id, calc_date);


-- ============================================================================
-- FUNCTION 1: aggregate_backtest_summary
--
-- Returns aggregated statistics for a given backtest run.
-- ============================================================================

CREATE OR REPLACE FUNCTION trading.aggregate_backtest_summary(
    p_backtest_id UUID
)
RETURNS TABLE (
    total_trades        INTEGER,
    winning_trades      INTEGER,
    losing_trades       INTEGER,
    win_rate            NUMERIC(6, 4),
    avg_win_pnl         NUMERIC(20, 6),
    avg_loss_pnl        NUMERIC(20, 6),
    max_win_pnl         NUMERIC(20, 6),
    max_loss_pnl        NUMERIC(20, 6),
    total_pnl           NUMERIC(20, 6),
    gross_profit        NUMERIC(20, 6),
    gross_loss          NUMERIC(20, 6),
    profit_factor       NUMERIC(10, 6),
    avg_holding_period  INTERVAL,
    avg_trades_per_day  NUMERIC(10, 4)
)
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v_day_count INTEGER;
BEGIN
    -- Count trading days in the backtest period
    SELECT COUNT(DISTINCT entry_time::DATE)
    INTO v_day_count
    FROM trading.trade_records
    WHERE backtest_id = p_backtest_id;

    RETURN QUERY
    WITH trade_stats AS (
        SELECT
            COUNT(*)                                                                    AS total_trades,
            COUNT(*) FILTER (WHERE pnl > 0)                                             AS winning_trades,
            COUNT(*) FILTER (WHERE pnl < 0)                                             AS losing_trades,
            COALESCE(AVG(pnl) FILTER (WHERE pnl > 0), 0)                                AS avg_win_pnl,
            COALESCE(AVG(pnl) FILTER (WHERE pnl < 0), 0)                                AS avg_loss_pnl,
            COALESCE(MAX(pnl), 0)                                                       AS max_win_pnl,
            COALESCE(MIN(pnl), 0)                                                       AS max_loss_pnl,
            COALESCE(SUM(pnl), 0)                                                       AS total_pnl,
            COALESCE(SUM(pnl) FILTER (WHERE pnl > 0), 0)                                AS gross_profit,
            COALESCE(ABS(SUM(pnl) FILTER (WHERE pnl < 0)), 0)                           AS gross_loss,
            COALESCE(AVG(EXIT_TIME - ENTRY_TIME), INTERVAL '0')                         AS avg_holding_period,
            COALESCE(COUNT(*)::NUMERIC / NULLIF(v_day_count, 0), 0)                     AS avg_trades_per_day
        FROM trading.trade_records
        WHERE backtest_id = p_backtest_id
          AND pnl IS NOT NULL
    )
    SELECT
        total_trades,
        winning_trades,
        losing_trades,
        CASE
            WHEN total_trades > 0
            THEN winning_trades::NUMERIC / total_trades
            ELSE 0
        END                                                                             AS win_rate,
        avg_win_pnl,
        avg_loss_pnl,
        max_win_pnl,
        max_loss_pnl,
        total_pnl,
        gross_profit,
        gross_loss,
        CASE
            WHEN gross_loss > 0
            THEN gross_profit / gross_loss
            ELSE NULL
        END                                                                             AS profit_factor,
        avg_holding_period,
        avg_trades_per_day
    FROM trade_stats;
END;
$$;


-- ============================================================================
-- FUNCTION 2: calculate_strategy_risk_metrics
--
-- Computes risk metrics for a strategy across all backtest runs.
-- ============================================================================

CREATE OR REPLACE FUNCTION risk.calculate_strategy_risk_metrics(
    p_strategy_name VARCHAR(128),
    p_start_date    TIMESTAMPTZ DEFAULT '-infinity'::TIMESTAMPTZ,
    p_end_date      TIMESTAMPTZ DEFAULT 'infinity'::TIMESTAMPTZ
)
RETURNS TABLE (
    strategy_name       VARCHAR(128),
    total_backtests     INTEGER,
    avg_sharpe          NUMERIC(10, 6),
    avg_max_drawdown    NUMERIC(10, 6),
    avg_win_rate        NUMERIC(6, 4),
    avg_total_return    NUMERIC(10, 6),
    best_return         NUMERIC(10, 6),
    worst_return        NUMERIC(10, 6),
    calmar_ratio        NUMERIC(10, 6),
    risk_adjusted_return NUMERIC(10, 6)
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        br.strategy_name,
        COUNT(*)                                                                       AS total_backtests,
        AVG(br.sharpe_ratio)                                                           AS avg_sharpe,
        AVG(br.max_drawdown)                                                           AS avg_max_drawdown,
        AVG(br.win_rate)                                                               AS avg_win_rate,
        AVG(br.total_return)                                                           AS avg_total_return,
        MAX(br.total_return)                                                           AS best_return,
        MIN(br.total_return)                                                           AS worst_return,
        CASE
            WHEN AVG(br.max_drawdown) <> 0
            THEN AVG(br.total_return) / ABS(AVG(br.max_drawdown))
            ELSE NULL
        END                                                                            AS calmar_ratio,
        CASE
            WHEN STDDEV(br.total_return) > 0
            THEN AVG(br.total_return) / STDDEV(br.total_return)
            ELSE NULL
        END                                                                            AS risk_adjusted_return
    FROM trading.backtest_results br
    WHERE br.strategy_name = p_strategy_name
      AND br.created_at >= p_start_date
      AND br.created_at <= p_end_date
    GROUP BY br.strategy_name;
END;
$$;


-- ============================================================================
-- FUNCTION 3: detect_drawdown_periods
--
-- Identifies all drawdown periods (peak-to-trough) from daily equity data.
-- ============================================================================

CREATE OR REPLACE FUNCTION risk.detect_drawdown_periods(
    p_backtest_id UUID
)
RETURNS TABLE (
    period_id       INTEGER,
    peak_date       DATE,
    trough_date     DATE,
    recovery_date   DATE,
    drawdown_pct    NUMERIC(10, 6),
    duration_days   INTEGER,
    recovery_days   INTEGER
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    RETURN QUERY
    WITH ranked_equity AS (
        SELECT
            calc_date,
            equity,
            MAX(equity) OVER (ORDER BY calc_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_equity
        FROM risk.daily_risk_metrics
        WHERE backtest_id = p_backtest_id
        ORDER BY calc_date
    ),
    drawdown_periods AS (
        SELECT
            calc_date,
            equity,
            peak_equity,
            (equity - peak_equity) / peak_equity AS drawdown,
            CASE
                WHEN (equity - peak_equity) / peak_equity = 0
                THEN 1
                ELSE 0
            END AS is_peak
        FROM ranked_equity
    ),
    period_groups AS (
        SELECT
            calc_date,
            drawdown,
            is_peak,
            SUM(is_peak) OVER (ORDER BY calc_date ROWS UNBOUNDED PRECEDING) AS period_id
        FROM drawdown_periods
    ),
    period_stats AS (
        SELECT
            period_id,
            MIN(calc_date) AS peak_date,
            MIN(drawdown) AS min_drawdown
        FROM period_groups
        WHERE drawdown < 0
        GROUP BY period_id
    ),
    trough_dates AS (
        SELECT DISTINCT ON (pg.period_id)
            pg.period_id,
            pg.calc_date AS trough_date
        FROM period_groups pg
        JOIN period_stats ps ON pg.period_id = ps.period_id
        WHERE pg.drawdown = ps.min_drawdown
    ),
    recovery_dates AS (
        SELECT DISTINCT ON (pg.period_id)
            pg.period_id,
            pg.calc_date AS recovery_date
        FROM period_groups pg
        WHERE pg.drawdown >= 0
          AND pg.period_id IN (SELECT period_id FROM period_stats WHERE min_drawdown < 0)
        ORDER BY pg.period_id, pg.calc_date
    )
    SELECT
        ps.period_id,
        ps.peak_date,
        td.trough_date,
        rd.recovery_date,
        ps.min_drawdown AS drawdown_pct,
        COALESCE(td.trough_date - ps.peak_date, 0) AS duration_days,
        COALESCE(rd.recovery_date - td.trough_date, NULL) AS recovery_days
    FROM period_stats ps
    LEFT JOIN trough_dates td ON ps.period_id = td.period_id
    LEFT JOIN recovery_dates rd ON ps.period_id = rd.period_id
    WHERE ps.min_drawdown < 0
    ORDER BY ps.period_id;
END;
$$;


-- ============================================================================
-- FUNCTION 4: calculate_var_historical
--
-- Historical Value-at-Risk calculation from daily returns.
-- ============================================================================

CREATE OR REPLACE FUNCTION risk.calculate_var_historical(
    p_backtest_id   UUID,
    p_confidence    NUMERIC(4, 3) DEFAULT 0.95,
    p_lookback_days INTEGER DEFAULT 252
)
RETURNS TABLE (
    calc_date        DATE,
    daily_return     NUMERIC(10, 6),
    var_historical    NUMERIC(10, 6),
    cvar_historical   NUMERIC(10, 6),
    exceeds_var      BOOLEAN
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    RETURN QUERY
    WITH ranked_returns AS (
        SELECT
            calc_date,
            daily_return,
            PERCENTILE_CONT(1 - p_confidence) WITHIN GROUP (
                ORDER BY daily_return ASC
            ) OVER (PARTITION BY backtest_id ORDER BY calc_date ROWS BETWEEN p_lookback_days PRECEDING AND 1 PRECEDING) AS var_est
        FROM risk.daily_risk_metrics
        WHERE backtest_id = p_backtest_id
          AND daily_return IS NOT NULL
    ),
    cvar_calc AS (
        SELECT
            r.calc_date,
            r.daily_return,
            r.var_est,
            AVG(r.daily_return) FILTER (WHERE r.daily_return <= r.var_est)
                OVER (PARTITION BY r.backtest_id ORDER BY r.calc_date ROWS BETWEEN p_lookback_days PRECEDING AND 1 PRECEDING) AS cvar_est
        FROM ranked_returns r
    )
    SELECT
        calc_date,
        daily_return,
        ROUND(var_est, 6) AS var_historical,
        ROUND(cvar_est, 6) AS cvar_historical,
        daily_return < var_est AS exceeds_var
    FROM cvar_calc
    WHERE var_est IS NOT NULL
    ORDER BY calc_date;
END;
$$;


-- ============================================================================
-- FUNCTION 5: monthly_performance_pivot
--
-- Pivots monthly returns into a calendar-year matrix.
-- ============================================================================

CREATE OR REPLACE FUNCTION trading.monthly_performance_pivot(
    p_strategy_name VARCHAR(128)
)
RETURNS TABLE (
    year        INTEGER,
    jan         NUMERIC(10, 6),
    feb         NUMERIC(10, 6),
    mar         NUMERIC(10, 6),
    apr         NUMERIC(10, 6),
    may         NUMERIC(10, 6),
    jun         NUMERIC(10, 6),
    jul         NUMERIC(10, 6),
    aug         NUMERIC(10, 6),
    sep         NUMERIC(10, 6),
    oct         NUMERIC(10, 6),
    nov         NUMERIC(10, 6),
    dec         NUMERIC(10, 6),
    ytd_return  NUMERIC(10, 6)
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    RETURN QUERY
    WITH monthly_returns AS (
        SELECT
            EXTRACT(YEAR FROM entry_time)::INTEGER AS year,
            EXTRACT(MONTH FROM entry_time)::INTEGER AS month,
            SUM(pnl) / NULLIF(
                SUM(quantity * entry_price) FILTER (WHERE side = 'BUY'),
                0
            ) AS monthly_return
        FROM trading.trade_records
        WHERE strategy_name = p_strategy_name
          AND pnl IS NOT NULL
        GROUP BY year, month
    ),
    pivoted AS (
        SELECT
            year,
            MAX(CASE WHEN month = 1  THEN monthly_return END) AS jan,
            MAX(CASE WHEN month = 2  THEN monthly_return END) AS feb,
            MAX(CASE WHEN month = 3  THEN monthly_return END) AS mar,
            MAX(CASE WHEN month = 4  THEN monthly_return END) AS apr,
            MAX(CASE WHEN month = 5  THEN monthly_return END) AS may,
            MAX(CASE WHEN month = 6  THEN monthly_return END) AS jun,
            MAX(CASE WHEN month = 7  THEN monthly_return END) AS jul,
            MAX(CASE WHEN month = 8  THEN monthly_return END) AS aug,
            MAX(CASE WHEN month = 9  THEN monthly_return END) AS sep,
            MAX(CASE WHEN month = 10 THEN monthly_return END) AS oct,
            MAX(CASE WHEN month = 11 THEN monthly_return END) AS nov,
            MAX(CASE WHEN month = 12 THEN monthly_return END) AS dec,
            SUM(monthly_return) OVER (PARTITION BY year ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ytd_return
        FROM monthly_returns
        GROUP BY year, month
    )
    SELECT DISTINCT ON (year)
        year,
        jan, feb, mar, apr, may, jun,
        jul, aug, sep, oct, nov, dec,
        ytd_return
    FROM pivoted
    ORDER BY year;
END;
$$;


-- ============================================================================
-- FUNCTION 6: factor_exposure_analysis
--
-- Computes factor exposure for trades grouped by signal source.
-- ============================================================================

CREATE OR REPLACE FUNCTION trading.factor_exposure_analysis(
    p_backtest_id UUID
)
RETURNS TABLE (
    factor_name     TEXT,
    total_exposure  NUMERIC(20, 6),
    avg_exposure    NUMERIC(20, 6),
    net_pnl         NUMERIC(20, 6),
    trade_count     INTEGER,
    win_count       INTEGER,
    loss_count      INTEGER,
    win_rate        NUMERIC(6, 4),
    avg_holding_hrs NUMERIC(10, 2)
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    RETURN QUERY
    WITH unnested_tags AS (
        SELECT
            unnest(tags) AS factor_tag,
            pnl,
            side,
            quantity,
            entry_price,
            exit_price,
            entry_time,
            exit_time
        FROM trading.trade_records
        WHERE backtest_id = p_backtest_id
          AND tags IS NOT NULL
    )
    SELECT
        factor_tag AS factor_name,
        SUM(
            CASE WHEN side = 'BUY' THEN quantity * entry_price
                 ELSE quantity * entry_price * -1
            END
        ) AS total_exposure,
        AVG(
            CASE WHEN side = 'BUY' THEN quantity * entry_price
                 ELSE quantity * entry_price * -1
            END
        ) AS avg_exposure,
        COALESCE(SUM(pnl), 0) AS net_pnl,
        COUNT(*) AS trade_count,
        COUNT(*) FILTER (WHERE pnl > 0) AS win_count,
        COUNT(*) FILTER (WHERE pnl < 0) AS loss_count,
        CASE
            WHEN COUNT(*) > 0
            THEN COUNT(*) FILTER (WHERE pnl > 0)::NUMERIC / COUNT(*)
            ELSE 0
        END AS win_rate,
        COALESCE(
            AVG(
                EXTRACT(EPOCH FROM (exit_time - entry_time)) / 3600.0
            ),
            0
        ) AS avg_holding_hrs
    FROM unnested_tags
    GROUP BY factor_tag
    ORDER BY net_pnl DESC;
END;
$$;


-- ────────────────────────────────────────────────────────────────────────────
-- Comments & Grants
-- ────────────────────────────────────────────────────────────────────────────

COMMENT ON FUNCTION trading.aggregate_backtest_summary(UUID) IS
    'Returns aggregated trade statistics for a given backtest run.';

COMMENT ON FUNCTION risk.calculate_strategy_risk_metrics(VARCHAR, TIMESTAMPTZ, TIMESTAMPTZ) IS
    'Computes risk metrics (Sharpe, Calmar, drawdown) aggregated across all backtest runs for a strategy.';

COMMENT ON FUNCTION risk.detect_drawdown_periods(UUID) IS
    'Identifies all peak-to-trough drawdown periods with duration and recovery time.';

COMMENT ON FUNCTION risk.calculate_var_historical(UUID, NUMERIC, INTEGER) IS
    'Computes historical Value-at-Risk and Conditional VaR using a rolling window.';

COMMENT ON FUNCTION trading.monthly_performance_pivot(VARCHAR) IS
    'Returns a calendar-year matrix of monthly returns with YTD aggregation.';

COMMENT ON FUNCTION trading.factor_exposure_analysis(UUID) IS
    'Analyzes factor exposure, PnL attribution, and win rates by signal source tag.';