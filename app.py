# mealmoment_app.py
# COMPLETE MEALMOMENT FOOD ORDERING SYSTEM
# COPY AND PASTE THIS ENTIRE FILE

import os
import json
import time
import sqlite3
import hashlib
import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import random

# ============================================
# DATABASE SETUP (SQLite - Simple & Ready)
# ============================================

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('mealmoment.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.seed_data()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # States table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                code TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Cities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                state_id INTEGER NOT NULL,
                timezone TEXT DEFAULT 'America/New_York',
                FOREIGN KEY (state_id) REFERENCES states(id),
                UNIQUE(name, state_id)
            )
        ''')
        
        # ZIP codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zip_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zip_code TEXT UNIQUE NOT NULL,
                city_id INTEGER NOT NULL,
                FOREIGN KEY (city_id) REFERENCES cities(id)
            )
        ''')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Menu categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                city_id INTEGER NOT NULL,
                meal_type TEXT CHECK(meal_type IN ('breakfast', 'lunch', 'dinner')),
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (city_id) REFERENCES cities(id)
            )
        ''')
        
        # Menu items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category_id INTEGER NOT NULL,
                city_id INTEGER NOT NULL,
                cuisine_type TEXT NOT NULL,
                image_url TEXT,
                is_special BOOLEAN DEFAULT 0,
                is_available BOOLEAN DEFAULT 1,
                preparation_time INTEGER DEFAULT 30,
                calories INTEGER,
                allergens TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES menu_categories(id),
                FOREIGN KEY (city_id) REFERENCES cities(id)
            )
        ''')
        
        # Carts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Cart items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cart_id INTEGER NOT NULL,
                menu_item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                special_instructions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
                FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
            )
        ''')
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                tax_amount REAL DEFAULT 0,
                delivery_fee REAL DEFAULT 2.99,
                final_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                delivery_address TEXT NOT NULL,
                delivery_city TEXT NOT NULL,
                delivery_state TEXT NOT NULL,
                delivery_zip TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                special_instructions TEXT,
                payment_status TEXT DEFAULT 'pending',
                stripe_payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                estimated_delivery TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Order items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                menu_item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                special_instructions TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
            )
        ''')
        
        self.conn.commit()
    
    def seed_data(self):
        cursor = self.conn.cursor()
        
        # Check if data exists
        cursor.execute("SELECT COUNT(*) FROM states")
        if cursor.fetchone()[0] > 0:
            return
        
        print("🌱 Seeding initial data...")
        
        # Add states
        states = [
            ("California", "CA"),
            ("New York", "NY"),
            ("Texas", "TX"),
            ("Florida", "FL"),
            ("Illinois", "IL")
        ]
        cursor.executemany("INSERT INTO states (name, code) VALUES (?, ?)", states)
        
        # Get California ID
        cursor.execute("SELECT id FROM states WHERE code = 'CA'")
        ca_id = cursor.fetchone()[0]
        
        # Add cities for California
        cities = [
            ("Los Angeles", ca_id, "America/Los_Angeles"),
            ("San Francisco", ca_id, "America/Los_Angeles"),
            ("San Diego", ca_id, "America/Los_Angeles")
        ]
        cursor.executemany(
            "INSERT INTO cities (name, state_id, timezone) VALUES (?, ?, ?)", 
            cities
        )
        
        # Get LA city ID
        cursor.execute("SELECT id FROM cities WHERE name = 'Los Angeles'")
        la_id = cursor.fetchone()[0]
        
        # Add ZIP codes for LA
        zip_codes = [
            ("90001", la_id),
            ("90012", la_id),
            ("90024", la_id),
            ("90210", la_id)
        ]
        cursor.executemany(
            "INSERT INTO zip_codes (zip_code, city_id) VALUES (?, ?)",
            zip_codes
        )
        
        # Create admin user
        admin_password = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute(
            """INSERT INTO users (email, password_hash, first_name, last_name, is_admin) 
               VALUES (?, ?, ?, ?, ?)""",
            ("admin@mealmoment.com", admin_password, "Admin", "User", 1)
        )
        
        # Create regular user
        user_password = hashlib.sha256("password123".encode()).hexdigest()
        cursor.execute(
            """INSERT INTO users (email, password_hash, first_name, last_name) 
               VALUES (?, ?, ?, ?)""",
            ("customer@example.com", user_password, "John", "Doe")
        )
        
        # Add menu categories for LA
        categories = [
            ("Breakfast Specials", "Morning favorites", la_id, "breakfast"),
            ("Lunch Combos", "Quick lunch options", la_id, "lunch"),
            ("Dinner Entrees", "Evening meals", la_id, "dinner"),
            ("Italian Classics", "Pasta & Pizza", la_id, "dinner"),
            ("Chinese Favorites", "Asian cuisine", la_id, "lunch"),
            ("Indian Delights", "Spicy curries", la_id, "dinner"),
            ("American Classics", "Classic dishes", la_id, "lunch"),
        ]
        cursor.executemany(
            """INSERT INTO menu_categories (name, description, city_id, meal_type) 
               VALUES (?, ?, ?, ?)""",
            categories
        )
        
        # Get category IDs
        cursor.execute("SELECT id, name FROM menu_categories WHERE city_id = ?", (la_id,))
        categories_data = cursor.fetchall()
        category_map = {name: cid for cid, name in categories_data}
        
        # Add 20+ menu items (including exactly 20 specials)
        menu_items = []
        
        # Breakfast items (7 items, 5 specials)
        breakfast_items = [
            ("Avocado Toast", "Smashed avocado on artisan bread", 12.99, "American", True, 450),
            ("Pancake Stack", "Three fluffy pancakes with syrup", 14.99, "American", True, 650),
            ("Eggs Benedict", "Poached eggs with hollandaise", 16.99, "American", True, 520),
            ("Breakfast Burrito", "Eggs, sausage, cheese in tortilla", 13.99, "Mexican", True, 780),
            ("Greek Yogurt Bowl", "Yogurt with honey and berries", 10.99, "Greek", True, 320),
            ("Belgian Waffles", "Crispy waffles with cream", 15.99, "American", False, 580),
            ("Breakfast Sandwich", "Egg, cheese, bacon on croissant", 11.99, "American", False, 420),
        ]
        
        # Lunch items (8 items, 5 specials)
        lunch_items = [
            ("Chicken Caesar Salad", "Grilled chicken, romaine, parmesan", 15.99, "American", True, 380),
            ("Turkey Club Sandwich", "Triple decker with bacon", 17.99, "American", True, 720),
            ("Vegetable Wrap", "Grilled vegetables with hummus", 13.99, "American", True, 290),
            ("BBQ Chicken Pizza", "Wood-fired pizza with BBQ sauce", 21.99, "Italian", True, 850),
            ("Beef Burger", "1/2 lb beef patty with cheese", 18.99, "American", True, 920),
            ("Cobb Salad", "Mixed greens with chicken, avocado", 16.99, "American", False, 410),
            ("Fish Tacos", "Grilled fish with cabbage slaw", 16.99, "Mexican", False, 480),
            ("Chicken Quesadilla", "Grilled chicken and cheese", 14.99, "Mexican", False, 620),
        ]
        
        # Italian items (7 items, 5 specials)
        italian_items = [
            ("Spaghetti Carbonara", "Pasta with eggs, cheese, pancetta", 18.99, "Italian", True, 650),
            ("Margherita Pizza", "Classic pizza with tomato, mozzarella", 22.99, "Italian", True, 820),
            ("Lasagna Bolognese", "Layers of pasta with meat sauce", 24.99, "Italian", True, 780),
            ("Chicken Parmesan", "Breaded chicken with marinara", 26.99, "Italian", True, 920),
            ("Fettuccine Alfredo", "Creamy pasta with parmesan", 19.99, "Italian", True, 720),
            ("Eggplant Parmesan", "Breaded eggplant with marinara", 22.99, "Italian", False, 580),
            ("Minestrone Soup", "Traditional vegetable soup", 9.99, "Italian", False, 210),
        ]
        
        # Chinese items (8 items, 5 specials)
        chinese_items = [
            ("Kung Pao Chicken", "Spicy stir-fried chicken", 19.99, "Chinese", True, 680),
            ("Beef with Broccoli", "Tender beef with broccoli", 21.99, "Chinese", True, 520),
            ("Vegetable Lo Mein", "Stir-fried noodles", 16.99, "Chinese", True, 490),
            ("Sweet and Sour Pork", "Crispy pork in tangy sauce", 20.99, "Chinese", True, 710),
            ("General Tso's Chicken", "Crispy chicken in spicy sauce", 22.99, "Chinese", True, 850),
            ("Fried Rice", "Vegetable fried rice", 14.99, "Chinese", False, 420),
            ("Wonton Soup", "Chicken broth with wontons", 8.99, "Chinese", False, 180),
            ("Mongolian Beef", "Beef strips in savory sauce", 23.99, "Chinese", False, 690),
        ]
        
        # Combine all items
        all_items = []
        all_items.extend([(name, desc, price, category_map["Breakfast Specials"], la_id, cuisine, f"https://via.placeholder.com/400x300/FF6B6B/FFFFFF?text={name.replace(' ', '+')}", special, 25, calories, None) for name, desc, price, cuisine, special, calories in breakfast_items])
        all_items.extend([(name, desc, price, category_map["Lunch Combos"], la_id, cuisine, f"https://via.placeholder.com/400x300/4ECDC4/FFFFFF?text={name.replace(' ', '+')}", special, 25, calories, None) for name, desc, price, cuisine, special, calories in lunch_items])
        all_items.extend([(name, desc, price, category_map["Italian Classics"], la_id, cuisine, f"https://via.placeholder.com/400x300/45B7D1/FFFFFF?text={name.replace(' ', '+')}", special, 30, calories, None) for name, desc, price, cuisine, special, calories in italian_items])
        all_items.extend([(name, desc, price, category_map["Chinese Favorites"], la_id, cuisine, f"https://via.placeholder.com/400x300/96CEB4/FFFFFF?text={name.replace(' ', '+')}", special, 25, calories, None) for name, desc, price, cuisine, special, calories in chinese_items])
        
        # Add more specials to reach exactly 20
        extra_specials = [
            ("Grilled Salmon", "Atlantic salmon with lemon butter", 28.99, category_map["Dinner Entrees"], la_id, "American", "https://via.placeholder.com/400x300/FFEAA7/000000?text=Salmon", True, 35, 480, "Fish"),
            ("Filet Mignon", "8oz beef tenderloin", 39.99, category_map["Dinner Entrees"], la_id, "American", "https://via.placeholder.com/400x300/DDA0DD/000000?text=Steak", True, 40, 920, None),
            ("BBQ Ribs", "Pork ribs with house sauce", 32.99, category_map["Dinner Entrees"], la_id, "American", "https://via.placeholder.com/400x300/98D8C8/000000?text=Ribs", True, 45, 1120, None),
            ("Tandoori Chicken", "Chicken marinated in yogurt and spices", 24.99, category_map["Indian Delights"], la_id, "Indian", "https://via.placeholder.com/400x300/F7DC6F/000000?text=Tandoori", True, 35, 620, "Dairy"),
            ("Vegetable Biryani", "Fragrant rice with vegetables", 18.99, category_map["Indian Delights"], la_id, "Indian", "https://via.placeholder.com/400x300/ABD9DA/000000?text=Biryani", True, 30, 450, None),
        ]
        
        all_items.extend(extra_specials)
        
        # Insert all menu items
        cursor.executemany(
            """INSERT INTO menu_items (name, description, price, category_id, city_id, cuisine_type, image_url, is_special, preparation_time, calories, allergens) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            all_items
        )
        
        self.conn.commit()
        print("✅ Data seeded successfully!")
    
    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor
    
    def fetch_one(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def fetch_all(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        return [dict(row) for row in results]

# Initialize database
db = Database()

# ============================================
# BUSINESS LOGIC
# ============================================

def get_current_meal_type(city_timezone="America/New_York"):
    """Determine current meal type based on time"""
    current_hour = datetime.datetime.now().hour
    
    if 5 <= current_hour < 11:    # 5 AM - 10:59 AM
        return "breakfast"
    elif 11 <= current_hour < 16: # 11 AM - 3:59 PM
        return "lunch"
    else:                         # 4 PM - 4:59 AM
        return "dinner"

def generate_order_number():
    """Generate unique order number"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
    return f"MM-{timestamp}-{random_str}"

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

# ============================================
# API FUNCTIONS
# ============================================

def register_user(email, password, first_name=None, last_name=None, phone=None):
    """Register a new user"""
    existing = db.fetch_one("SELECT id FROM users WHERE email = ?", (email,))
    if existing:
        return {"error": "Email already registered"}
    
    password_hash = hash_password(password)
    db.execute(
        """INSERT INTO users (email, password_hash, first_name, last_name, phone) 
           VALUES (?, ?, ?, ?, ?)""",
        (email, password_hash, first_name, last_name, phone)
    )
    
    user = db.fetch_one("SELECT id, email, first_name, last_name, is_admin FROM users WHERE email = ?", (email,))
    return {"success": True, "user": user}

def login_user(email, password):
    """Login user"""
    password_hash = hash_password(password)
    user = db.fetch_one(
        "SELECT id, email, first_name, last_name, is_admin FROM users WHERE email = ? AND password_hash = ?",
        (email, password_hash)
    )
    
    if not user:
        return {"error": "Invalid email or password"}
    
    return {"success": True, "user": user}

def get_states():
    """Get all states"""
    return db.fetch_all("SELECT * FROM states ORDER BY name")

def get_zip_info(zip_code):
    """Get city info for ZIP code"""
    result = db.fetch_one("""
        SELECT z.*, c.name as city_name, c.timezone, s.name as state_name, s.code as state_code
        FROM zip_codes z
        JOIN cities c ON z.city_id = c.id
        JOIN states s ON c.state_id = s.id
        WHERE z.zip_code = ?
    """, (zip_code,))
    
    if not result:
        return {"error": "ZIP code not found"}
    
    return result

def get_menu(city_id):
    """Get menu for city based on current time"""
    city = db.fetch_one("SELECT * FROM cities WHERE id = ?", (city_id,))
    if not city:
        return {"error": "City not found"}
    
    meal_type = get_current_meal_type(city["timezone"])
    
    # Get exactly 20 specials
    specials = db.fetch_all("""
        SELECT mi.*, mc.name as category_name
        FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.id
        WHERE mi.city_id = ? 
        AND mi.is_special = 1
        AND mi.is_available = 1
        ORDER BY RANDOM()
        LIMIT 20
    """, (city_id,))
    
    # Get all menu items for current meal type
    menu_items = db.fetch_all("""
        SELECT mi.*, mc.name as category_name
        FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.id
        WHERE mi.city_id = ? 
        AND mc.meal_type = ?
        AND mi.is_available = 1
        ORDER BY mi.cuisine_type, mi.name
    """, (city_id, meal_type))
    
    # Group by cuisine
    menu_by_cuisine = {}
    for item in menu_items:
        cuisine = item["cuisine_type"]
        if cuisine not in menu_by_cuisine:
            menu_by_cuisine[cuisine] = []
        menu_by_cuisine[cuisine].append(item)
    
    return {
        "city_id": city_id,
        "city_name": city["name"],
        "meal_type": meal_type,
        "specials": specials,
        "menu_by_cuisine": menu_by_cuisine,
        "timestamp": datetime.datetime.now().isoformat()
    }

def add_to_cart(user_id, menu_item_id, quantity=1, special_instructions=None, session_id=None):
    """Add item to cart"""
    # Get or create cart
    cart = db.fetch_one(
        "SELECT id FROM carts WHERE user_id = ? OR session_id = ? LIMIT 1",
        (user_id, session_id)
    )
    
    if not cart:
        db.execute(
            "INSERT INTO carts (user_id, session_id) VALUES (?, ?)",
            (user_id, session_id)
        )
        cart = db.fetch_one("SELECT id FROM carts WHERE user_id = ?", (user_id,))
    
    cart_id = cart["id"]
    
    # Check if item already in cart
    existing = db.fetch_one(
        "SELECT id, quantity FROM cart_items WHERE cart_id = ? AND menu_item_id = ?",
        (cart_id, menu_item_id)
    )
    
    if existing:
        # Update quantity
        new_quantity = existing["quantity"] + quantity
        db.execute(
            "UPDATE cart_items SET quantity = ? WHERE id = ?",
            (new_quantity, existing["id"])
        )
    else:
        # Add new item
        db.execute(
            """INSERT INTO cart_items (cart_id, menu_item_id, quantity, special_instructions) 
               VALUES (?, ?, ?, ?)""",
            (cart_id, menu_item_id, quantity, special_instructions)
        )
    
    return {"success": True, "cart_id": cart_id}

def get_cart(user_id, session_id=None):
    """Get cart with items and totals"""
    cart = db.fetch_one(
        "SELECT id FROM carts WHERE user_id = ? OR session_id = ? LIMIT 1",
        (user_id, session_id)
    )
    
    if not cart:
        return {"items": [], "subtotal": 0, "tax": 0, "delivery_fee": 2.99, "total": 0}
    
    cart_id = cart["id"]
    items = db.fetch_all("""
        SELECT ci.*, mi.name, mi.price, mi.image_url, mi.description
        FROM cart_items ci
        JOIN menu_items mi ON ci.menu_item_id = mi.id
        WHERE ci.cart_id = ?
    """, (cart_id,))
    
    # Calculate totals
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    tax = subtotal * 0.0825
    delivery_fee = 2.99
    total = subtotal + tax + delivery_fee
    
    return {
        "cart_id": cart_id,
        "items": items,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "delivery_fee": delivery_fee,
        "total": round(total, 2)
    }

def checkout(user_id, checkout_data):
    """Process checkout"""
    cart = db.fetch_one("SELECT id FROM carts WHERE user_id = ?", (user_id,))
    if not cart:
        return {"error": "Cart is empty"}
    
    cart_id = cart["id"]
    cart_items = db.fetch_all("""
        SELECT ci.*, mi.name, mi.price
        FROM cart_items ci
        JOIN menu_items mi ON ci.menu_item_id = mi.id
        WHERE ci.cart_id = ?
    """, (cart_id,))
    
    if not cart_items:
        return {"error": "Cart is empty"}
    
    # Calculate totals
    subtotal = sum(item["price"] * item["quantity"] for item in cart_items)
    tax = subtotal * 0.0825
    delivery_fee = 2.99
    total = subtotal + tax + delivery_fee
    
    # Simulate Stripe payment
    order_number = generate_order_number()
    payment_id = f"ch_{random.randint(100000, 999999)}"
    
    # Create order
    db.execute("""
        INSERT INTO orders (
            order_number, user_id, total_amount, tax_amount, delivery_fee,
            final_amount, delivery_address, delivery_city, delivery_state,
            delivery_zip, customer_name, customer_phone, special_instructions,
            payment_status, stripe_payment_id, status, estimated_delivery
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_number, user_id, subtotal, tax, delivery_fee,
        total, checkout_data["delivery_address"], checkout_data["delivery_city"],
        checkout_data["delivery_state"], checkout_data["delivery_zip"],
        checkout_data["customer_name"], checkout_data["customer_phone"],
        checkout_data.get("special_instructions"), "paid", payment_id, "confirmed",
        (datetime.datetime.now() + datetime.timedelta(minutes=45)).isoformat()
    ))
    
    order = db.fetch_one("SELECT id FROM orders WHERE order_number = ?", (order_number,))
    order_id = order["id"]
    
    # Add order items
    for item in cart_items:
        db.execute("""
            INSERT INTO order_items (order_id, menu_item_id, item_name, quantity, price, special_instructions)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id, item["menu_item_id"], item["name"],
            item["quantity"], item["price"], item.get("special_instructions")
        ))
    
    # Clear cart
    db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
    db.execute("DELETE FROM carts WHERE id = ?", (cart_id,))
    
    return {
        "success": True,
        "order_number": order_number,
        "order_id": order_id,
        "total": round(total, 2),
        "estimated_delivery": (datetime.datetime.now() + datetime.timedelta(minutes=45)).isoformat()
    }

