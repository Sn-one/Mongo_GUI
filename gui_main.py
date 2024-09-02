import streamlit as st
from pymongo import MongoClient
import pandas as pd
import pandasql as psql
import json
from datetime import datetime

# Connect to MongoDB
@st.cache_resource
def get_mongo_client():
    mongo_uri = st.secrets["mongo"]["uri"]
    client = MongoClient(mongo_uri)
    return client

# Fetch database and collection names
def get_database_names(client):
    return client.list_database_names()

def get_collection_names(client, db_name):
    db = client[db_name]
    return db.list_collection_names()

# Load data from the selected collection
def load_data(client, db_name, collection_name):
    db = client[db_name]
    collection = db[collection_name]
    data = pd.DataFrame(list(collection.find()))
    if '_id' in data.columns:
        data = data.drop(columns=['_id'])
    return data

# Save data to the selected collection
def save_data(client, db_name, collection_name, data):
    db = client[db_name]
    collection = db[collection_name]
    collection.delete_many({})
    collection.insert_many(data.to_dict('records'))

# Add new column
def add_column(data, column_name, default_value):
    data[column_name] = default_value
    return data

# Merge columns
def merge_columns(data, col1, col2, new_col_name, drop_originals):
    data[new_col_name] = data[col1].astype(str) + data[col2].astype(str)
    if drop_originals:
        data = data.drop(columns=[col1, col2])
    return data

# Remove column
def remove_columns(data, columns):
    return data.drop(columns=columns)

# Conditional update
def conditional_update(data, column, condition, new_value):
    data.loc[data[column] == condition, column] = new_value
    return data

# Rename column
def rename_column(data, old_column_name, new_column_name):
    data = data.rename(columns={old_column_name: new_column_name})
    return data

# Process uploaded file
def process_uploaded_file(uploaded_file):
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                data = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith('.xlsx'):
                data = pd.read_excel(uploaded_file)
            else:
                st.error("Unsupported file type. Please upload a CSV or Excel file.")
                return None
            return data
        except Exception as e:
            st.error(f"Error processing file: {e}")
            return None
    return None

