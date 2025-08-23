import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import zipfile
import os

# Set page config
st.set_page_config(page_title="Formula Scaling App", layout="wide")

# Session state initialization
if 'formulas' not in st.session_state:
    st.session_state.formulas = {}
if 'edited_formula_name' not in st.session_state:
    st.session_state.edited_formula_name = None
if 'scaled_results' not in st.session_state:
    st.session_state.scaled_results = None
if 'consolidated_list' not in st.session_state:
    st.session_state.consolidated_list = pd.DataFrame(columns=['Product', 'Ingredient', 'Quantity', 'Unit'])
if 'consolidated_ingredients' not in st.session_state:
    st.session_state.consolidated_ingredients = pd.DataFrame(columns=['Ingredient', 'Quantity', 'Unit', 'Used_In'])

# Helper functions
def validate_formulas():
    for name in list(st.session_state.formulas.keys()):
        # If the formula is just a DataFrame (old format), convert to new format
        if isinstance(st.session_state.formulas[name], pd.DataFrame):
            st.session_state.formulas[name] = {
                'data': st.session_state.formulas[name],
                'desired_qty': 1.0,
                'unit': 'each'
            }
        # Ensure all required keys exist
        elif isinstance(st.session_state.formulas[name], dict):
            st.session_state.formulas[name].setdefault('desired_qty', 1.0)
            st.session_state.formulas[name].setdefault('unit', 'each')
            if 'data' not in st.session_state.formulas[name]:
                st.session_state.formulas[name]['data'] = pd.DataFrame()

def calculate_percentage_contribution(formula_df): #, quantity_column='Quantity'):
    """
    Calculate percentage contribution of each ingredient in a formula.
    """
    df = formula_df.copy()
    
    # Convert quantity to numeric
    #df[quantity_column] = pd.to_numeric(df[quantity_column], errors='coerce')
    quantity_col = pd.to_numeric(df['Quantity'], errors='coerce')
    #df = df.dropna(subset=[quantity_column])
    
    # Calculate total and percentages
    total = quantity_col.sum()
    df['Percentage'] = (df[quantity_col] / total * 100).round(2) if total > 0 else 0
    
    return df

def display_formula_editor():
    st.header("Formula Management")
    validate_formulas()

    if not st.session_state.formulas:
        st.info("No formulas uploaded yet. Please upload formulas first.")
        return
    
    # Create editable table of all formulas
    edit_df = pd.DataFrame([
        {
            'Formula Name': name,
            'Desired Quantity': details['desired_qty'],
            'Unit of Measure': details['unit'],
            'Ingredients Count': len(details['data'])
        }
        for name, details in st.session_state.formulas.items()
    ])
    
    # Display editable table
    edited_df = st.data_editor(
        edit_df,
        num_rows="fixed",
        use_container_width=True,
        column_config={
            "Formula Name": st.column_config.TextColumn(required=True),
            "Desired Quantity": st.column_config.NumberColumn(min_value=0.1, step=0.1),
            "Unit of Measure": st.column_config.TextColumn(required=True)
        }
    )
    
    # Save changes button
    if st.button("Save All Changes"):
        # Create mapping of old to new names
        name_changes = {}
        for idx, row in edited_df.iterrows():
            old_name = edit_df.iloc[idx]['Formula Name']
            new_name = row['Formula Name']
            if old_name != new_name:
                name_changes[old_name] = new_name
        
        # Update formula names and properties
        updated_formulas = {}
        for idx, row in edited_df.iterrows():
            old_name = edit_df.iloc[idx]['Formula Name']
            if old_name in name_changes:
                data = st.session_state.formulas[old_name]['data']
            else:
                data = st.session_state.formulas[row['Formula Name']]['data']
            
            updated_formulas[row['Formula Name']] = {
                'data': data,
                'desired_qty': row['Desired Quantity'],
                'unit': row['Unit of Measure']
            }
        
        st.session_state.formulas = updated_formulas
        st.success("All changes saved successfully!")