def get_user_orders(user_id):
    """Get orders for user"""
    orders = db.fetch_all("""
        SELECT * FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (user_id,))
    
    for order in orders:
        items = db.fetch_all(
            "SELECT * FROM order_items WHERE order_id = ?",
            (order["id"],)
        )
        order["items"] = items
    
    return orders

# Admin functions
def get_all_orders():
    """Get all orders (admin)"""
    orders = db.fetch_all("SELECT * FROM orders ORDER BY created_at DESC")
    
    for order in orders:
        items = db.fetch_all(
            "SELECT * FROM order_items WHERE order_id = ?",
            (order["id"],)
        )
        order["items"] = items
        
        user = db.fetch_one(
            "SELECT email, first_name, last_name FROM users WHERE id = ?",
            (order["user_id"],)
        )
        order["user"] = user
    
    return orders

def update_order_status(order_id, status):
    """Update order status (admin)"""
    db.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (status, order_id)
    )
    return {"success": True, "order_id": order_id, "status": status}

def create_menu_item(item_data):
    """Create new menu item (admin)"""
    db.execute("""
        INSERT INTO menu_items (
            name, description, price, category_id, city_id, cuisine_type,
            image_url, is_special, is_available, preparation_time, calories, allergens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item_data["name"], item_data["description"], item_data["price"],
        item_data["category_id"], item_data["city_id"], item_data["cuisine_type"],
        item_data.get("image_url"), item_data.get("is_special", False),
        item_data.get("is_available", True), item_data.get("preparation_time", 30),
        item_data.get("calories"), item_data.get("allergens")
    ))
    
    return {"success": True, "message": "Menu item created"}

