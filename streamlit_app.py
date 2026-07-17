"""
EQPIS - Earthly Q Production Intelligence System
Version 15.0 - Comprehensive Data Matching & Business Intelligence
"""

import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import string
import time
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import bcrypt

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = "eqpis_database.sqlite"
BATCH_PREFIX = "EQ"
DEFAULT_BATCH_SIZE = 1000

COLORS = {
    'primary': '#C2185B', 'primary_light': '#F8BBD0', 'primary_pale': '#FCE4EC',
    'accent': '#E91E63', 'bg_beige': '#F5F0E6', 'white': '#FFFFFF',
    'success': '#4CAF50', 'warning': '#FF9800', 'error': '#F44336',
}

# All business data fields that can be matched
BUSINESS_DATA_FIELDS = {
    'Product Information': {
        'product_name': 'Product Name',
        'product_category': 'Product Category',
        'product_description': 'Product Description',
        'sku_code': 'SKU Code',
        'barcode': 'Barcode',
    },
    'Pricing & Sales': {
        'selling_price_unit': 'Selling Price per Unit (R)',
        'wholesale_price': 'Wholesale Price (R)',
        'retail_price': 'Retail Price (R)',
        'bulk_price': 'Bulk/Volume Price (R)',
        'discount_rate': 'Discount Rate (%)',
        'min_order_quantity': 'Minimum Order Quantity',
    },
    'Production Costs': {
        'raw_material_cost_batch': 'Raw Material Cost per Batch (R)',
        'packaging_cost_unit': 'Packaging Cost per Unit (R)',
        'labour_cost_hour': 'Labour Cost per Hour (R)',
        'labour_cost_batch': 'Labour Cost per Batch (R)',
        'overhead_cost_batch': 'Overhead Cost per Batch (R)',
        'equipment_cost_batch': 'Equipment Cost per Batch (R)',
        'utility_cost_batch': 'Utility Cost per Batch (R)',
        'total_production_cost': 'Total Production Cost (R)',
    },
    'Batch Production': {
        'units_produced': 'Units Produced per Batch',
        'batch_size_grams': 'Batch Size (grams)',
        'batch_size_liters': 'Batch Size (liters)',
        'production_time_hours': 'Production Time (Hours)',
        'time_per_unit_minutes': 'Time per Unit (Minutes)',
        'yield_percentage': 'Production Yield (%)',
        'wastage_percentage': 'Wastage (%)',
        'quality_pass_rate': 'Quality Pass Rate (%)',
    },
    'Inventory & Supply Chain': {
        'material_name': 'Material/Ingredient Name',
        'stock_quantity': 'Current Stock Quantity',
        'reorder_level': 'Reorder Level',
        'reorder_quantity': 'Reorder Quantity',
        'lead_time_days': 'Supplier Lead Time (Days)',
        'safety_stock': 'Safety Stock Level',
        'storage_location': 'Storage Location',
        'expiry_date': 'Expiry Date',
    },
    'Supplier Information': {
        'supplier_name': 'Supplier Name',
        'supplier_contact': 'Supplier Contact Person',
        'supplier_email': 'Supplier Email',
        'supplier_phone': 'Supplier Phone',
        'supplier_price': 'Supplier Price (R)',
        'supplier_size': 'Supplier Package Size',
        'supplier_price_per_unit': 'Supplier Price per Unit (R)',
        'supplier_link': 'Supplier Link/URL',
        'supplier_rating': 'Supplier Rating (1-5)',
        'supplier_payment_terms': 'Payment Terms',
    },
    'Financial Metrics': {
        'revenue_per_batch': 'Revenue per Batch (R)',
        'revenue_per_unit': 'Revenue per Unit (R)',
        'gross_profit_batch': 'Gross Profit per Batch (R)',
        'gross_profit_unit': 'Gross Profit per Unit (R)',
        'gross_margin_percent': 'Gross Margin (%)',
        'net_profit_batch': 'Net Profit per Batch (R)',
        'marketing_cost_unit': 'Marketing Cost per Unit (R)',
        'shipping_cost_unit': 'Shipping Cost per Unit (R)',
        'total_cost_per_unit': 'Total Cost per Unit (R)',
        'break_even_units': 'Break-Even Units',
        'return_on_investment': 'ROI (%)',
    },
    'Sales & Customer': {
        'units_sold_month': 'Units Sold per Month',
        'units_sold_week': 'Units Sold per Week',
        'customer_acquisition_cost': 'Customer Acquisition Cost (R)',
        'customer_lifetime_value': 'Customer Lifetime Value (R)',
        'repeat_purchase_rate': 'Repeat Purchase Rate (%)',
        'return_rate': 'Return/Refund Rate (%)',
        'marketplace_fees': 'Marketplace/Platform Fees (R)',
    },
}

