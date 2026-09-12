import aiosqlite
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import DB_PATH

logger = logging.getLogger("AutoBuyDB")

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Khởi tạo bảng cơ sở dữ liệu SQLite nếu chưa tồn tại"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tự động thêm cột username nếu chưa có trong DB cũ
            try:
                await db.execute("ALTER TABLE users ADD COLUMN username TEXT")
            except Exception:
                pass

            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    item_data TEXT NOT NULL,
                    is_sold INTEGER DEFAULT 0,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sold_at TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    category_name TEXT NOT NULL,
                    stock_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    item_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Bảng Nạp Tiền Ngân Hàng Auto VietQR
            await db.execute("""
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    memo TEXT UNIQUE NOT NULL,
                    amount_vnd REAL NOT NULL,
                    amount_usd REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            # Bảng Cấu Hình Tùy Chỉnh Chữ Cửa Hàng & System Settings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            await db.commit()
            logger.info("Giếng Ma Thuật (Database) SQLite đã khởi tạo bảng thành công!")

    # --- CẤU HÌNH TÙY CHỈNH CHỮ CỬA HÀNG (SETTINGS) ---
    async def get_setting(self, key: str, default: str = "") -> str:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default

    async def set_setting(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?", (key, value, value))
            await db.commit()

    async def get_store_settings(self) -> Dict[str, str]:
        title = await self.get_setting("store_title", "⚡ HỆ THỐNG CỬA HÀNG TỰ ĐỘNG - AUTOBUY STORE 24/7")
        desc = await self.get_setting(
            "store_description",
            "Chào mừng ngài đến với Cửa Hàng Tự Động!\nHệ thống tự động giao key/tài khoản qua DM và quét VietQR nạp tiền 24/7.\n\n👉 **Bấm `🏪 Xem Cửa Hàng & Mua`** để chọn sản phẩm và mua ngay.\n👉 **Bấm `💳 Auto Nạp Tiền VietQR`** để tạo mã VietQR nạp tiền tự động.\n👉 **Bấm `💰 Ví Của Tôi`** để kiểm tra số dư tài khoản."
        )
        footer = await self.get_setting("store_footer", "AutoBuy Bot Engine & Web Management System © 2026")
        banner = await self.get_setting("store_banner_url", "")
        color = await self.get_setting("store_color", "0x3498db")
        return {
            "title": title,
            "description": desc,
            "footer": footer,
            "banner_url": banner,
            "color": color
        }

    # --- QUẢN LÝ NGƯỜI DÙNG & SỐ DƯ ---
    async def save_or_update_user(self, user_id: int, username: Optional[str] = None) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    if username:
                        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
                        await db.commit()
                    return float(row[0])
                else:
                    await db.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0.0)", (user_id, username))
                    await db.commit()
                    return 0.0

    async def get_user_balance(self, user_id: int) -> float:
        return await self.save_or_update_user(user_id)

    async def find_user_by_username_or_id(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Tìm người dùng theo Username hoặc Discord ID trong Database"""
        clean_input = str(user_input).strip().lstrip("@")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # 1. Nếu nhập chuỗi số -> tìm theo ID
            if clean_input.isdigit():
                user_id = int(clean_input)
                async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    # Nếu chưa có trong DB, trả về dict giả định để khởi tạo
                    return {"user_id": user_id, "username": f"User_{user_id}", "balance": 0.0}

            # 2. Nếu nhập Username -> tìm theo tên trong DB (không phân biệt hoa thường)
            async with db.execute(
                "SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(username) LIKE LOWER(?)",
                (clean_input, f"{clean_input}#%")
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            return None

    async def update_balance(self, user_id: int, amount: float) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            current = await self.get_user_balance(user_id)
            new_balance = max(0.0, current + amount)
            await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
            await db.commit()
            return new_balance

    async def get_all_users(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # --- QUẢN LÝ NẠP TIỀN BANK (VIETQR DEPOSITS) ---
    async def create_deposit_request(self, user_id: int, amount_vnd: float, amount_usd: float, memo: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await self.get_user_balance(user_id)
            try:
                await db.execute(
                    "INSERT INTO deposits (user_id, memo, amount_vnd, amount_usd, status) VALUES (?, ?, ?, ?, 'pending')",
                    (user_id, memo, amount_vnd, amount_usd)
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def get_deposit_by_memo(self, memo: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM deposits WHERE memo = ?", (memo.strip().upper(),)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def complete_deposit(self, memo: str) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            memo_clean = memo.strip().upper()
            async with db.execute("SELECT * FROM deposits WHERE memo = ?", (memo_clean,)) as cursor:
                dep = await cursor.fetchone()
                if not dep:
                    return {"success": False, "message": "Không tìm thấy mã đơn nạp!"}
                dep_dict = dict(dep)

            if dep_dict["status"] == "completed":
                return {"success": True, "already_completed": True, "user_id": dep_dict["user_id"], "amount_usd": dep_dict["amount_usd"]}

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("UPDATE deposits SET status = 'completed', completed_at = ? WHERE id = ?", (now_str, dep_dict["id"]))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (dep_dict["amount_vnd"], dep_dict["user_id"]))
            await db.commit()

            new_bal = await self.get_user_balance(dep_dict["user_id"])

            return {
                "success": True, 
                "already_completed": False,
                "user_id": dep_dict["user_id"], 
                "amount_usd": dep_dict["amount_usd"],
                "amount_vnd": dep_dict["amount_vnd"],
                "new_balance": new_bal
            }

    async def get_pending_deposits(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT d.*, u.username FROM deposits d LEFT JOIN users u ON d.user_id = u.user_id WHERE d.status = 'pending' ORDER BY d.created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def complete_deposit_by_id(self, deposit_id: int) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,)) as cursor:
                dep = await cursor.fetchone()
                if not dep:
                    return {"success": False, "message": "Không tìm thấy đơn nạp!"}
                dep_dict = dict(dep)

            if dep_dict["status"] == "completed":
                new_bal = await self.get_user_balance(dep_dict["user_id"])
                return {"success": True, "already_completed": True, "user_id": dep_dict["user_id"], "amount_vnd": dep_dict["amount_vnd"], "new_balance": new_bal}

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("UPDATE deposits SET status = 'completed', completed_at = ? WHERE id = ?", (now_str, deposit_id))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (dep_dict["amount_vnd"], dep_dict["user_id"]))
            await db.commit()

            new_bal = await self.get_user_balance(dep_dict["user_id"])

            return {
                "success": True, 
                "user_id": dep_dict["user_id"], 
                "amount_vnd": dep_dict["amount_vnd"],
                "new_balance": new_bal
            }

    async def direct_deposit(self, user_id: int, amount_vnd: float, memo: str) -> Dict[str, Any]:
        """Tự động cộng tiền trực tiếp cho User khi nhận được Webhook ngân hàng"""
        async with aiosqlite.connect(self.db_path) as db:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            amount_usd = amount_vnd / EXCHANGE_RATE if EXCHANGE_RATE > 0 else amount_vnd
            await self.get_user_balance(user_id)
            await db.execute(
                "INSERT INTO deposits (user_id, memo, amount_vnd, amount_usd, status, completed_at) VALUES (?, ?, ?, ?, 'completed', ?)",
                (user_id, memo, amount_vnd, amount_usd, now_str)
            )
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount_vnd, user_id))
            await db.commit()

            new_bal = await self.get_user_balance(user_id)
            return {
                "success": True,
                "already_completed": False,
                "user_id": user_id,
                "amount_vnd": amount_vnd,
                "amount_usd": amount_usd,
                "new_balance": new_bal
            }

    # --- QUẢN LÝ DANH MỤC SẢN PHẨM ---
    async def add_category(self, name: str, description: str, price: float) -> Optional[int]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "INSERT INTO categories (name, description, price) VALUES (?, ?, ?)",
                    (name, description, price)
                )
                await db.commit()
                return cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None

    async def get_categories(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT c.*, 
                       (SELECT COUNT(*) FROM stock s WHERE s.category_id = c.id AND s.is_sold = 0) as stock_count
                FROM categories c
                ORDER BY c.id ASC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_category_by_id(self, cat_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def delete_category(self, cat_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
            await db.commit()
            return True

    # --- QUẢN LÝ KHO HÀNG (STOCK) ---
    async def add_stock_items(self, category_id: int, items: List[str]) -> int:
        count = 0
        async with aiosqlite.connect(self.db_path) as db:
            for item in items:
                item_clean = item.strip()
                if item_clean:
                    await db.execute(
                        "INSERT INTO stock (category_id, item_data) VALUES (?, ?)",
                        (category_id, item_clean)
                    )
                    count += 1
            await db.commit()
        return count

    async def get_available_stock(self, category_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM stock WHERE category_id = ? AND is_sold = 0",
                (category_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    # --- GIAO DỊCH & MUA HÀNG TỰ ĐỘNG ---
    async def process_purchase(self, user_id: int, category_id: int) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)) as cursor:
                cat = await cursor.fetchone()
                if not cat:
                    return {"success": False, "message": "Danh mục sản phẩm không tồn tại."}
                cat_dict = dict(cat)

            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_row = await cursor.fetchone()
                current_balance = user_row[0] if user_row else 0.0

            if current_balance < cat_dict["price"]:
                return {
                    "success": False, 
                    "message": f"Số dư không đủ! Ngài có ${current_balance:.2f}, sản phẩm giá ${cat_dict['price']:.2f}."
                }

            async with db.execute(
                "SELECT * FROM stock WHERE category_id = ? AND is_sold = 0 LIMIT 1",
                (category_id,)
            ) as cursor:
                stock_item = await cursor.fetchone()
                if not stock_item:
                    return {"success": False, "message": "Sản phẩm này hiện tại đã HẾT HÀNG!"}
                stock_dict = dict(stock_item)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (cat_dict["price"], user_id)
            )
            await db.execute(
                "UPDATE stock SET is_sold = 1, sold_at = ? WHERE id = ?",
                (now_str, stock_dict["id"])
            )
            await db.execute("""
                INSERT INTO orders (user_id, category_id, category_name, stock_id, price, item_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, category_id, cat_dict["name"], stock_dict["id"], cat_dict["price"], stock_dict["item_data"]))

            await db.commit()

            return {
                "success": True,
                "category_name": cat_dict["name"],
                "price": cat_dict["price"],
                "item_data": stock_dict["item_data"],
                "new_balance": current_balance - cat_dict["price"]
            }

    # --- BÁO CÁO & THỐNG KÊ ---
    async def get_recent_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT SUM(price), COUNT(*) FROM orders") as cursor:
                rev_row = await cursor.fetchone()
                total_revenue = rev_row[0] if rev_row and rev_row[0] else 0.0
                total_orders = rev_row[1] if rev_row else 0

            async with db.execute("SELECT COUNT(*) FROM stock WHERE is_sold = 0") as cursor:
                stock_row = await cursor.fetchone()
                available_stock = stock_row[0] if stock_row else 0

            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                user_row = await cursor.fetchone()
                total_users = user_row[0] if user_row else 0

            return {
                "total_revenue": total_revenue,
                "total_orders": total_orders,
                "available_stock": available_stock,
                "total_users": total_users
            }

db = Database()
