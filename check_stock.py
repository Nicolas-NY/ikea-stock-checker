#!/usr/bin/env python3
"""
IKEA Mexico Stock Checker
Checks product availability and sends notifications via ntfy.sh
"""

import requests
import json
import os
import sys
from datetime import datetime

# === CONFIGURATION ===
# Set these as GitHub Secrets or environment variables
PRODUCT_URL = os.environ.get(
    "IKEA_PRODUCT_URL",
    "https://www.ikea.com/mx/es/p/radmansoe-base-de-cama-cafe-efecto-nogal-20601053/"
)
ITEM_NUMBER = os.environ.get("IKEA_ITEM_NUMBER", "20601053")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "ikea-stock-radman")
NTFY_TOKEN = os.environ.get("NTFY_TOKEN", "")  # Optional: for private topics
PRODUCT_NAME = os.environ.get("IKEA_PRODUCT_NAME", "RÅDMANSÖ Base de cama King")

# === ENDPOINTS ===
FRAGMENT_URL = f"https://www.ikea.com/mx/es/lower-funnel-fragments/product-availability/?itemNo={ITEM_NUMBER}&inline"
INGKA_API_URL = f"https://api.salesitem.ingka.com/cia/availabilities/ru/mx?itemNos={ITEM_NUMBER}"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Headers to mimic browser request (no Accept-Encoding to get plain text)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Referer": "https://www.ikea.com/mx/es/",
    "Origin": "https://www.ikea.com",
}


