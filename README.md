# ⚡ Discord AutoBuy Bot & Web Management Dashboard

Hệ thống **Discord AutoBuy Bot** tự động hóa bán hàng số (Key, Tài khoản, Mã quà tặng) kết hợp **Web Management Dashboard** thời gian thực, xây dựng bằng Python (`discord.py` v2 + `FastAPI` + `aiosqlite`).

---

## 🌟 Tính Năng Nổi Bật

### 🤖 Discord Bot
- Giao diện cửa hàng `/shop` tương tác bằng **Nút Bấm (`discord.ui.Button`)**.
- Tự động trừ số dư, rút key khỏi kho và **gửi trực tiếp qua Tin Nhắn Riêng (DM)** cho khách hàng 24/7.
- Tự động **hoàn tiền** nếu người dùng khóa DM.
- Lệnh kiểm tra số dư `/balance`.
- Bộ lệnh Admin Discord: `/addcategory`, `/addstock`, `/addbalance`, `/checkstock`.

### 🌐 Web Management Dashboard (`http://localhost:8000`)
- **Bảng Thống Kê Tổng Quan**: Doanh thu, Đơn hàng, Tồn kho, Số lượng khách hàng.
- **Quản Lý Kho Hàng**: Thêm danh mục mới, nạp key/tài khoản hàng loạt (Bulk Import).
- **Quản Lý Người Dùng & Số Dư**: Tra cứu Discord ID, nạp/trừ tiền trực tiếp cho khách.
- **Nhật Ký Giao Dịch**: Xem toàn bộ lịch sử bán hàng và mã key đã phát.
- Đăng nhập bảo mật bằng Mật Khẩu Admin.

---

## 🚀 Hướng Dẫn Kích Hoạt (Cực Kỳ Đơn Giản)

### 1. Cài đặt thư viện phụ thuộc
Mở Terminal / PowerShell tại thư mục dự án và chạy:
```bash
pip install -r requirements.txt
```

### 2. Cấu hình File Môi Trường (.env)
Tạo file `.env` (hoặc đổi tên `.env.example` thành `.env`) và cập nhật thông tin:
```env
BOT_TOKEN=TOKEN_DISCORD_BOT_CỦA_BẠN
ADMIN_DISCORD_IDS=ID_DISCORD_CỦA_BẠN
ADMIN_PASSWORD=admin123
WEB_PORT=8000
```

### 3. Khởi chạy Hệ Thống
Chạy lệnh sau:
```bash
python main.py
```

- **Mở Web Dashboard**: Truy cập `http://localhost:8000` (Mật khẩu mặc định: `admin123`).
- **Sử dụng trên Discord**: Gõ `/shop` trên kênh Discord để mở cửa hàng.