def edit_formula():
    st.header("Edit Formula")
    
    if not st.session_state.formulas:
        st.warning("No formulas available to edit. Please upload formulas first.")
        return
    
    # Select formula to edit
    formula_name = st.selectbox(
        "Select formula to edit",
        list(st.session_state.formulas.keys()),
        key='formula_selector'
    )
    
    if formula_name not in st.session_state.formulas:
        st.error("Selected formula not found")
        return
    
    formula_data = st.session_state.formulas[formula_name]
    
    # Edit basic properties
    with st.expander("Formula Properties", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input(
                "Formula Name",
                value=formula_name,
                key=f'name_{formula_name}'
            )
        with col2:
            new_desired_qty = st.number_input(
                "Desired Quantity",
                min_value=0.1,
                value=float(formula_data['desired_qty']),
                step=0.1,
                key=f'qty_{formula_name}'
            )
        new_unit = st.text_input(
            "Unit of Measure",
            value=formula_data['unit'],
            key=f'unit_{formula_name}'
        )
    
    # Edit ingredients
    with st.expander("Edit Ingredients", expanded=True):
        # Make editable copy of the ingredients dataframe
        edited_ingredients = st.data_editor(
            formula_data['data'],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Ingredient": st.column_config.TextColumn(required=True),
                "Quantity": st.column_config.NumberColumn(required=True, min_value=0),
                "Unit": st.column_config.TextColumn(required=True)
            },
            key=f'ingredients_{formula_name}'
        )
    
    # Save changes
    if st.button("Save Formula Changes", key=f'save_{formula_name}'):
        try:
            # Handle formula rename
            if new_name != formula_name:
                if new_name in st.session_state.formulas:
                    st.error("A formula with this name already exists")
                    return
                # Remove old entry
                st.session_state.formulas.pop(formula_name)
            
            # Update formula data
            st.session_state.formulas[new_name] = {
                'data': edited_ingredients,
                'desired_qty': new_desired_qty,
                'unit': new_unit
            }
            
            st.success(f"Formula '{new_name}' updated successfully!")
            
            # Recalculate consolidated ingredients if they exist
            if not st.session_state.consolidated_ingredients.empty:
                calculate_consolidated_ingredients()
                
        except Exception as e:
            st.error(f"Error saving changes: {str(e)}")
    
    # Delete formula option
    if st.button("Delete Formula", type="primary"):
        if st.checkbox(f"Confirm deletion of '{formula_name}'?"):
            st.session_state.formulas.pop(formula_name)
            st.success(f"Formula '{formula_name}' deleted")
            # Refresh the page to clear the editor
            st.rerun()
    return

def calculate_consolidated_ingredients():
  consolidated = []
    
  for formula_name, details in st.session_state.formulas.items():
      df = details['data'].copy()
      desired_qty = details['desired_qty']
      
      # Standardize columns
      ingredient_col = find_matching_column(df.columns, ['ingredient', 'material', 'component', 'item'])
      quantity_col = find_matching_column(df.columns, ['quantity', 'amount', 'qty', 'weight'])
      unit_col = find_matching_column(df.columns, ['unit', 'measurement', 'uom'])
      
      if not ingredient_col or not quantity_col:
          continue
      
      df['Ingredient'] = df[ingredient_col]
      df['Quantity'] = pd.to_numeric(df[quantity_col], errors='coerce')
      
      if unit_col:
          df['Unit'] = df[unit_col]
      else:
          df['Unit'] = details['unit']
      
      # Drop rows with invalid quantities
      df = df.dropna(subset=['Quantity'])
      
      # Calculate percentage contribution first
      total = df['Quantity'].sum()
      if total > 0:
          df['Percentage'] = (df['Quantity'] / total) * 100
      else:
          df['Percentage'] = 0
      
      # Now calculate scaled quantity based on percentage of desired quantity
      df['Scaled Quantity'] = (desired_qty * df['Percentage'] / 100).round(4)
      
      for _, row in df.iterrows():
          consolidated.append({
              'Ingredient': row['Ingredient'],
              'Quantity': row['Scaled Quantity'],
              'Unit': row['Unit'],
              'Used_In': formula_name,
              'Percentage': row['Percentage']
          })
  
  if consolidated:
      st.session_state.consolidated_ingredients = pd.DataFrame(consolidated)
  return
    

