import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Supply Chain Inventory KPI Dashboard")

# FIX: Calculate the current date outside of the cached function to prevent caching errors.
TODAY = datetime.now().normalize()

# --- Data Loading and Preprocessing ---
@st.cache_data
def load_data(file_path, current_date): # Now accepts current_date as an argument
    """Loads and preprocesses the inventory data."""
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        st.error(f"Error: File not found at {file_path}. Please ensure 'Grocery_Inventory.csv' is in the correct path.")
        return pd.DataFrame() # Return empty DataFrame on error

    # FIX 1: Clean column names by stripping whitespace (solves KeyError)
    df.columns = df.columns.str.strip()

    # 1. Clean 'Unit_Price' (Remove '$' and convert to float)
    df['Unit_Price'] = df['Unit_Price'].astype(str).str.replace('$', '', regex=False).str.strip()
    df['Unit_Price'] = pd.to_numeric(df['Unit_Price'], errors='coerce')

    # 2. Clean 'percentage' (now treated as 'Product_Margin')
    if 'percentage' in df.columns:
        # Convert the percentage string to a decimal fraction (e.g., "1.96%" -> 0.0196)
        df['Product_Margin'] = df['percentage'].astype(str).str.replace('%', '', regex=False).str.strip()
        df['Product_Margin'] = pd.to_numeric(df['Product_Margin'], errors='coerce') / 100 
    else:
        # Fallback if the original column is missing
        st.error("Financial column 'percentage' (intended for Margin) not found. Setting Margin to 0.0.")
        df['Product_Margin'] = 0.0

    # 3. Calculate Key Derived Metrics
    df['Inventory_Value'] = df['Stock_Quantity'] * df['Unit_Price']
    df['Total_Revenue'] = df['Sales_Volume'] * df['Unit_Price']
    df['Stock_Out_Risk'] = df['Stock_Quantity'] <= df['Reorder_Level']
    
    # 4. Handle Date Columns (for shelf-life analysis)
    date_cols = ['Date_Received', 'Last_Order_Date', 'Expiration_Date']
    for col in date_cols:
        # Use a flexible conversion attempt
        df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=False)

    # 5. Calculate Days Until Expiration
    # Use the passed argument instead of calling datetime.now() inside the cached function
    df['Days_to_Expire'] = (df['Expiration_Date'] - current_date).dt.days
    
    # Fill any missing Category values for safe grouping
    df['Catagory'] = df['Catagory'].fillna('Unknown')

    return df

# Attempt to load the data, passing TODAY as a parameter
df = load_data('Grocery_Inventory.csv', TODAY)

# --- KPI Calculation Function ---
def calculate_kpis(df):
    """Calculates and returns the primary dashboard KPIs."""
    if df.empty:
        return None

    # KPI 1: Total Inventory Value
    total_inventory_value = df['Inventory_Value'].sum()

    # KPI 2: Number of Products at Stock-Out Risk
    stock_out_risk_count = df['Stock_Out_Risk'].sum()

    # KPI 3: Average Inventory Turnover Rate (ATR)
    avg_turnover_rate = df['Inventory_Turnover_Rate'].mean()
    
    # KPI 4: Average Product Margin (New KPI)
    # Filter out potential non-finite values before calculating the mean
    avg_margin = df['Product_Margin'].replace([float('inf'), float('-inf')], float('nan')).mean()

    # KPI 5: Average Shelf Life Risk (Count of products expiring in 30 days)
    shelf_life_risk_count = df[df['Days_to_Expire'] <= 30].shape[0]

    return {
        'Total Inventory Value': total_inventory_value,
        'Stock Out Risk Items': stock_out_risk_count,
        'Avg Inventory Turnover Rate': avg_turnover_rate,
        'Expiring Soon Items (30 Days)': shelf_life_risk_count,
        'Average Product Margin': avg_margin 
    }

