# app.py
import streamlit as st
import pandas as pd
import os
from model.optimizer import generate_schedule
import json

st.set_page_config(layout="wide")
st.title("Dynamic Workforce Scheduling Optimizer")

# Sidebar: select industry or upload files
st.sidebar.header("Data / Industry")

industry = st.sidebar.selectbox("Industry", ["hospital","callcenter","retail"])
use_sample = st.sidebar.checkbox("Use sample data from /data folder", value=True)

if use_sample:
    demand_path = f"data/demand_{industry}.csv"
    employees_path = f"data/employees_{industry}.csv"
    st.sidebar.write("Using sample files:", demand_path, employees_path)
else:
    demand_file = st.sidebar.file_uploader("Upload Demand CSV", type=["csv"])
    employees_file = st.sidebar.file_uploader("Upload Employees CSV", type=["csv"])
    demand_path = None
    employees_path = None
    if demand_file and employees_file:
        df_d = pd.read_csv(demand_file)
        df_e = pd.read_csv(employees_file)
        st.session_state['uploaded_demand'] = df_d
        st.session_state['uploaded_employees'] = df_e

# Load dataframes
if use_sample:
    df_d = pd.read_csv(demand_path)
    df_e = pd.read_csv(employees_path)
else:
    if 'uploaded_demand' in st.session_state and 'uploaded_employees' in st.session_state:
        df_d = st.session_state['uploaded_demand']
        df_e = st.session_state['uploaded_employees']
    else:
        st.info("Please upload both demand and employee CSVs or check 'Use sample data'.")
        st.stop()

st.subheader("Demand sample")
st.write(df_d.head())

st.subheader("Employees sample")
st.write(df_e.head())

# Load constraints JSON if exists
config_path = f"configs/constraints_{industry}.json"
config = None
if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    st.sidebar.write("Loaded constraints for", industry)

if st.button("Generate Schedule"):
    with st.spinner("Running scheduler (MVP)..."):
        schedule_df, coverage_df = generate_schedule(df_d, df_e, config=config, output_path=f"outputs/schedule_{industry}.csv")
    st.success("Schedule generated!")
    st.subheader("Assignments (first 200 rows)")
    st.dataframe(schedule_df.head(200))
    st.subheader("Coverage / Understaff summary (first 200 rows)")
    st.dataframe(coverage_df.head(200))
    st.markdown(f"Download outputs: `outputs/schedule_{industry}.csv`")
