# scripts/generate_synthetic_data.py
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm
np.random.seed(42)

OUT_DIR = "data"
os.makedirs(OUT_DIR, exist_ok=True)

START_DATE = "2025-07-01"   # change as you like
END_DATE = "2025-10-31"     # ~4 months of hourly data

def make_hour_range(start_date, end_date):
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    rng = pd.date_range(start=start, end=end, freq="h")
    return rng

def weekday_weekend_multiplier(dt):
    # weekday: baseline 1.0, weekend higher/lower depending on industry
    return 1.2 if dt.weekday() >= 5 else 1.0

def holiday_multiplier(dt, holidays):
    return 1.5 if dt.date() in holidays else 1.0

def generate_hospital_demand(rng):
    # Hospital: baseline lower overnight, peaks morning & late afternoon; Poisson noise
    base_by_hour = {h: 60 if 7 <= h < 11 else
                        80 if 11 <= h < 15 else
                        70 if 15 <= h < 19 else
                        40 if 19 <= h < 23 else
                        20 for h in range(24)}
    holidays = []  # keep empty or add dates as datetime.date
    records = []
    for ts in rng:
        base = base_by_hour[ts.hour]
        day_factor = 1.1 if ts.weekday() < 5 else 1.25
        hol = holiday_multiplier(ts, holidays)
        lam = base * day_factor * hol
        calls = np.random.poisson(lam=max(1, lam))
        records.append({"timestamp": ts, "hour": ts.hour, "date": ts.date(), "demand": int(calls)})
    return pd.DataFrame(records)

def generate_callcenter_demand(rng):
    # Call center: strong business hours, low night; seasonal weekly pattern
    base_by_hour = {h: 5 if h < 7 else
                        60 if 9 <= h < 12 else
                        120 if 12 <= h < 14 else
                        100 if 14 <= h < 17 else
                        40 if 17 <= h < 20 else
                        10 for h in range(24)}
    holidays = []  # could add lowered demand on public holidays
    records = []
    for ts in rng:
        base = base_by_hour[ts.hour]
        weekday_factor = 1.0 if ts.weekday() < 5 else 0.7  # weekends less calls
        lam = base * weekday_factor
        calls = np.random.poisson(lam=max(1, lam))
        records.append({"timestamp": ts, "hour": ts.hour, "date": ts.date(), "demand": int(calls)})
    return pd.DataFrame(records)

def generate_retail_demand(rng):
    # Retail: peak midday & evening, weekends busier; add seasonal noise
    base_by_hour = {h: 5 if h < 9 else
                        50 if 10 <= h < 13 else
                        80 if 13 <= h < 16 else
                        60 if 16 <= h < 20 else
                        20 for h in range(24)}
    holidays = []  # fill if you want promotions
    records = []
    for ts in rng:
        base = base_by_hour[ts.hour]
        weekend_mul = 1.5 if ts.weekday() >= 5 else 1.0
        # random promotional spikes
        promo = 2.0 if np.random.rand() < 0.005 else 1.0
        lam = base * weekend_mul * promo
        customers = np.random.poisson(lam=max(1, lam))
        records.append({"timestamp": ts, "hour": ts.hour, "date": ts.date(), "demand": int(customers)})
    return pd.DataFrame(records)

def generate_employees_for_industry(industry, n_emp=40):
    # Generic employee properties
    employees = []
    for i in range(n_emp):
        emp_id = f"{industry[:3].upper()}_E{1000+i}"
        # skill: 1 (junior) to 3 (senior). Hospital will have more seniors.
        if industry == "hospital":
            skill = np.random.choice([2,3], p=[0.6,0.4])
            max_week_hours = np.random.choice([36,40,48], p=[0.2,0.6,0.2])
        elif industry == "callcenter":
            skill = np.random.choice([1,2], p=[0.7,0.3])
            max_week_hours = np.random.choice([32,36,40], p=[0.2,0.6,0.2])
        else: # retail
            skill = np.random.choice([1,2], p=[0.6,0.4])
            max_week_hours = np.random.choice([24,32,40], p=[0.3,0.5,0.2])
        # preferred shifts: morning/afternoon/night
        pref = np.random.choice(["morning","afternoon","evening","flex"], p=[0.35,0.35,0.15,0.15])
        employees.append({
            "employee_id": emp_id,
            "skill_level": int(skill),
            "max_week_hours": int(max_week_hours),
            "preferred_shift": pref,
            "base_productivity": round(np.random.normal(1.0, 0.05), 2)  # multiplier
        })
    return pd.DataFrame(employees)

def generate_constraints(industry):
    if industry == "hospital":
        c = {
            "max_shift_hours": 12,
            "min_rest_hours_between_shifts": 12,
            "max_week_hours": 48,
            "shift_templates": [{"name":"day","start":7,"end":19},{"name":"night","start":19,"end":7}],
            "role_requirements": {"ICU": {"skill_min":3, "min_on_shift":2}}
        }
    elif industry == "callcenter":
        c = {
            "max_shift_hours": 8,
            "min_rest_hours_between_shifts": 10,
            "max_week_hours": 40,
            "shift_templates": [{"name":"morning","start":8,"end":16},{"name":"afternoon","start":12,"end":20},{"name":"short","start":9,"end":13}],
            "role_requirements": {}
        }
    else: # retail
        c = {
            "max_shift_hours": 8,
            "min_rest_hours_between_shifts": 10,
            "max_week_hours": 40,
            "shift_templates": [{"name":"morning","start":8,"end":14},{"name":"afternoon","start":13,"end":19},{"name":"evening","start":16,"end":22}],
            "role_requirements": {"manager": {"skill_min":2, "min_on_shift":1}}
        }
    return c

def save_df(df, fname):
    path = os.path.join(OUT_DIR, fname)
    df.to_csv(path, index=False)
    print("Saved:", path)

def main():
    rng = make_hour_range(START_DATE, END_DATE)
    print("Generating hospital demand...")
    hosp = generate_hospital_demand(rng)
    save_df(hosp, "demand_hospital.csv")

    print("Generating call center demand...")
    cc = generate_callcenter_demand(rng)
    save_df(cc, "demand_callcenter.csv")

    print("Generating retail demand...")
    retail = generate_retail_demand(rng)
    save_df(retail, "demand_retail.csv")

    # employees
    print("Generating employees...")
    hosp_emp = generate_employees_for_industry("hospital", n_emp=60)
    cc_emp = generate_employees_for_industry("callcenter", n_emp=45)
    retail_emp = generate_employees_for_industry("retail", n_emp=50)
    save_df(hosp_emp, "employees_hospital.csv")
    save_df(cc_emp, "employees_callcenter.csv")
    save_df(retail_emp, "employees_retail.csv")

    # constraints
    print("Saving constraints JSON...")
    os.makedirs("configs", exist_ok=True)
    json.dump(generate_constraints("hospital"), open("configs/constraints_hospital.json","w"), indent=2)
    json.dump(generate_constraints("callcenter"), open("configs/constraints_callcenter.json","w"), indent=2)
    json.dump(generate_constraints("retail"), open("configs/constraints_retail.json","w"), indent=2)
    print("Done.")

if __name__ == "__main__":
    main()