# --- Main Dashboard Layout ---
if not df.empty and calculate_kpis(df) is not None:
    kpis = calculate_kpis(df)

    # --- Header ---
    st.title("🛒 Supply Chain Inventory & Sales Dashboard")
    st.markdown("---")

    # --- KPI Cards (Row 1) ---
    st.subheader("Inventory & Efficiency Snapshot")
    
    # Using 5 columns to fit the new Margin KPI
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Total Inventory Value",
            value=f"${kpis['Total Inventory Value']:,.0f}",
            help="Monetary value of all stock currently in the warehouse."
        )

    with col2:
        st.metric(
            label="Avg Product Margin",
            value=f"{kpis['Average Product Margin']:.1%}",
            help="The average profit margin across all products."
        )

    with col3:
        st.metric(
            label="Avg Inventory Turnover Rate (ATR)",
            value=f"{kpis['Avg Inventory Turnover Rate']:.1f}x",
            help="Higher turnover indicates faster sales and better efficiency."
        )

    with col4:
        st.metric(
            label="Stock-Out Risk Items",
            value=kpis['Stock Out Risk Items'],
            delta_color="inverse", # Red when count is high
            help="Number of products where Stock Quantity is at or below Reorder Level."
        )

    with col5:
        st.metric(
            label="Expiring Soon (Next 30 Days)",
            value=kpis['Expiring Soon Items (30 Days)'],
            delta_color="inverse", # Red when count is high
            help="Number of products whose expiration date is within the next 30 days."
        )

    st.markdown("---")

    # --- Analytical Charts (Row 2) ---
    st.subheader("Deep Dive Analysis")
    chart_col1, chart_col2 = st.columns([1, 1.3])

    # Chart 1: Inventory Health by Status (Pie Chart)
    with chart_col1:
        st.markdown("##### 1. Inventory Status Breakdown")
        status_counts = df['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.pie(
            status_counts,
            values='Count',
            names='Status',
            title='Proportion of Stock by Operational Status',
            color_discrete_sequence=px.colors.qualitative.Bold,
            hole=0.4
        )
        fig_status.update_traces(textposition='inside', textinfo='percent+label')
        fig_status.update_layout(showlegend=True)
        st.plotly_chart(fig_status, use_container_width=True)

    # Chart 2: Top 10 Products by Sales Revenue (Bar Chart)
    with chart_col2:
        st.markdown("##### 2. Top 10 Products by Sales Revenue")
        top_products = df.groupby('Product_Name')['Total_Revenue'].sum().nlargest(10).reset_index()
        top_products.columns = ['Product_Name', 'Total_Revenue']
        fig_revenue = px.bar(
            top_products,
            x='Product_Name',
            y='Total_Revenue',
            color='Total_Revenue',
            title='Highest Revenue Generating Products',
            labels={'Total_Revenue': 'Total Revenue ($)', 'Product_Name': 'Product'},
            color_continuous_scale=px.colors.sequential.Plasma
        )
        fig_revenue.update_layout(xaxis={'categoryorder':'total descending'}, yaxis_title="Total Revenue ($)")
        st.plotly_chart(fig_revenue, use_container_width=True)

    # --- Analytical Chart (Row 3) ---
    st.subheader("Category and Supplier Performance")
    
    # Chart 3: Inventory Value and Sales Volume by Category (Scatter Plot)
    category_agg = df.groupby('Catagory').agg(
        Total_Inventory_Value=('Inventory_Value', 'sum'),
        Average_Sales_Volume=('Sales_Volume', 'mean'),
        Average_Margin=('Product_Margin', 'mean'), 
        Unique_Suppliers=('Supplier_ID', 'nunique')
    ).reset_index()
    
    fig_cat = px.scatter(
        category_agg,
        x='Average_Sales_Volume',
        y='Total_Inventory_Value',
        size='Total_Inventory_Value',
        color='Average_Margin', # Color is based on Average Margin
        hover_name='Catagory',
        size_max=60,
        title='Inventory Value vs. Avg Sales Volume by Category (Color = Avg Margin)',
        labels={
            'Average_Sales_Volume': 'Average Sales Volume (Units)',
            'Total_Inventory_Value': 'Total Inventory Value ($)',
            'Average_Margin': 'Average Margin'
        },
        color_continuous_scale=px.colors.sequential.Viridis
    )
    # Customize hover template for margin display
    fig_cat.update_traces(hovertemplate="<b>Category: %{hovertext}</b><br>" +
                                        "Inventory Value: $%{y:,.0f}<br>" +
                                        "Avg Sales Volume: %{x:,.0f}<br>" +
                                        "Avg Margin: %{marker.color:.1%}<extra></extra>")
    st.plotly_chart(fig_cat, use_container_width=True)

    # --- Raw Data Expiring Soon ---
    st.markdown("---")
    st.subheader("🚨 Raw Data: Products Nearing Expiration")
    expiring_soon_data = df[df['Days_to_Expire'] <= 30].sort_values('Days_to_Expire')
    
    # Select relevant columns for display
    display_cols = [
        'Product_Name',
        'Catagory',
        'Supplier_Name',
        'Stock_Quantity',
        'Expiration_Date',
        'Days_to_Expire',
        'Inventory_Value',
        'Product_Margin' # Display the new margin column
    ]
    st.dataframe(expiring_soon_data[display_cols].style.format({'Product_Margin': '{:.1%}'}).background_gradient(cmap='Reds', subset=['Days_to_Expire']), use_container_width=True)


else:
    # This message appears if the DataFrame is empty (e.g., file not found or corrupted)
    st.warning("Please ensure the 'Grocery_Inventory.csv' file is accessible and properly formatted to run the dashboard. Check for data inconsistencies or missing critical columns.")