def display_consolidated_ingredients():
    st.header("Consolidated Ingredients (Percentage-Based Scaling)")
    
    if st.session_state.consolidated_ingredients.empty:
        st.info("No ingredients to display. Please calculate first.")
        return
    
    # Group by ingredient and sum quantities
    summary_df = st.session_state.consolidated_ingredients.groupby(
        ['Ingredient', 'Unit']
    ).agg({
        'Quantity': 'sum',
        'Percentage': 'mean',  # Average percentage across formulas
        'Used_In': lambda x: ', '.join(sorted(set(x)))
    }).reset_index()
    
    # Format the display
    summary_df['Percentage'] = summary_df['Percentage'].round(4)
    summary_df['Quantity'] = summary_df['Quantity'].round(4)
    st.markdown("""
    ### Formula Scaling Results
    
    1. **Upload Formulas**: Go to the "Upload Formula" tab
    2. **Edit Formula Names**: Rename uploaded formulas
    3. **Scale Formulas**: Use the "Formula Scaling" tab
    4. **View Results**: See scaled results in "Calculate Ingredients"
    5. **Build Consolidated List**: Add scaled formulas to your master list
    """)
    
    st.dataframe(
        summary_df[['Ingredient', 'Quantity', 'Unit', 'Percentage', 'Used_In']],
        use_container_width=True,
        column_config={
            "Percentage": st.column_config.NumberColumn(format="%.2f%%"),
            "Quantity": st.column_config.NumberColumn(format="%.4f")
        }
    )

    
    # Download buttons
    csv = summary_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Consolidated Ingredients (CSV)",
        data=csv,
        file_name='percentage_based_ingredients.csv',
        mime='text/csv'
    )
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        summary_df.to_excel(writer, index=False)
    st.download_button(
        label="Download Consolidated Ingredients (Excel)",
        data=buffer.getvalue(),
        file_name='percentage_based_ingredients.xlsx',
        mime='application/vnd.ms-excel'
    )

def find_matching_column(columns, keywords):
    for keyword in keywords:
        for col in columns:
            if keyword.lower() in col.lower():
                return col
    return None

def process_uploaded_files(uploaded_files):
    formulas = {}
    
    for uploaded_file in uploaded_files:
        try:
            if uploaded_file.name.endswith('.zip'):
                with zipfile.ZipFile(uploaded_file) as z:
                    for file_name in z.namelist():
                        if file_name.endswith(('.csv', '.xlsx', '.xls')):
                            with z.open(file_name) as f:
                                if file_name.endswith('.csv'):
                                    df = pd.read_csv(f)
                                else:
                                    df = pd.read_excel(f)
                                formula_name = os.path.splitext(os.path.basename(file_name))[0]
                                formulas[formula_name] = {
                                    'data': df,
                                    'desired_qty': 1.0,
                                    'unit': 'each'
                                }
            else:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                formula_name = os.path.splitext(uploaded_file.name)[0]
                formulas[formula_name] = {
                    'data': df,
                    'desired_qty': 1.0,
                    'unit': 'each'
                }
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
    
    return formulas

def home_tab():
    st.title("Formula Scaling App")
    st.markdown("""
    ## Welcome to the Formula Scaling Application
    
    This app helps you:
    - Upload and manage product formulas
    - Edit formula names and contents
    - Scale formulas to different production quantities
    - Build a consolidated ingredients list
    - Download scaled formulas
    
    ### How It Works
    
    1. **Upload Formulas**: Go to the "Upload Formula" tab
    2. **Edit Formula Names**: Rename uploaded formulas
    3. **Scale Formulas**: Use the "Formula Scaling" tab
    4. **View Results**: See scaled results in "Calculate Ingredients"
    5. **Build Consolidated List**: Add scaled formulas to your master list
    """)

def upload_tab():
    st.title("Upload Formulas")
    
    uploaded_files = st.file_uploader(
        "Upload formula files (CSV, Excel) or zip containing multiple files",
        type=['csv', 'xlsx', 'xls', 'zip'],
        accept_multiple_files=True
    )
    
    if st.button("Process Uploaded Files") and uploaded_files:
        with st.spinner("Processing files..."):
            new_formulas = process_uploaded_files(uploaded_files)
            st.session_state.formulas.update(new_formulas)
            st.success(f"Successfully loaded {len(new_formulas)} formulas")
    
    if st.session_state.formulas:
        st.subheader("Manage Uploaded Formulas")
        display_formula_editor()
    
    if st.button("View Consolidated Ingredients"):
        calculate_consolidated_ingredients()
        display_consolidated_ingredients()

def main():
    home, upload = st.tabs(["Home", "Upload Formula"])

    with home:
        home_tab()
    
    with upload:
        upload_tab()

if __name__ == "__main__":
    main()
