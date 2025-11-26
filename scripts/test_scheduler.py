# scripts/test_scheduler.py
import pandas as pd
from model.optimizer import generate_schedule

df_d = pd.read_csv("data/demand_hospital.csv")
df_e = pd.read_csv("data/employees_hospital.csv")

schedule, coverage = generate_schedule(df_d.head(48), df_e)  # test first 48 hours
print("Assignments sample:")
print(schedule.head())
print("Coverage sample:")
print(coverage.head())
schedule.to_csv("outputs/test_schedule_hospital.csv", index=False)
coverage.to_csv("outputs/test_coverage_hospital.csv", index=False)
print("Saved outputs/test_schedule_hospital.csv")