# Function to serialize complex data types to JSON strings
def serialize_complex_data(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    elif isinstance(value, datetime):
        return value.isoformat()
    else:
        return value

# Apply serialization to the DataFrame
def serialize_dataframe(data):
    return data.applymap(serialize_complex_data)

# Execute SQL query on DataFrame
def execute_sql_query(data, query):
    # Serialize complex data types
    serialized_data = serialize_dataframe(data)
    return psql.sqldf(query, {'data': serialized_data})

def main():
    st.set_page_config(layout="wide")
    st.title("MongoDB Data Management App")

    client = get_mongo_client()

    # Database and Collection Selection
    st.header("Database and Collection Selection")
    db_names = get_database_names(client)
    
    # Option to use an existing database or create a new one
    db_choice = st.radio("Database Option", ["Use Existing", "Create New"], key='db_option')
    if db_choice == "Use Existing":
        db_name = st.selectbox("Database", db_names, key='db_select')
    else:
        db_name = st.text_input("New Database Name", key='new_db_name')

    if db_name:
        # Option to use an existing collection or create a new one
        collection_choice = st.radio("Collection Option", ["Use Existing", "Create New"], key='collection_option')
        if collection_choice == "Use Existing":
            collection_names = get_collection_names(client, db_name)
            collection_name = st.selectbox("Collection", collection_names, key='collection_select')
        else:
            collection_name = st.text_input("New Collection Name", key='new_collection_name')

    data = None

    # File Upload Section
    uploaded_file = st.file_uploader("Choose a file to upload (CSV or Excel)", type=["csv", "xlsx"])

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Load Data"):
            if db_name and collection_name:
                data = load_data(client, db_name, collection_name)
                st.session_state.data = data
                st.success("Data loaded successfully!")
            else:
                st.error("Please select a database and collection.")

    with col2:
        if st.button("Upload and Save Data"):
            if uploaded_file and db_name and collection_name:
                data = process_uploaded_file(uploaded_file)
                if data is not None:
                    save_data(client, db_name, collection_name, data)
                    st.session_state.data = data
                    st.success(f"File '{uploaded_file.name}' uploaded and saved to {db_name}.{collection_name}!")
            else:
                st.error("Please upload a file and select a database and collection.")

    # Display and manipulate loaded or uploaded data
    if 'data' in st.session_state:
        data = st.session_state.data
        st.header(f"Data from {db_name}.{collection_name}")

        # Sidebar - Data Manipulation
        st.sidebar.header("Data Manipulation")
        
        # Add new column
        with st.sidebar.expander("Add Column"):
            new_col = st.text_input("New column name", key='add_new_col_name')
            default_val = st.text_input("Default value for new column", key='add_default_val')
            if st.button("Add Column", key='add_column_button'):
                if new_col:
                    data = add_column(data, new_col, default_val)
                    st.session_state.data = data
                    st.success(f"Column '{new_col}' added with default value '{default_val}'")
                    st.experimental_rerun()
                else:
                    st.error("Column name cannot be empty")
        
        # Merge columns
        with st.sidebar.expander("Merge Columns"):
            col1 = st.selectbox("Select first column to merge", data.columns, key='merge_col1')
            col2 = st.selectbox("Select second column to merge", data.columns, key='merge_col2')
            merged_col_name = st.text_input("New column name for merged columns", key='merged_col_name')
            drop_originals = st.checkbox("Drop original columns after merging", key='drop_originals')
            if st.button("Merge Columns", key='merge_columns_button'):
                if col1 and col2 and merged_col_name:
                    data = merge_columns(data, col1, col2, merged_col_name, drop_originals)
                    st.session_state.data = data
                    st.success(f"Columns '{col1}' and '{col2}' merged into '{merged_col_name}'")
                    st.experimental_rerun()
                else:
                    st.error("Please provide all details for merging columns")

        # Remove columns
        with st.sidebar.expander("Remove Columns"):
            cols_to_remove = st.multiselect("Select columns to remove", data.columns, key='remove_columns')
            if st.button("Remove Columns", key='remove_columns_button'):
                if cols_to_remove:
                    data = remove_columns(data, cols_to_remove)
                    st.session_state.data = data
                    st.success(f"Columns {', '.join(cols_to_remove)} removed")
                    st.experimental_rerun()
                else:
                    st.error("Please select columns to remove")
        
        # Rename column
        with st.sidebar.expander("Rename Column"):
            old_col_name = st.selectbox("Select column to rename", data.columns, key='rename_col_old')
            new_col_name = st.text_input("New column name", key='rename_col_new')
            if st.button("Rename Column", key='rename_column_button'):
                if old_col_name and new_col_name:
                    data = rename_column(data, old_col_name, new_col_name)
                    st.session_state.data = data
                    st.success(f"Column '{old_col_name}' renamed to '{new_col_name}'")
                    st.experimental_rerun()
                else:
                    st.error("Please provide both the old and new column names")

        # Conditional updates
        with st.sidebar.expander("Conditional Update"):
            col_to_update = st.selectbox("Select column to update", data.columns, key='update_col')
            condition_val = st.text_input("Condition value", key='condition_value')
            new_val = st.text_input("New value", key='new_value')
            if st.button("Update Column", key='update_button'):
                if col_to_update and condition_val and new_val:
                    data = conditional_update(data, col_to_update, condition_val, new_val)
                    st.session_state.data = data
                    st.success(f"Column '{col_to_update}' updated where value was '{condition_val}'")
                    st.experimental_rerun()
                else:
                    st.error("Please provide all details for the update")

        # SQL query execution
        with st.sidebar.expander("SQL Query Execution"):
            query = st.text_area("SQL query", key='sql_query')
            if st.button("Execute SQL", key='execute_sql_button'):
                if query:
                    try:
                        query_result = execute_sql_query(data, query)
                        st.session_state.data = query_result
                        st.success("SQL query executed successfully")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Error executing SQL query: {e}")
                else:
                    st.error("Please enter a SQL query")

        edited_data = st.data_editor(data, height=600)

        # Sidebar - Save Data button
        if st.sidebar.button("Save Data", key='save_data_button'):
            save_data(client, db_name, collection_name, edited_data)
            st.sidebar.success("Data saved successfully!")

if __name__ == "__main__":
    main()