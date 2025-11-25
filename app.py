import streamlit as st
import pandas as pd
from model.optimizer import generate_schedule  # your optimization function

st.title("Dynamic Workforce Scheduling Optimizer")

st.sidebar.header("Upload Data")

demand_file = st.sidebar.file_uploader("Upload Demand CSV", type=["csv"])
employees_file = st.sidebar.file_uploader("Upload Employees CSV", type=["csv"])

if demand_file and employees_file:
    demand = pd.read_csv(demand_file)
    employees = pd.read_csv(employees_file)

    st.subheader("Demand Sample")
    st.write(demand.head())

    st.subheader("Employees Sample")
    st.write(employees.head())

    if st.button("Generate Schedule"):
        schedule = generate_schedule(demand, employees)
        st.success("Schedule generated!")
        st.dataframe(schedule)
