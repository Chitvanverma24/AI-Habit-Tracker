"""

AI Habit Tracker SaaS - User Analytics Dashboard
Production Commercial Quality — Linear / Supabase / Vercel Aesthetics

"""

from datetime import datetime, timedelta, date
from typing import Dict, Any, List
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from database import get_db
from auth import auth
import utils
import ui_components


def init_session_state() -> None:
    if "analytics_timeframe" not in st.session_state:
        st.session_state.analytics_timeframe = 30



# Caching & Data Ingestion

@st.cache_data(show_spinner=False, ttl=180)
def fetch_analytics_raw_data() -> Dict[str, pd.DataFrame]:
    """Fetch raw database tables into pandas DataFrames.
    
    NOTE: For scalability, we limit the data fetched. Profile and habit
    data is fetched with SELECT *, but habit_logs are limited to recent
    data to avoid loading millions of rows.
    """
    db = get_db()
    dfs = {}

    # Profiles — needed for user growth chart and counts
    try:
        res = db.table("profiles").select("id, display_name, is_admin, timezone, created_at").execute()
        dfs["profiles"] = pd.DataFrame(res.data or [])
    except Exception:
        dfs["profiles"] = pd.DataFrame()

    # Habits — needed for frequency distribution
    try:
        res = db.table("habits").select("id, user_id, frequency, created_at").execute()
        dfs["habits"] = pd.DataFrame(res.data or [])
    except Exception:
        dfs["habits"] = pd.DataFrame()

    # Habit logs — limit to last 365 days for performance
    try:
        cutoff = (utils.now() - timedelta(days=365)).isoformat()
        res = db.table("habit_logs").select("id, user_id, log_date, status, created_at").gte("created_at", cutoff).execute()
        dfs["habit_logs"] = pd.DataFrame(res.data or [])
    except Exception:
        dfs["habit_logs"] = pd.DataFrame()

    # Journal entries — only need count and dates
    try:
        res = db.table("journal_entries").select("id, user_id, entry_date").execute()
        dfs["journal_entries"] = pd.DataFrame(res.data or [])
    except Exception:
        dfs["journal_entries"] = pd.DataFrame()

    # Achievements — only need count
    try:
        res = db.table("achievements").select("id, user_id, earned_at").execute()
        dfs["achievements"] = pd.DataFrame(res.data or [])
    except Exception:
        dfs["achievements"] = pd.DataFrame()

    # Process Datetime Columns safely
    def _safe_to_datetime(series):
        dt_s = pd.to_datetime(series, errors='coerce')
        try:
            if getattr(dt_s.dt, 'tz', None) is not None:
                return dt_s.dt.tz_convert(None)
            return dt_s.dt.tz_localize(None)
        except Exception:
            return dt_s

    if not dfs["profiles"].empty and "created_at" in dfs["profiles"].columns:
        dfs["profiles"]["created_at"] = _safe_to_datetime(dfs["profiles"]["created_at"])

    if not dfs["habits"].empty and "created_at" in dfs["habits"].columns:
        dfs["habits"]["created_at"] = _safe_to_datetime(dfs["habits"]["created_at"])

    if not dfs["habit_logs"].empty:
        if "log_date" in dfs["habit_logs"].columns:
            dfs["habit_logs"]["log_date"] = pd.to_datetime(dfs["habit_logs"]["log_date"], errors='coerce').dt.date
        if "created_at" in dfs["habit_logs"].columns:
            dfs["habit_logs"]["created_at"] = _safe_to_datetime(dfs["habit_logs"]["created_at"])

    if not dfs["journal_entries"].empty and "entry_date" in dfs["journal_entries"].columns:
        dfs["journal_entries"]["entry_date"] = pd.to_datetime(dfs["journal_entries"]["entry_date"], errors='coerce').dt.date

    if not dfs["achievements"].empty and "earned_at" in dfs["achievements"].columns:
        dfs["achievements"]["earned_at"] = _safe_to_datetime(dfs["achievements"]["earned_at"])

    return dfs