def apply_css():
    st.markdown(f"""
    <style>
        .stApp {{ background-color: {COLORS['bg_beige']}; }}
        [data-testid="stSidebar"] {{ background-color: {COLORS['white']}; }}
        h1, h2, h3 {{ color: {COLORS['primary']} !important; }}
        .stButton > button {{ background-color: {COLORS['primary']}; color: white; border: none; border-radius: 8px; padding: 10px 24px; font-weight: 600; }}
        .capacity-card {{ background: white; border-radius: 10px; padding: 15px; margin: 8px 0; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
        .can-produce {{ border-left: 4px solid {COLORS['success']}; }}
        .cannot-produce {{ border-left: 4px solid {COLORS['error']}; }}
        .queue-card {{ background: white; border-radius: 10px; padding: 20px; margin: 10px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .user-info-card {{ background: {COLORS['primary_pale']}; padding: 15px; border-radius: 10px; margin-bottom: 20px; }}
        .role-badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.8em; color: white; }}
        .role-owner {{ background-color: {COLORS['primary']}; }}
        .role-manager {{ background-color: {COLORS['accent']}; }}
        .role-worker {{ background-color: #F48FB1; }}
        [data-testid="stMetric"] {{ background: white; border-radius: 8px; padding: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .completion-report {{ background: white; border: 2px solid {COLORS['success']}; border-radius: 12px; padding: 25px; margin: 20px 0; }}
        .data-match-card {{ background: white; border: 2px solid {COLORS['primary_light']}; border-radius: 10px; padding: 20px; margin: 15px 0; }}
        .matched-field {{ background: #E8F5E9; border-left: 4px solid {COLORS['success']}; padding: 10px; margin: 5px 0; border-radius: 5px; }}
        .unmatched-field {{ background: #FFF3E0; border-left: 4px solid {COLORS['warning']}; padding: 10px; margin: 5px 0; border-radius: 5px; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 8px; padding: 10px; border-radius: 10px; }}
        .stTabs [data-baseweb="tab"] {{ background: white; border-radius: 8px; padding: 12px 24px; font-size: 0.95em; white-space: nowrap; }}
        .stTabs [aria-selected="true"] {{ background: {COLORS['primary']} !important; color: white !important; }}
        .section-divider {{ border-top: 2px solid {COLORS['primary_light']}; margin: 25px 0; }}
        .production-line {{ background: white; border-radius: 12px; padding: 25px; margin: 15px 0; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def dict_from_row(self, row):
        if row is None: return None
        return {key: row[key] for key in row.keys()}
    
    @staticmethod
    def safe_float(val, default=0):
        if val is None: return default
        if isinstance(val, (int, float)): return float(val)
        if isinstance(val, str):
            val = val.strip().replace('%', '').replace(',', '').replace('R', '')
            try: return float(val)
            except: return default
        try: return float(val)
        except: return default
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.executescript('''
            CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, is_current INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS formula_ingredients (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, ingredient_name TEXT NOT NULL, percentage REAL NOT NULL, unit TEXT DEFAULT 'g');
            CREATE TABLE IF NOT EXISTS raw_materials (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, supplier TEXT DEFAULT '', cost_per_unit REAL DEFAULT 0, unit TEXT DEFAULT 'g', stock_quantity REAL DEFAULT 0, reorder_quantity REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, ingredient_name TEXT NOT NULL, supplier1_name TEXT DEFAULT '', supplier1_price REAL DEFAULT 0, supplier1_size TEXT DEFAULT '', supplier1_price_per_unit REAL DEFAULT 0, link1 TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS packaging_costs (id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT NOT NULL, total_packaging_cost REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS product_cost_analysis (id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT NOT NULL, raw_material_cost_batch REAL DEFAULT 0, units_produced INTEGER DEFAULT 0, selling_price_unit REAL DEFAULT 0, labour_cost_hour REAL DEFAULT 0, production_time_hours REAL DEFAULT 0, time_per_unit_minutes REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS production_batches (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_number TEXT NOT NULL UNIQUE, product_id INTEGER NOT NULL, batch_size REAL NOT NULL, production_date TEXT, start_time TEXT, end_time TEXT, time_spent REAL DEFAULT 0, units_produced INTEGER DEFAULT 0, notes TEXT DEFAULT '', status TEXT DEFAULT 'queued', completed_by TEXT DEFAULT '', total_material_cost REAL DEFAULT 0, total_packaging_cost REAL DEFAULT 0, total_batch_cost REAL DEFAULT 0, has_shortages INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS batch_materials_used (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL, ingredient_name TEXT NOT NULL, quantity_used REAL NOT NULL, unit TEXT DEFAULT 'g', batch_number TEXT DEFAULT '', expiry_date TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS batch_files (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL, filename TEXT, file_data BLOB, file_type TEXT, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS batch_completion_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL, batch_number TEXT, product_name TEXT, completed_by TEXT, time_spent REAL, units_produced INTEGER, low_stock_alerts TEXT, completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS unmapped_data (id INTEGER PRIMARY KEY AUTOINCREMENT, sheet_name TEXT, column_name TEXT, sample_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS data_mappings (id INTEGER PRIMARY KEY AUTOINCREMENT, sheet_name TEXT, source_column TEXT, target_field TEXT, target_category TEXT, target_product TEXT DEFAULT '', manual_value TEXT DEFAULT '', mapped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS business_data (id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT, field_name TEXT, field_value TEXT, field_category TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS production_instructions (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL UNIQUE, instructions TEXT DEFAULT '', safety_notes TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS restock_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, ingredient_name TEXT NOT NULL, quantity_needed REAL, estimated_cost REAL, status TEXT DEFAULT 'pending', requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS ops_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, note_text TEXT, note_type TEXT DEFAULT 'general', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        ''')
        conn.commit()
        conn.close()
    
    def has_data(self):
        conn = self.connect()
        return conn.execute("SELECT COUNT(*) FROM products WHERE is_current=1").fetchone()[0] > 0
    
    def get_stats(self):
        conn = self.connect()
        return {
            'products': conn.execute("SELECT COUNT(*) FROM products WHERE is_current=1").fetchone()[0],
            'formula_ingredients': conn.execute("SELECT COUNT(*) FROM formula_ingredients").fetchone()[0],
            'raw_materials': conn.execute("SELECT COUNT(*) FROM raw_materials").fetchone()[0],
            'suppliers': conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
            'packaging': conn.execute("SELECT COUNT(*) FROM packaging_costs").fetchone()[0],
            'cost_analysis': conn.execute("SELECT COUNT(*) FROM product_cost_analysis").fetchone()[0],
        }
    
    def get_uploaded_sheets(self):
        """Get list of all uploaded sheets for data matching"""
        conn = self.connect()
        sheets = set()
        for r in conn.execute("SELECT DISTINCT sheet_name FROM unmapped_data").fetchall():
            sheets.add(r['sheet_name'])
        # Also get sheets from mapped data
        for r in conn.execute("SELECT DISTINCT sheet_name FROM data_mappings").fetchall():
            sheets.add(r['sheet_name'])
        conn.close()
        return sorted(list(sheets))
    
    def get_sheet_columns(self, sheet_name):
        """Get all columns from a specific sheet"""
        conn = self.connect()
        columns = []
        for r in conn.execute("SELECT column_name, sample_data FROM unmapped_data WHERE sheet_name=?", (sheet_name,)).fetchall():
            columns.append({'column': r['column_name'], 'sample': r['sample_data']})
        conn.close()
        return columns
    
    def save_data_mapping(self, sheet_name, source_column, target_field, target_category, target_product=""):
        conn = self.connect()
        existing = conn.execute("SELECT id FROM data_mappings WHERE sheet_name=? AND source_column=? AND target_field=?", (sheet_name, source_column, target_field)).fetchone()
        if existing:
            conn.execute("UPDATE data_mappings SET target_category=?, target_product=?, mapped_at=? WHERE id=?", (target_category, target_product, datetime.now(), existing[0]))
        else:
            conn.execute("INSERT INTO data_mappings (sheet_name, source_column, target_field, target_category, target_product) VALUES (?,?,?,?,?)", (sheet_name, source_column, target_field, target_category, target_product))
        conn.commit(); conn.close()
    
    def get_data_mappings(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM data_mappings ORDER BY target_category, target_field").fetchall()]
    
    def save_business_data(self, product_name, field_name, field_value, field_category):
        conn = self.connect()
        existing = conn.execute("SELECT id FROM business_data WHERE product_name=? AND field_name=?", (product_name, field_name)).fetchone()
        if existing:
            conn.execute("UPDATE business_data SET field_value=?, field_category=?, updated_at=? WHERE id=?", (str(field_value), field_category, datetime.now(), existing[0]))
        else:
            conn.execute("INSERT INTO business_data (product_name, field_name, field_value, field_category) VALUES (?,?,?,?)", (product_name, field_name, str(field_value), field_category))
        conn.commit(); conn.close()
    
    def get_business_data(self, product_name=None):
        conn = self.connect()
        if product_name:
            return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM business_data WHERE product_name=? ORDER BY field_category, field_name", (product_name,)).fetchall()]
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM business_data ORDER BY product_name, field_category, field_name").fetchall()]
    
    def apply_mappings_to_data(self, sheet_name):
        """Apply saved mappings to populate business_data from unmapped_data"""
        conn = self.connect()
        mappings = [self.dict_from_row(r) for r in conn.execute("SELECT * FROM data_mappings WHERE sheet_name=?", (sheet_name,)).fetchall()]
        
        count = 0
        for mp in mappings:
            # Get the data from unmapped_data
            data = conn.execute("SELECT sample_data FROM unmapped_data WHERE sheet_name=? AND column_name=?", (sheet_name, mp['source_column'])).fetchone()
            if data:
                values = data['sample_data'].split('|')
                # For now, associate with target_product or first product
                product = mp['target_product'] if mp['target_product'] else 'General'
                for val in values:
                    if val and val != 'nan':
                        existing = conn.execute("SELECT id FROM business_data WHERE product_name=? AND field_name=?", (product, mp['target_field'])).fetchone()
                        if existing:
                            conn.execute("UPDATE business_data SET field_value=?, field_category=?, updated_at=? WHERE id=?", (val, mp['target_category'], datetime.now(), existing[0]))
                        else:
                            conn.execute("INSERT INTO business_data (product_name, field_name, field_value, field_category) VALUES (?,?,?,?)", (product, mp['target_field'], val, mp['target_category']))
                        count += 1
        conn.commit(); conn.close()
        return count
    
    # ============ STANDARD METHODS (kept for compatibility) ============
    def add_product(self, name):
        conn = self.connect()
        r = conn.execute("SELECT id FROM products WHERE name=?", (name,)).fetchone()
        if r: return r[0]
        conn.execute("INSERT INTO products (name) VALUES (?)", (name,)); conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    def rename_product(self, old_name, new_name):
        conn = self.connect()
        conn.execute("UPDATE products SET name=? WHERE name=?", (new_name, old_name))
        conn.execute("UPDATE packaging_costs SET product_name=? WHERE product_name=?", (new_name, old_name))
        conn.execute("UPDATE product_cost_analysis SET product_name=? WHERE product_name=?", (new_name, old_name))
        conn.execute("UPDATE business_data SET product_name=? WHERE product_name=?", (new_name, old_name))
        conn.commit(); conn.close()
    
    def get_all_products(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM products WHERE is_current=1").fetchall()]
    
    def has_formula(self, product_name):
        conn = self.connect()
        return conn.execute("SELECT COUNT(*) FROM formula_ingredients fi JOIN products p ON fi.product_id=p.id WHERE p.name=?", (product_name,)).fetchone()[0] > 0
    
    def save_formula(self, product_name, ingredients_df):
        conn = self.connect()
        pid = self.add_product(product_name)
        conn.execute("DELETE FROM formula_ingredients WHERE product_id=?", (pid,))
        count = 0
        for _, row in ingredients_df.iterrows():
            ing = None
            for col in ['Ingredient', 'ingredient_name', 'Ingredient Name']:
                if col in row.index:
                    val = row[col]
                    if not pd.isna(val) and str(val).strip() and str(val) != 'nan': ing = str(val).strip(); break
            pct = 0
            for col in ['%', 'percentage', 'Percentage']:
                if col in row.index:
                    try: pct = float(row[col])
                    except: pct = 0; break
            if ing and pct > 0:
                conn.execute("INSERT INTO formula_ingredients (product_id, ingredient_name, percentage) VALUES (?,?,?)", (pid, ing, pct)); count += 1
        conn.commit(); conn.close(); return count
    
    def get_formula(self, product_id):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM formula_ingredients WHERE product_id=?", (product_id,)).fetchall()]
    
    def delete_formula(self, product_id):
        conn = self.connect()
        conn.execute("DELETE FROM formula_ingredients WHERE product_id=?", (product_id,))
        conn.execute("UPDATE products SET is_current=0 WHERE id=?", (product_id,)); conn.commit(); conn.close()
    
    def add_material(self, name, unit='g', stock=0):
        conn = self.connect()
        if conn.execute("SELECT id FROM raw_materials WHERE LOWER(name)=LOWER(?)", (name,)).fetchone(): conn.close(); return False
        conn.execute("INSERT INTO raw_materials (name, unit, stock_quantity) VALUES (?,?,?)", (name, unit, float(stock))); conn.commit(); conn.close(); return True
    
    def save_materials(self, df):
        conn = self.connect()
        for _, row in df.iterrows():
            name = str(row.get('name', row.get('Name', '')))
            if not name or name == 'nan': continue
            stock = self.safe_float(row.get('stock_quantity', row.get('Stock', 0)))
            existing = conn.execute("SELECT id FROM raw_materials WHERE LOWER(name)=LOWER(?)", (name,)).fetchone()
            if existing: conn.execute("UPDATE raw_materials SET stock_quantity=? WHERE id=?", (stock, existing[0]))
            else: conn.execute("INSERT INTO raw_materials (name, stock_quantity) VALUES (?,?)", (name, stock))
        conn.commit(); conn.close()
    
    def get_all_materials(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM raw_materials").fetchall()]
    
    def update_material(self, mat_id, name=None, stock=None, unit=None):
        conn = self.connect()
        if name is not None: conn.execute("UPDATE raw_materials SET name=? WHERE id=?", (str(name), mat_id))
        if stock is not None: conn.execute("UPDATE raw_materials SET stock_quantity=? WHERE id=?", (float(stock), mat_id))
        if unit is not None: conn.execute("UPDATE raw_materials SET unit=? WHERE id=?", (str(unit), mat_id))
        conn.commit(); conn.close()
    
    def remove_material(self, mat_id):
        conn = self.connect(); conn.execute("DELETE FROM raw_materials WHERE id=?", (mat_id,)); conn.commit(); conn.close()
    
    def calculate_reorder(self):
        conn = self.connect()
        mats = conn.execute("SELECT id FROM raw_materials").fetchall()
        prods = conn.execute("SELECT id FROM products WHERE is_current=1").fetchall()
        for mat in mats:
            total = 0
            mat_name = conn.execute("SELECT name FROM raw_materials WHERE id=?", (mat['id'],)).fetchone()
            if mat_name:
                for p in prods:
                    for ing in conn.execute("SELECT ingredient_name, percentage FROM formula_ingredients WHERE product_id=?", (p['id'],)).fetchall():
                        if ing['ingredient_name'].lower() == mat_name['name'].lower(): total += (ing['percentage']/100)*DEFAULT_BATCH_SIZE
            conn.execute("UPDATE raw_materials SET reorder_quantity=? WHERE id=?", (total, mat['id']))
        conn.commit(); conn.close()
    
    def save_packaging(self, df):
        conn = self.connect()
        for _, row in df.iterrows():
            pn = str(row.get('product_name', ''))
            if not pn or pn == 'nan': continue
            cost = self.safe_float(row.get('total_packaging_cost', 0))
            ex = conn.execute("SELECT id FROM packaging_costs WHERE product_name=?", (pn,)).fetchone()
            if ex: conn.execute("UPDATE packaging_costs SET total_packaging_cost=? WHERE id=?", (cost, ex[0]))
            else: conn.execute("INSERT INTO packaging_costs (product_name, total_packaging_cost) VALUES (?,?)", (pn, cost))
        conn.commit(); conn.close()
    
    def get_packaging_cost(self, product_name):
        conn = self.connect()
        r = conn.execute("SELECT total_packaging_cost FROM packaging_costs WHERE product_name=?", (product_name,)).fetchone()
        conn.close(); return r[0] if r else 0
    
    def save_cost_analysis(self, df):
        conn = self.connect()
        for _, row in df.iterrows():
            pn = str(row.get('product_name', ''))
            if not pn or pn == 'nan': continue
            fields = {'raw_material_cost_batch': self.safe_float(row.get('raw_material_cost_batch', 0)), 'units_produced': int(self.safe_float(row.get('units_produced', 0))), 'selling_price_unit': self.safe_float(row.get('selling_price_unit', 0)), 'labour_cost_hour': self.safe_float(row.get('labour_cost_hour', 0))}
            ex = conn.execute("SELECT id FROM product_cost_analysis WHERE product_name=?", (pn,)).fetchone()
            if ex: conn.execute("UPDATE product_cost_analysis SET "+", ".join([f"{k}=?" for k in fields])+" WHERE id=?", list(fields.values())+[ex[0]])
            else: conn.execute(f"INSERT INTO product_cost_analysis (product_name, {', '.join(fields.keys())}) VALUES (?, {', '.join(['?']*len(fields))})", [pn]+list(fields.values()))
        conn.commit(); conn.close()
    
    def get_cost_analysis(self, product_name):
        conn = self.connect()
        r = conn.execute("SELECT * FROM product_cost_analysis WHERE product_name=?", (product_name,)).fetchone()
        conn.close(); return self.dict_from_row(r) if r else {}
    
    def save_suppliers(self, df):
        conn = self.connect()
        for _, row in df.iterrows():
            ing = str(row.get('ingredient_name', row.get('Ingredient', '')))
            if not ing or ing == 'nan': continue
            existing = conn.execute("SELECT id FROM suppliers WHERE ingredient_name=?", (ing,)).fetchone()
            data = {'ingredient_name': ing, 'supplier1_name': str(row.get('supplier1_name', '')), 'supplier1_price': self.safe_float(row.get('supplier1_price', 0)), 'supplier1_size': str(row.get('supplier1_size', '')), 'supplier1_price_per_unit': self.safe_float(row.get('supplier1_price_per_unit', 0)), 'link1': str(row.get('link1', ''))}
            if existing: conn.execute("UPDATE suppliers SET "+", ".join([f"{k}=?" for k in data])+" WHERE id=?", list(data.values())+[existing[0]])
            else: conn.execute(f"INSERT INTO suppliers ({', '.join(data.keys())}) VALUES ({', '.join(['?']*len(data))})", list(data.values()))
        conn.commit(); conn.close()
    
    def get_all_suppliers(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM suppliers").fetchall()]
    
    def create_batch(self, product_id, batch_size, mat_cost=0, pkg_cost=0, total_cost=0):
        conn = self.connect()
        prod = conn.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()
        if not prod: conn.close(); return None
        acr = ''.join([w[0].upper() for w in prod['name'].split() if w])[:4] or prod['name'][:4].upper()
        bn = f"{BATCH_PREFIX}-{acr}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{''.join(random.choices(string.ascii_uppercase+string.digits,k=4))}"
        conn.execute("INSERT INTO production_batches (batch_number, product_id, batch_size, production_date, status, total_material_cost, total_packaging_cost, total_batch_cost) VALUES (?,?,?,?,?,?,?,?)", (bn, product_id, float(batch_size), datetime.now().strftime("%Y-%m-%d"), 'queued', float(mat_cost), float(pkg_cost), float(total_cost)))
        bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for ing in conn.execute("SELECT * FROM formula_ingredients WHERE product_id=?", (product_id,)).fetchall():
            qty = (ing['percentage']/100)*float(batch_size)
            conn.execute("INSERT INTO batch_materials_used (batch_id, ingredient_name, quantity_used, unit, batch_number) VALUES (?,?,?,?,?)", (bid, ing['ingredient_name'], qty, ing['unit'], bn))
        conn.commit(); conn.close(); return bn
    
    def get_batches(self, status=None):
        conn = self.connect()
        q = "SELECT pb.*, p.name as product_name FROM production_batches pb JOIN products p ON pb.product_id=p.id"
        if status: return [self.dict_from_row(r) for r in conn.execute(q+" WHERE pb.status=? ORDER BY pb.id DESC", (status,)).fetchall()]
        return [self.dict_from_row(r) for r in conn.execute(q+" ORDER BY pb.id DESC").fetchall()]
    
    def get_batch_materials(self, batch_id):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM batch_materials_used WHERE batch_id=?", (batch_id,)).fetchall()]
    
    def update_batch_materials(self, batch_id, materials_data):
        conn = self.connect()
        for item in materials_data: conn.execute("UPDATE batch_materials_used SET batch_number=?, expiry_date=? WHERE batch_id=? AND ingredient_name=?", (item.get('batch_number',''), item.get('expiry_date',''), batch_id, item['ingredient_name']))
        conn.commit(); conn.close()
    
    def start_batch(self, batch_id, started_by=""):
        conn = self.connect()
        conn.execute("UPDATE production_batches SET status='active', start_time=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), batch_id)); conn.commit(); conn.close()
    
    def save_batch_file(self, batch_id, filename, file_data, file_type):
        conn = self.connect()
        conn.execute("INSERT INTO batch_files (batch_id, filename, file_data, file_type) VALUES (?,?,?,?)", (batch_id, filename, file_data, file_type)); conn.commit(); conn.close()
    
    def get_batch_files(self, batch_id):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT id, filename, file_type, uploaded_at FROM batch_files WHERE batch_id=?", (batch_id,)).fetchall()]
    
    def complete_batch(self, batch_id, units, notes="", completed_by=""):
        conn = self.connect()
        batch = conn.execute("SELECT * FROM production_batches WHERE id=?", (batch_id,)).fetchone()
        if not batch or not batch['start_time']: conn.close(); return False, {}
        start = datetime.strptime(batch['start_time'], "%Y-%m-%d %H:%M:%S")
        elapsed = (datetime.now() - start).total_seconds()/3600
        conn.execute("UPDATE production_batches SET status='completed', end_time=?, time_spent=?, units_produced=?, notes=?, completed_by=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), elapsed, int(units), notes, completed_by, batch_id))
        low_stock_alerts = []
        for m in conn.execute("SELECT * FROM batch_materials_used WHERE batch_id=?", (batch_id,)).fetchall():
            mat = conn.execute("SELECT id, name, stock_quantity, reorder_quantity FROM raw_materials WHERE LOWER(name)=LOWER(?)", (m['ingredient_name'],)).fetchone()
            if mat:
                new_stock = max(0, mat['stock_quantity']-m['quantity_used'])
                conn.execute("UPDATE raw_materials SET stock_quantity=? WHERE id=?", (new_stock, mat['id']))
                if new_stock < mat['reorder_quantity']: low_stock_alerts.append(f"{mat['name']}: {new_stock:.1f}g")
        prod_name = conn.execute("SELECT name FROM products WHERE id=?", (batch['product_id'],)).fetchone()['name']
        report = {'batch_number': batch['batch_number'], 'product_name': prod_name, 'completed_by': completed_by, 'time_spent': round(elapsed, 2), 'units_produced': int(units), 'low_stock_alerts': '; '.join(low_stock_alerts) if low_stock_alerts else 'None'}
        conn.execute("INSERT INTO batch_completion_reports (batch_id, batch_number, product_name, completed_by, time_spent, units_produced, low_stock_alerts) VALUES (?,?,?,?,?,?,?)", (batch_id, report['batch_number'], report['product_name'], report['completed_by'], report['time_spent'], report['units_produced'], report['low_stock_alerts']))
        conn.commit(); conn.close(); return True, report
    
    def get_completion_reports(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM batch_completion_reports ORDER BY completed_at DESC").fetchall()]
    
    def get_completion_reports_csv(self):
        reports = self.get_completion_reports()
        if not reports: return None
        return pd.DataFrame(reports).to_csv(index=False)
    
    def save_unmapped_data(self, sheet_name, df, mapped_columns):
        conn = self.connect()
        all_cols = df.columns.tolist()
        unmapped = [c for c in all_cols if c not in mapped_columns]
        for col in unmapped:
            sample = '|'.join([str(v) for v in df[col].dropna().head(50).tolist()])
            existing = conn.execute("SELECT id FROM unmapped_data WHERE sheet_name=? AND column_name=?", (sheet_name, col)).fetchone()
            if existing:
                conn.execute("UPDATE unmapped_data SET sample_data=? WHERE id=?", (sample, existing[0]))
            else:
                conn.execute("INSERT INTO unmapped_data (sheet_name, column_name, sample_data) VALUES (?,?,?)", (sheet_name, col, sample))
        conn.commit(); conn.close()
    
    def get_unmapped_data(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM unmapped_data ORDER BY created_at DESC").fetchall()]
    
    def save_instructions(self, product_id, instructions, safety=""):
        conn = self.connect()
        ex = conn.execute("SELECT id FROM production_instructions WHERE product_id=?", (product_id,)).fetchone()
        if ex: conn.execute("UPDATE production_instructions SET instructions=?, safety_notes=? WHERE product_id=?", (instructions, safety, product_id))
        else: conn.execute("INSERT INTO production_instructions (product_id, instructions, safety_notes) VALUES (?,?,?)", (product_id, instructions, safety))
        conn.commit(); conn.close()
    
    def get_instructions(self, product_id):
        conn = self.connect()
        r = conn.execute("SELECT * FROM production_instructions WHERE product_id=?", (product_id,)).fetchone()
        conn.close(); return self.dict_from_row(r)
    
    def create_restock_request(self, ingredient_name, quantity_needed, estimated_cost):
        conn = self.connect()
        conn.execute("INSERT INTO restock_requests (ingredient_name, quantity_needed, estimated_cost) VALUES (?,?,?)", (ingredient_name, quantity_needed, estimated_cost)); conn.commit(); conn.close()
    
    def get_restock_requests(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM restock_requests ORDER BY requested_at DESC").fetchall()]
    
    def save_ops_note(self, note_text, note_type="general"):
        conn = self.connect()
        conn.execute("INSERT INTO ops_notes (note_text, note_type) VALUES (?,?)", (note_text, note_type)); conn.commit(); conn.close()
    
    def get_ops_notes(self):
        conn = self.connect()
        return [self.dict_from_row(r) for r in conn.execute("SELECT * FROM ops_notes ORDER BY created_at DESC LIMIT 20").fetchall()]
    
    def get_total_units_produced(self):
        conn = self.connect()
        return conn.execute("SELECT COALESCE(SUM(units_produced), 0) FROM production_batches WHERE status='completed'").fetchone()[0]
    
    def get_production_capacity(self):
        prods = self.get_all_products(); mats = self.get_all_materials()
        capacity = {'can_produce': [], 'cannot_produce': []}
        for p in prods:
            ings = self.get_formula(p['id'])
            if not ings: continue
            can_make = True
            for ing in ings:
                mat = next((m for m in mats if m['name'].lower() == ing['ingredient_name'].lower()), None)
                if mat:
                    needed = (ing['percentage']/100) * 1000
                    if mat['stock_quantity'] < needed: can_make = False
            if can_make: capacity['can_produce'].append({'name': p['name'], 'id': p['id']})
            else: capacity['cannot_produce'].append({'name': p['name'], 'id': p['id']})
        return capacity
    
    def get_insights_data(self):
        batches = self.get_batches()
        completed = [b for b in batches if b['status'] == 'completed']
        ingredient_usage = {}
        for b in completed:
            for m in self.get_batch_materials(b['id']):
                ing = m['ingredient_name']
                if ing not in ingredient_usage: ingredient_usage[ing] = 0
                ingredient_usage[ing] += m['quantity_used']
        product_margins = {}
        for b in completed:
            ca = self.get_cost_analysis(b['product_name'])
            revenue = (b.get('units_produced', 0) * ca.get('selling_price_unit', 0)) if ca else 0
            cost = b.get('total_batch_cost', 0)
            pn = b['product_name']
            if pn not in product_margins: product_margins[pn] = {'revenue': 0, 'cost': 0, 'profit': 0, 'units': 0}
            product_margins[pn]['revenue'] += revenue; product_margins[pn]['cost'] += cost; product_margins[pn]['profit'] += revenue - cost; product_margins[pn]['units'] += b.get('units_produced', 0)
        for pn in product_margins:
            if product_margins[pn]['revenue'] > 0: product_margins[pn]['margin'] = product_margins[pn]['profit'] / product_margins[pn]['revenue'] * 100
        return {'ingredient_usage': ingredient_usage, 'product_margins': product_margins, 'completed_count': len(completed)}

# ============================================================================
# DATA PARSER
# ============================================================================

class DataParser:
    @staticmethod
    def detect_category(df, sheet_name=""):
        cols = ' '.join([c.lower().strip() for c in df.columns])
        if any(k in cols for k in ['supplier1','supplier2','price/unit']): return 'suppliers'
        if any(k in cols for k in ['cost of raw materials','gross profit','selling price']): return 'cost_analysis'
        if any(k in cols for k in ['container price','cap/lid','labeling']): return 'packaging'
        fs = sum(1 for k in ['ingredient','percentage','%'] if k in cols or k in sheet_name.lower())
        ms = sum(1 for k in ['stock','quantity','inventory'] if k in cols or k in sheet_name.lower())
        return 'formulas' if fs>=ms and fs>0 else ('materials' if ms>0 else 'unknown')
    
    @staticmethod
    def clean_pct(v):
        if pd.isna(v): return 0
        if isinstance(v,str): v = v.strip().replace('%','')
        try: n = float(v); return n*100 if 0<n<=1 else n
        except: return 0

# ============================================================================
# RBAC
# ============================================================================

class RBAC:
    PERMS = {
        'business_owner': {'data':1,'ops':1,'production':1,'insights':1,'import':1,'edit_formula':1,'view_pct':1,'edit_inv':1,'add_inv':1,'remove_inv':1,'queue':1,'start':1,'complete':1,'instructions':1,'restock':1,'download':1},
        'production_manager': {'data':1,'ops':1,'production':1,'insights':1,'import':1,'edit_formula':1,'view_pct':1,'edit_inv':1,'add_inv':0,'remove_inv':0,'queue':1,'start':1,'complete':0,'instructions':0,'restock':1,'download':0},
        'factory_worker': {'data':0,'ops':0,'production':1,'insights':0,'import':0,'edit_formula':0,'view_pct':0,'edit_inv':1,'add_inv':0,'remove_inv':0,'queue':0,'start':1,'complete':1,'instructions':0,'restock':0,'download':0}
    }
    @classmethod
    def can(cls, role, perm): return cls.PERMS.get(role,{}).get(perm,0)

# ============================================================================
# UI - SIDEBAR
# ============================================================================

def render_sidebar(db):
    st.sidebar.markdown(f'<div style="text-align:center;padding:20px;"><h2 style="color:{COLORS["primary"]};">🌿 EQPIS</h2></div>', unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("👤 Select Role")
    roles = {'business_owner': '💼 Business Owner', 'production_manager': '📋 Production Manager', 'factory_worker': '👷 Factory Worker'}
    
    if 'role' not in st.session_state:
        st.session_state.role = 'business_owner'
    
    selected_role = st.sidebar.selectbox("Role:", list(roles.keys()), format_func=lambda x: roles[x], index=list(roles.keys()).index(st.session_state.role), key="role_selector")
    st.session_state.role = selected_role
    
    rc = f"role-{selected_role.split('_')[0]}" if '_' in selected_role else "role-owner"
    st.sidebar.markdown(f'<div class="user-info-card"><p><span class="role-badge {rc}">{roles[selected_role]}</span></p></div>', unsafe_allow_html=True)
    
    if RBAC.can(selected_role, 'import'):
        st.sidebar.markdown("---")
        st.sidebar.subheader("📥 Data Upload")
        uf = st.sidebar.file_uploader("Excel/CSV/ZIP files", type=['xlsx','xls','csv','zip'], accept_multiple_files=True, key="sfu", label_visibility="collapsed")
        if uf and st.sidebar.button("🔍 Process Files", type="primary", use_container_width=True):
            sheets = []
            for f in uf:
                try:
                    if f.name.endswith('.zip'):
                        with zipfile.ZipFile(f) as zf:
                            for fn in zf.namelist():
                                if fn.endswith('.csv'): df=pd.read_csv(zf.open(fn)); sheets.append({'name':fn.replace('.csv',''),'df':df,'source':f.name})
                                elif fn.endswith(('.xlsx','.xls')): df=pd.read_excel(zf.open(fn)); sheets.append({'name':fn,'df':df,'source':f.name})
                    elif f.name.endswith('.csv'): df=pd.read_csv(f); sheets.append({'name':f.name.replace('.csv',''),'df':df,'source':f.name})
                    else:
                        for sn in pd.ExcelFile(f).sheet_names: df=pd.read_excel(f,sheet_name=sn); sheets.append({'name':sn,'df':df,'source':f.name})
                except Exception as e: st.sidebar.error(f"Error: {f.name}")
            for s in sheets: s['category']=DataParser.detect_category(s['df'],s['name'])
            st.session_state.pending_sheets=sheets; st.session_state.show_mapping=True; st.rerun()
    
    if selected_role in ['business_owner','production_manager']:
        st.sidebar.markdown("---"); st.sidebar.subheader("📊 Status")
        s=db.get_stats()
        c1,c2=st.sidebar.columns(2)
        c1.metric("Products",s['products']); c1.metric("Materials",s['raw_materials']); c2.metric("Ingredients",s['formula_ingredients']); c2.metric("Suppliers",s['suppliers'])
    
    return selected_role

# ============================================================================
# UI - WELCOME, MAPPING, DATA CENTRE, OPERATIONS, PRODUCTION
# (Same as previous version - kept for brevity)
# ============================================================================

def render_welcome_page():
    st.markdown(f"<h1 style='text-align:center;color:{COLORS['primary']};'>🌿 Welcome to EQPIS!</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Select your role and upload Excel/CSV/ZIP files via sidebar to begin.</p>", unsafe_allow_html=True)

def render_mapping(db):
    st.subheader("🔧 Column Mapping")
    if not st.session_state.get('pending_sheets'): return
    sti = []
    for i, s in enumerate(st.session_state.pending_sheets):
        df = s['df']; sheet_name = s['name']
        with st.expander(f"📄 {sheet_name}", expanded=True):
            st.dataframe(df.head(3), use_container_width=True)
            dc = s.get('category', 'unknown')
            co = ['formulas', 'materials', 'packaging', 'cost_analysis', 'suppliers', 'unknown']
            try: di = co.index(dc)
            except: di = 5
            cat = st.selectbox("Category", co, index=di, key=f"cat_{i}")
            ign = st.checkbox(f"☐ Ignore: **{sheet_name}**", key=f"ign_{i}")
            if not ign and cat != 'unknown':
                mp = {}; cols = df.columns.tolist(); mapped_cols = []
                if cat == 'formulas':
                    ic = next((c for c in cols if 'ingredient' in c.lower()), cols[0] if cols else None)
                    if ic: mp['ingredient_name'] = st.selectbox("Ingredient", cols, index=cols.index(ic) if ic in cols else 0, key=f"in_{i}"); mapped_cols.append(ic)
                    pc = next((c for c in cols if '%' in c.lower() or 'percent' in c.lower()), cols[1] if len(cols) > 1 else (cols[0] if cols else None))
                    if pc: mp['percentage'] = st.selectbox("%", cols, index=cols.index(pc) if pc in cols else 0, key=f"pct_{i}"); mapped_cols.append(pc)
                elif cat == 'materials':
                    nc = next((c for c in cols if 'name' in c.lower() or 'material' in c.lower()), cols[0] if cols else None)
                    if nc: mp['name'] = st.selectbox("Name", cols, index=cols.index(nc) if nc in cols else 0, key=f"mn_{i}"); mapped_cols.append(nc)
                    sc = next((c for c in cols if 'stock' in c.lower() or 'quantity' in c.lower()), cols[1] if len(cols) > 1 else (cols[0] if cols else None))
                    if sc: mp['stock_quantity'] = st.selectbox("Stock", cols, index=cols.index(sc) if sc in cols else 0, key=f"ms_{i}"); mapped_cols.append(sc)
                elif cat == 'packaging':
                    pc = next((c for c in cols if 'product' in c.lower()), cols[0] if cols else None)
                    if pc: mp['product_name'] = st.selectbox("Product", cols, index=cols.index(pc) if pc in cols else 0, key=f"pn_{i}"); mapped_cols.append(pc)
                    for fld, kw, ky in [("Container", "container", "container_price"), ("Cap/Lid", "cap", "cap_price"), ("Labeling", "label", "label_cost")]:
                        mc = next((c for c in cols if kw in c.lower()), None); mp[ky] = st.selectbox(fld, ['None'] + cols, index=cols.index(mc) + 1 if mc and mc in cols else 0, key=f"pk_{ky}_{i}")
                        if mc and mp[ky] != 'None': mapped_cols.append(mc)
                elif cat == 'cost_analysis':
                    pc = next((c for c in cols if 'product' in c.lower()), cols[0] if cols else None)
                    if pc: mp['product_name'] = st.selectbox("Product", cols, index=cols.index(pc) if pc in cols else 0, key=f"cn_{i}"); mapped_cols.append(pc)
                    for fld, trms in [('raw_material_cost_batch', ['raw material']), ('units_produced', ['units']), ('selling_price_unit', ['selling price']), ('labour_cost_hour', ['labour'])]:
                        mc = next((c for c in cols if any(t in c.lower() for t in trms)), None); mp[fld] = st.selectbox(fld.replace('_', ' ').title(), ['None'] + cols, index=cols.index(mc) + 1 if mc and mc in cols else 0, key=f"cf_{fld}_{i}")
                        if mc and mp[fld] != 'None': mapped_cols.append(mc)
                if mp:
                    cdf = pd.DataFrame()
                    for k, col in mp.items():
                        if col and col != 'None' and col in df.columns: cdf[k] = df[col]
                    if not cdf.empty: st.caption("Preview:"); st.dataframe(cdf.head(5), use_container_width=True)
                db.save_unmapped_data(sheet_name, df, mapped_cols)
                sti.append({'name': sheet_name, 'category': cat, 'data': df, 'mapping': mp, 'ignore': False})
            elif ign: sti.append({'name': sheet_name, 'ignore': True})
    
    if sti and st.button("💾 Save and Import All", type="primary", use_container_width=True):
        ir = []
        for sd in sti:
            if sd.get('ignore'): ir.append({'sheet': sd['name'], 'status': 'ignored'}); continue
            try:
                df = sd['data'].copy(); cat = sd['category']; mp = sd['mapping']; sn = cat.replace('_', ' ').title()
                if cat == 'formulas':
                    pn = sd['name']
                    if db.has_formula(pn): ir.append({'sheet': sd['name'], 'status': 'skipped'}); continue
                    cdf = pd.DataFrame()
                    if 'ingredient_name' in mp: cdf['ingredient_name'] = df[mp['ingredient_name']]
                    if 'percentage' in mp: cdf['percentage'] = df[mp['percentage']].apply(DataParser.clean_pct)
                    if not cdf.empty: db.save_formula(pn, cdf); ir.append({'sheet': sd['name'], 'status': 'imported', 'section': sn})
                elif cat == 'materials':
                    cdf = pd.DataFrame()
                    if 'name' in mp: cdf['name'] = df[mp['name']]
                    if 'stock_quantity' in mp: cdf['stock_quantity'] = pd.to_numeric(df[mp['stock_quantity']], errors='coerce').fillna(0)
                    if not cdf.empty: db.save_materials(cdf); ir.append({'sheet': sd['name'], 'status': 'imported', 'section': sn})
                elif cat == 'packaging':
                    cdf = pd.DataFrame()
                    if 'product_name' in mp: cdf['product_name'] = df[mp['product_name']]
                    tc = pd.Series(0.0, index=df.index)
                    for pc in ['container_price', 'cap_price', 'label_cost']:
                        if pc in mp and mp[pc] != 'None': tc += pd.to_numeric(df[mp[pc]], errors='coerce').fillna(0)
                    cdf['total_packaging_cost'] = tc
                    if not cdf.empty: db.save_packaging(cdf[['product_name', 'total_packaging_cost']]); ir.append({'sheet': sd['name'], 'status': 'imported', 'section': sn})
                elif cat == 'cost_analysis':
                    cdf = pd.DataFrame()
                    if 'product_name' in mp: cdf['product_name'] = df[mp['product_name']]
                    for f in ['raw_material_cost_batch', 'units_produced', 'selling_price_unit', 'labour_cost_hour']:
                        if f in mp and mp[f] != 'None': cdf[f] = pd.to_numeric(df[mp[f]], errors='coerce').fillna(0)
                    if not cdf.empty: db.save_cost_analysis(cdf); ir.append({'sheet': sd['name'], 'status': 'imported', 'section': sn})
            except Exception as e: ir.append({'sheet': sd['name'], 'status': 'error', 'reason': str(e)})
        db.calculate_reorder()
        st.session_state.import_results = ir; st.session_state.show_mapping = False; st.session_state.pending_sheets = []; st.session_state.data_ok = True; st.rerun()

def render_data_centre(db):
    st.header("🖥️ Data Command Centre")
    if st.session_state.get('import_results'):
        with st.expander("📋 Last Import Results", expanded=True):
            for r in st.session_state.import_results:
                if r['status'] == 'imported': st.success(f"✅ **{r['sheet']}** → {r.get('section', 'Imported')}")
                elif r['status'] == 'skipped': st.warning(f"⚠️ **{r['sheet']}**")
                elif r['status'] == 'error': st.error(f"❌ **{r['sheet']}**")
    if st.session_state.get('pending_sheets'): render_mapping(db)
    else: st.info("📤 Upload files via sidebar, then click 'Process Files'.")

# ============================================================================
# UI - INSIGHTS HUB (Tab 2) - ENHANCED DATA MATCHING
# ============================================================================

def render_insights(db):
    st.header("📊 Insights & Reports")
    role = st.session_state.get('role', '')
    
    # Sub-tabs within Insights
    ins_tab = st.radio("Section:", ["📊 Analytics & Charts", "🔗 Data Matching Hub", "📋 Reports"], horizontal=True, key="ins_tab")
    
    if ins_tab == "🔗 Data Matching Hub":
        render_data_matching_hub(db)
        return
    
    if ins_tab == "📋 Reports":
        render_reports_section(db, role)
        return
    
    # Analytics & Charts (default)
    insights_data = db.get_insights_data()
    batches = db.get_batches()
    completed = [b for b in batches if b['status'] == 'completed']
    total_units = db.get_total_units_produced()
    
    q, a, c = sum(1 for b in batches if b['status']=='queued'), sum(1 for b in batches if b['status']=='active'), len(completed)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Queued", q); c2.metric("🔄 Active", a); c3.metric("✅ Completed", c); c4.metric("📦 Total Units", total_units)
    
    # Product Cost Analysis with Charts
    st.markdown("---")
    st.markdown("## 📊 Product Cost Analysis")
    mats = db.get_all_materials()
    prods = db.get_all_products()
    for p in prods:
        ings = db.get_formula(p['id'])
        if not ings: continue
        ca = db.get_cost_analysis(p['name']); pkg = db.get_packaging_cost(p['name'])
        with st.expander(f"📦 {p['name']} - Cost Breakdown", expanded=False):
            chart_type = st.radio("Chart:", ["📊 Bar", "🥧 Pie"], horizontal=True, key=f"ct_{p['id']}")
            cost_data = []; total_mat_cost = 0
            for i in ings:
                mat = next((m for m in mats if m['name'].lower() == i['ingredient_name'].lower()), None)
                cpu = mat['cost_per_unit'] if mat else 0; qpb = (i['percentage']/100) * DEFAULT_BATCH_SIZE; ic = (qpb / 1000) * cpu if cpu else 0; total_mat_cost += ic
                cost_data.append({'Ingredient': i['ingredient_name'], '%': i['percentage'], 'Weight (g)': qpb, 'Cost/g (R)': cpu, 'Cost/Batch (R)': ic})
            if cost_data:
                cdf = pd.DataFrame(cost_data)
                st.dataframe(cdf[['Ingredient', '%', 'Weight (g)', 'Cost/g (R)', 'Cost/Batch (R)']], use_container_width=True, hide_index=True)
                col1, col2 = st.columns(2)
                with col1:
                    if chart_type == "📊 Bar":
                        fig = px.bar(cdf, x='Ingredient', y='Weight (g)', title='Weight by Ingredient', color_discrete_sequence=[COLORS['primary']])
                    else: fig = px.pie(cdf, values='Weight (g)', names='Ingredient', title='Weight Distribution')
                    fig.update_layout(plot_bgcolor=COLORS['bg_beige'], paper_bgcolor=COLORS['bg_beige']); st.plotly_chart(fig, use_container_width=True)
                with col2:
                    if chart_type == "📊 Bar":
                        fig2 = px.bar(cdf, x='Ingredient', y='Cost/Batch (R)', title='Cost by Ingredient', color_discrete_sequence=[COLORS['accent']])
                    else: fig2 = px.pie(cdf, values='Cost/Batch (R)', names='Ingredient', title='Cost Distribution')
                    fig2.update_layout(plot_bgcolor=COLORS['bg_beige'], paper_bgcolor=COLORS['bg_beige']); st.plotly_chart(fig2, use_container_width=True)
                
                units = ca.get('units_produced', 10) if ca else 10; sp_val = ca.get('selling_price_unit', 0) if ca else 0
                lc_val = (ca.get('labour_cost_hour', 0) * (ca.get('production_time_hours', 1) or 1)) if ca else 0
                tc_val = total_mat_cost + pkg + lc_val; cost_per_g = total_mat_cost / DEFAULT_BATCH_SIZE if DEFAULT_BATCH_SIZE > 0 else 0
                rev = units * sp_val; prof = rev - tc_val; mar = (prof / rev * 100) if rev > 0 else 0
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Material/Batch", f"R{total_mat_cost:.2f}"); c2.metric("Total Cost", f"R{tc_val:.2f}"); c3.metric("Cost/g", f"R{cost_per_g:.2f}"); c4.metric("Price/Unit", f"R{sp_val:.2f}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Revenue", f"R{rev:.2f}"); c2.metric("Profit", f"R{prof:.2f}"); c3.metric("Margin", f"{mar:.1f}%")

def render_data_matching_hub(db):
    """Comprehensive data matching interface"""
    st.subheader("🔗 Data Matching Hub")
    st.caption("Match your uploaded data columns to business metrics for complete operational context.")
    
    # Get all uploaded sheets
    sheets = db.get_uploaded_sheets()
    prods = db.get_all_products()
    
    if not sheets:
        st.warning("No data uploaded yet. Please upload Excel/CSV files first via the sidebar.")
        return
    
    # Sheet selector
    selected_sheet = st.selectbox("📄 Select Uploaded Sheet:", sheets, key="dm_sheet")
    
    if selected_sheet:
        columns = db.get_sheet_columns(selected_sheet)
        
        if columns:
            st.markdown("---")
            st.markdown(f"### 📊 Map Columns from '{selected_sheet}'")
            
            # Show sample data
            with st.expander("👁️ View Sample Data from this Sheet", expanded=False):
                for col in columns:
                    sample = col['sample'][:100] if col['sample'] else 'No data'
                    st.text(f"Column: {col['column']} | Sample: {sample}...")
            
            st.markdown("---")
            
            # For each category of business fields
            for category, fields in BUSINESS_DATA_FIELDS.items():
                with st.expander(f"📁 {category} ({len(fields)} fields)", expanded=False):
                    # Show existing mappings for this category
                    existing_mappings = [m for m in db.get_data_mappings() if m['sheet_name'] == selected_sheet and m['target_category'] == category]
                    
                    for field_key, field_label in fields.items():
                        col1, col2, col3 = st.columns([2, 2, 1])
                        
                        with col1:
                            st.markdown(f"**{field_label}**")
                        
                        with col2:
                            # Check if already mapped
                            existing = next((m for m in existing_mappings if m['target_field'] == field_key), None)
                            current_value = existing['source_column'] if existing else None
                            
                            # Dropdown to select source column
                            col_options = ['-- Select Column --'] + [c['column'] for c in columns]
                            if current_value and current_value in [c['column'] for c in columns]:
                                idx = [c['column'] for c in columns].index(current_value) + 1
                            else:
                                idx = 0
                            
                            selected_col = st.selectbox(
                                f"Source",
                                col_options,
                                index=idx,
                                key=f"dm_{selected_sheet}_{category}_{field_key}",
                                label_visibility="collapsed"
                            )
                        
                        with col3:
                            # Option to enter manual value instead
                            manual_val = st.text_input(
                                "Manual",
                                value=existing['manual_value'] if existing and existing.get('manual_value') else '',
                                key=f"mv_{selected_sheet}_{category}_{field_key}",
                                label_visibility="collapsed",
                                placeholder="Or type value"
                            )
                        
                        # Save mapping if changed
                        if selected_col != '-- Select Column --' or manual_val:
                            target_product = st.selectbox(
                                "For Product:",
                                ['General'] + [p['name'] for p in prods],
                                key=f"tp_{selected_sheet}_{category}_{field_key}"
                            )
                            
                            if st.button(f"💾 Save", key=f"sv_{selected_sheet}_{category}_{field_key}"):
                                if selected_col != '-- Select Column --':
                                    db.save_data_mapping(selected_sheet, selected_col, field_key, category, target_product)
                                if manual_val:
                                    db.save_business_data(target_product if target_product != 'General' else 'General', field_key, manual_val, category)
                                st.success(f"✅ Saved {field_label}!")
                                st.rerun()
            
            # Apply all mappings button
            st.markdown("---")
            if st.button("🚀 Apply All Mappings & Populate Business Data", type="primary", use_container_width=True):
                count = db.apply_mappings_to_data(selected_sheet)
                st.success(f"✅ Applied {count} data points from '{selected_sheet}' to business records!")
                st.rerun()
    
    # Show current business data
    st.markdown("---")
    st.markdown("### 📋 Current Business Data Records")
    all_bd = db.get_business_data()
    if all_bd:
        bd_df = pd.DataFrame(all_bd)
        st.dataframe(bd_df, use_container_width=True, hide_index=True)
        
        # Allow manual editing
        with st.expander("✏️ Manually Add/Edit Business Data", expanded=False):
            st.markdown("Enter any missing data manually:")
            product = st.selectbox("Product:", ['General'] + [p['name'] for p in prods], key="man_prod")
            category = st.selectbox("Category:", list(BUSINESS_DATA_FIELDS.keys()), key="man_cat")
            field = st.selectbox("Field:", list(BUSINESS_DATA_FIELDS[category].keys()), format_func=lambda x: BUSINESS_DATA_FIELDS[category][x], key="man_field")
            value = st.text_input("Value:", key="man_val")
            if st.button("💾 Save Manual Entry", type="primary"):
                db.save_business_data(product, field, value, category)
                st.success("✅ Saved!"); st.rerun()
    else:
        st.info("No business data records yet. Map your uploaded data above or enter manually.")

def render_reports_section(db, role):
    """Reports section with batch summaries and downloads"""
    st.subheader("📋 Reports")
    
    reports = db.get_completion_reports()
    if reports:
        st.markdown(f"### Batch Completion Reports ({len(reports)})")
        st.dataframe(pd.DataFrame(reports), use_container_width=True, hide_index=True)
        if RBAC.can(role, 'download'):
            csv_data = db.get_completion_reports_csv()
            if csv_data: st.download_button("📥 Download CSV", csv_data, "completion_reports.csv", "text/csv")
    
    # Batch Production Summary
    batches = db.get_batches()
    completed = [b for b in batches if b['status'] == 'completed']
    if completed:
        st.markdown("---")
        st.markdown("### 📦 Batch Production Summary")
        batch_summary = []
        for b in completed:
            ca = db.get_cost_analysis(b['product_name'])
            revenue = (b.get('units_produced', 0) * ca.get('selling_price_unit', 0)) if ca else 0
            batch_summary.append({'Batch': b['batch_number'], 'Product': b['product_name'], 'Weight (g)': b['batch_size'], 'Units': b.get('units_produced', 0), 'Cost (R)': f"{b.get('total_batch_cost', 0):.2f}", 'Revenue (R)': f"{revenue:.2f}" if revenue else 'N/A', 'Time (hrs)': f"{b.get('time_spent', 0):.1f}" if b.get('time_spent') else 'N/A', 'By': b.get('completed_by', 'N/A')})
        st.dataframe(pd.DataFrame(batch_summary), use_container_width=True, hide_index=True)
    
    # Business Data Summary
    all_bd = db.get_business_data()
    if all_bd:
        st.markdown("---")
        st.markdown("### 📊 Business Data Summary")
        st.dataframe(pd.DataFrame(all_bd), use_container_width=True, hide_index=True)

# ============================================================================
# UI - OPERATIONS HUB (Tab 3) - Same as previous version
# ============================================================================

def render_operations_centre(db):
    st.header("🏭 Operations Centre")
    role = st.session_state.get('role', '')
    if not RBAC.can(role, 'ops'): st.error("Access denied"); return
    
    op_tab = st.radio("Section:", ["📊 Capacity & Planning", "🧪 Formulas", "🏪 Suppliers & Restock", "📝 Notes"], horizontal=True, key="ops_tab")
    
    if op_tab == "📊 Capacity & Planning":
        st.markdown("## 📊 Production Capacity")
        cap = db.get_production_capacity()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"### ✅ Can Produce ({len(cap['can_produce'])})")
            for p in cap['can_produce']: st.markdown(f'<div class="capacity-card can-produce"><strong>✅ {p["name"]}</strong></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"### ❌ Cannot Produce ({len(cap['cannot_produce'])})")
            for p in cap['cannot_produce']: st.markdown(f'<div class="capacity-card cannot-produce"><strong>❌ {p["name"]}</strong></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("## 📋 Production Planning")
        prods = db.get_all_products(); mats = db.get_all_materials()
        if prods and mats:
            pd_data = []
            for p in prods:
                ings = db.get_formula(p['id'])
                if not ings: continue
                mu = float('inf')
                for i in ings:
                    mat = next((m for m in mats if m['name'].lower() == i['ingredient_name'].lower()), None)
                    if mat:
                        nd = (i['percentage'] / 100) * 100
                        if nd > 0: mu = min(mu, mat['stock_quantity'] / nd)
                mu = int(mu) if mu != float('inf') else 0
                pd_data.append({'Product': p['name'], 'Product ID': p['id'], 'Batch Size': min(mu, 50), 'Max Possible': mu})
            if pd_data:
                pdf = pd.DataFrame(pd_data)
                edf = st.data_editor(pdf, column_config={'Product': st.column_config.TextColumn(disabled=True), 'Product ID': st.column_config.NumberColumn(disabled=True), 'Batch Size': st.column_config.NumberColumn(min_value=0, step=1), 'Max Possible': st.column_config.NumberColumn(disabled=True)}, hide_index=True, use_container_width=True, key="ops_pp")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 Check Availability", type="primary", use_container_width=True):
                        for _, row in edf.iterrows():
                            if row['Batch Size'] > 0:
                                ings = db.get_formula(row['Product ID']); bs = row['Batch Size'] * 100
                                st.markdown(f"**{row['Product']}** - {row['Batch Size']} units ({bs}g)")
                                cd = []
                                for i in ings:
                                    qn = (i['percentage'] / 100) * bs; mat = next((m for m in mats if m['name'].lower() == i['ingredient_name'].lower()), None); sa = mat['stock_quantity'] if mat else 0
                                    cd.append({'Ingredient': i['ingredient_name'], 'Needed (g)': f"{qn:.1f}", 'Available': f"{sa:.1f}", 'Status': '✅' if sa >= qn else '❌'})
                                st.dataframe(pd.DataFrame(cd), use_container_width=True, hide_index=True)
                with col2:
                    if st.button("📋 Queue for Production", type="primary", use_container_width=True):
                        count = 0
                        for _, row in edf.iterrows():
                            if row['Batch Size'] > 0: bn = db.create_batch(row['Product ID'], row['Batch Size'] * 100)
                            if bn: count += 1; st.success(f"✅ Queued: {row['Product']} ({bn})")
                        if count > 0: st.success(f"### {count} batches sent!"); st.rerun()
    
    elif op_tab == "🧪 Formulas":
        st.subheader("🧪 Formula Management")
        prods = db.get_all_products()
        if not prods: st.info("No products."); return
        can_edit = RBAC.can(role, 'edit_formula'); can_view_pct = RBAC.can(role, 'view_pct'); is_owner = role == 'business_owner'
        for p in prods:
            ings = db.get_formula(p['id'])
            if not ings: continue
            with st.expander(f"📝 {p['name']} ({len(ings)} ingredients)", expanded=False):
                if is_owner:
                    new_name = st.text_input("Formula Name:", value=p['name'], key=f"rn_{p['id']}")
                    if new_name != p['name'] and st.button("✏️ Rename", key=f"rename_{p['id']}"): db.rename_product(p['name'], new_name); st.success(f"✅ Renamed!"); st.rerun()
                if can_view_pct:
                    fd = [{'Ingredient': i['ingredient_name'], '%': i['percentage']} for i in ings]; fdf = pd.DataFrame(fd)
                    if can_edit:
                        edf = st.data_editor(fdf, column_config={'Ingredient': st.column_config.TextColumn('Ingredient'), '%': st.column_config.NumberColumn('%', min_value=0.0, max_value=100.0, step=0.1, format="%.1f%%")}, hide_index=True, use_container_width=True, key=f"fe_ops_{p['id']}")
                        total = edf['%'].sum(); color = "green" if 95 <= total <= 105 else "red"
                        st.markdown(f"**Total:** <span style='color:{color}'>{total:.1f}%</span>", unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        if c1.button("💾 Save", key=f"sf_ops_{p['id']}"):
                            if 95 <= total <= 105: db.save_formula(p['name'], edf); st.success("✅ Saved!"); st.rerun()
                        if c2.button("🗑️ Delete", key=f"df_ops_{p['id']}", type="secondary") and is_owner: db.delete_formula(p['id']); st.success("Deleted!"); st.rerun()
                    else: st.dataframe(fdf, use_container_width=True, hide_index=True)
                else: st.dataframe(pd.DataFrame([{'Ingredient': i['ingredient_name']} for i in ings]), use_container_width=True, hide_index=True)
    
    elif op_tab == "🏪 Suppliers & Restock":
        st.markdown("## 🏪 Supplier Directory")
        sups = db.get_all_suppliers(); mats = db.get_all_materials()
        if sups or mats:
            sd = []; ai = set()
            for s in sups: ai.add(s['ingredient_name'])
            for m in mats: ai.add(m['name'])
            for ing in sorted(ai):
                sup = next((s for s in sups if s['ingredient_name'].lower() == ing.lower()), None); mat = next((m for m in mats if m['name'].lower() == ing.lower()), None)
                row = {'Ingredient': ing}
                if sup: row['Supplier'] = sup.get('supplier1_name', ''); row['Price'] = f"R{sup.get('supplier1_price', 0):.2f}"; row['Size'] = sup.get('supplier1_size', ''); row['Price/Unit'] = f"R{sup.get('supplier1_price_per_unit', 0):.4f}"; row['Link'] = sup.get('link1', '')
                if mat: row['Stock'] = f"{mat['stock_quantity']:.1f} {mat.get('unit', 'g')}"
                sd.append(row)
            if sd: st.dataframe(pd.DataFrame(sd), use_container_width=True, hide_index=True)
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("## 📦 Restock Calculator")
        if RBAC.can(role, 'restock'):
            prods = db.get_all_products()
            if prods:
                sp = st.selectbox("Product:", [p['name'] for p in prods], key="rp"); du = st.number_input("Desired Units:", min_value=1, value=10, step=1)
                if st.button("🧮 Calculate", type="primary"):
                    prod = next((p for p in prods if p['name'] == sp), None)
                    if prod:
                        ings = db.get_formula(prod['id']); bs = du * 100
                        st.markdown(f"### Restock for {sp} ({du} units / {bs}g)")
                        rd = []; tc = 0
                        for i in ings:
                            qn = (i['percentage'] / 100) * bs; mat = next((m for m in mats if m['name'].lower() == i['ingredient_name'].lower()), None); sup = next((s for s in sups if s['ingredient_name'].lower() == i['ingredient_name'].lower()), None)
                            needed = max(0, qn - (mat['stock_quantity'] if mat else 0)); cpu = sup.get('supplier1_price_per_unit', mat.get('cost_per_unit', 0)) if (sup or mat) else 0; ec = needed * cpu if cpu else 0; tc += ec
                            rd.append({'Ingredient': i['ingredient_name'], 'Needed (g)': f"{qn:.1f}", 'In Stock': f"{mat['stock_quantity']:.1f}" if mat else '0', 'To Order': f"{needed:.1f}", 'Est. Cost': f"R{ec:.2f}"})
                        st.dataframe(pd.DataFrame(rd), use_container_width=True, hide_index=True); st.metric("Total Est. Cost", f"R{tc:.2f}")
                        if st.button("📤 Send to Insights", type="primary"):
                            for r in rd: db.create_restock_request(r['Ingredient'], float(r['To Order'].replace(',','')), float(r['Est. Cost'].replace('R','').replace(',','')))
                            st.success("✅ Sent!"); st.rerun()
    
    elif op_tab == "📝 Notes":
        st.markdown("## 📝 Production Notes")
        with st.form("onf"):
            nt = st.text_area("Note:", height=150); nty = st.selectbox("Type:", ["general", "production", "inventory", "quality"])
            if st.form_submit_button("💾 Save", type="primary") and nt: db.save_ops_note(nt, nty); st.success("✅ Saved!"); st.rerun()
        st.markdown("---"); st.subheader("📜 Recent Notes")
        for n in db.get_ops_notes():
            nd = n.get('created_at', '')
            try: nd = pd.to_datetime(nd).strftime('%Y-%m-%d %H:%M') if nd else ''
            except: pass
            st.markdown(f'<div style="background:white;border-left:4px solid {COLORS["primary"]};padding:10px;margin:5px 0;border-radius:5px;"><small><strong>{n.get("note_type","general").title()}</strong> | {nd}</small><p>{n.get("note_text","")}</p></div>', unsafe_allow_html=True)

# ============================================================================
# UI - PRODUCTION HUB (Tab 4)
# ============================================================================

def render_production_centre(db):
    st.header("🔧 Production Hub")
    role = st.session_state.get('role', '')
    user_name = {'business_owner': 'Business Owner', 'production_manager': 'Production Manager', 'factory_worker': 'Factory Worker'}.get(role, 'Worker')
    
    prod_tab = st.radio("Section:", ["📋 Production Line", "📦 Inventory"], horizontal=True, key="prod_tab")
    
    if prod_tab == "📦 Inventory":
        st.subheader("📦 Inventory Management")
        can_add = RBAC.can(role, 'add_inv'); can_edit = RBAC.can(role, 'edit_inv'); can_remove = RBAC.can(role, 'remove_inv')
        if can_add:
            with st.expander("➕ Add Material", expanded=False):
                with st.form("amf_prod"):
                    c1, c2 = st.columns(2); nm = c1.text_input("Name*"); nu = c1.selectbox("Unit", ['g', 'ml', 'kg', 'l']); ns = c2.number_input("Stock", min_value=0.0, step=0.1)
                    if st.form_submit_button("Add", type="primary") and nm: db.add_material(nm, nu, ns); st.success("Added!"); st.rerun()
        mats = db.get_all_materials()
        if mats:
            idata = [{'ID': m['id'], 'Name': m['name'], 'Unit': m['unit'], 'Stock': m['stock_quantity'], 'Reorder': f"{m['reorder_quantity']:.1f}"} for m in mats]
            idf = pd.DataFrame(idata)
            if can_edit:
                edf = st.data_editor(idf, column_config={'ID': st.column_config.NumberColumn(disabled=True), 'Name': st.column_config.TextColumn('Name'), 'Unit': st.column_config.TextColumn('Unit'), 'Stock': st.column_config.NumberColumn('Stock', min_value=0, step=0.1), 'Reorder': st.column_config.TextColumn('Reorder', disabled=True)}, hide_index=True, use_container_width=True, key="ie_prod")
                if st.button("💾 Save Changes", type="primary"):
                    for _, r in edf.iterrows(): db.update_material(r['ID'], name=r['Name'], stock=r['Stock'], unit=r['Unit'])
                    st.success("✅ Updated!"); st.rerun()
                if can_remove:
                    tr = st.selectbox("Remove", [m['Name'] for m in idata], key="rs_prod")
                    if st.button("🗑️ Remove", type="secondary") and tr: mid = next(m['ID'] for m in idata if m['Name'] == tr); db.remove_material(mid); st.success("Removed!"); st.rerun()
            else: st.dataframe(idf, use_container_width=True, hide_index=True)
        else: st.info("No materials.")
        return
    
    queued = db.get_batches(status='queued'); active = db.get_batches(status='active')
    if not queued and not active: st.info("No batches in queue."); return
    
    if queued:
        st.markdown(f"### 📋 Queued ({len(queued)})")
        for b in queued:
            ings = db.get_batch_materials(b['id']); tw = sum(m['quantity_used'] for m in ings)
            border_color = COLORS['success'] if not b.get("has_shortages") else COLORS['warning'] 
            status_text = "✅ Ready" if not b.get("has_shortages") else "⚠️ Shortages"
            st.markdown(f'<div class="queue-card" style="border-top:3px solid {border_color}"><h4>{status_text} - {b["product_name"]}</h4><p>Batch: {b["batch_number"]} | Size: {b["batch_size"]}g | Ingredients: {len(ings)} | Weight: {tw:.1f}g</p></div>', unsafe_allow_html=True)
    
    if active:
        st.markdown(f"### 🔄 Active ({len(active)})")
        for b in active:
            timer_text = "N/A"
            if b['start_time']:
                try: st_time = datetime.strptime(b['start_time'], "%Y-%m-%d %H:%M:%S"); el = datetime.now() - st_time; h, r = divmod(int(el.total_seconds()), 3600); m, s = divmod(r, 60); timer_text = f"{h:02d}:{m:02d}:{s:02d}"
                except: pass
            border_color = COLORS['success'] 
            st.markdown(f'<div class="queue-card" style="border-top:3px solid {border_color};"><h4>🔧 {b["product_name"]} <span style="float:right;">⏱️ {timer_text}</span></h4></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown("## 🏭 Production Line")
    all_batches = queued + active
    if all_batches:
        batch_options = [f"{'✅' if b['status']=='queued' else '🔧'} {b['batch_number']} - {b['product_name']} ({b['batch_size']}g)" for b in all_batches]
        si = st.selectbox("Select Batch:", range(len(batch_options)), format_func=lambda x: batch_options[x], key="pb")
        selected_batch = all_batches[si]
        
        st.markdown(f'<div class="production-line">', unsafe_allow_html=True)
        st.markdown(f"### 📦 {selected_batch['product_name']}")
        st.markdown(f"**Batch:** {selected_batch['batch_number']} | **Size:** {selected_batch['batch_size']}g | **Status:** {selected_batch['status'].title()}")
        
        mats_used = db.get_batch_materials(selected_batch['id'])
        if mats_used:
            st.markdown("### 📊 Formula Weights")
            fd = []
            for m in mats_used:
                ed = m.get('expiry_date', '')
                if ed and ed != '' and ed != 'None':
                    try: ed = pd.to_datetime(ed).date()
                    except: ed = None
                else: ed = None
                fd.append({'Ingredient': m['ingredient_name'], 'Weight (g)': m['quantity_used'], 'Batch Number': m.get('batch_number', '') or '', 'Expiry Date': ed})
            
            fdf = pd.DataFrame(fd)
            edf = st.data_editor(fdf, column_config={'Ingredient': st.column_config.TextColumn('Ingredient', disabled=True), 'Weight (g)': st.column_config.NumberColumn('Weight (g)', disabled=True, format="%.1f"), 'Batch Number': st.column_config.TextColumn('Batch #'), 'Expiry Date': st.column_config.DateColumn('Expiry Date')}, hide_index=True, use_container_width=True, key=f"f_{selected_batch['id']}")
            
            def save_mat():
                md = []
                for _, r in edf.iterrows():
                    ex = r['Expiry Date']; es = str(ex) if ex and not pd.isna(ex) else ''
                    md.append({'ingredient_name': r['Ingredient'], 'batch_number': str(r['Batch Number']) if r['Batch Number'] else '', 'expiry_date': es})
                db.update_batch_materials(selected_batch['id'], md)
            
            st.markdown("---")
            if selected_batch['status'] == 'queued' and RBAC.can(role, 'start'):
                if st.button(f"▶️ Start Production", type="primary", use_container_width=True, key=f"s_{selected_batch['id']}"): save_mat(); db.start_batch(selected_batch['id']); st.success("✅ Started!"); st.rerun()
            
            if selected_batch['status'] == 'active' and RBAC.can(role, 'complete'):
                uploaded_files = st.file_uploader("📎 Attach files", type=['png','jpg','jpeg','pdf'], accept_multiple_files=True, key=f"files_{selected_batch['id']}")
                if st.button(f"⏹️ End Production", type="secondary", use_container_width=True, key=f"e_{selected_batch['id']}"): 
                    save_mat()
                    if uploaded_files:
                        for uf in uploaded_files: db.save_batch_file(selected_batch['id'], uf.name, uf.read(), uf.type)
                    st.session_state[f"end_{selected_batch['id']}"] = True; st.rerun()
            
            if st.session_state.get(f"end_{selected_batch['id']}"):
                st.markdown("---"); st.markdown("### 📦 Complete Batch")
                c1, c2 = st.columns(2)
                with c1: units = st.number_input("Units Produced *", min_value=0, value=0, key=f"u_{selected_batch['id']}")
                with c2: notes = st.text_area("Notes", key=f"n_{selected_batch['id']}")
                c1, c2 = st.columns(2)
                if c1.button("💾 Save & Complete", type="primary", key=f"sc_{selected_batch['id']}"):
                    if units <= 0: st.error("⚠️ Please enter units produced.")
                    else:
                        save_mat()
                        success, report = db.complete_batch(selected_batch['id'], units, notes, user_name)
                        if success:
                            st.session_state[f"end_{selected_batch['id']}"] = False; st.success("✅ Completed!"); st.balloons()
                            st.markdown(f'<div class="completion-report"><h3>📋 Report</h3><p>Batch: {report["batch_number"]}<br>Product: {report["product_name"]}<br>By: {report["completed_by"]}<br>Time: {report["time_spent"]} hrs<br>Units: {report["units_produced"]}</p></div>', unsafe_allow_html=True)
                            if RBAC.can(role, 'download'):
                                csv_data = db.get_completion_reports_csv()
                                if csv_data: st.download_button("📥 Download Report", csv_data, f"report_{selected_batch['batch_number']}.csv", "text/csv")
                            time.sleep(2); st.rerun()
                if c2.button("Cancel", key=f"cc_{selected_batch['id']}"): st.session_state[f"end_{selected_batch['id']}"] = False; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# MAIN
# ============================================================================

def main():
    st.set_page_config(page_title="EQPIS", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
    apply_css()
    
    defaults = {'data_ok': False, 'show_mapping': False, 'pending_sheets': [], 'import_results': None, 'role': 'business_owner'}
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
    
    db = DatabaseManager()
    role = render_sidebar(db)
    
    if not st.session_state.data_ok: st.session_state.data_ok = db.has_data()
    
    if st.session_state.get('show_mapping') and st.session_state.get('pending_sheets'):
        st.header("🖥️ Data Command Centre"); render_data_centre(db); return
    
    if not st.session_state.data_ok and role != 'factory_worker': render_welcome_page(); return
    
    if role == 'factory_worker': render_production_centre(db); return
    
    tl = []
    if RBAC.can(role, 'data'): tl.append(("🖥️ Data Centre", "data"))
    if RBAC.can(role, 'insights'): tl.append(("📊 Insights Hub", "insights"))
    if RBAC.can(role, 'ops'): tl.append(("🏭 Operations Hub", "ops"))
    if RBAC.can(role, 'production'): tl.append(("🔧 Production Hub", "production"))
    
    if tl:
        tabs = st.tabs([t[0] for t in tl])
        for i, (_, tn) in enumerate(tl):
            with tabs[i]:
                if tn == 'data': render_data_centre(db)
                elif tn == 'insights': render_insights(db)
                elif tn == 'ops': render_operations_centre(db)
                elif tn == 'production': render_production_centre(db)

if __name__ == "__main__":
    main()
