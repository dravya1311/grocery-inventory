import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

# --- Streamlit Page Config ---
st.set_page_config(page_title="Supply Chain Inventory KPI Dashboard", layout="wide")

# --- Constants ---
TODAY = pd.Timestamp(date.today())

# --- Data Loading ---
@st.cache_data
def load_data(file_path, current_date):
    """Loads and preprocesses the inventory data."""
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        st.error(f"Error: File not found at {file_path}. Please upload 'Grocery_Inventory.csv'.")
        return pd.DataFrame()

    # Clean column names
    df.columns = df.columns.str.strip()

    # Clean 'Unit_Price'
    if 'Unit_Price' in df.columns:
        df['Unit_Price'] = df['Unit_Price'].astype(str).str.replace('$', '', regex=False).str.strip()
        df['Unit_Price'] = pd.to_numeric(df['Unit_Price'], errors='coerce')
    else:
        st.warning("'Unit_Price' column missing — using 0 as placeholder.")
        df['Unit_Price'] = 0

    # Product Margin (from 'percentage')
    if 'percentage' in df.columns:
        df['Product_Margin'] = df['percentage'].astype(str).str.replace('%', '', regex=False).str.strip()
        df['Product_Margin'] = pd.to_numeric(df['Product_Margin'], errors='coerce') / 100
    else:
        df['Product_Margin'] = 0.0

    # Derived columns
    if 'Stock_Quantity' in df.columns and 'Unit_Price' in df.columns:
        df['Inventory_Value'] = df['Stock_Quantity'] * df['Unit_Price']
    else:
        df['Inventory_Value'] = 0

    if 'Sales_Volume' in df.columns:
        df['Total_Revenue'] = df['Sales_Volume'] * df['Unit_Price']
    else:
        df['Total_Revenue'] = 0

    if 'Reorder_Level' in df.columns and 'Stock_Quantity' in df.columns:
        df['Stock_Out_Risk'] = df['Stock_Quantity'] <= df['Reorder_Level']
    else:
        df['Stock_Out_Risk'] = False

    # Parse date columns
    date_cols = ['Date_Received', 'Last_Order_Date', 'Expiration_Date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        else:
            df[col] = pd.NaT

    # Days to expire
    df['Days_to_Expire'] = (df['Expiration_Date'] - current_date).dt.days
    df['Catagory'] = df.get('Catagory', 'Unknown').fillna('Unknown')

    return df

# --- Load Data ---
df = load_data("Grocery_Inventory.csv", TODAY)

# --- KPI Calculation ---
def calculate_kpis(df):
    if df.empty:
        return None

    total_inventory_value = df['Inventory_Value'].sum()
    stock_out_risk_count = df['Stock_Out_Risk'].sum()
    avg_turnover_rate = df.get('Inventory_Turnover_Rate', pd.Series([0])).mean()
    avg_margin = df['Product_Margin'].mean()
    shelf_life_risk_count = df[df['Days_to_Expire'] <= 30].shape[0]

    return {
        'Total Inventory Value': total_inventory_value,
        'Stock Out Risk Items': stock_out_risk_count,
        'Avg Inventory Turnover Rate': avg_turnover_rate,
        'Expiring Soon Items (30 Days)': shelf_life_risk_count,
        'Average Product Margin': avg_margin
    }

# --- Dashboard Layout ---
if not df.empty and calculate_kpis(df) is not None:
    kpis = calculate_kpis(df)

    st.title("📦 Supply Chain Inventory & Sales Dashboard — Ravindra Yadav")
    st.markdown("---")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Inventory Value", f"${kpis['Total Inventory Value']:,.0f}")
    col2.metric("Avg Product Margin", f"{kpis['Average Product Margin']:.1%}")
    col3.metric("Avg Inventory Turnover", f"{kpis['Avg Inventory Turnover Rate']:.1f}x")
    col4.metric("Stock-Out Risk", int(kpis['Stock Out Risk Items']))
    col5.metric("Expiring Soon (30 Days)", int(kpis['Expiring Soon Items (30 Days)']))

    st.markdown("---")
    st.subheader("📊 Inventory Insights")

    # Chart 1: Inv
