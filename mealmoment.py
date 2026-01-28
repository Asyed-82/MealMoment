"""
COMPLETE MEALMOMENT FOOD ORDERING SYSTEM
Single-file implementation with PostgreSQL, Stripe, and real-time menus
"""

import os
import sys
import json
import asyncio
import stripe
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from decimal import Decimal
from enum import Enum
import bcrypt
import jwt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from contextlib import contextmanager
import logging

# Configuration
DATABASE_URL = "postgresql://postgres:password@localhost/mealmoment"
STRIPE_SECRET_KEY = "sk_test_your_stripe_key_here"
STRIPE_PUBLIC_KEY = "pk_test_your_stripe_key_here"
JWT_SECRET = "your_jwt_secret_key_change_in_production"
JWT_ALGORITHM = "HS256"

# Database setup
class Database:
    _pool = None
    
    @classmethod
    def initialize(cls):
        if not cls._pool:
            cls._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL
            )
            cls._create_tables()
    
    @classmethod
    def _create_tables(cls):
        with cls.get_connection() as conn:
            with conn.cursor() as cur:
                # States table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS states (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        code VARCHAR(2) UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Cities table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cities (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        state_id INTEGER REFERENCES states(id),
                        timezone VARCHAR(50) DEFAULT 'America/New_York',
                        UNIQUE(name, state_id)
                    )
                """)
                
                # ZIP codes table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS zip_codes (
                        id SERIAL PRIMARY KEY,
                        zip_code VARCHAR(10) UNIQUE NOT NULL,
                        city_id INTEGER REFERENCES cities(id),
                        latitude DECIMAL(10,8),
                        longitude DECIMAL(11,8)
                    )
                """)
                
                # Users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        first_name VARCHAR(100),
                        last_name VARCHAR(100),
                        phone VARCHAR(20),
                        is_admin BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Menu categories table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS menu_categories (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        city_id INTEGER REFERENCES cities(id),
                        meal_type VARCHAR(20) CHECK (meal_type IN ('breakfast', 'lunch', 'dinner')),
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # Menu items table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS menu_items (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        description TEXT,
                        price DECIMAL(10,2) NOT NULL,
                        category_id INTEGER REFERENCES menu_categories(id),
                        city_id INTEGER REFERENCES cities(id),
                        cuisine_type VARCHAR(50),
                        image_url TEXT,
                        is_special BOOLEAN DEFAULT FALSE,
                        is_available BOOLEAN DEFAULT TRUE,
                        preparation_time INTEGER DEFAULT 30,
                        calories INTEGER,
                        allergens TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Carts table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS carts (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        session_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Cart items table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cart_items (
                        id SERIAL PRIMARY KEY,
                        cart_id INTEGER REFERENCES carts(id) ON DELETE CASCADE,
                        menu_item_id INTEGER REFERENCES menu_items(id),
                        quantity INTEGER NOT NULL DEFAULT 1,
                        special_instructions TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Orders table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id SERIAL PRIMARY KEY,
                        order_number VARCHAR(50) UNIQUE NOT NULL,
                        user_id INTEGER REFERENCES users(id),
                        total_amount DECIMAL(10,2) NOT NULL,
                        tax_amount DECIMAL(10,2) DEFAULT 0,
                        delivery_fee DECIMAL(10,2) DEFAULT 2.99,
                        final_amount DECIMAL(10,2) NOT NULL,
                        status VARCHAR(50) DEFAULT 'pending',
                        delivery_address TEXT NOT NULL,
                        delivery_city VARCHAR(100),
                        delivery_state VARCHAR(50),
                        delivery_zip VARCHAR(20),
                        customer_name VARCHAR(200),
                        customer_phone VARCHAR(20),
                        special_instructions TEXT,
                        payment_status VARCHAR(50) DEFAULT 'pending',
                        stripe_payment_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        estimated_delivery TIMESTAMP
                    )
                """)
                
                # Order items table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS order_items (
                        id SERIAL PRIMARY KEY,
                        order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                        menu_item_id INTEGER REFERENCES menu_items(id),
                        item_name VARCHAR(200) NOT NULL,
                        quantity INTEGER NOT NULL,
                        price DECIMAL(10,2) NOT NULL,
                        special_instructions TEXT
                    )
                """)
                
                # Create indexes
                cur.execute("CREATE INDEX IF NOT EXISTS idx_zip_codes_zip ON zip_codes(zip_code)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_city ON menu_items(city_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_carts_session ON carts(session_id)")
                
                conn.commit()
    
    @classmethod
    @contextmanager
    def get_connection(self):
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)
    
    @classmethod
    def execute_query(cls, query, params=None, fetch_one=False, fetch_all=False):
        with cls.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, params or ())
                if fetch_one:
                    return dict(cur.fetchone()) if cur.rowcount > 0 else None
                elif fetch_all:
                    return [dict(row) for row in cur.fetchall()]
                return cur.rowcount