def calc_highest_global_streak(logs: pd.DataFrame) -> int:
    """Calculate highest global user streak across platform."""
    if logs.empty or "status" not in logs.columns or "log_date" not in logs.columns:
        return 0
    c = logs[logs["status"] == "completed"].copy()
    if c.empty:
        return 0
    try:
        c = c.drop_duplicates(["user_id", "log_date"]).sort_values(["user_id", "log_date"])
        c["prev"] = c.groupby("user_id")["log_date"].shift(1)
        c["consec"] = (pd.to_datetime(c["log_date"]) - pd.to_datetime(c["prev"])).dt.days == 1
        c["streak_group"] = c.groupby("user_id")["consec"].transform(lambda x: (~x).cumsum())
        return int(c.groupby(["user_id", "streak_group"]).size().max() or 0)
    except Exception:
        return 0



# Plotly Theme Styling Helper

def apply_saas_plotly_theme(fig: go.Figure, height: int = 300) -> go.Figure:
    """Applies a crisp, modern SaaS theme matching Vercel/Supabase blue palette."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", size=12, color="#475569"),
        margin=dict(l=15, r=15, t=30, b=25),
        height=height,
        hoverlabel=dict(
            bgcolor="#0f172a",
            font_size=12,
            font_family="Inter, sans-serif",
            font_color="#ffffff"
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=False,
            showline=True,
            linecolor="#e2e8f0",
            tickfont=dict(size=11, color="#64748b")
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=False,
            showline=False,
            tickfont=dict(size=11, color="#64748b")
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#475569")
        )
    )
    return fig



# Visualization Components

def render_dau_chart(logs: pd.DataFrame, days: int) -> None:
    """Daily Active Users (DAU) smooth line chart."""
    st.markdown("##### 📈 Daily Active Users (DAU)")
    if logs.empty or "log_date" not in logs.columns or "user_id" not in logs.columns:
        ui_components.render_empty_state("📈", "No activity recorded", f"Waiting for active user logs in the last {days} days.")
        return

    cutoff = utils.today() - timedelta(days=days - 1)
    df = logs[logs["log_date"] >= cutoff].copy()
    if df.empty:
        ui_components.render_empty_state("📈", "No activity recorded", f"No active user logs found in the last {days} days.")
        return

    dau = df.groupby("log_date")["user_id"].nunique().reset_index(name="active_users")

    # Complete date range fill
    date_range = [cutoff + timedelta(days=i) for i in range(days)]
    range_df = pd.DataFrame({"log_date": date_range})
    dau = pd.merge(range_df, dau, on="log_date", how="left").fillna({"active_users": 0})
    dau["active_users"] = dau["active_users"].astype(int)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dau["log_date"],
        y=dau["active_users"],
        mode="lines+markers",
        name="Active Users",
        line=dict(shape="spline", width=3, color="#2563eb"),
        marker=dict(size=6, color="#1d4ed8", symbol="circle"),
        hovertemplate="<b>%{x|%b %d, %Y}</b><br>Active Users: <b>%{y}</b><extra></extra>"
    ))
    apply_saas_plotly_theme(fig, height=280)
    st.plotly_chart(fig, use_container_width=True)


def render_user_growth_chart(profiles: pd.DataFrame, days: int) -> None:
    """Cumulative User Growth Area Chart."""
    st.markdown("##### 👥 Cumulative User Growth")
    if profiles.empty or "created_at" not in profiles.columns:
        ui_components.render_empty_state("👥", "No registration data", f"No user growth recorded yet.")
        return

    cutoff = utils.today() - timedelta(days=days - 1)
    cutoff_dt = pd.to_datetime(cutoff)

    df = profiles.copy()
    df["reg_date"] = df["created_at"].dt.date
    df = df[df["reg_date"].notna()]

    if df.empty:
        ui_components.render_empty_state("👥", "No registrations", f"No new registrations in the last {days} days.")
        return

    growth = df.groupby("reg_date").size().reset_index(name="new_users")
    date_range = [cutoff + timedelta(days=i) for i in range(days)]
    range_df = pd.DataFrame({"reg_date": date_range})
    growth = pd.merge(range_df, growth, on="reg_date", how="left").fillna({"new_users": 0})

    # Prior cumulative baseline
    prior_users = len(df[df["reg_date"] < cutoff])
    growth["cumulative"] = prior_users + growth["new_users"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=growth["reg_date"],
        y=growth["cumulative"],
        mode="lines",
        name="Total Users",
        fill="tozeroy",
        line=dict(shape="spline", width=2.5, color="#3b82f6"),
        fillcolor="rgba(59, 130, 246, 0.12)",
        hovertemplate="<b>%{x|%b %d, %Y}</b><br>Total Platform Users: <b>%{y}</b><extra></extra>"
    ))
    apply_saas_plotly_theme(fig, height=280)
    st.plotly_chart(fig, use_container_width=True)


def render_completion_gauge(logs: pd.DataFrame) -> None:
    """Plotly Semicircular Completion Rate Gauge."""
    st.markdown("##### 🎯 Overall Habit Completion Rate")
    if logs.empty or "status" not in logs.columns:
        ui_components.render_empty_state("🎯", "No completion logs", "Waiting for habit execution data.")
        return

    total_logs = len(logs)
    completed = len(logs[logs["status"] == "completed"])
    rate = round((completed / total_logs) * 100, 1) if total_logs > 0 else 0.0

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=rate,
        number={'suffix': "%", 'font': {'size': 36, 'color': '#0f172a', 'family': 'Inter'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#cbd5e1"},
            'bar': {'color': "#2563eb", 'thickness': 0.75},
            'bgcolor': "#f8fafc",
            'bordercolor': "#e2e8f0",
            'steps': [
                {'range': [0, 50], 'color': "rgba(239, 68, 68, 0.08)"},
                {'range': [50, 80], 'color': "rgba(245, 158, 11, 0.08)"},
                {'range': [80, 100], 'color': "rgba(16, 185, 129, 0.08)"}
            ]
        }
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=25, b=10),
        height=220
    )
    st.plotly_chart(fig, use_container_width=True)


def render_frequency_distribution(habits: pd.DataFrame) -> None:
    """Horizontal Bar Chart of Habit Frequencies."""
    st.markdown("##### 📊 Habit Frequencies")
    if habits.empty or "frequency" not in habits.columns:
        ui_components.render_empty_state("📊", "No habits created", "No habit category data available.")
        return

    dist = habits["frequency"].str.capitalize().value_counts().reset_index()
    dist.columns = ["Frequency", "Count"]

    fig = px.bar(
        dist,
        x="Count",
        y="Frequency",
        orientation="h",
        text="Count",
        color_discrete_sequence=["#2563eb"]
    )
    fig.update_traces(
        textposition="auto",
        hovertemplate="Frequency: <b>%{y}</b><br>Habits: <b>%{x}</b><extra></extra>",
        marker_color="#2563eb"
    )
    apply_saas_plotly_theme(fig, height=220)
    fig.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)


def render_habit_creation_trend(habits: pd.DataFrame, days: int) -> None:
    """Vertical Bar Chart of Habit Creation Trend."""
    st.markdown("##### ➕ Habit Creation Trend")
    if habits.empty or "created_at" not in habits.columns:
        ui_components.render_empty_state("➕", "No creation trend", f"No new habits added in the last {days} days.")
        return

    cutoff = utils.today() - timedelta(days=days - 1)
    df = habits.copy()
    df["c_date"] = df["created_at"].dt.date
    df = df[df["c_date"] >= cutoff]

    if df.empty:
        ui_components.render_empty_state("➕", "No new habits", f"No habits created in the last {days} days.")
        return

    counts = df.groupby("c_date").size().reset_index(name="habits_created")
    date_range = [cutoff + timedelta(days=i) for i in range(days)]
    range_df = pd.DataFrame({"c_date": date_range})
    counts = pd.merge(range_df, counts, on="c_date", how="left").fillna({"habits_created": 0})
    counts["habits_created"] = counts["habits_created"].astype(int)

    fig = px.bar(
        counts,
        x="c_date",
        y="habits_created",
        color_discrete_sequence=["#3b82f6"]
    )
    fig.update_traces(
        hovertemplate="<b>%{x|%b %d, %Y}</b><br>Habits Created: <b>%{y}</b><extra></extra>"
    )
    apply_saas_plotly_theme(fig, height=250)
    st.plotly_chart(fig, use_container_width=True)


def render_weekly_activity_heatmap(logs: pd.DataFrame) -> None:
    """Weekly Habit Execution Heatmap Matrix."""
    st.markdown("##### 🗓️ Activity Density (Day of Week)")
    if logs.empty or "log_date" not in logs.columns:
        ui_components.render_empty_state("🗓️", "No log density", "Waiting for habit execution activity.")
        return

    df = logs[logs["status"] == "completed"].copy()
    if df.empty:
        ui_components.render_empty_state("🗓️", "No completed logs", "No completed habit activity recorded.")
        return

    df["dt"] = pd.to_datetime(df["log_date"])
    df["day_name"] = df["dt"].dt.day_name()
    df["hour"] = df["dt"].dt.hour

    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_counts = df["day_name"].value_counts().reindex(days_order, fill_value=0).reset_index()
    day_counts.columns = ["Day", "Completions"]

    fig = px.bar(
        day_counts,
        x="Day",
        y="Completions",
        color="Completions",
        color_continuous_scale="Blues"
    )
    fig.update_coloraxes(showscale=False)
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Total Completions: <b>%{y}</b><extra></extra>"
    )
    apply_saas_plotly_theme(fig, height=250)
    st.plotly_chart(fig, use_container_width=True)


def render_top_active_users_table(dfs: Dict[str, pd.DataFrame]) -> None:
    """Modern Data Table of Top Platform Users."""
    st.markdown("##### 🏆 Top Active Users Leaderboard")
    profiles, habits, logs = dfs["profiles"], dfs["habits"], dfs["habit_logs"]

    if profiles.empty:
        ui_components.render_empty_state("🏆", "No users found", "No registered users on the platform.")
        return

    df = profiles.copy()

    # Aggregate habits count
    if not habits.empty and "user_id" in habits.columns:
        hc = habits.groupby("user_id").size().reset_index(name="habits_count")
        df = pd.merge(df, hc, left_on="id", right_on="user_id", how="left")
        df["habits_count"] = df["habits_count"].fillna(0).astype(int)
    else:
        df["habits_count"] = 0

    # Aggregate completions count
    if not logs.empty and "user_id" in logs.columns and "status" in logs.columns:
        lc = logs[logs["status"] == "completed"].groupby("user_id").size().reset_index(name="completions_count")
        df = pd.merge(df, lc, left_on="id", right_on="user_id", how="left")
        df["completions_count"] = df["completions_count"].fillna(0).astype(int)
    else:
        df["completions_count"] = 0

    df["is_admin_str"] = df["is_admin"].apply(lambda x: "Admin 🛡️" if x else "User 👤")
    df = df.sort_values(by=["completions_count", "habits_count"], ascending=False).head(10)

    # Modern styled dataframe display
    display_df = df[["display_name", "is_admin_str", "habits_count", "completions_count", "timezone"]].copy()
    display_df.columns = ["User Name", "Role", "Active Habits", "Total Completions", "Timezone"]
    display_df.index = np.arange(1, len(display_df) + 1)

    st.dataframe(
        display_df,
        use_container_width=True,
        column_config={
            "User Name": st.column_config.TextColumn("User Name", width="medium"),
            "Role": st.column_config.TextColumn("Role", width="small"),
            "Active Habits": st.column_config.NumberColumn("Active Habits", format="%d"),
            "Total Completions": st.column_config.NumberColumn("Total Completions", format="%d 🔥"),
            "Timezone": st.column_config.TextColumn("Timezone", width="small")
        }
    )


def render_recent_activity_timeline(dfs: Dict[str, pd.DataFrame]) -> None:
    """Timeline feed of recent platform activities."""
    st.markdown("##### ⚡ Recent Platform Activity Stream")
    logs = dfs["habit_logs"]

    if logs.empty or "log_date" not in logs.columns:
        ui_components.render_empty_state("⚡", "No recent activity", "No habit logs recorded recently.")
        return

    recent_logs = logs.sort_values("created_at" if "created_at" in logs.columns else "log_date", ascending=False).head(8)

    with st.container(border=True):
        for _, row in recent_logs.iterrows():
            st_date = row.get("log_date", utils.today())
            status = row.get("status", "completed")
            badge = "✅ Completed" if status == "completed" else ("⏭️ Skipped" if status == "skipped" else "❌ Failed")
            
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**Habit Log Entry** &bull; {badge}")
            c2.caption(f"{st_date}")
            st.divider()



# Main Analytics Page Entrypoint

def main() -> None:
    auth.require_admin()
    init_session_state()

    ui_components.render_hero("📈 User Analytics", "Deep dive into user engagement, habit completion trends, and retention.", icon="📈")

    col_tf, _ = st.columns([1, 2])
    with col_tf:
        tf = st.selectbox("Timeframe (Days)", [7, 30, 90, 365], index=1, key="a_tf")
        st.session_state.analytics_timeframe = tf

    dfs = fetch_analytics_raw_data()
    profiles, habits, logs, achievements = dfs["profiles"], dfs["habits"], dfs["habit_logs"], dfs["achievements"]

    
    # Top KPI Metrics Cards
    
    c1, c2, c3, c4 = st.columns(4)

    total_users = len(profiles)
    active_users = 0
    if not logs.empty and "log_date" in logs.columns and "user_id" in logs.columns:
        cutoff = utils.today() - timedelta(days=tf)
        active_users = logs[logs["log_date"] >= cutoff]["user_id"].nunique()

    comp_rate = 0.0
    if not logs.empty and "status" in logs.columns and len(logs) > 0:
        comp_rate = round((len(logs[logs["status"] == "completed"]) / len(logs)) * 100, 1)

    c1.metric("Total Registered Users", f"{total_users:,}")
    c2.metric(f"Active Users ({tf}d)", f"{active_users:,}")
    c3.metric("Habit Completion Rate", f"{comp_rate}%")
    c4.metric("Highest Global Streak", f"{calc_highest_global_streak(logs)}d 🔥")

    st.write("")

    
    # Charts Grid Row 1: DAU & User Growth
    
    row1_c1, row1_c2 = st.columns(2)
    with row1_c1:
        render_dau_chart(logs, tf)
    with row1_c2:
        render_user_growth_chart(profiles, tf)

    st.write("")

    
    # Charts Grid Row 2: Completion Gauge & Frequencies
    
    row2_c1, row2_c2 = st.columns(2)
    with row2_c1:
        render_completion_gauge(logs)
    with row2_c2:
        render_frequency_distribution(habits)

    st.write("")

    
    # Charts Grid Row 3: Creation Trend & Weekly Density
    
    row3_c1, row3_c2 = st.columns(2)
    with row3_c1:
        render_habit_creation_trend(habits, tf)
    with row3_c2:
        render_weekly_activity_heatmap(logs)

    st.write("")

    
    # Leaderboard & Activity Feed
    
    render_top_active_users_table(dfs)
    st.write("")
    render_recent_activity_timeline(dfs)


if __name__ == "__main__":
    main()