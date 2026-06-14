-- ============================================================================
-- ReinforceTrade — Complex Analytical Queries (10 queries)
-- ============================================================================
--
-- Ad-hoc analytical queries for backtest performance analysis, trade
-- pattern detection, risk monitoring, and strategy comparison.
--
-- Usage:
--     psql -h localhost -U your_user -d reinforcetrade -f sql/analysis_queries.sql
--
-- Note: Some queries reference placeholder UUIDs — replace
-- ``'00000000-0000-0000-0000-000000000000'`` with an actual backtest_id.
--
-- Requires: PostgreSQL 13+, init.sql schema must be loaded first
--
-- Query catalog:
--     1. Monthly Return Pivot (calendar year matrix with YTD)
--     2. Factor Exposure & PnL Attribution (by signal source tag)
--     3. Maximum Drawdown Intervals (peak → trough → recovery)
--     4. Trade Streak & Pattern Analysis (winning/losing streaks)
--     5. Rolling Risk Metrics (21-day and 63-day rolling stats)
--     6. Strategy Performance Ranking (composite score + star rating)
--     7. PnL Distribution Analysis (quartiles, skewness, kurtosis)
--     8. Strategy Correlation Matrix (pairwise daily return correlation)
--     9. Top/Bottom N Trades (outlier P&L analysis)
--    10. Trade Frequency Heatmap (by hour of day × day of week)
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 1: Monthly Return Pivot (Calendar Year Matrix)
--
-- Produces a table like:
--   Year | Jan  | Feb  | ... | Dec  | YTD
-- ────────────────────────────────────────────────────────────────────────────

