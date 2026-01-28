#!/usr/bin/env python3
"""
MEALMOMENT COMPLETE FOOD ORDERING SYSTEM
Single File Implementation - Ready for GitHub
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal
from enum import Enum

# Third-party imports
try:
    from fastapi import FastAPI, HTTPException, Depends, status, Header, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from pydantic import BaseModel, Field
    import psycopg2
    from psycopg2.pool import SimpleConnectionPool
    import psycopg2.extras
    import bcrypt
    import jwt
    import stripe
    import uvicorn
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([
        "pip", "install", 
        "fastapi", "uvicorn[standard]", 
        "psycopg2-binary", "python-jose[cryptography]", 
        "passlib[bcrypt]", "python-multipart", 
        "stripe", "pydantic"
    ])
    print("Packages installed. Please run the script again.")
    exit(1)

# ============================================
# CONFIGURATION
# ============================================
DATABASE_URL = "postgresql://postgres:password@localhost/mealmoment"
STRIPE_SECRET_KEY = "sk_test_51QJY3zRtz1KJd1Bm4dummykeychangethis"
STRIPE_PUBLIC_KEY = "pk_test_51QJY3zRtz1KJd1Bmdummykeychangethis"
JWT_SECRET = "mealmoment-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

# ============================================
# DATABASE SETUP
# ============================================
class Database:
    _pool = None
    
    @classmethod
    def initialize(cls):
        """Initialize database connection pool"""
        if not cls._pool:
            cls._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL
            )
            cls._create_tables()
            cls._seed_initial_data()
    
    @classmethod
    def _create_tables(cls):
        """Create all database tables"""
        conn = cls._pool.getconn()
        try:
            with conn.cursor() as cur:
                # States
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS states (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        code VARCHAR(2) UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Cities
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cities (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        state_id INTEGER REFERENCES states(id),
                        timezone VARCHAR(50) DEFAULT 'America/New_York',
                        UNIQUE(name, state_id)
                    );
                """)
                
                # ZIP Codes
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS zip_codes (
                        id SERIAL PRIMARY KEY,
                        zip_code VARCHAR(10) UNIQUE NOT NULL,
                        city_id INTEGER REFERENCES cities(id),
                        latitude DECIMAL(10,8),
                        longitude DECIMAL(11,8)
                    );
                """)
                
                # Users
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
                    );
                """)
                
                # Menu Categories
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS menu_categories (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        city_id INTEGER REFERENCES cities(id),
                        meal_type VARCHAR(20) CHECK (meal_type IN ('breakfast', 'lunch', 'dinner')),
                        is_active BOOLEAN DEFAULT TRUE
                    );
                """)
                
                # Menu Items
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
                    );
                """)
                
                # Carts
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS carts (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        session_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Cart Items
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cart_items (
                        id SERIAL PRIMARY KEY,
                        cart_id INTEGER REFERENCES carts(id) ON DELETE CASCADE,
                        menu_item_id INTEGER REFERENCES menu_items(id),
                        quantity INTEGER NOT NULL DEFAULT 1,
                        special_instructions TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Orders
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
                    );
                """)
                
                # Order Items
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS order_items (
                        id SERIAL PRIMARY KEY,
                        order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                        menu_item_id INTEGER REFERENCES menu_items(id),
                        item_name VARCHAR(200) NOT NULL,
                        quantity INTEGER NOT NULL,
                        price DECIMAL(10,2) NOT NULL,
                        special_instructions TEXT
                    );
                """)
                
                conn.commit()
        finally:
            cls._pool.putconn(conn)
    
    @classmethod
    def _seed_initial_data(cls):
        """Seed initial data for testing"""
        conn = cls._pool.getconn()
        try:
            with conn.cursor() as cur:
                # Check if data already exists
                cur.execute("SELECT COUNT(*) FROM states")
                if cur.fetchone()[0] > 0:
                    return
                
                print("Seeding initial data...")
                
                # Add states
                states = [
                    ("California", "CA"),
                    ("New York", "NY"),
                    ("Texas", "TX"),
                    ("Florida", "FL"),
                    ("Illinois", "IL"),
                ]
                for name, code in states:
                    cur.execute(
                        "INSERT INTO states (name, code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (name, code)
                    )
                
                # Add cities for California
                cur.execute("SELECT id FROM states WHERE code = 'CA'")
                ca_id = cur.fetchone()[0]
                
                cities_ca = [
                    ("Los Angeles", ca_id, "America/Los_Angeles"),
                    ("San Francisco", ca_id, "America/Los_Angeles"),
                    ("San Diego", ca_id, "America/Los_Angeles"),
                ]
                for name, state_id, tz in cities_ca:
                    cur.execute(
                        "INSERT INTO cities (name, state_id, timezone) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                        (name, state_id, tz)
                    )
                
                # Get LA city ID
                cur.execute("SELECT id FROM cities WHERE name = 'Los Angeles'")
                la_id = cur.fetchone()[0]
                
                # Add ZIP codes for LA
                la_zips = [
                    ("90001", la_id, 33.9731, -118.2479),
                    ("90012", la_id, 34.0614, -118.2389),
                    ("90024", la_id, 34.0633, -118.4459),
                    ("90210", la_id, 34.1030, -118.4108),
                ]
                for zip_code, city_id, lat, lon in la_zips:
                    cur.execute(
                        "INSERT INTO zip_codes (zip_code, city_id, latitude, longitude) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (zip_code, city_id, lat, lon)
                    )
                
                # Create admin user
                password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
                cur.execute(
                    """INSERT INTO users (email, password_hash, first_name, last_name, is_admin) 
                       VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    ("admin@mealmoment.com", password_hash, "Admin", "User", True)
                )
                
                # Add menu categories for LA
                categories = [
                    ("Breakfast Specials", "Start your day right", la_id, "breakfast"),
                    ("Lunch Combos", "Quick and delicious", la_id, "lunch"),
                    ("Dinner Entrees", "Evening delights", la_id, "dinner"),
                    ("Italian Classics", "Authentic Italian cuisine", la_id, "dinner"),
                    ("Chinese Favorites", "Traditional Chinese dishes", la_id, "lunch"),
                    ("Indian Delights", "Spicy and flavorful", la_id, "dinner"),
                    ("American Classics", "All-American favorites", la_id, "lunch"),
                ]
                for name, desc, city_id, meal_type in categories:
                    cur.execute(
                        """INSERT INTO menu_categories (name, description, city_id, meal_type) 
                           VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                        (name, desc, city_id, meal_type)
                    )
                
                # Get category IDs
                cur.execute("SELECT id, name FROM menu_categories WHERE city_id = %s", (la_id,))
                categories_data = cur.fetchall()
                category_map = {name: cid for cid, name in categories_data}
                
                # Add menu items (20+ items with 20 specials)
                menu_items = [
                    # Breakfast Specials (7 items, 5 specials)
                    ("Avocado Toast", "Smashed avocado on artisan bread with cherry tomatoes", 12.99, category_map["Breakfast Specials"], la_id, "American", "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400", True, 450),
                    ("Pancake Stack", "Three fluffy pancakes with maple syrup and butter", 14.99, category_map["Breakfast Specials"], la_id, "American", "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=400", True, 650),
                    ("Eggs Benedict", "Poached eggs with ham on English muffin, hollandaise", 16.99, category_map["Breakfast Specials"], la_id, "American", "https://images.unsplash.com/photo-1556909212-d5b604d0c90d?w-400", True, 520),
                    ("Breakfast Burrito", "Scrambled eggs, sausage, cheese in flour tortilla", 13.99, category_map["Breakfast Specials"], la_id, "Mexican", "https://images.unsplash.com/photo-1582515073490-39981397c445?w=400", True, 780),
                    ("Greek Yogurt Bowl", "Greek yogurt with honey, granola, and fresh berries", 10.99, category_map["Breakfast Specials"], la_id, "Greek", "https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=400", True, 320),
                    ("Belgian Waffles", "Crispy waffles with whipped cream and strawberries", 15.99, category_map["Breakfast Specials"], la_id, "American", "https://images.unsplash.com/photo-1562376552-0d160a2f238d?w=400", False, 580),
                    ("Breakfast Sandwich", "Egg, cheese, and bacon on croissant", 11.99, category_map["Breakfast Specials"], la_id, "American", "https://images.unsplash.com/photo-1484723091739-30a097e8f929?w=400", False, 420),
                    
                    # Lunch Combos (8 items, 5 specials)
                    ("Chicken Caesar Salad", "Grilled chicken, romaine, parmesan, caesar dressing", 15.99, category_map["Lunch Combos"], la_id, "American", "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400", True, 380),
                    ("Turkey Club Sandwich", "Triple decker with bacon, avocado, and fries", 17.99, category_map["Lunch Combos"], la_id, "American", "https://images.unsplash.com/photo-1556909212-d5b604d0c90d?w=400", True, 720),
                    ("Vegetable Wrap", "Grilled vegetables with hummus in spinach wrap", 13.99, category_map["Lunch Combos"], la_id, "American", "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400", True, 290),
                    ("BBQ Chicken Pizza", "Wood-fired pizza with BBQ sauce and chicken", 21.99, category_map["Lunch Combos"], la_id, "Italian", "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400", True, 850),
                    ("Beef Burger", "1/2 lb beef patty with cheese and all fixings", 18.99, category_map["Lunch Combos"], la_id, "American", "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400", True, 920),
                    ("Cobb Salad", "Mixed greens with chicken, avocado, egg, bacon", 16.99, category_map["Lunch Combos"], la_id, "American", "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=400", False, 410),
                    ("Fish Tacos", "Grilled fish with cabbage slaw and lime crema", 16.99, category_map["Lunch Combos"], la_id, "Mexican", "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=400", False, 480),
                    ("Chicken Quesadilla", "Grilled chicken and cheese in flour tortilla", 14.99, category_map["Lunch Combos"], la_id, "Mexican", "https://images.unsplash.com/photo-1599490659213-e2b9527bd087?w=400", False, 620),
                    
                    # Italian Classics (7 items, 5 specials)
                    ("Spaghetti Carbonara", "Pasta with eggs, cheese, pancetta, and black pepper", 18.99, category_map["Italian Classics"], la_id, "Italian", "https://images.unsplash.com/photo-1598866594230-a7c12756260f?w=400", True, 650),
                    ("Margherita Pizza", "Classic pizza with tomato, mozzarella, and basil", 22.99, category_map["Italian Classics"], la_id, "Italian", "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400", True, 820),
                    ("Lasagna Bolognese", "Layers of pasta with meat sauce and cheese", 24.99, category_map["Italian Classics"], la_id, "Italian", "https://images.unsplash.com/photo-1574894709920-11b28e7367e3?w=400", True, 780),
                    ("Chicken Parmesan", "Breaded chicken with marinara and melted cheese", 26.99, category_map["Italian Classics"], la_id, "Italian", "https://images.unsplash.com/photo-1603360946369-dc9bb6258143?w=400", True, 920),
                    ("Fettuccine Alfredo", "Creamy pasta with parmesan cheese", 19.99, category_map["Italian Classics"], la_id, "Italian", "https://images.unsplash.com/photo-1471193945509-9ad0617afabf?w=400", True, 720),
                    ("Eggplant Parmesan", "Breaded eggplant with marinara and cheese", 22.99, category_map["Italian Classics"], la_id, "Italian", "https://images.unsplash.com/photo-1593253787226-567eda4ad32d?w=400", False, 580),
                    ("Minestrone Soup", "Traditional Italian vegetable soup", 9.99, category_map["Italian Classics"], la_id, "Italian", "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400", False, 210),
                    
                    # Chinese Favorites (8 items, 5 specials)
                    ("Kung Pao Chicken", "Spicy stir-fried chicken with peanuts", 19.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=400", True, 680),
                    ("Beef with Broccoli", "Tender beef stir-fried with fresh broccoli", 21.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=400", True, 520),
                    ("Vegetable Lo Mein", "Stir-fried noodles with mixed vegetables", 16.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1555126634-323283e090fa?w=400", True, 490),
                    ("Sweet and Sour Pork", "Crispy pork in tangy sweet and sour sauce", 20.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=400", True, 710),
                    ("General Tso's Chicken", "Crispy chicken in spicy sauce", 22.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1585032221-4a2d6c7e7c1c?w=400", True, 850),
                    ("Fried Rice", "Vegetable fried rice with eggs", 14.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1603133872878-684f208fb84b?w=400", False, 420),
                    ("Wonton Soup", "Chicken broth with pork wontons", 8.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=400", False, 180),
                    ("Mongolian Beef", "Beef strips in savory sauce with scallions", 23.99, category_map["Chinese Favorites"], la_id, "Chinese", "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=400", False, 690),
                    
                    # More items to reach 20+ specials...
                    ("Grilled Salmon", "Atlantic salmon with lemon butter sauce", 28.99, category_map["Dinner Entrees"], la_id, "American", "https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=400", True, 480),
                    ("Filet Mignon", "8oz beef tenderloin with mashed potatoes", 39.99, category_map["Dinner Entrees"], la_id, "American", "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400", True, 920),
                    ("BBQ Ribs", "Pork ribs with house BBQ sauce", 32.99, category_map["Dinner Entrees"], la_id, "American", "https://images.unsplash.com/photo-1544025162-d76694265947?w=400", True, 1120),
                ]
                
                for name, desc, price, cat_id, city_id, cuisine, img, special, calories in menu_items:
                    cur.execute(
                        """INSERT INTO menu_items (name, description, price, category_id, city_id, cuisine_type, image_url, is_special, calories, is_available) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE) ON CONFLICT DO NOTHING""",
                        (name, desc, price, cat_id, city_id, cuisine, img, special, calories)
                    )
                
                conn.commit()
                print("✅ Initial data seeded successfully!")
        finally:
            cls._pool.putconn(conn)
    
    @classmethod
    def get_connection(cls):
        """Get a database connection from the pool"""
        return cls._pool.getconn()
    
    @classmethod
    def return_connection(cls, conn):
        """Return connection to the pool"""
        cls._pool.putconn(conn)
    
    @classmethod
    def execute_query(cls, query, params=None, fetch_one=False, fetch_all=False):
        """Execute a query and return results"""
        conn = cls.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, params or ())
                if fetch_one:
                    result = cur.fetchone()
                    return dict(result) if result else None
                elif fetch_all:
                    return [dict(row) for row in cur.fetchall()]
                conn.commit()
                return cur.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cls.return_connection(conn)

# Initialize database
Database.initialize()

# ============================================
# PYDANTIC MODELS
# ============================================
class UserCreate(BaseModel):
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

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

# ============================================
# AUTHENTICATION
# ============================================
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

def create_jwt_token(data: dict) -> str:
    """Create a JWT token"""
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
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
    """Get current admin user"""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ============================================
# HELPER FUNCTIONS
# ============================================
def get_current_meal_type():
    """Determine current meal type based on server time"""
    current_hour = datetime.now().hour
    if 5 <= current_hour < 11:    # 5 AM - 10:59 AM
        return "breakfast"
    elif 11 <= current_hour < 16: # 11 AM - 3:59 PM
        return "lunch"
    else:                         # 4 PM - 4:59 AM
        return "dinner"

def generate_order_number():
    """Generate unique order number"""
    import random
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
    return f"MM-{timestamp}-{random_str}"

# ============================================
# FASTAPI APPLICATION
# ============================================
app = FastAPI(
    title="MealMoment API",
    description="Complete food ordering system with real-time menus",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# API ENDPOINTS
# ============================================
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "app": "MealMoment Food Ordering System",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "auth": ["POST /api/register", "POST /api/login"],
            "public": ["GET /api/states", "GET /api/zip/{zip_code}", "GET /api/menu/{city_id}"],
            "cart": ["GET /api/cart", "POST /api/cart/add", "DELETE /api/cart/item/{item_id}"],
            "orders": ["POST /api/checkout", "GET /api/orders", "GET /api/order/{order_id}"],
            "admin": ["POST /api/admin/menu-item", "GET /api/admin/orders", "PUT /api/admin/order/{order_id}/status"]
        }
    }

@app.post("/api/register")
async def register(user_data: UserCreate):
    """Register a new user"""
    # Check if user exists
    existing = Database.execute_query(
        "SELECT id FROM users WHERE email = %s",
        (user_data.email,),
        fetch_one=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password and create user
    hashed_pw = hash_password(user_data.password)
    user_id = Database.execute_query(
        """INSERT INTO users (email, password_hash, first_name, last_name, phone) 
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (user_data.email, hashed_pw, user_data.first_name, 
         user_data.last_name, user_data.phone),
        fetch_one=True
    )["id"]
    
    # Create JWT token
    token = create_jwt_token({"user_id": user_id, "email": user_data.email})
    
    return {
        "message": "Registration successful",
        "token": token,
        "user": {
            "id": user_id,
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name
        }
    }

@app.post("/api/login")
async def login(user_data: UserLogin):
    """Login user and return JWT token"""
    user = Database.execute_query(
        "SELECT * FROM users WHERE email = %s",
        (user_data.email,),
        fetch_one=True
    )
    
    if not user or not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
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
    """Get all states"""
    states = Database.execute_query(
        "SELECT * FROM states ORDER BY name",
        fetch_all=True
    )
    return {"states": states}

@app.get("/api/zip/{zip_code}")
async def get_zip_info(zip_code: str):
    """Get city and state information for a ZIP code"""
    result = Database.execute_query("""
        SELECT z.*, c.name as city_name, c.timezone, c.id as city_id,
               s.name as state_name, s.code as state_code, s.id as state_id
        FROM zip_codes z
        JOIN cities c ON z.city_id = c.id
        JOIN states s ON c.state_id = s.id
        WHERE z.zip_code = %s
    """, (zip_code,), fetch_one=True)
    
    if not result:
        raise HTTPException(status_code=404, detail="ZIP code not found")
    
    return {
        "zip_code": zip_code,
        "city": result["city_name"],
        "city_id": result["city_id"],
        "state": result["state_name"],
        "state_code": result["state_code"],
        "timezone": result["timezone"]
    }

@app.get("/api/menu/{city_id}")
async def get_menu(city_id: int):
    """Get menu for a city based on current time"""
    # Check if city exists
    city = Database.execute_query(
        "SELECT * FROM cities WHERE id = %s",
        (city_id,),
        fetch_one=True
    )
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    
    # Get current meal type
    meal_type = get_current_meal_type()
    
    # Get specials (exactly 20 items)
    specials = Database.execute_query("""
        SELECT mi.*, mc.name as category_name
        FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.id
        WHERE mi.city_id = %s 
        AND mi.is_special = TRUE
        AND mi.is_available = TRUE
        ORDER BY RANDOM()
        LIMIT 20
    """, (city_id,), fetch_all=True)
    
    # Get all menu items for current meal type
    menu_items = Database.execute_query("""
        SELECT mi.*, mc.name as category_name
        FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.id
        WHERE mi.city_id = %s 
        AND mc.meal_type = %s
        AND mi.is_available = TRUE
        ORDER BY mi.cuisine_type, mi.name
    """, (city_id, meal_type), fetch_all=True)
    
    # Group by cuisine type
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
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/cart/add")
async def add_to_cart(
    item: CartItemAdd,
    user: dict = Depends(get_current_user),
    x_session_id: Optional[str] = Header(None)
):
    """Add item to cart"""
    # Get or create cart
    cart = Database.execute_query(
        "SELECT id FROM carts WHERE user_id = %s OR session_id = %s LIMIT 1",
        (user["id"], x_session_id),
        fetch_one=True
    )
    
    if not cart:
        # Create new cart
        cart_id = Database.execute_query(
            "INSERT INTO carts (user_id, session_id) VALUES (%s, %s) RETURNING id",
            (user["id"], x_session_id),
            fetch_one=True
        )["id"]
    else:
        cart_id = cart["id"]
    
    # Check if item already in cart
    existing_item = Database.execute_query(
        "SELECT id, quantity FROM cart_items WHERE cart_id = %s AND menu_item_id = %s",
        (cart_id, item.menu_item_id),
        fetch_one=True
    )
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item["quantity"] + item.quantity
        Database.execute_query(
            "UPDATE cart_items SET quantity = %s WHERE id = %s",
            (new_quantity, existing_item["id"])
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
    x_session_id: Optional[str] = Header(None)
):
    """Get current cart with items and totals"""
    cart = Database.execute_query(
        "SELECT id FROM carts WHERE user_id = %s OR session_id = %s LIMIT 1",
        (user["id"], x_session_id),
        fetch_one=True
    )
    
    if not cart:
        return {
            "items": [],
            "subtotal": 0,
            "tax": 0,
            "delivery_fee": 2.99,
            "total": 0
        }
    
    # Get cart items
    items = Database.execute_query("""
        SELECT ci.*, mi.name, mi.price, mi.image_url, mi.description
        FROM cart_items ci
        JOIN menu_items mi ON ci.menu_item_id = mi.id
        WHERE ci.cart_id = %s
        ORDER BY ci.created_at DESC
    """, (cart["id"],), fetch_all=True)
    
    # Calculate totals
    subtotal = sum(float(item["price"]) * item["quantity"] for item in items)
    tax = subtotal * 0.0825  # 8.25% tax
    delivery_fee = 2.99
    total = subtotal + tax + delivery_fee
    
    return {
        "cart_id": cart["id"],
        "items": items,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "delivery_fee": delivery_fee,
        "total": round(total, 2)
    }

@app.delete("/api/cart/item/{item_id}")
async def remove_cart_item(
    item_id: int,
    user: dict = Depends(get_current_user),
    x_session_id: Optional[str] = Header(None)
):
    """Remove item from cart"""
    cart = Database.execute_query(
        "SELECT id FROM carts WHERE user_id = %s OR session_id = %s LIMIT 1",
        (user["id"], x_session_id),
        fetch_one=True
    )
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    deleted = Database.execute_query(
        "DELETE FROM cart_items WHERE id = %s AND cart_id = %s RETURNING id",
        (item_id, cart["id"]),
        fetch_one=True
    )
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    return {"message": "Item removed from cart"}

@app.post("/api/checkout")
async def checkout(
    checkout_data: CheckoutRequest,
    user: dict = Depends(get_current_user)
):
    """Process checkout and payment"""
    # Get cart
    cart = Database.execute_query(
        "SELECT id FROM carts WHERE user_id = %s",
        (user["id"],),
        fetch_one=True
    )
    
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Get cart items
    cart_items = Database.execute_query("""
        SELECT ci.*, mi.name, mi.price
        FROM cart_items ci
        JOIN menu_items mi ON ci.menu_item_id = mi.id
        WHERE ci.cart_id = %s
    """, (cart["id"],), fetch_all=True)
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Calculate totals
    subtotal = sum(float(item["price"]) * item["quantity"] for item in cart_items)
    tax = subtotal * 0.0825
    delivery_fee = 2.99
    total = subtotal + tax + delivery_fee
    
    # Process Stripe payment
    try:
        charge = stripe.Charge.create(
            amount=int(total * 100),  # Convert to cents
            currency="usd",
            source=checkout_data.stripe_token,
            description=f"MealMoment Order - {checkout_data.customer_name}",
            metadata={
                "customer_name": checkout_data.customer_name,
                "customer_phone": checkout_data.customer_phone
            }
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
        order_number, user["id"], subtotal, tax, delivery_fee,
        total, checkout_data.delivery_address, checkout_data.delivery_city,
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
    
    # Get order details
    order = Database.execute_query(
        "SELECT * FROM orders WHERE id = %s",
        (order_id,),
        fetch_one=True
    )
    
    return {
        "message": "Order placed successfully",
        "order": {
            "id": order_id,
            "order_number": order_number,
            "total": total,
            "status": "confirmed",
            "estimated_delivery": order["estimated_delivery"].isoformat() if order["estimated_delivery"] else None,
            "payment_id": charge.id
        }
    }

@app.get("/api/orders")
async def get_user_orders(user: dict = Depends(get_current_user)):
    """Get orders for current user"""
    orders = Database.execute_query("""
        SELECT * FROM orders 
        WHERE user_id = %s 
        ORDER BY created_at DESC
        LIMIT 50
    """, (user["id"],), fetch_all=True)
    
    # Get items for each order
    for order in orders:
        items = Database.execute_query(
            "SELECT * FROM order_items WHERE order_id = %s",
            (order["id"],),
            fetch_all=True
        )
        order["items"] = items
    
    return {"orders": orders}

@app.get("/api/order/{order_id}")
async def get_order(order_id: int, user: dict = Depends(get_current_user)):
    """Get specific order"""
    order = Database.execute_query("""
        SELECT * FROM orders WHERE id = %s AND user_id = %s
    """, (order_id, user["id"]), fetch_one=True)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    items = Database.execute_query(
        "SELECT * FROM order_items WHERE order_id = %s",
        (order_id,),
        fetch_all=True
    )
    
    order["items"] = items
    return {"order": order}

# ============================================
# ADMIN ENDPOINTS
# ============================================
@app.post("/api/admin/menu-item")
async def create_menu_item(
    name: str = Query(...),
    description: str = Query(...),
    price: float = Query(...),
    category_id: int = Query(...),
    city_id: int = Query(...),
    cuisine_type: str = Query(...),
    is_special: bool = Query(False),
    image_url: Optional[str] = Query(None),
    calories: Optional[int] = Query(None),
    admin: dict = Depends(get_current_admin)
):
    """Create a new menu item (admin only)"""
    item_id = Database.execute_query("""
        INSERT INTO menu_items (
            name, description, price, category_id, city_id, 
            cuisine_type, is_special, image_url, calories, is_available
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        RETURNING id
    """, (
        name, description, price, category_id, city_id,
        cuisine_type, is_special, image_url, calories
    ), fetch_one=True)["id"]
    
    return {"message": "Menu item created", "item_id": item_id}

@app.get("/api/admin/orders")
async def get_all_orders(
    status: Optional[str] = None,
    limit: int = 100,
    admin: dict = Depends(get_current_admin)
):
    """Get all orders (admin only)"""
    query = "SELECT * FROM orders"
    params = []
    
    if status:
        query += " WHERE status = %s"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    
    orders = Database.execute_query(query, tuple(params), fetch_all=True)
    
    # Get items for each order
    for order in orders:
        items = Database.execute_query(
            "SELECT * FROM order_items WHERE order_id = %s",
            (order["id"],),
            fetch_all=True
        )
        order["items"] = items
        
        # Get user info
        user = Database.execute_query(
            "SELECT email, first_name, last_name FROM users WHERE id = %s",
            (order["user_id"],),
            fetch_one=True
        )
        order["user"] = user
    
    return {"orders": orders}

@app.put("/api/admin/order/{order_id}/status")
async def update_order_status(
    order_id: int,
    status: str = Query(..., regex="^(pending|confirmed|preparing|out_for_delivery|delivered|cancelled)$"),
    admin: dict = Depends(get_current_admin)
):
    """Update order status (admin only)"""
    updated = Database.execute_query(
        "UPDATE orders SET status = %s WHERE id = %s RETURNING id",
        (status, order_id),
        fetch_one=True
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {"message": "Order status updated", "order_id": order_id, "status": status}

# ============================================
# MAIN ENTRY POINT
# ============================================
if __name__ == "__main__":
    print("=" * 50)
    print("MEALMOMENT FOOD ORDERING SYSTEM")
    print("=" * 50)
    print(f"Database URL: {DATABASE_URL}")
    print(f"API Documentation: http://localhost:8000/docs")
    print(f"Admin Login: admin@mealmoment.com / admin123")
    print("=" * 50)
    
    uvicorn.run(
        "mealmoment_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
