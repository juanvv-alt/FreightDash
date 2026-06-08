import requests
import io
import pandas as pd
import sqlite3

# Function to fetch and process CSV data
def fetch_data(api_url, api_token, dataset_name):
    print(f"\nFetching {dataset_name} data...")
    full_url = f"{api_url}?apiToken={api_token}"
    response = requests.get(full_url, headers={"Content-Type": "application/json"})

    if response.status_code == 200:
        csv_data = response.text
        csv_file = io.StringIO(csv_data)
        df = pd.read_csv(csv_file)
        df.columns = df.columns.str.strip().str.lower()  # Normalize column names
        print(f"{dataset_name} data retrieved successfully!\n")
        return df
    else:
        print(f"Error fetching {dataset_name} data: {response.status_code} - {response.text}")
        return None

# Function to save data to SQLite
def save_to_db(df, table_name, db_name="data.db"):
    conn = sqlite3.connect(db_name)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"{table_name} data saved to database.\n")

# Function to load data from SQLite
def load_from_db(query, db_name="data.db"):
    conn = sqlite3.connect(db_name)
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# API details
api_token = "3e8395ce04114a2d00f6d6ff7f3692edb423cd8b26e42c65042a89fe458537c7"
api_url_fuel = "https://api.veslink.com/v1/imos/reports/DasboardExportFuel"
api_url_port_exp = "https://api.veslink.com/v1/imos/reports/DasboardExportPortexp"

# Fetch and store datasets in SQLite
df_fuel = fetch_data(api_url_fuel, api_token, "Fuel Data")
df_port_exp = fetch_data(api_url_port_exp, api_token, "Port Expenses")

if df_fuel is not None:
    save_to_db(df_fuel, "fuel_data")

if df_port_exp is not None:
    save_to_db(df_port_exp, "port_expenses")

# User Input
estimate_id = input("Enter the Estimate ID to search: ").strip()
daily_hire = float(input("Enter the Daily Hire rate: "))

# Query SQLite instead of API
query_fuel = f"SELECT * FROM fuel_data WHERE `estimate id` = '{estimate_id}'"
query_port_exp = f"SELECT * FROM port_expenses WHERE `estimate id` = '{estimate_id}'"

df_fuel = load_from_db(query_fuel)
df_port_exp = load_from_db(query_port_exp)

# Processing the retrieved data
if not df_fuel.empty and not df_port_exp.empty:
    estimate_column = 'estimate id'
    fuel_column = 'fuel type'
    consumption_column = 'consumption total'
    voyage_days_column = 'voyage days'
    total_load_quantity_column = 'total load quantity'
    port_expenses_column = 'port expenses base'
    misc_expenses_column = 'amount base'

    print("\nProcessing Fuel Data...\n")
    voyage_days_value = df_fuel.iloc[0][voyage_days_column] if not df_fuel.empty else 0

    fuel_vars = {}
    consumption_vars = {}

    for i, (_, row) in enumerate(df_fuel.iterrows(), start=1):
        fuel_vars[f"fuel{i}"] = row[fuel_column]
        consumption_vars[f"consumption{i}"] = row[consumption_column]

    print("\nProcessing Port Expenses data...\n")
    total_port_expenses = df_port_exp[port_expenses_column].sum()
    misc_expenses = df_port_exp.iloc[0][misc_expenses_column] if not df_port_exp.empty else 0
    total_load_quantity = df_port_exp.iloc[0][total_load_quantity_column] if not df_port_exp.empty else 0
    total_expenses = total_port_expenses + misc_expenses

    # Ask user for fuel prices
    fuel_prices = {}
    print("\nEnter Fuel Prices:")
    for i in range(1, len(df_fuel) + 1):
        fuel_type = fuel_vars.get(f'fuel{i}', 'N/A')
        if fuel_type != 'N/A':
            fuel_price = float(input(f"Enter the price per unit for {fuel_type}: "))
            fuel_prices[fuel_type] = fuel_price

    # Calculate fuel costs
    total_fuel_cost = sum(consumption_vars[f"consumption{i}"] * fuel_prices.get(fuel_vars[f"fuel{i}"], 0)
                          for i in range(1, len(df_fuel) + 1))

    # Calculate Freight Rate
    freight_rate = (voyage_days_value * daily_hire + total_expenses + total_fuel_cost) / total_load_quantity if total_load_quantity > 0 else 0

    # Print Final Results
    print("\n===== Final Output =====")
    print(f"Estimate ID: {estimate_id}")
    print(f"Voyage Days: {voyage_days_value}")
    print(f"Total Load Quantity: {total_load_quantity}")
    print(f"Total Port Expenses: {total_port_expenses}")
    print(f"Misc Expenses: {misc_expenses}")
    print(f"Total Expenses: {total_expenses}")

    # Print Fuel and Consumption values
    for i in range(1, len(df_fuel) + 1):
        fuel_type = fuel_vars.get(f'fuel{i}', 'N/A')
        fuel_price = fuel_prices.get(fuel_type, 0)
        print(f"Fuel{i}: {fuel_type}, Consumption{i}: {consumption_vars.get(f'consumption{i}', 'N/A')}, Price: {fuel_price}")

    print(f"\nTotal Fuel Cost: {total_fuel_cost}")
    print(f"Freight Rate: {freight_rate:.2f}")

else:
    print("Error: Unable to retrieve required data from the database.")