WITH monthly_returns AS (
    SELECT
        EXTRACT(YEAR FROM tr.entry_time)::INTEGER       AS year,
        EXTRACT(MONTH FROM tr.entry_time)::INTEGER      AS month,
        SUM(tr.pnl) / NULLIF(
            SUM(tr.quantity * tr.entry_price) FILTER (WHERE tr.side = 'BUY'),
            0
        )                                               AS monthly_return
    FROM trading.trade_records tr
    WHERE tr.pnl IS NOT NULL
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
        SUM(monthly_return) OVER (
            PARTITION BY year
            ORDER BY month
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                               AS ytd_return
    FROM monthly_returns
    GROUP BY year, month
)
SELECT DISTINCT ON (year)
    year,
    ROUND(jan::NUMERIC, 6) AS jan,
    ROUND(feb::NUMERIC, 6) AS feb,
    ROUND(mar::NUMERIC, 6) AS mar,
    ROUND(apr::NUMERIC, 6) AS apr,
    ROUND(may::NUMERIC, 6) AS may,
    ROUND(jun::NUMERIC, 6) AS jun,
    ROUND(jul::NUMERIC, 6) AS jul,
    ROUND(aug::NUMERIC, 6) AS aug,
    ROUND(sep::NUMERIC, 6) AS sep,
    ROUND(oct::NUMERIC, 6) AS oct,
    ROUND(nov::NUMERIC, 6) AS nov,
    ROUND(dec::NUMERIC, 6) AS dec,
    ROUND(ytd_return::NUMERIC, 6) AS ytd_return
FROM pivoted
ORDER BY year DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 2: Factor Exposure & PnL Attribution
--
-- Groups trades by signal source tag and computes:
--   - Total / average exposure (in base currency)
--   - Net PnL per factor
--   - Win rate and average holding time
-- ────────────────────────────────────────────────────────────────────────────

SELECT
    unnest(tr.tags)                                     AS factor_name,
    SUM(
        CASE
            WHEN tr.side = 'BUY'  THEN tr.quantity * tr.entry_price
            WHEN tr.side = 'SELL' THEN tr.quantity * tr.entry_price * -1
            ELSE 0
        END
    )                                                   AS total_exposure_base,
    AVG(
        CASE
            WHEN tr.side = 'BUY'  THEN tr.quantity * tr.entry_price
            WHEN tr.side = 'SELL' THEN tr.quantity * tr.entry_price * -1
            ELSE 0
        END
    )                                                   AS avg_exposure_base,
    COUNT(*)                                            AS trade_count,
    COUNT(*) FILTER (WHERE tr.pnl > 0)                  AS win_count,
    COUNT(*) FILTER (WHERE tr.pnl < 0)                  AS loss_count,
    ROUND(
        CASE
            WHEN COUNT(*) > 0
            THEN COUNT(*) FILTER (WHERE tr.pnl > 0)::NUMERIC / COUNT(*)
            ELSE 0
        END,
        4
    )                                                   AS win_rate,
    ROUND(COALESCE(SUM(tr.pnl), 0), 4)                AS net_pnl,
    ROUND(COALESCE(AVG(tr.pnl), 0), 4)                AS avg_pnl,
    ROUND(
        COALESCE(
            AVG(
                EXTRACT(EPOCH FROM (tr.exit_time - tr.entry_time)) / 3600.0
            ),
            0
        ),
        2
    )                                                   AS avg_holding_hours,
    ROUND(
        CASE
            WHEN SUM(
                CASE
                    WHEN tr.side = 'BUY'  THEN tr.quantity * tr.entry_price
                    WHEN tr.side = 'SELL' THEN tr.quantity * tr.entry_price * -1
                    ELSE 0
                END
            ) <> 0
            THEN COALESCE(SUM(tr.pnl), 0) / SUM(
                CASE
                    WHEN tr.side = 'BUY'  THEN tr.quantity * tr.entry_price
                    WHEN tr.side = 'SELL' THEN tr.quantity * tr.entry_price * -1
                    ELSE 0
                END
            )
            ELSE NULL
        END,
        6
    )                                                   AS return_on_exposure
FROM trading.trade_records tr
WHERE tr.tags IS NOT NULL
  AND tr.pnl IS NOT NULL
GROUP BY factor_name
ORDER BY net_pnl DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 3: Maximum Drawdown Intervals
--
-- Identifies all drawdown periods with peak, trough and recovery dates.
-- Uses window functions to track running maximum equity.
-- ────────────────────────────────────────────────────────────────────────────

WITH ranked_equity AS (
    SELECT
        dm.calc_date,
        dm.equity,
        MAX(dm.equity) OVER (
            ORDER BY dm.calc_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                               AS peak_equity
    FROM risk.daily_risk_metrics dm
    WHERE dm.backtest_id = '00000000-0000-0000-0000-000000000000'  -- << REPLACE with actual backtest_id
),
drawdown_periods AS (
    SELECT
        calc_date,
        equity,
        peak_equity,
        (equity - peak_equity) / peak_equity            AS drawdown,
        CASE
            WHEN (equity - peak_equity) / peak_equity = 0
            THEN 1
            ELSE 0
        END                                             AS is_peak_flag
    FROM ranked_equity
),
period_groups AS (
    SELECT
        calc_date,
        drawdown,
        is_peak_flag,
        SUM(is_peak_flag) OVER (
            ORDER BY calc_date
            ROWS UNBOUNDED PRECEDING
        )                                               AS drawdown_period_id
    FROM drawdown_periods
    WHERE drawdown < 0
),
period_stats AS (
    SELECT
        drawdown_period_id,
        MIN(calc_date)                                  AS peak_date,
        MIN(drawdown)                                   AS max_drawdown_pct,
        COUNT(*)                                        AS duration_days
    FROM period_groups
    GROUP BY drawdown_period_id
)
SELECT
    ps.drawdown_period_id                               AS period_id,
    ps.peak_date,
    ps.peak_date + ps.duration_days                     AS trough_date,
    ROUND(ps.max_drawdown_pct::NUMERIC, 6)              AS max_drawdown_pct,
    ps.duration_days                                    AS drawdown_duration_days,
    RANK() OVER (ORDER BY ps.max_drawdown_pct ASC)      AS severity_rank
FROM period_stats ps
ORDER BY ps.max_drawdown_pct ASC
LIMIT 20;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 4: Trade Clustering & Pattern Analysis
--
-- Detects consecutive winning/losing streaks and trade frequency patterns.
-- ────────────────────────────────────────────────────────────────────────────

WITH trade_streaks AS (
    SELECT
        tr.entry_time::DATE                             AS trade_date,
        tr.side,
        tr.pnl,
        CASE
            WHEN tr.pnl > 0 THEN 1
            WHEN tr.pnl < 0 THEN -1
            ELSE 0
        END                                             AS result_sign,
        ROW_NUMBER() OVER (ORDER BY tr.entry_time)
            - ROW_NUMBER() OVER (
                PARTITION BY CASE
                    WHEN tr.pnl > 0 THEN 'win'
                    WHEN tr.pnl < 0 THEN 'loss'
                    ELSE 'flat'
                END
                ORDER BY tr.entry_time
            )                                           AS streak_group
    FROM trading.trade_records tr
    WHERE tr.pnl IS NOT NULL
),
streak_summary AS (
    SELECT
        CASE
            WHEN result_sign = 1  THEN 'WINNING'
            WHEN result_sign = -1 THEN 'LOSING'
            ELSE 'FLAT'
        END                                             AS streak_type,
        COUNT(*)                                        AS streak_length,
        SUM(tr.pnl)                                    AS streak_total_pnl,
        AVG(tr.pnl)                                    AS streak_avg_pnl,
        MIN(tr.entry_time::DATE)                        AS streak_start,
        MAX(tr.entry_time::DATE)                        AS streak_end
    FROM trade_streaks tr
    GROUP BY result_sign, streak_group
)
SELECT
    streak_type,
    COUNT(*)                                            AS streak_count,
    MIN(streak_length)                                  AS min_streak,
    MAX(streak_length)                                  AS max_streak,
    ROUND(AVG(streak_length), 2)                        AS avg_streak_length,
    ROUND(AVG(streak_total_pnl), 4)                     AS avg_streak_pnl,
    ROUND(MAX(streak_total_pnl), 4)                     AS best_streak_pnl,
    ROUND(MIN(streak_total_pnl), 4)                     AS worst_streak_pnl
FROM streak_summary
GROUP BY streak_type
ORDER BY streak_type DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 5: Rolling Risk Metrics
--
-- Computes rolling 21-day (monthly) and 63-day (quarterly) risk statistics
-- for a specific backtest run.
-- ────────────────────────────────────────────────────────────────────────────

WITH rolling_stats AS (
    SELECT
        dm.calc_date,
        dm.equity,
        dm.daily_return,
        dm.drawdown,
        AVG(dm.daily_return) OVER (
            ORDER BY dm.calc_date
            ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
        )                                               AS rolling_return_21d,
        STDDEV(dm.daily_return) OVER (
            ORDER BY dm.calc_date
            ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
        )                                               AS rolling_vol_21d,
        AVG(dm.daily_return) OVER (
            ORDER BY dm.calc_date
            ROWS BETWEEN 62 PRECEDING AND CURRENT ROW
        )                                               AS rolling_return_63d,
        STDDEV(dm.daily_return) OVER (
            ORDER BY dm.calc_date
            ROWS BETWEEN 62 PRECEDING AND CURRENT ROW
        )                                               AS rolling_vol_63d,
        MIN(dm.drawdown) OVER (
            ORDER BY dm.calc_date
            ROWS BETWEEN 62 PRECEDING AND CURRENT ROW
        )                                               AS rolling_max_dd_63d
    FROM risk.daily_risk_metrics dm
    WHERE dm.backtest_id = '00000000-0000-0000-0000-000000000000'  -- << REPLACE with actual backtest_id
)
SELECT
    calc_date,
    ROUND(equity::NUMERIC, 2)                          AS equity,
    ROUND(daily_return::NUMERIC, 6)                    AS daily_return,
    ROUND(drawdown::NUMERIC, 6)                        AS current_drawdown,
    ROUND(rolling_return_21d::NUMERIC * 252, 6)        AS annualized_return_21d,
    ROUND(rolling_vol_21d::NUMERIC * SQRT(252), 6)     AS annualized_vol_21d,
    CASE
        WHEN rolling_vol_21d > 0
        THEN ROUND(
            (rolling_return_21d / rolling_vol_21d * SQRT(252))::NUMERIC,
            4
        )
        ELSE NULL
    END                                                 AS rolling_sharpe_21d,
    ROUND(rolling_max_dd_63d::NUMERIC, 6)               AS rolling_max_dd_63d,
    CASE
        WHEN rolling_max_dd_63d < 0
        THEN ROUND(
            (rolling_return_63d / ABS(rolling_max_dd_63d))::NUMERIC,
            4
        )
        ELSE NULL
    END                                                 AS rolling_calmar_63d
FROM rolling_stats
WHERE rolling_vol_21d IS NOT NULL
ORDER BY calc_date DESC
LIMIT 100;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 6: Strategy Performance Ranking
--
-- Ranks all strategies by composite performance score.
-- ────────────────────────────────────────────────────────────────────────────

WITH strategy_metrics AS (
    SELECT
        br.strategy_name,
        COUNT(*)                                        AS num_backtests,
        AVG(br.total_return)                            AS avg_return,
        AVG(br.sharpe_ratio)                            AS avg_sharpe,
        AVG(ABS(br.max_drawdown))                       AS avg_max_dd,
        AVG(br.win_rate)                                AS avg_win_rate,
        AVG(br.total_trades)                            AS avg_trades,
        STDDEV(br.total_return)                         AS return_volatility
    FROM trading.backtest_results br
    GROUP BY br.strategy_name
),
composite_score AS (
    SELECT
        strategy_name,
        num_backtests,
        ROUND(avg_return::NUMERIC, 6)                   AS avg_return,
        ROUND(avg_sharpe::NUMERIC, 4)                   AS avg_sharpe,
        ROUND(avg_max_dd::NUMERIC, 6)                   AS avg_max_dd,
        ROUND(avg_win_rate::NUMERIC, 4)                 AS avg_win_rate,
        ROUND(avg_trades::NUMERIC, 0)::INTEGER          AS avg_trades,
        -- Composite score: weighted combination of key metrics
        ROUND(
            (
                COALESCE(avg_return, 0) * 0.30 +
                COALESCE(avg_sharpe, 0) * 0.25 +
                COALESCE(avg_win_rate, 0) * 0.20 -
                COALESCE(avg_max_dd, 0) * 0.15 -
                COALESCE(return_volatility, 0) * 0.10
            )::NUMERIC,
            6
        )                                               AS composite_score
    FROM strategy_metrics
)
SELECT
    ROW_NUMBER() OVER (ORDER BY composite_score DESC)   AS rank,
    strategy_name,
    avg_return,
    avg_sharpe,
    avg_max_dd,
    avg_win_rate,
    avg_trades,
    composite_score,
    CASE
        WHEN composite_score >= 0.05 THEN '⭐⭐⭐⭐⭐'
        WHEN composite_score >= 0.03 THEN '⭐⭐⭐⭐'
        WHEN composite_score >= 0.01 THEN '⭐⭐⭐'
        WHEN composite_score >= 0.00 THEN '⭐⭐'
        ELSE '⭐'
    END                                                 AS rating
FROM composite_score
ORDER BY composite_score DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 7: PnL Distribution Analysis
--
-- Statistical distribution of trade PnL values.
-- ────────────────────────────────────────────────────────────────────────────

WITH trade_pnl AS (
    SELECT
        tr.pnl
    FROM trading.trade_records tr
    WHERE tr.pnl IS NOT NULL
),
distribution AS (
    SELECT
        COUNT(*)                                        AS total_trades,
        ROUND(MIN(tr.pnl)::NUMERIC, 4)                  AS min_pnl,
        ROUND(AVG(tr.pnl)::NUMERIC, 4)                  AS mean_pnl,
        ROUND(MAX(tr.pnl)::NUMERIC, 4)                  AS max_pnl,
        ROUND(STDDEV(tr.pnl)::NUMERIC, 4)               AS stddev_pnl,
        ROUND(
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY tr.pnl)::NUMERIC,
            4
        )                                               AS q1_pnl,
        ROUND(
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY tr.pnl)::NUMERIC,
            4
        )                                               AS median_pnl,
        ROUND(
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY tr.pnl)::NUMERIC,
            4
        )                                               AS q3_pnl,
        ROUND(
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY tr.pnl)::NUMERIC,
            4
        )                                               AS p90_pnl,
        ROUND(
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY tr.pnl)::NUMERIC,
            4
        )                                               AS p95_pnl,
        ROUND(
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY tr.pnl)::NUMERIC,
            4
        )                                               AS p99_pnl,
        -- Skewness
        ROUND(
            (AVG((tr.pnl - AVG(tr.pnl) OVER ()) ^ 3) / NULLIF(STDDEV(tr.pnl) ^ 3, 0))::NUMERIC,
            4
        )                                               AS skewness,
        -- Kurtosis
        ROUND(
            (AVG((tr.pnl - AVG(tr.pnl) OVER ()) ^ 4) / NULLIF(STDDEV(tr.pnl) ^ 4, 0) - 3)::NUMERIC,
            4
        )                                               AS excess_kurtosis
    FROM trade_pnl tr
)
SELECT * FROM distribution;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 8: Strategy Correlation Matrix
--
-- Computes pairwise correlation of daily returns between strategies.
-- ────────────────────────────────────────────────────────────────────────────

