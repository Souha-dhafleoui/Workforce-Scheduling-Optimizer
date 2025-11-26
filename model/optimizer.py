# model/optimizer.py
import pandas as pd
import math
from datetime import datetime, timedelta

# Helper: map preferred_shift to hours ranges for matching preference
PREF_SHIFT_WINDOWS = {
    "morning": range(7, 14),    # 7-13
    "afternoon": range(13, 20), # 13-19
    "evening": range(16, 23),   # 16-22
    "night": list(range(0,7)) + list(range(23,24)), # 23-6
    "flex": range(0,24)
}

def _hour_pref_score(pref, hour):
    """Return 1 if hour in preferred window, else 0"""
    if pref not in PREF_SHIFT_WINDOWS:
        return 0
    return 1 if hour in PREF_SHIFT_WINDOWS[pref] else 0

def generate_schedule(demand_df, employees_df, config=None, output_path=None):
    """
    Simple greedy scheduler (MVP).
    - demand_df: columns ['timestamp','hour','date','demand']
    - employees_df: columns ['employee_id','skill_level','max_week_hours','preferred_shift','base_productivity']
    - config: optional dict (not required for MVP)
    - output_path: if provided, CSV is written there
    Returns: schedule_df
    """

    # Normalize inputs
    df_d = demand_df.copy()
    if 'timestamp' in df_d.columns:
        df_d['timestamp'] = pd.to_datetime(df_d['timestamp'])
    else:
        raise ValueError("demand_df must have 'timestamp' column")

    df_e = employees_df.copy()
    # Ensure productivity exists
    if 'base_productivity' not in df_e.columns:
        df_e['base_productivity'] = 1.0

    # Prepare per-employee bookkeeping
    # track hours assigned per employee per ISO week
    df_e['assigned_hours'] = 0.0
    emp_book = {}
    for _, row in df_e.iterrows():
        emp_book[row['employee_id']] = {
            "skill": int(row.get("skill_level", 1)),
            "max_week_hours": float(row.get("max_week_hours", 40)),
            "preferred_shift": row.get("preferred_shift", "flex"),
            "base_productivity": float(row.get("base_productivity", 1.0)),
            "assigned_hours_by_week": {},  # week -> hours
            "last_assigned_ts": None
        }

    # sort demand by timestamp ascending
    df_d = df_d.sort_values("timestamp").reset_index(drop=True)

    assignments = []  # list of dicts to build schedule

    # For feasible runtime, group by day then by hour
    for idx, row in df_d.iterrows():
        ts = pd.to_datetime(row['timestamp'])
        hour = int(row['hour'])
        demand = int(row['demand'])

        # We define one "hour-slot" work unit = 1 hour of work per worker (adjusted by productivity)
        # Compute needed headcount as ceil(demand / avg_capacity)
        # Estimate avg capacity per employee = mean(base_productivity)
        avg_capacity = df_e['base_productivity'].mean() if len(df_e)>0 else 1.0
        needed = math.ceil(demand / max(0.1, avg_capacity))

        # Build candidate employees sorted by:
        # 1) pref match (1 or 0), 2) higher skill, 3) fewer assigned hours this week
        week = ts.isocalendar()[1]
        candidates = []
        for emp_id, info in emp_book.items():
            # compute assigned this week
            assigned_this_week = info['assigned_hours_by_week'].get(week, 0.0)
            # available if assigned_this_week < max_week_hours
            if assigned_this_week >= info['max_week_hours']:
                continue
            # simple rest constraint: ensure at least 8 hours since last assigned (soft)
            if info['last_assigned_ts'] is not None:
                delta = (ts - info['last_assigned_ts']).total_seconds() / 3600.0
                if delta < 8:  # too recent
                    continue
            pref_score = _hour_pref_score(info['preferred_shift'], hour)
            candidates.append( (emp_id, pref_score, info['skill'], assigned_this_week, info['base_productivity']) )

        # If not enough candidates, we will relax rest constraint: consider all employees with remaining hours
        if len(candidates) < needed:
            candidates = []
            for emp_id, info in emp_book.items():
                assigned_this_week = info['assigned_hours_by_week'].get(week, 0.0)
                if assigned_this_week >= info['max_week_hours']:
                    continue
                pref_score = _hour_pref_score(info['preferred_shift'], hour)
                candidates.append( (emp_id, pref_score, info['skill'], assigned_this_week, info['base_productivity']) )

        # sort candidates: pref_score desc, skill desc, assigned_this_week asc
        candidates.sort(key=lambda x: (-x[1], -x[2], x[3]))

        # pick top `needed` employees
        chosen = candidates[:needed]

        # create assignments (1.0 hour each) but consider productivity
        for emp_id, pref_score, skill, assigned_this_week, prod in chosen:
            # assigned hours is 1 (hour slot). We track raw assigned hours.
            emp_info = emp_book[emp_id]
            emp_info['assigned_hours_by_week'][week] = emp_info['assigned_hours_by_week'].get(week, 0.0) + 1.0
            emp_info['last_assigned_ts'] = ts
            assignments.append({
                "employee_id": emp_id,
                "timestamp": ts,
                "date": ts.date(),
                "hour": hour,
                "assigned_hours": 1.0,
                "week": week,
                "preferred_shift_match": pref_score,
                "skill_level": emp_info['skill'],
                "base_productivity": emp_info['base_productivity']
            })

        # If no chosen (no employees), create empty assignment rows to indicate understaffing (optional)
        if len(chosen) == 0:
            assignments.append({
                "employee_id": None,
                "timestamp": ts,
                "date": ts.date(),
                "hour": hour,
                "assigned_hours": 0.0,
                "week": week,
                "preferred_shift_match": 0,
                "skill_level": 0,
                "base_productivity": 0.0
            })

    schedule_df = pd.DataFrame(assignments)

    # summary: compute coverage per timestamp
    cover = schedule_df.groupby("timestamp")["assigned_hours"].sum().reset_index().rename(columns={"assigned_hours":"total_assigned_hours"})
    df_out = pd.merge(df_d, cover, on="timestamp", how="left")
    df_out['total_assigned_hours'] = df_out['total_assigned_hours'].fillna(0)
    df_out['understaff'] = df_out['demand'] - df_out['total_assigned_hours']*avg_capacity
    df_out['understaff'] = df_out['understaff'].apply(lambda x: max(0, round(x,2)))

    # write output schedules per employee in outputs/ if requested
    final_schedule = schedule_df.copy()
    final_schedule = final_schedule.sort_values(["timestamp","employee_id"]).reset_index(drop=True)

    if output_path:
        final_schedule.to_csv(output_path, index=False)

    return final_schedule, df_out  # return both assignment-level and coverage-level dfs