def fetch_availability():
    """Fetch stock availability from IKEA's product-availability fragment endpoint."""
    print(f"[{datetime.now()}] Checking stock for {PRODUCT_NAME} (item: {ITEM_NUMBER})...")
    
    # Method 1: Fragment endpoint (returns full page with embedded JSON)
    try:
        resp = requests.get(FRAGMENT_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        
        html = resp.text
        marker = '<script type="text/hydrate">'
        start = html.find(marker)
        
        if start != -1:
            start += len(marker)
            end = html.find('</script>', start)
            if end != -1:
                try:
                    data = json.loads(html[start:end])
                    print(f"  ✓ Got data from fragment endpoint")
                    return data
                except json.JSONDecodeError as e:
                    print(f"  Fragment endpoint JSON error: {e}")
    except requests.RequestException as e:
        print(f"  Fragment endpoint error: {e}")
    
    # Method 2: Ingka API (returns clean JSON)
    print(f"  Trying Ingka API...")
    ingka_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json;version=2",
        "x-client-id": "ef382663-a2a5-40d4-8afe-f0634821c0ed",
        "Origin": "https://www.ikea.com",
        "Referer": "https://www.ikea.com/mx/es/",
    }
    
    try:
        resp = requests.get(INGKA_API_URL, headers=ingka_headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        # Convert Ingka API response to our expected format
        if "availabilities" in data and data["availabilities"]:
            avail = data["availabilities"][0]
            # Transform to our format
            return transform_ingka_response(avail)
    except requests.RequestException as e:
        print(f"  Ingka API error: {e}")
    except (KeyError, IndexError) as e:
        print(f"  Ingka API parse error: {e}")
    
    print("  ERROR: All endpoints failed")
    return None


def transform_ingka_response(avail):
    """Transform Ingka API response to our expected format."""
    # This is a simplified transform - adapt based on actual API response
    return {
        "product": {
            "itemNo": ITEM_NUMBER,
            "name": PRODUCT_NAME.split(" ")[0] if PRODUCT_NAME else "RÅDMANSÖ",
            "typeName": "Base de cama",
            "price": 0,
            "currencyCode": "MXN",
        },
        "availabilityResponse": {
            "availability": {
                "isOnlineSellable": False,
                "isSoldOut": True,
                "isSoldOutOnline": True,
                "homeDelivery": {"isAvailable": False, "stockStatus": "UNKNOWN", "isInRange": False},
                "clickCollect": {"isAvailable": False, "isEnabled": False, "isInRange": False},
                "stores": {},
            }
        }
    }


def analyze_stock(data):
    """Analyze stock availability from the parsed response."""
    if not data:
        return None
    
    product = data.get("product", {})
    availability = data.get("availabilityResponse", {}).get("availability", {})
    
    result = {
        "product_name": product.get("name", PRODUCT_NAME),
        "product_type": product.get("typeName", ""),
        "price": product.get("price", 0),
        "currency": product.get("currencyCode", "MXN"),
        "item_number": product.get("itemNo", ITEM_NUMBER),
        "is_online_sellable": availability.get("isOnlineSellable", False),
        "is_sold_out": availability.get("isSoldOut", False),
        "is_sold_out_online": availability.get("isSoldOutOnline", False),
        "home_delivery": {},
        "click_collect": {},
        "stores": {},
        "any_in_stock": False,
        "restock_dates": [],
    }
    
    # Home delivery
    hd = availability.get("homeDelivery", {})
    result["home_delivery"] = {
        "available": hd.get("isAvailable", False),
        "status": hd.get("stockStatus", "UNKNOWN"),
        "in_range": hd.get("isInRange", False),
    }
    
    # Click & collect
    cc = availability.get("clickCollect", {})
    result["click_collect"] = {
        "available": cc.get("isAvailable", False),
        "enabled": cc.get("isEnabled", False),
        "in_range": cc.get("isInRange", False),
    }
    
    # Per-store availability
    stores = availability.get("stores", {})
    for store_id, store_data in stores.items():
        in_stock = not store_data.get("isOutOfStock", True)
        stock_status = store_data.get("stockStatus", "UNKNOWN")
        quantity = store_data.get("quantity")
        restocks = store_data.get("restocks", {})
        
        result["stores"][store_id] = {
            "in_stock": in_stock,
            "status": stock_status,
            "quantity": quantity,
            "cash_carry": store_data.get("isAvailableForCashCarry", False),
            "click_collect": store_data.get("isAvailableForClickCollect", False),
            "restock_dates": restocks.get("shortDate", []),
        }
        
        if in_stock:
            result["any_in_stock"] = True
        
        if restocks.get("shortDate"):
            result["restock_dates"].extend(restocks["shortDate"])
    
    # Check if online is available
    if result["is_online_sellable"] or not result["is_sold_out_online"]:
        result["any_in_stock"] = True
    
    # Check home delivery
    if result["home_delivery"]["available"]:
        result["any_in_stock"] = True
    
    # Check click & collect
    if result["click_collect"]["available"]:
        result["any_in_stock"] = True
    
    return result


def format_message(result):
    """Format a notification message from the result."""
    if not result:
        return f"❌ Error al verificar {PRODUCT_NAME}"
    
    product = f"{result['product_name']} {result['product_type']}"
    price = f"${result['price']:,.0f} {result['currency']}"
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if result["any_in_stock"]:
        msg = f"🎉 ¡STOCK DISPONIBLE! 🎉\n\n"
        msg += f"📦 {product}\n"
        msg += f"💰 {price}\n"
        msg += f"🕐 {timestamp}\n\n"
        
        # Online
        if result["is_online_sellable"] or not result["is_sold_out_online"]:
            msg += "✅ Compra en línea: DISPONIBLE\n"
        else:
            msg += "❌ Compra en línea: Agotado\n"
        
        # Home delivery
        if result["home_delivery"]["available"]:
            msg += f"🚚 Envío a domicilio: DISPONIBLE\n"
        else:
            msg += f"🚚 Envío a domicilio: No disponible\n"
        
        # Click & collect
        if result["click_collect"]["available"]:
            msg += "🏪 Click & Collect: DISPONIBLE\n"
        else:
            msg += "🏪 Click & Collect: No disponible\n"
        
        # Stores with stock
        stores_in_stock = [
            sid for sid, s in result["stores"].items() if s["in_stock"]
        ]
        if stores_in_stock:
            msg += f"\n📍 Tiendas con stock: {', '.join(stores_in_stock)}\n"
        
        msg += f"\n🔗 {PRODUCT_URL}"
    else:
        msg = f"🔍 {product} — Sin stock\n"
        msg += f"💰 {price}\n"
        msg += f"🕐 {timestamp}\n"
        
        # Show restock dates
        if result["restock_dates"]:
            dates = list(set(result["restock_dates"]))
            msg += f"\n📅 Próximas fechas de reabastecimiento:\n"
            for d in dates:
                msg += f"   • {d}\n"
        
        # Show store statuses
        msg += "\n📍 Estado por tienda:\n"
        for sid, store in result["stores"].items():
            status = store["status"]
            qty = store.get("quantity")
            qty_str = f" ({qty} unidades)" if qty is not None else ""
            msg += f"   • Tienda {sid}: {status}{qty_str}\n"
            if store["restock_dates"]:
                msg += f"     Próximo stock: {', '.join(store['restock_dates'])}\n"
    
    return msg


def send_notification(message, priority="high"):
    """Send notification via ntfy.sh."""
    headers = {"Title": f"IKEA Stock: {PRODUCT_NAME}"}
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
    
    try:
        resp = requests.post(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"  ✅ Notification sent to {NTFY_URL}")
            return True
        else:
            print(f"  ❌ Notification failed: {resp.status_code} - {resp.text}")
            return False
    except requests.RequestException as e:
        print(f"  ❌ Notification error: {e}")
        return False


def log_result(result):
    """Append result to a log file for tracking."""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, "stock_log.jsonl")
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "item_number": ITEM_NUMBER,
        "any_in_stock": result["any_in_stock"] if result else None,
        "is_online_sellable": result["is_online_sellable"] if result else None,
        "stores": result.get("stores", {}) if result else {},
    }
    
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"  📝 Logged to {log_file}")
    except IOError as e:
        print(f"  ⚠️  Could not write log: {e}")


def main():
    """Main entry point."""
    print("=" * 60)
    print(f"IKEA Mexico Stock Checker")
    print(f"Product: {PRODUCT_NAME}")
    print(f"Item: {ITEM_NUMBER}")
    print(f"Notification: {NTFY_URL}")
    print("=" * 60)
    
    # Fetch availability
    data = fetch_availability()
    if data is None:
        msg = f"❌ Error al verificar disponibilidad de {PRODUCT_NAME}"
        print(f"\n{msg}")
        send_notification(msg, priority="low")
        sys.exit(1)
    
    # Analyze stock
    result = analyze_stock(data)
    
    # Format and show message
    message = format_message(result)
    print(f"\n{message}\n")
    
    # Log result
    log_result(result)
    
    # Send notification if in stock
    if result and result["any_in_stock"]:
        send_notification(message, priority="high")
        print("\n🎉 STOCK FOUND! Notification sent!")
    else:
        print("\n😴 Still out of stock. No notification sent.")
    
    # Always print the message for GitHub Actions logs
    print("\n--- MESSAGE ---")
    print(message)
    print("--- END ---")
    
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