WITH strategy_daily_returns AS (
    SELECT
        br.strategy_name,
        dm.calc_date,
        dm.daily_return
    FROM risk.daily_risk_metrics dm
    JOIN trading.backtest_results br ON dm.backtest_id = br.id
    WHERE dm.daily_return IS NOT NULL
),
correlation_pairs AS (
    SELECT
        a.strategy_name                                AS strategy_a,
        b.strategy_name                                AS strategy_b,
        CORR(a.daily_return, b.daily_return)            AS correlation
    FROM strategy_daily_returns a
    JOIN strategy_daily_returns b
        ON a.calc_date = b.calc_date
        AND a.strategy_name < b.strategy_name
    GROUP BY a.strategy_name, b.strategy_name
)
SELECT
    strategy_a,
    strategy_b,
    ROUND(correlation::NUMERIC, 4)                      AS correlation,
    CASE
        WHEN ABS(correlation) >= 0.8 THEN 'Strong'
        WHEN ABS(correlation) >= 0.5 THEN 'Moderate'
        WHEN ABS(correlation) >= 0.3 THEN 'Weak'
        ELSE 'Negligible'
    END                                                 AS correlation_strength
FROM correlation_pairs
ORDER BY ABS(correlation) DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 9: Top/bottom N trades by PnL (for outlier analysis)
-- ────────────────────────────────────────────────────────────────────────────

