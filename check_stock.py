#!/usr/bin/env python3
"""
IKEA Mexico Stock Checker
Checks product availability for multiple products and sends notifications via ntfy.sh
"""

import requests
import json
import os
import sys
from datetime import datetime

# === CONFIGURATION ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.environ.get("IKEA_PRODUCTS_FILE", os.path.join(SCRIPT_DIR, "products.json"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "ikea-stock-radman")
NTFY_TOKEN = os.environ.get("NTFY_TOKEN", "")  # Optional: for private topics

# === ENDPOINTS ===
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Headers to mimic browser request (no Accept-Encoding to get plain text)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Referer": "https://www.ikea.com/mx/es/",
    "Origin": "https://www.ikea.com",
}


def load_products():
    """Load product list from config file."""
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        products = config.get("products", [])
        if not products:
            print(f"  ERROR: No products found in {PRODUCTS_FILE}")
            return []
        print(f"  ✓ Loaded {len(products)} products from {PRODUCTS_FILE}")
        return products
    except (IOError, json.JSONDecodeError) as e:
        print(f"  ERROR loading products file {PRODUCTS_FILE}: {e}")
        return []


def fetch_availability(product):
    """Fetch stock availability for a single product."""
    item_number = product["item_number"]
    name = product["name"]
    fragment_url = f"https://www.ikea.com/mx/es/lower-funnel-fragments/product-availability/?itemNo={item_number}&inline"
    ingka_api_url = f"https://api.salesitem.ingka.com/cia/availabilities/ru/mx?itemNos={item_number}"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking {name} (item: {item_number})...")
    
    # Method 1: Fragment endpoint (returns full page with embedded JSON)
    try:
        resp = requests.get(fragment_url, headers=HEADERS, timeout=30)
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
        resp = requests.get(ingka_api_url, headers=ingka_headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if "availabilities" in data and data["availabilities"]:
            avail = data["availabilities"][0]
            return transform_ingka_response(avail, product)
    except requests.RequestException as e:
        print(f"  Ingka API error: {e}")
    except (KeyError, IndexError) as e:
        print(f"  Ingka API parse error: {e}")
    
    print("  ERROR: All endpoints failed")
    return None


def transform_ingka_response(avail, product):
    """Transform Ingka API response to our expected format."""
    item_number = product["item_number"]
    name = product["name"]
    
    # Parse the Ingka response structure
    # avail looks like: {"buyingOption": {...}, "classUnitKey": {...}, ...}
    result = {
        "product": {
            "itemNo": item_number,
            "name": name,
            "typeName": "",
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
    
    # Parse buyingOption for cashCarry / homeDelivery availability
    buying = avail.get("buyingOption", {})
    
    # cashCarry (in-store)
    cash = buying.get("cashCarry", {})
    if cash.get("availability", {}).get("probability", {}).get("thisDay", {}).get("messageType"):
        msg_type = cash["availability"]["probability"]["thisDay"]["messageType"]
        quantity = cash.get("availability", {}).get("quantity", 0)
        store_id = avail.get("classUnitKey", {}).get("classUnitCode", "UNKNOWN")
        result["availabilityResponse"]["availability"]["stores"][store_id] = {
            "in_stock": msg_type != "OUT_OF_STOCK",
            "status": msg_type,
            "quantity": quantity,
            "cash_carry": True,
            "click_collect": False,
            "restock_dates": [],
        }
    
    return result


def analyze_stock(data, product):
    """Analyze stock availability from the parsed response."""
    if not data:
        return None
    
    product_data = data.get("product", {})
    availability = data.get("availabilityResponse", {}).get("availability", {})
    
    result = {
        "product_name": product.get("name", product_data.get("name", "IKEA Product")),
        "product_type": product_data.get("typeName", ""),
        "price": product_data.get("price", 0),
        "currency": product_data.get("currencyCode", "MXN"),
        "item_number": product_data.get("itemNo", product["item_number"]),
        "url": product["url"],
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
        return None
    
    product = result["product_name"]
    price = f"${result['price']:,.0f} {result['currency']}" if result["price"] else ""
    
    lines = []
    
    if result["any_in_stock"]:
        lines.append(f"🎉 ¡STOCK DISPONIBLE! 🎉")
        lines.append(f"📦 {product}")
        if price:
            lines.append(f"💰 {price}")
        lines.append("")
        
        # Online
        if result["is_online_sellable"] or not result["is_sold_out_online"]:
            lines.append("✅ Compra en línea: DISPONIBLE")
        else:
            lines.append("❌ Compra en línea: Agotado")
        
        # Home delivery
        if result["home_delivery"]["available"]:
            lines.append(f"🚚 Envío a domicilio: DISPONIBLE")
        else:
            lines.append(f"🚚 Envío a domicilio: No disponible")
        
        # Click & collect
        if result["click_collect"]["available"]:
            lines.append("🏪 Click & Collect: DISPONIBLE")
        else:
            lines.append("🏪 Click & Collect: No disponible")
        
        # Stores with stock
        stores_in_stock = [
            sid for sid, s in result["stores"].items() if s["in_stock"]
        ]
        if stores_in_stock:
            lines.append(f"\n📍 Tiendas con stock: {', '.join(stores_in_stock)}")
        
        lines.append(f"\n🔗 {result['url']}")
    else:
        lines.append(f"🔍 {product} — Sin stock")
        if price:
            lines.append(f"💰 {price}")
        
        # Show restock dates
        if result["restock_dates"]:
            dates = list(set(result["restock_dates"]))
            lines.append(f"\n📅 Próximas fechas de reabastecimiento:")
            for d in dates:
                lines.append(f"   • {d}")
        
        # Show store statuses
        if result["stores"]:
            lines.append("\n📍 Estado por tienda:")
            for sid, store in result["stores"].items():
                status = store["status"]
                qty = store.get("quantity")
                qty_str = f" ({qty} unidades)" if qty is not None else ""
                lines.append(f"   • Tienda {sid}: {status}{qty_str}")
                if store["restock_dates"]:
                    lines.append(f"     Próximo stock: {', '.join(store['restock_dates'])}")
    
    return "\n".join(lines)


def send_notification(messages, title):
    """Send notification via ntfy.sh with one or more messages."""
    if not messages:
        return
    
    # Build the message body (limit to a reasonable size)
    body = "\n\n".join(messages)
    if len(body) > 3900:  # ntfy has a 4096 byte limit, keep under
        body = body[:3900] + "\n... (truncado)"
    
    # HTTP headers must be latin-1 encodable, so strip non-latin-1 chars from title
    safe_title = title.encode("latin-1", errors="replace").decode("latin-1")
    headers = {"Title": safe_title}
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
    
    try:
        resp = requests.post(
            NTFY_URL,
            data=body.encode("utf-8"),
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


def log_result(result, timestamp):
    """Append result to a log file for tracking."""
    log_file = os.path.join(SCRIPT_DIR, "stock_log.jsonl")
    
    entry = {
        "timestamp": timestamp,
        "item_number": result["item_number"],
        "product_name": result["product_name"],
        "any_in_stock": result["any_in_stock"],
        "is_online_sellable": result["is_online_sellable"],
        "stores": result.get("stores", {}),
    }
    
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"  ⚠️  Could not write log: {e}")


def main():
    """Main entry point."""
    now = datetime.now()
    print("=" * 60)
    print(f"IKEA Mexico Stock Checker")
    print(f"Time: {now.strftime('%d/%m/%Y %H:%M')}")
    print(f"Notification: {NTFY_URL}")
    print("=" * 60)
    
    # Load products
    products = load_products()
    if not products:
        print("  ERROR: No products to check. Exiting.")
        sys.exit(1)
    
    # Check each product
    results = []
    errors = []
    for product in products:
        data = fetch_availability(product)
        if data is None:
            errors.append(product["name"])
            continue
        result = analyze_stock(data, product)
        if result:
            results.append(result)
            log_result(result, now.isoformat())
    
    # Build messages
    in_stock_msgs = []
    out_stock_msgs = []
    for r in results:
        msg = format_message(r)
        if r["any_in_stock"]:
            in_stock_msgs.append(msg)
        else:
            out_stock_msgs.append(msg)
    
    # Print summary
    print(f"\n--- RESULTADO ---")
    for r in results:
        status = "✅ EN STOCK" if r["any_in_stock"] else "❌ Sin stock"
        print(f"{status}: {r['product_name']}")
    if errors:
        print(f"⚠️  Error al verificar: {', '.join(errors)}")
    print("--- FIN ---")
    
    # Send notifications
    if in_stock_msgs:
        send_notification(in_stock_msgs, "🎉 IKEA: ¡Stock disponible!")
        print("\n🎉 STOCK FOUND! Notification sent!")
    else:
        print("\n😴 Todos los productos sin stock. No se envió notificación.")
    
    # Send daily summary if there are out-of-stock products (helps verify the bot works)
    if out_stock_msgs and not in_stock_msgs:
        # Only send a brief summary when a product is newly out of stock? 
        # For now, skip to avoid daily spam - only notify on stock or errors
        pass
    
    # If there were errors, notify
    if errors and not in_stock_msgs:
        msg = f"⚠️ Error al verificar: {', '.join(errors)}\nRevisa los logs de GitHub Actions."
        send_notification([msg], "IKEA Stock Checker: Error")
    
    return 0 if (results and not in_stock_msgs) else (1 if in_stock_msgs else 2)


if __name__ == "__main__":
    sys.exit(main())
