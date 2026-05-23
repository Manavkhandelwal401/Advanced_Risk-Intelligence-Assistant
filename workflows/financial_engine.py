"""
financial_engine.py  –  Data Processing Module
Implements all algorithms described in Chapter 4.4 of the project report:
  1. Profit Margin Calculation
  2. Revenue Trend Analysis
  3. Risk Score Calculation  (0-34 Low | 35-69 Moderate | 70-100 High)
  4. Predictive Risk Projection (30-day)
  5. What-If Scenario Simulation
"""

import math
import statistics
from collections import defaultdict
from datetime import datetime

from database.history_repository import get_financial_data, get_user_starting_cash


def finite_number(value, fallback=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


# ==============================
# MONTHLY AGGREGATION
# ==============================

def group_by_month(data):
    """
    Groups daily/periodic financial records into monthly buckets.
    Each bucket: { "revenue": float, "expense": float }
    """
    monthly = defaultdict(lambda: {"revenue": 0.0, "expense": 0.0})

    for record in data:
        dt = record["date"]
        if isinstance(dt, str):
            try:
                dt = datetime.strptime(dt, "%Y-%m-%d")
            except ValueError:
                dt = datetime.fromisoformat(dt)

        month_key = dt.strftime("%Y-%m")
        monthly[month_key]["revenue"] += max(0.0, finite_number(record["revenue"]))
        monthly[month_key]["expense"] += max(0.0, finite_number(record["expenses"]))

    return dict(sorted(monthly.items()))


# ==============================
# CORE CALCULATIONS
# ==============================

def calculate_totals(monthly_data):
    """Total revenue and expenses across all months."""
    total_revenue = sum(m["revenue"] for m in monthly_data.values())
    total_expenses = sum(m["expense"] for m in monthly_data.values())
    return round(total_revenue, 2), round(total_expenses, 2)


def calculate_profit_margin(revenue, expenses):
    """
    Algorithm 1 (Section 4.4):
    Profit Margin = ((Revenue - Expenses) / Revenue) * 100
    """
    revenue = finite_number(revenue)
    expenses = finite_number(expenses)
    if revenue <= 0:
        return 0.0
    return round(((revenue - expenses) / revenue) * 100, 2)


def calculate_average_monthly_net_cashflow(monthly_data):
    nets = [m["revenue"] - m["expense"] for m in monthly_data.values()]
    if not nets:
        return 0.0
    return round(sum(nets) / len(nets), 2)


def calculate_cash_runway(current_cash, avg_monthly_net):
    """
    Estimates how many days the business can survive at current burn rate.
    Returns None if business is cash-flow positive (no burn).
    """
    current_cash = finite_number(current_cash)
    avg_monthly_net = finite_number(avg_monthly_net)
    if avg_monthly_net >= 0:
        return None                   # Stable – no burn
    monthly_burn = abs(avg_monthly_net)
    if current_cash <= 0:
        return 0
    return round((current_cash / monthly_burn) * 30, 2)


def calculate_revenue_trend(monthly_data):
    """
    Algorithm 2 (Section 4.4):
    Linear regression slope as % of mean revenue.
    Negative = declining, Positive = growing.
    """
    revenues = [m["revenue"] for m in monthly_data.values()]
    if len(revenues) < 2:
        return 0.0

    n = len(revenues)
    x = list(range(n))
    mean_x = sum(x) / n
    mean_y = sum(revenues) / n

    numerator   = sum((x[i] - mean_x) * (revenues[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0 or mean_y == 0:
        return 0.0

    slope = numerator / denominator
    return round((slope / mean_y) * 100, 2)


def calculate_volatility_ratio(monthly_data):
    """Coefficient of variation of monthly revenues (%)."""
    revenues = [m["revenue"] for m in monthly_data.values()]
    if len(revenues) < 2:
        return 0.0
    avg_revenue = sum(revenues) / len(revenues)
    if avg_revenue == 0:
        return 0.0
    stdev = statistics.stdev(revenues)
    return round((stdev / avg_revenue) * 100, 2)


def calculate_expense_growth(monthly_data):
    """Linear regression slope as % of mean monthly expenses."""
    expenses = [m["expense"] for m in monthly_data.values()]
    if len(expenses) < 2:
        return 0.0

    n = len(expenses)
    x = list(range(n))
    mean_x = sum(x) / n
    mean_y = sum(expenses) / n

    if mean_y == 0:
        return 0.0

    numerator = sum((x[i] - mean_x) * (expenses[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    return round((numerator / denominator / mean_y) * 100, 2)


def calculate_loss_streak(monthly_data):
    """Returns consecutive loss months at the end of the dataset."""
    streak = 0
    for item in reversed(list(monthly_data.values())):
        if item["revenue"] - item["expense"] < 0:
            streak += 1
        else:
            break
    return streak


def calculate_cash_coverage_ratio(current_cash, monthly_expenses):
    monthly_expenses = finite_number(monthly_expenses)
    if monthly_expenses <= 0:
        return 999.0
    return round(max(0.0, finite_number(current_cash)) / monthly_expenses, 2)


# ==============================
# RISK MODEL  (Section 4.4 – Algorithm 3)
# ==============================

def calculate_risk_score(
    profit_margin,
    runway_days,
    revenue_trend,
    volatility_ratio,
    expense_growth=0,
    loss_streak=0,
    cash_coverage_ratio=999,
):
    """
    Generates a composite risk score 0–100 from business health indicators.
    Score bands (from report):
        0  – 34  → Low Risk
        35 – 69  → Moderate Risk
        70 – 100 → High Risk
    """
    profit_margin = finite_number(profit_margin)
    revenue_trend = finite_number(revenue_trend)
    volatility_ratio = finite_number(volatility_ratio)
    expense_growth = finite_number(expense_growth)
    loss_streak = max(0, int(finite_number(loss_streak)))
    cash_coverage_ratio = finite_number(cash_coverage_ratio, 999.0)
    runway_days = None if runway_days is None else finite_number(runway_days)
    score = 0

    # Profitability and loss severity
    if profit_margin < -25:
        score += 30
    elif profit_margin < 0:
        score += 24
    elif profit_margin < 5:
        score += 17
    elif profit_margin < 15:
        score += 10

    # Liquidity and runway deterioration
    if runway_days is not None:
        if runway_days < 30:
            score += 25
        elif runway_days < 60:
            score += 19
        elif runway_days < 120:
            score += 12
        elif runway_days < 180:
            score += 6

    if cash_coverage_ratio < 0.5:
        score += 14
    elif cash_coverage_ratio < 1:
        score += 10
    elif cash_coverage_ratio < 2:
        score += 6

    # Revenue decline severity
    if revenue_trend <= -30:
        score += 20
    elif revenue_trend <= -20:
        score += 16
    elif revenue_trend <= -10:
        score += 10
    elif revenue_trend < 0:
        score += 5

    # Expense growth pressure
    if expense_growth >= 25:
        score += 16
    elif expense_growth >= 15:
        score += 11
    elif expense_growth >= 8:
        score += 6

    # Stability and loss probability
    if volatility_ratio >= 70:
        score += 14
    elif volatility_ratio >= 50:
        score += 10
    elif volatility_ratio >= 30:
        score += 6

    if loss_streak >= 3:
        score += 15
    elif loss_streak == 2:
        score += 10
    elif loss_streak == 1:
        score += 5

    # Compounding stress: losses become materially riskier when revenue is
    # falling and costs are rising at the same time.
    if profit_margin < 0 and revenue_trend <= -10:
        score += 8
    if profit_margin < 0 and expense_growth >= 15:
        score += 7

    return min(int(score), 100)


def classify_risk(score):
    """Maps numeric score to risk category string."""
    score = finite_number(score)
    if score >= 70:
        return "High"
    elif score >= 35:
        return "Moderate"
    else:
        return "Low"


# ==============================
# MAIN SUMMARY  (Data Processing Module)
# ==============================

def generate_financial_summary(user_id):
    """
    Master function: fetches data, runs all algorithms,
    and returns a complete financial summary dict.
    """
    data = get_financial_data(user_id)

    if not data:
        raise ValueError(f"No financial data found for User ID {user_id}. Please upload a dataset first.")

    starting_cash   = get_user_starting_cash(user_id)
    monthly_data    = group_by_month(data)

    revenue, expenses       = calculate_totals(monthly_data)
    profit_margin           = calculate_profit_margin(revenue, expenses)
    avg_monthly_net         = calculate_average_monthly_net_cashflow(monthly_data)

    current_cash = starting_cash + sum(
        m["revenue"] - m["expense"] for m in monthly_data.values()
    )

    runway_days       = calculate_cash_runway(current_cash, avg_monthly_net)
    revenue_trend     = calculate_revenue_trend(monthly_data)
    volatility_ratio  = calculate_volatility_ratio(monthly_data)
    expense_growth    = calculate_expense_growth(monthly_data)
    loss_streak       = calculate_loss_streak(monthly_data)
    monthly_expenses  = expenses / max(len(monthly_data), 1)
    cash_coverage     = calculate_cash_coverage_ratio(current_cash, monthly_expenses)

    risk_score  = calculate_risk_score(
        profit_margin,
        runway_days,
        revenue_trend,
        volatility_ratio,
        expense_growth,
        loss_streak,
        cash_coverage,
    )
    risk_level  = classify_risk(risk_score)

    revenue_history = [m["revenue"] for m in monthly_data.values()]
    month_labels    = list(monthly_data.keys())

    # Burn rate: average monthly cash outflow when expenses exceed revenue
    monthly_burn_rate = abs(avg_monthly_net) if avg_monthly_net < 0 else 0.0

    return {
        "user_id":                  user_id,
        "starting_cash":            starting_cash,
        "current_cash":             round(current_cash, 2),
        "revenue":                  revenue,
        "expenses":                 expenses,
        "profit_margin":            profit_margin,
        "avg_monthly_net":          avg_monthly_net,
        "burn_rate":                round(monthly_burn_rate, 2),
        "cash_runway_days":         runway_days,
        "risk_score":               risk_score,
        "risk_level":               risk_level,
        "revenue_trend_percent":    revenue_trend,
        "revenue_volatility_ratio": volatility_ratio,
        "expense_growth_percent":   expense_growth,
        "loss_streak_months":       loss_streak,
        "cash_coverage_ratio":      cash_coverage,
        "revenue_history":          revenue_history,
        "expense_history":          [m["expense"] for m in monthly_data.values()],
        "month_labels":             month_labels
    }


# ==============================
# 30-DAY PREDICTIVE PROJECTION  (Algorithm 4)
# ==============================

def project_30_day_risk(summary):
    """
    Algorithm 4 (Section 4.4):
    Simulates next 30 days based on current revenue trend continuation.
    Returns predicted risk level string.
    """
    months = max(len(summary.get("revenue_history", [])), 1)
    monthly_revenue  = summary["revenue"] / months
    monthly_expenses = summary["expenses"] / months

    projected_revenue = max(
        0.0,
        monthly_revenue * (1 + finite_number(summary["revenue_trend_percent"]) / 100),
    )
    projected_net     = projected_revenue - monthly_expenses
    projected_cash    = summary["current_cash"] + projected_net

    if projected_net < 0:
        monthly_burn      = abs(projected_net)
        projected_runway  = 0 if projected_cash <= 0 else (projected_cash / monthly_burn) * 30
    else:
        projected_runway  = None

    projected_score = calculate_risk_score(
        summary["profit_margin"],
        projected_runway,
        summary["revenue_trend_percent"],
        summary["revenue_volatility_ratio"],
        summary.get("expense_growth_percent", 0),
        summary.get("loss_streak_months", 0) + (1 if projected_net < 0 else 0),
        calculate_cash_coverage_ratio(projected_cash, monthly_expenses),
    )

    return classify_risk(min(projected_score, 100))


# ==============================
# WHAT-IF SCENARIO SIMULATION
# ==============================

def simulate_scenario(summary, revenue_change_pct=0, expense_change_pct=0):
    """
    Simulates financial outcomes under a hypothetical revenue/expense change.
    Displayed values stay on the same full-period basis as the dashboard so
    0% / 0% is an exact baseline match. Monthly averages are still used for
    burn/runway because those metrics are time-based.
    """
    months = max(len(summary["revenue_history"]), 1)

    revenue_change_pct = finite_number(revenue_change_pct)
    expense_change_pct = finite_number(expense_change_pct)
    sim_revenue  = max(0.0, summary["revenue"]  * (1 + revenue_change_pct  / 100))
    sim_expenses = max(0.0, summary["expenses"] * (1 + expense_change_pct  / 100))

    sim_profit        = sim_revenue - sim_expenses
    sim_cash          = finite_number(summary.get("starting_cash", 0)) + sim_profit
    sim_profit_margin = calculate_profit_margin(sim_revenue, sim_expenses)
    sim_avg_monthly_net = sim_profit / months
    sim_runway        = calculate_cash_runway(sim_cash, sim_avg_monthly_net)

    simulated_expense_growth = finite_number(summary.get("expense_growth_percent", 0)) + max(expense_change_pct, 0) / 2
    simulated_revenue_trend = finite_number(summary["revenue_trend_percent"]) + min(revenue_change_pct, 0)
    simulated_volatility = finite_number(summary["revenue_volatility_ratio"]) + abs(revenue_change_pct) * 0.35 + max(expense_change_pct, 0) * 0.2
    simulated_loss_streak = finite_number(summary.get("loss_streak_months", 0))
    if sim_profit < 0 and (revenue_change_pct != 0 or expense_change_pct != 0):
        simulated_loss_streak += 1

    sim_score = calculate_risk_score(
        sim_profit_margin,
        sim_runway,
        simulated_revenue_trend,
        simulated_volatility,
        simulated_expense_growth,
        simulated_loss_streak,
        calculate_cash_coverage_ratio(sim_cash, sim_expenses / months),
    )

    return {
        "simulated_revenue":       round(sim_revenue, 2),
        "simulated_expenses":      round(sim_expenses, 2),
        "simulated_profit":        round(sim_profit, 2),
        "simulated_profit_margin": sim_profit_margin,
        "simulated_cash_position": round(sim_cash, 2),
        "simulated_runway_days":   sim_runway,
        "simulated_risk_score":    sim_score,
        "simulated_risk_level":    classify_risk(sim_score)
    }
