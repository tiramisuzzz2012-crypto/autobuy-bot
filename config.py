import os
from dotenv import load_dotenv

# Nạp biến môi trường từ .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", 8000))
SECRET_KEY = os.getenv("SECRET_KEY", "autobuy-secret-key-2026")
DB_PATH = os.getenv("DB_PATH", "autobuy.db")

# Cấu hình Ngân Hàng VietQR & Auto Deposit
BANK_ID = os.getenv("BANK_ID", "MB")                     # Mã Ngân hàng (MB, VCB, TCB, ACB, VPB, etc.)
ACCOUNT_NO = os.getenv("ACCOUNT_NO", "0999999999")        # Số tài khoản ngân hàng
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME", "NGUYEN VAN A")   # Tên chủ tài khoản
EXCHANGE_RATE = float(os.getenv("EXCHANGE_RATE", 25000))  # 25,000 VNĐ = $1.00 USD (Đặt là 1 nếu ví dùng VNĐ)
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY", "")            # API Key / Webhook Secret SePay.vn (Tùy chọn)

raw_admin_ids = os.getenv("ADMIN_DISCORD_IDS", "")
ADMIN_DISCORD_IDS = [
    int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()
]