# ============================================
# WEB SERVER (Simple HTTP Server)
# ============================================

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json

class MealMomentHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        # API Routes
        if path == "/api/states":
            self.send_json(get_states())
        
        elif path.startswith("/api/zip/"):
            zip_code = path.split("/")[-1]
            result = get_zip_info(zip_code)
            self.send_json(result)
        
        elif path.startswith("/api/menu/"):
            try:
                city_id = int(path.split("/")[-1])
                result = get_menu(city_id)
                self.send_json(result)
            except:
                self.send_error(400, "Invalid city ID")
        
        elif path == "/":
            # Serve HTML interface
            self.serve_html_interface()
        
        else:
            self.send_error(404, "Endpoint not found")
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        path = self.path
        
        if path == "/api/register":
            result = register_user(
                data["email"], data["password"],
                data.get("first_name"), data.get("last_name"), data.get("phone")
            )
            self.send_json(result)
        
        elif path == "/api/login":
            result = login_user(data["email"], data["password"])
            self.send_json(result)
        
        elif path == "/api/cart/add":
            result = add_to_cart(
                data["user_id"], data["menu_item_id"],
                data.get("quantity", 1), data.get("special_instructions"),
                data.get("session_id")
            )
            self.send_json(result)
        
        elif path == "/api/checkout":
            result = checkout(data["user_id"], data)
            self.send_json(result)
        
        else:
            self.send_error(404, "Endpoint not found")
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def serve_html_interface(self):
        """Serve a simple HTML interface"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MealMoment - Food Ordering System</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }
                .container {
                    background: white;
                    border-radius: 10px;
                    padding: 30px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #333;
                    text-align: center;
                    margin-bottom: 30px;
                }
                h2 {
                    color: #667eea;
                    border-bottom: 2px solid #667eea;
                    padding-bottom: 10px;
                }
                .menu-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }
                .menu-item {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 15px;
                    background: #f9f9f9;
                    transition: transform 0.2s;
                }
                .menu-item:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                }
                .menu-item.special {
                    border: 2px solid #ff6b6b;
                    background: #fff5f5;
                }
                .menu-item img {
                    width: 100%;
                    height: 200px;
                    object-fit: cover;
                    border-radius: 5px;
                    margin-bottom: 10px;
                }
                .price {
                    color: #667eea;
                    font-weight: bold;
                    font-size: 1.2em;
                }
                .special-badge {
                    background: #ff6b6b;
                    color: white;
                    padding: 3px 10px;
                    border-radius: 20px;
                    font-size: 0.8em;
                    display: inline-block;
                    margin-bottom: 10px;
                }
                .section {
                    margin-bottom: 40px;
                    padding: 20px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                }
                .test-buttons {
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                    margin: 20px 0;
                }
                .test-btn {
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                }
                .test-btn:hover {
                    background: #5a67d8;
                }
                .output {
                    background: #f7f7f7;
                    padding: 15px;
                    border-radius: 5px;
                    margin-top: 20px;
                    font-family: monospace;
                    white-space: pre-wrap;
                    max-height: 400px;
                    overflow-y: auto;
                }
                .api-status {
                    background: #e8f5e8;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0;
                    color: #2e7d32;
                }
                .api-status.error {
                    background: #ffebee;
                    color: #c62828;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🍽️ MealMoment Food Ordering System</h1>
                
                <div class="api-status" id="status">System Ready</div>
                
                <div class="section">
                    <h2>🚀 Quick Test</h2>
                    <div class="test-buttons">
                        <button class="test-btn" onclick="testAPI('states')">Get States</button>
                        <button class="test-btn" onclick="testAPI('zip', '90001')">Test ZIP 90001</button>
                        <button class="test-btn" onclick="testAPI('menu', 1)">Get LA Menu</button>
                        <button class="test-btn" onclick="testAPI('register')">Register User</button>
                        <button class="test-btn" onclick="testAPI('login')">Login User</button>
                        <button class="test-btn" onclick="showMenu()">Show Menu Preview</button>
                    </div>
                    
                    <div id="output" class="output">Click buttons to test API...</div>
                </div>
                
                <div class="section" id="menu-preview" style="display:none;">
                    <h2>📋 Menu Preview (Los Angeles)</h2>
                    <div id="menu-content"></div>
                </div>
                
                <div class="section">
                    <h2>📚 API Documentation</h2>
                    <h3>GET Endpoints:</h3>
                    <ul>
                        <li><code>GET /api/states</code> - Get all states</li>
                        <li><code>GET /api/zip/{zip_code}</code> - Get city info by ZIP</li>
                        <li><code>GET /api/menu/{city_id}</code> - Get menu for city</li>
                    </ul>
                    
                    <h3>POST Endpoints:</h3>
                    <ul>
                        <li><code>POST /api/register</code> - Register user</li>
                        <li><code>POST /api/login</code> - Login user</li>
                        <li><code>POST /api/cart/add</code> - Add to cart</li>
                        <li><code>POST /api/checkout</code> - Checkout order</li>
                    </ul>
                    
                    <h3>Database Info:</h3>
                    <p>✅ All data saved to SQLite database: <code>mealmoment.db</code></p>
                    <p>✅ 20+ daily specials automatically selected</p>
                    <p>✅ Real-time breakfast/lunch/dinner switching</p>
                    <p>✅ Complete cart & checkout system</p>
                </div>
            </div>
            
            <script>
                async function testAPI(endpoint, param = '') {
                    const status = document.getElementById('status');
                    const output = document.getElementById('output');
                    
                    status.textContent = `Testing ${endpoint}...`;
                    status.className = 'api-status';
                    
                    try {
                        let url = '';
                        let method = 'GET';
                        let data = null;
                        
                        switch(endpoint) {
                            case 'states':
                                url = '/api/states';
                                break;
                            case 'zip':
                                url = `/api/zip/${param}`;
                                break;
                            case 'menu':
                                url = `/api/menu/${param}`;
                                break;
                            case 'register':
                                url = '/api/register';
                                method = 'POST';
                                data = {
                                    email: 'test@example.com',
                                    password: 'password123',
                                    first_name: 'Test',
                                    last_name: 'User'
                                };
                                break;
                            case 'login':
                                url = '/api/login';
                                method = 'POST';
                                data = {
                                    email: 'customer@example.com',
                                    password: 'password123'
                                };
                                break;
                        }
                        
                        const options = {
                            method: method,
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        };
                        
                        if (data) {
                            options.body = JSON.stringify(data);
                        }
                        
                        const response = await fetch(url, options);
                        const result = await response.json();
                        
                        output.textContent = JSON.stringify(result, null, 2);
                        status.textContent = `${endpoint} successful!`;
                        status.className = 'api-status';
                        
                        if (endpoint === 'menu') {
                            showMenuPreview(result);
                        }
                        
                    } catch (error) {
                        output.textContent = 'Error: ' + error.message;
                        status.textContent = 'API Error';
                        status.className = 'api-status error';
                    }
                }
                
                function showMenu() {
                    testAPI('menu', 1);
                    document.getElementById('menu-preview').style.display = 'block';
                }
                
                function showMenuPreview(data) {
                    const container = document.getElementById('menu-content');
                    let html = `<h3>${data.city_name} - ${data.meal_type.toUpperCase()}</h3>`;
                    
                    // Show specials
                    html += `<h4>🎯 Daily Specials (${data.specials.length} items)</h4>`;
                    html += '<div class="menu-grid">';
                    data.specials.forEach(item => {
                        html += `
                            <div class="menu-item special">
                                <div class="special-badge">SPECIAL</div>
                                <img src="${item.image_url}" alt="${item.name}">
                                <h3>${item.name}</h3>
                                <p>${item.description}</p>
                                <p class="price">$${item.price}</p>
                                <p>🔥 ${item.calories} cal | ⏱️ ${item.preparation_time} min</p>
                            </div>
                        `;
                    });
                    html += '</div>';
                    
                    // Show by cuisine
                    for (const [cuisine, items] of Object.entries(data.menu_by_cuisine)) {
                        html += `<h4>${cuisine} Cuisine</h4>`;
                        html += '<div class="menu-grid">';
                        items.forEach(item => {
                            html += `
                                <div class="menu-item">
                                    <img src="${item.image_url}" alt="${item.name}">
                                    <h3>${item.name}</h3>
                                    <p>${item.description}</p>
                                    <p class="price">$${item.price}</p>
                                    <p>🔥 ${item.calories} cal</p>
                                </div>
                            `;
                        });
                        html += '</div>';
                    }
                    
                    container.innerHTML = html;
                }
                
                // Auto-test on load
                window.onload = () => {
                    setTimeout(() => testAPI('states'), 1000);
                };
            </script>
        </body>
        </html>
        """
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

def run_server():
    """Run the HTTP server"""
    print("=" * 60)
    print("🍽️  MEALMOMENT FOOD ORDERING SYSTEM")
    print("=" * 60)
    print("📁 Database: mealmoment.db (SQLite)")
    print("🌐 Server: http://localhost:8080")
    print("📚 API Docs: http://localhost:8080")
    print("=" * 60)
    print("🔑 Admin Login: admin@mealmoment.com / admin123")
    print("👤 Customer Login: customer@example.com / password123")
    print("=" * 60)
    
    server = HTTPServer(('localhost', 8080), MealMomentHandler)
    print("✅ Server started! Press Ctrl+C to stop")
    server.serve_forever()

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