(
    SELECT
        tr.id,
        tr.strategy_name,
        tr.symbol,
        tr.side,
        tr.entry_time,
        tr.exit_time,
        tr.pnl,
        tr.pnl_pct,
        unnest(tr.tags)                                 AS factor_tag,
        'BEST'                                          AS category
    FROM trading.trade_records tr
    WHERE tr.pnl IS NOT NULL
    ORDER BY tr.pnl DESC
    LIMIT 10
)
UNION ALL
(
    SELECT
        tr.id,
        tr.strategy_name,
        tr.symbol,
        tr.side,
        tr.entry_time,
        tr.exit_time,
        tr.pnl,
        tr.pnl_pct,
        unnest(tr.tags)                                 AS factor_tag,
        'WORST'                                         AS category
    FROM trading.trade_records tr
    WHERE tr.pnl IS NOT NULL
    ORDER BY tr.pnl ASC
    LIMIT 10
)
ORDER BY category, pnl DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- QUERY 10: Time-based Trade Frequency Heatmap
--
-- Shows trade frequency by hour of day and day of week.
-- ────────────────────────────────────────────────────────────────────────────

SELECT
    EXTRACT(DOW FROM tr.entry_time)::INTEGER            AS day_of_week,
    EXTRACT(HOUR FROM tr.entry_time)::INTEGER            AS hour_of_day,
    COUNT(*)                                            AS trade_count,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER () * 100, 2) AS pct_of_total
FROM trading.trade_records tr
GROUP BY day_of_week, hour_of_day
ORDER BY day_of_week, hour_of_day;