# Initialize database
Database.initialize()

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Pydantic Models
class UserCreate(BaseModel):
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class StateCreate(BaseModel):
    name: str
    code: str

class CityCreate(BaseModel):
    name: str
    state_id: int
    timezone: str = "America/New_York"

class ZipCodeCreate(BaseModel):
    zip_code: str
    city_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class MenuItemCreate(BaseModel):
    name: str
    description: str
    price: float
    category_id: int
    city_id: int
    cuisine_type: str
    image_url: Optional[str] = None
    is_special: bool = False
    is_available: bool = True
    preparation_time: int = 30
    calories: Optional[int] = None
    allergens: Optional[str] = None

class CartItemAdd(BaseModel):
    menu_item_id: int
    quantity: int = 1
    special_instructions: Optional[str] = None

class CheckoutRequest(BaseModel):
    delivery_address: str
    delivery_city: str
    delivery_state: str
    delivery_zip: str
    customer_name: str
    customer_phone: str
    special_instructions: Optional[str] = None
    stripe_token: str

class OrderStatusUpdate(BaseModel):
    status: str

# Authentication
security = HTTPBearer()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

def create_jwt_token(data: dict) -> str:
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("user_id")
    user = Database.execute_query(
        "SELECT * FROM users WHERE id = %s",
        (user_id,),
        fetch_one=True
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_admin(user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# FastAPI App
app = FastAPI(title="MealMoment API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper Functions
def get_current_meal_type(city_timezone="America/New_York"):
    """Determine current meal type based on time"""
    # For simplicity, using server time. In production, use city timezone
    current_hour = datetime.now().hour
    
    if 5 <= current_hour < 11:  # 5 AM - 10:59 AM
        return "breakfast"
    elif 11 <= current_hour < 16:  # 11 AM - 3:59 PM
        return "lunch"
    else:  # 4 PM - 4:59 AM
        return "dinner"

def generate_order_number():
    return f"MM{datetime.now().strftime('%Y%m%d%H%M%S')}{os.urandom(2).hex()}"

# API Routes
@app.post("/api/register")
async def register(user_data: UserCreate):
    # Check if user exists
    existing = Database.execute_query(
        "SELECT id FROM users WHERE email = %s",
        (user_data.email,),
        fetch_one=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_pw = hash_password(user_data.password)
    
    # Create user
    user_id = Database.execute_query(
        """INSERT INTO users (email, password_hash, first_name, last_name, phone) 
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (user_data.email, hashed_pw, user_data.first_name, 
         user_data.last_name, user_data.phone),
        fetch_one=True
    )["id"]
    
    token = create_jwt_token({"user_id": user_id, "email": user_data.email})
    
    return {
        "message": "Registration successful",
        "token": token,
        "user_id": user_id
    }

@app.post("/api/login")
async def login(user_data: UserLogin):
    user = Database.execute_query(
        "SELECT * FROM users WHERE email = %s",
        (user_data.email,),
        fetch_one=True
    )
    
    if not user or not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_jwt_token({"user_id": user["id"], "email": user["email"]})
    
    return {
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "is_admin": user["is_admin"]
        }
    }

@app.get("/api/states")
async def get_states():
    states = Database.execute_query(
        "SELECT * FROM states ORDER BY name",
        fetch_all=True
    )
    return {"states": states}

@app.get("/api/zip/{zip_code}")
async def get_zip_info(zip_code: str):
    """Get city and state information for ZIP code"""
    result = Database.execute_query("""
        SELECT z.*, c.name as city_name, c.timezone, s.name as state_name, s.code as state_code
        FROM zip_codes z
        JOIN cities c ON z.city_id = c.id
        JOIN states s ON c.state_id = s.id
        WHERE z.zip_code = %s
    """, (zip_code,), fetch_one=True)
    
    if not result:
        raise HTTPException(status_code=404, detail="ZIP code not found")
    
    # Get current meal type for this city
    meal_type = get_current_meal_type(result["timezone"])
    
    return {
        "city": result["city_name"],
        "state": result["state_name"],
        "state_code": result["state_code"],
        "timezone": result["timezone"],
        "current_meal": meal_type,
        "city_id": result["city_id"]
    }

@app.get("/api/menu/{city_id}")
async def get_menu(city_id: int):
    """Get menu for city based on current meal type"""
    # Get city timezone
    city = Database.execute_query(
        "SELECT timezone FROM cities WHERE id = %s",
        (city_id,),
        fetch_one=True
    )
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    
    meal_type = get_current_meal_type(city["timezone"])
    
    # Get menu items for this city and meal type
    menu_items = Database.execute_query("""
        SELECT mi.*, mc.name as category_name
        FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.id
        WHERE mi.city_id = %s 
        AND mc.meal_type = %s
        AND mi.is_available = TRUE
        ORDER BY mi.is_special DESC, mi.name
    """, (city_id, meal_type), fetch_all=True)
    
    # Group by cuisine type
    menu_by_cuisine = {}
    for item in menu_items:
        cuisine = item["cuisine_type"]
        if cuisine not in menu_by_cuisine:
            menu_by_cuisine[cuisine] = []
        menu_by_cuisine[cuisine].append(item)
    
    # Get specials (exactly 20 items)
    specials = Database.execute_query("""
        SELECT * FROM menu_items 
        WHERE city_id = %s 
        AND is_special = TRUE 
        AND is_available = TRUE
        LIMIT 20
    """, (city_id,), fetch_all=True)
    
    return {
        "city_id": city_id,
        "meal_type": meal_type,
        "specials": specials,
        "menu_by_cuisine": menu_by_cuisine,
        "last_updated": datetime.now().isoformat()
    }

@app.post("/api/cart/add")
async def add_to_cart(
    item: CartItemAdd,
    user: dict = Depends(get_current_user),
    session_id: Optional[str] = Header(None, alias="X-Session-ID")
):
    """Add item to cart"""
    # Get or create cart
    cart = Database.execute_query(
        "SELECT id FROM carts WHERE user_id = %s OR session_id = %s LIMIT 1",
        (user["id"], session_id),
        fetch_one=True
    )
    
    if not cart:
        cart_id = Database.execute_query(
            "INSERT INTO carts (user_id, session_id) VALUES (%s, %s) RETURNING id",
            (user["id"], session_id),
            fetch_one=True
        )["id"]
    else:
        cart_id = cart["id"]
    
    # Check if item already in cart
    existing = Database.execute_query(
        "SELECT id, quantity FROM cart_items WHERE cart_id = %s AND menu_item_id = %s",
        (cart_id, item.menu_item_id),
        fetch_one=True
    )
    
    if existing:
        # Update quantity
        new_qty = existing["quantity"] + item.quantity
        Database.execute_query(
            "UPDATE cart_items SET quantity = %s WHERE id = %s",
            (new_qty, existing["id"])
        )
    else:
        # Add new item
        Database.execute_query(
            """INSERT INTO cart_items (cart_id, menu_item_id, quantity, special_instructions) 
               VALUES (%s, %s, %s, %s)""",
            (cart_id, item.menu_item_id, item.quantity, item.special_instructions)
        )
    
    return {"message": "Item added to cart", "cart_id": cart_id}

@app.get("/api/cart")
async def get_cart(
    user: dict = Depends(get_current_user),
    session_id: Optional[str] = Header(None, alias="X-Session-ID")
):
    """Get cart with items and total"""
    cart = Database.execute_query(
        "SELECT id FROM carts WHERE user_id = %s OR session_id = %s LIMIT 1",
        (user["id"], session_id),
        fetch_one=True
    )
    
    if not cart:
        return {"items": [], "total": 0, "tax": 0, "delivery_fee": 2.99, "final_total": 0}
    
    # Get cart items with details
    items = Database.execute_query("""
        SELECT ci.*, mi.name, mi.price, mi.image_url
        FROM cart_items ci
        JOIN menu_items mi ON ci.menu_item_id = mi.id
        WHERE ci.cart_id = %s
    """, (cart["id"],), fetch_all=True)
    
    # Calculate totals
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    tax = subtotal * Decimal('0.08')  # 8% tax
    delivery_fee = Decimal('2.99')
    final_total = subtotal + tax + delivery_fee
    
    return {
        "cart_id": cart["id"],
        "items": items,
        "subtotal": float(subtotal),
        "tax": float(tax),
        "delivery_fee": float(delivery_fee),
        "final_total": float(final_total)
    }

@app.post("/api/checkout")
async def checkout(
    checkout_data: CheckoutRequest,
    user: dict = Depends(get_current_user)
):
    """Process checkout with Stripe payment"""
    # Get cart
    cart = Database.execute_query(
        "SELECT id FROM carts WHERE user_id = %s",
        (user["id"],),
        fetch_one=True
    )
    
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Get cart items and calculate total
    cart_items = Database.execute_query("""
        SELECT ci.*, mi.name, mi.price
        FROM cart_items ci
        JOIN menu_items mi ON ci.menu_item_id = mi.id
        WHERE ci.cart_id = %s
    """, (cart["id"],), fetch_all=True)
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    subtotal = sum(Decimal(str(item["price"])) * item["quantity"] for item in cart_items)
    tax = subtotal * Decimal('0.08')
    delivery_fee = Decimal('2.99')
    final_total = subtotal + tax + delivery_fee
    
    # Process Stripe payment
    try:
        charge = stripe.Charge.create(
            amount=int(final_total * 100),  # Convert to cents
            currency="usd",
            source=checkout_data.stripe_token,
            description=f"MealMoment Order for {checkout_data.customer_name}"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Payment failed: {str(e)}")
    
    # Create order
    order_number = generate_order_number()
    order_id = Database.execute_query("""
        INSERT INTO orders (
            order_number, user_id, total_amount, tax_amount, delivery_fee,
            final_amount, delivery_address, delivery_city, delivery_state,
            delivery_zip, customer_name, customer_phone, special_instructions,
            payment_status, stripe_payment_id, status, estimated_delivery
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        order_number, user["id"], float(subtotal), float(tax), float(delivery_fee),
        float(final_total), checkout_data.delivery_address, checkout_data.delivery_city,
        checkout_data.delivery_state, checkout_data.delivery_zip,
        checkout_data.customer_name, checkout_data.customer_phone,
        checkout_data.special_instructions, "paid", charge.id, "confirmed",
        datetime.now() + timedelta(minutes=45)
    ), fetch_one=True)["id"]
    
    # Add order items
    for item in cart_items:
        Database.execute_query("""
            INSERT INTO order_items (order_id, menu_item_id, item_name, quantity, price, special_instructions)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            order_id, item["menu_item_id"], item["name"],
            item["quantity"], float(item["price"]), item["special_instructions"]
        ))
    
    # Clear cart
    Database.execute_query("DELETE FROM cart_items WHERE cart_id = %s", (cart["id"],))
    Database.execute_query("DELETE FROM carts WHERE id = %s", (cart["id"],))
    
    return {
        "message": "Order placed successfully",
        "order_number": order_number,
        "order_id": order_id,
        "payment_id": charge.id,
        "estimated_delivery": (datetime.now() + timedelta(minutes=45)).isoformat(),
        "total": float(final_total)
    }

# Admin Endpoints
@app.post("/api/admin/state")
async def create_state(
    state: StateCreate,
    admin: dict = Depends(get_current_admin)
):
    state_id = Database.execute_query(
        "INSERT INTO states (name, code) VALUES (%s, %s) RETURNING id",
        (state.name, state.code),
        fetch_one=True
    )["id"]
    
    return {"message": "State created", "state_id": state_id}

@app.post("/api/admin/city")
async def create_city(
    city: CityCreate,
    admin: dict = Depends(get_current_admin)
):
    city_id = Database.execute_query(
        "INSERT INTO cities (name, state_id, timezone) VALUES (%s, %s, %s) RETURNING id",
        (city.name, city.state_id, city.timezone),
        fetch_one=True
    )["id"]
    
    return {"message": "City created", "city_id": city_id}

@app.post("/api/admin/zip")
async def add_zip_code(
    zip_code: ZipCodeCreate,
    admin: dict = Depends(get_current_admin)
):
    zip_id = Database.execute_query(
        """INSERT INTO zip_codes (zip_code, city_id, latitude, longitude) 
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (zip_code.zip_code, zip_code.city_id, zip_code.latitude, zip_code.longitude),
        fetch_one=True
    )["id"]
    
    return {"message": "ZIP code added", "zip_id": zip_id}

@app.post("/api/admin/menu-item")
async def create_menu_item(
    item: MenuItemCreate,
    admin: dict = Depends(get_current_admin)
):
    item_id = Database.execute_query("""
        INSERT INTO menu_items (
            name, description, price, category_id, city_id, cuisine_type,
            image_url, is_special, is_available, preparation_time,
            calories, allergens
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        item.name, item.description, item.price, item.category_id,
        item.city_id, item.cuisine_type, item.image_url, item.is_special,
        item.is_available, item.preparation_time, item.calories, item.allergens
    ), fetch_one=True)["id"]
    
    return {"message": "Menu item created", "item_id": item_id}

@app.get("/api/admin/orders")
async def get_all_orders(
    admin: dict = Depends(get_current_admin),
    status: Optional[str] = None,
    limit: int = 100
):
    query = """
        SELECT o.*, u.email as customer_email, u.first_name, u.last_name
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.id
    """
    params = []
    
    if status:
        query += " WHERE o.status = %s"
        params.append(status)
    
    query += " ORDER BY o.created_at DESC LIMIT %s"
    params.append(limit)
    
    orders = Database.execute_query(query, tuple(params), fetch_all=True)
    
    # Get order items for each order
    for order in orders:
        items = Database.execute_query(
            "SELECT * FROM order_items WHERE order_id = %s",
            (order["id"],),
            fetch_all=True
        )
        order["items"] = items
    
    return {"orders": orders}

@app.put("/api/admin/order/{order_id}/status")
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    admin: dict = Depends(get_current_admin)
):
    updated = Database.execute_query(
        "UPDATE orders SET status = %s WHERE id = %s RETURNING id",
        (status_update.status, order_id),
        fetch_one=True
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {"message": "Order status updated", "order_id": order_id}

# Sample Data Initialization
def initialize_sample_data():
    """Initialize sample data for testing"""
    # Add California state
    Database.execute_query(
        "INSERT INTO states (name, code) VALUES ('California', 'CA') ON CONFLICT DO NOTHING"
    )
    
    # Get California ID
    ca = Database.execute_query(
        "SELECT id FROM states WHERE code = 'CA'",
        fetch_one=True
    )
    
    if ca:
        # Add Los Angeles city
        Database.execute_query(
            """INSERT INTO cities (name, state_id, timezone) 
               VALUES ('Los Angeles', %s, 'America/Los_Angeles') ON CONFLICT DO NOTHING""",
            (ca["id"],)
        )
        
        # Get LA city ID
        la = Database.execute_query(
            "SELECT id FROM cities WHERE name = 'Los Angeles'",
            fetch_one=True
        )
        
        if la:
            # Add ZIP codes for LA
            zip_codes = [
                ("90001", la["id"], 33.9731, -118.2479),
                ("90012", la["id"], 34.0614, -118.2389),
                ("90210", la["id"], 34.1030, -118.4108),
            ]
            
            for zip_code, city_id, lat, lon in zip_codes:
                Database.execute_query(
                    """INSERT INTO zip_codes (zip_code, city_id, latitude, longitude) 
                       VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    (zip_code, city_id, lat, lon)
                )
            
            # Add menu categories
            categories = [
                ("Breakfast Specials", "Morning favorites", la["id"], "breakfast"),
                ("Lunch Combos", "Quick lunch options", la["id"], "lunch"),
                ("Dinner Entrees", "Evening meals", la["id"], "dinner"),
                ("Italian", "Pasta & Pizza", la["id"], "lunch"),
                ("Chinese", "Asian cuisine", la["id"], "dinner"),
                ("Indian", "Spicy curries", la["id"], "dinner"),
                ("American", "Classic dishes", la["id"], "lunch"),
            ]
            
            for name, desc, city_id, meal_type in categories:
                Database.execute_query(
                    """INSERT INTO menu_categories (name, description, city_id, meal_type) 
                       VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    (name, desc, city_id, meal_type)
                )
            
            # Get category IDs
            categories_data = Database.execute_query(
                "SELECT id, name FROM menu_categories WHERE city_id = %s",
                (la["id"],),
                fetch_all=True
            )
            
            category_map = {cat["name"]: cat["id"] for cat in categories_data}
            
            # Add sample menu items (20 specials + regular items)
            menu_items = [
                # Breakfast Specials
                ("Avocado Toast", "Smashed avocado on artisan bread with cherry tomatoes", 12.99, category_map["Breakfast Specials"], la["id"], "American", "https://example.com/avocado.jpg", True),
                ("Pancake Stack", "Three fluffy pancakes with maple syrup and butter", 14.99, category_map["Breakfast Specials"], la["id"], "American", "https://example.com/pancakes.jpg", True),
                ("Eggs Benedict", "Poached eggs with ham on English muffin, hollandaise", 16.99, category_map["Breakfast Specials"], la["id"], "American", "https://example.com/eggs.jpg", False),
                
                # Lunch Combos
                ("Chicken Caesar Salad", "Grilled chicken, romaine, parmesan, caesar dressing", 15.99, category_map["Lunch Combos"], la["id"], "American", "https://example.com/caesar.jpg", True),
                ("Turkey Club Sandwich", "Triple decker with bacon, avocado, and fries", 17.99, category_map["Lunch Combos"], la["id"], "American", "https://example.com/turkey.jpg", True),
                ("Vegetable Wrap", "Grilled vegetables with hummus in spinach wrap", 13.99, category_map["Lunch Combos"], la["id"], "American", "https://example.com/wrap.jpg", False),
                
                # Italian
                ("Spaghetti Carbonara", "Pasta with eggs, cheese, pancetta, and black pepper", 18.99, category_map["Italian"], la["id"], "Italian", "https://example.com/carbonara.jpg", True),
                ("Margherita Pizza", "Classic pizza with tomato, mozzarella, and basil", 22.99, category_map["Italian"], la["id"], "Italian", "https://example.com/pizza.jpg", True),
                ("Lasagna Bolognese", "Layers of pasta with meat sauce and cheese", 24.99, category_map["Italian"], la["id"], "Italian", "https://example.com/lasagna.jpg", False),
                
                # Chinese
                ("Kung Pao Chicken", "Spicy stir-fried chicken with peanuts and vegetables", 19.99, category_map["Chinese"], la["id"], "Chinese", "https://example.com/kungpao.jpg", True),
                ("Beef with Broccoli", "Tender beef stir-fried with fresh broccoli", 21.99, category_map["Chinese"], la["id"], "Chinese", "https://example.com/beef.jpg", True),
                ("Vegetable Lo Mein", "Stir-fried noodles with mixed vegetables", 16.99, category_map["Chinese"], la["id"], "Chinese", "https://example.com/lo mein.jpg", False),
                
                # Indian
                ("Butter Chicken", "Tandoori chicken in creamy tomato sauce", 22.99, category_map["Indian"], la["id"], "Indian", "https://example.com/butter.jpg", True),
                ("Chicken Tikka Masala", "Grilled chicken in spiced tomato cream sauce", 23.99, category_map["Indian"], la["id"], "Indian", "https://example.com/tikka.jpg", True),
                ("Vegetable Biryani", "Fragrant rice with mixed vegetables and spices", 18.99, category_map["Indian"], la["id"], "Indian", "https://example.com/biryani.jpg", False),
                
                # American Dinner
                ("Grilled Salmon", "Atlantic salmon with lemon butter sauce and vegetables", 28.99, category_map["Dinner Entrees"], la["id"], "American", "https://example.com/salmon.jpg", True),
                ("Filet Mignon", "8oz beef tenderloin with mashed potatoes", 39.99, category_map["Dinner Entrees"], la["id"], "American", "https://example.com/steak.jpg", True),
                ("BBQ Ribs", "Pork ribs with house BBQ sauce and coleslaw", 32.99, category_map["Dinner Entrees"], la["id"], "American", "https://example.com/ribs.jpg", False),
            ]
            
            for name, desc, price, cat_id, city_id, cuisine, img, special in menu_items:
                Database.execute_query(
                    """INSERT INTO menu_items (name, description, price, category_id, city_id, cuisine_type, image_url, is_special, is_available) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE) ON CONFLICT DO NOTHING""",
                    (name, desc, price, cat_id, city_id, cuisine, img, special)
                )
            
            print("✅ Sample data initialized!")

@app.get("/")
async def root():
    return {
        "app": "MealMoment Food Ordering System",
        "version": "1.0.0",
        "endpoints": [
            "/api/register - POST - Register user",
            "/api/login - POST - Login user",
            "/api/states - GET - List states",
            "/api/zip/{zip} - GET - Get city info",
            "/api/menu/{city_id} - GET - Get menu",
            "/api/cart - GET - Get cart",
            "/api/cart/add - POST - Add to cart",
            "/api/checkout - POST - Checkout",
            "/api/admin/* - Admin endpoints"
        ]
    }

if __name__ == "__main__":
    # Initialize sample data
    initialize_sample_data()
    
    # Start server
    print("🚀 Starting MealMoment server on http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    uvicorn.run(
        "mealmoment:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
