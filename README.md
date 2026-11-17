# Permanent Delete: POS, Sessions, Payments, Production & Inventory (Odoo 20)

**Module Name:** `permanent_data_cleanup`  
**Version:** `20.0.1.0.0`  
**License:** LGPL-3  

## Overview

**Permanent Data Cleanup** allows authorized administrators in **Odoo 20** to permanently delete operational records—even when they are in `Done`, `Paid`, `Posted`, or `Closed` states—by cleanly removing all dependent lines, moves, valuation layers, and journal entries in the proper relational order.

---

## Features

### 1. Centralized Data Cleanup Wizard
Open **Data Cleanup** from the main Odoo app menu to:
- Filter by **All Records (All Time)** or a **Specific Date Range (`From` / `To`)** and optional **POS Terminal**.
- Choose which data categories to wipe:
  - **POS Sessions & Cash Statements** (`pos.session`, `account.bank.statement.line`)
  - **POS Orders & Order Lines** (`pos.order`, `pos.order.line`)
  - **POS Payments** (`pos.payment`)
  - **Manufacturing / Production Orders** (`mrp.production`, `mrp.workorder`, `mrp.unbuild`)
  - **Inventory Transfers, Stock Moves & Scrap** (`stock.picking`, `stock.move`, `stock.move.line`, `stock.scrap`, `stock.valuation.layer`)
  - **Reset All On-Hand Inventory (`stock.quant`) to 0**
  - **Reset Numbering Sequences (`ir.sequence`) to 1**
- **Live Impact Preview**: Displays the exact count of records that will be deleted before execution.
- **Safety Lock**: Requires typing **`DELETE`** in uppercase to prevent accidental data loss.

### 2. Contextual "Delete Permanently (Force)" Actions
Select one or multiple records in any of these list/form views and click **Action → Delete Permanently (Force)**:
- **POS Orders** (`pos.order`)
- **POS Sessions** (`pos.session`)
- **POS Payments** (`pos.payment`)
- **Manufacturing Orders** (`mrp.production`)
- **Inventory Transfers** (`stock.picking`)
- **Stock Moves** (`stock.move`)

### 3. Role-Based Security
- Restricted to users with the **Manager: Allow Permanent Deletion** privilege (`permanent_data_cleanup.group_permanent_delete_manager`).
- Can be toggled on/off per user under **Settings → Users & Companies → Users → Permanent Delete Access**.
- Every bulk cleanup operation is logged in the Odoo server log with the executing user's login and ID.

---

## Installation

1. Copy the `permanent_data_cleanup` folder into your Odoo 20 `addons` directory.
2. Restart the Odoo server.
3. Enable **Developer Mode** and go to **Apps → Update Apps List**.
4. Search for **Permanent Delete: POS, Sessions, Payments, Production & Inventory** and click **Activate**.