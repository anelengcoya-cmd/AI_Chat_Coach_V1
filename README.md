# Inventilytics - Earthly Q Production Intelligence System

A production management application for handmade natural hair and skin care businesses. Built with Streamlit.

## Overview

Inventilytics  helps small-batch cosmetics manufacturers manage their entire production workflow:

- **Formulas** - Store and edit product recipes with ingredient percentages
- **Inventory** - Track raw material stock levels and reorder points
- **Production** - Queue batches, start/complete production runs, track time spent
- **Suppliers** - Maintain supplier directory with pricing and links
- **Insights** - View cost breakdowns, profit margins, and production analytics
- **Data Matching** - Map uploaded Excel/CSV columns to 80+ business metrics

## Features

### 🖥️ Data Command Centre
- Upload Excel, CSV, or ZIP files
- Smart column mapping with auto-detection
- Preserves unmapped data for later matching

### 📊 Insights Hub (In Development)
- Cost analysis per product (material, labour, packaging)
- Pie and bar charts for ingredient weight and cost distribution
- Batch production summaries with revenue and profit calculations
- Data matching hub for comprehensive business context

### 🏭 Operations Hub (Working)
- Production capacity checker (can/cannot produce)
- Production planning with batch size editor
- Formula management with rename capability
- Supplier directory with restock calculator
- Production notes tracking

### 🔧 Production Hub (Working)
- Batch queue with live timers
- Formula weight table (weights only, no percentages for workers)
- Batch number and expiry date tracking per ingredient
- File attachments (photos, documents) for batches
- Completion reports with low stock alerts

## Installation

### Prerequisites
- Python 3.8+
- pip

## Run the app
streamlit run inventilytics.py
Usage
### Open the app in your browser 
default:https://inventilytics.streamlit.app/

### Select your role from the sidebar:

💼 Business Owner - Full access to all features

📋 Production Manager - Manage operations, queue production

👷 Factory Worker - Start and complete production batches

### Upload your data files (Excel/CSV/ZIP) via the sidebar

### Map columns to database fields

### Start managing production!

## Role Permissions
Feature	Business Owner	Production Manager	Factory Worker
Import Data	✅	✅	❌
Edit Formulas	✅	✅	❌
Add/Remove Inventory	✅	❌	❌
Queue Production	✅	✅	❌
Start Batches	✅	✅	✅
Complete Batches	✅	❌	✅
View Financials	✅	✅	❌
Download Reports	✅	❌	❌

## Data Upload Formats
### Formulas
Required columns: Ingredient Name, Percentage (%)

### Materials
Required columns: Material Name, Stock Quantity

### Packaging
Required columns: Product Name, Container Price, Cap/Lid Price, Labeling Costs

### Cost Analysis
Required columns: Product Name, Selling Price/Unit, Labour Cost/Hour

### Suppliers
Required columns: Ingredient Name, Supplier Name, Price, Size, Price/Unit

### Data Matching
Any columns not mapped during import are preserved. Use the Data Matching Hub in the Insights tab to map them to 80+ business metrics across 7 categories:

### Product Information

### Pricing & Sales

### Production Costs

### Batch Production

### Inventory & Supply Chain

### Supplier Information

### Financial Metrics

License
MIT License - see LICENSE file for details.

Support
For issues or feature requests, please open an issue on GitHub.



