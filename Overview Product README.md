## 1. Product Catalog & Category Hierarchy

To keep things organized for your "Baju Bareng" company, we use a parent-child relationship for categories. This allows you to pull reports for "Kaos" as a whole or drill down into specific models.

### Category Mapping
* **Category:** `Kaos`
    * **Products:** `Kaos Model Macan`, `Kaos Model Dinosaurus`, `Kaos Binatang`

* **Category:** `Celana Panjang`
    * **Products:** `Celana Panjang Chino`

---

## 2. The "Stocking Alignment" Logic (Shared SKU)

This is the most critical part of your request. To ensure SKU 1, SKU 2, and SKU 3 all pull from the same physical pile of shirts, we use a **Master SKU (Physical)** vs. **Store SKU (Marketplace)** system.

### How it works:

You don't track stock for the "Marketplace SKU"; you track it for the **Physical Variant**.

| Marketplace SKU (What Customer Sees) | Variant Attribute | **Linked Physical SKU** (The Stock Source) |
| --- | --- | --- |
| **SKU 1:** Kaos Model Macan | Single | **PHY-MACAN** |
| **SKU 2:** Kaos Model Dinosaurus | Single | **PHY-DINO** |
| **SKU 3:** Kaos Binatang | Variant: Macan | **PHY-MACAN** |
| **SKU 3:** Kaos Binatang | Variant: Dinosaurus | **PHY-DINO** |

**The Result:**
If a customer buys 1 unit of **SKU 3 (Variant: Macan)** on Tokopedia, the system looks at the link and deducts 1 unit from **PHY-MACAN**. Immediately, the stock for **SKU 1** on Shopee and Offline also drops by 1. This prevents overselling.

---

## 3. Warehouse & Marketplace Sync

As you mentioned, we need a "Holder Warehouse" for online stock.

* **Physical Reality:** * Warehouse Jakarta: 10 pcs (PHY-MACAN)
* Warehouse Tangerang: 10 pcs (PHY-MACAN)


* **Marketplace Logic:** * You set **Warehouse Jakarta** as the "Online Source."
* Shopee/Tokopedia will only show **10 pcs**, even though your total company stock is 20.
* If you move stock from Tangerang to Jakarta, the online stock updates automatically.



---

## 4. Enhanced Inventory & Finance Flow

Since you are using **FIFO**, the system will track the "Value" of your stock based on the **Landed Cost** (Product Price + Delivery Cost from your PO).

1. **PO Creation:** You buy 100 pcs of PHY-MACAN.
2. **Invoicing:** You upload the factory invoice ($1000) and the delivery invoice ($100).
3. **Landed Cost:** The system calculates each shirt cost as $11.00.
4. **Stock Movement Report:**
* **Beginning:** 0
* **In:** 100 ($1100 value)
* **Adjustment:** (e.g., +1 return from customer)
* **Out:** 20 ($220 COGS)
* **Ending:** 81 units.



---

## 5. Summary of Reports

* **Stock Movement:** Tracks Qty and Value (IDR/USD) including "Adjustment" columns for returns or human error.
* **Sales Order (SO):** Records which Marketplace sold the item, the Gross Revenue, and the calculated FIFO COGS.
* **Finance:** * **Income Statement:** Revenue - COGS - Ops Expenses (Salary/Debt) = Profit.
* **Balance Sheet:** Shows your "Inventory Asset Value" based on the current FIFO remaining stock.

