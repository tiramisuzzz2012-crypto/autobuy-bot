from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import secrets
import json
import logging
from config import ADMIN_PASSWORD, SECRET_KEY, BANK_ID, ACCOUNT_NO, ACCOUNT_NAME, EXCHANGE_RATE
from database import db
from payment import payment_manager

logger = logging.getLogger("AutoBuyDashboard")

web_app = FastAPI(title="Discord AutoBuy Web Dashboard & Auto Bank QR Deposit")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
web_app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

ACTIVE_SESSIONS = set()

def verify_session(request: Request):
    token = request.cookies.get("session_token")
    if not token or token not in ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return True

# --- TRANG CÔNG KHAI: AUTO NẠP TIỀN VIETQR BANK ---
@web_app.get("/deposit", response_class=HTMLResponse)
async def deposit_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="deposit.html", 
        context={
            "bank_id": BANK_ID,
            "account_no": ACCOUNT_NO,
            "account_name": ACCOUNT_NAME,
            "rate": EXCHANGE_RATE
        }
    )

@web_app.post("/api/payment/create")
async def api_payment_create(request: Request):
    data = await request.json()
    user_input = str(data.get("user_input", "") or data.get("user_id", "")).strip()
    amount_vnd = float(data.get("amount_vnd", 0))

    if not user_input or amount_vnd < 1000:
        return JSONResponse({"success": False, "message": "Số tiền nạp tối thiểu là 1,000 VNĐ và Tên/ID Discord phải hợp lệ!"}, status_code=400)

    user_data = await db.find_user_by_username_or_id(user_input)
    if not user_data:
        try:
            from main import bot
            clean_name = user_input.lstrip("@").lower()
            found_id = None
            if bot and bot.users:
                for u in bot.users:
                    if u.name.lower() == clean_name or (u.global_name and u.global_name.lower() == clean_name):
                        found_id = u.id
                        await db.save_or_update_user(u.id, u.name)
                        break
            if found_id:
                user_id = found_id
            else:
                return JSONResponse({
                    "success": False, 
                    "message": f"Không tìm thấy tài khoản Discord nào có Tên/ID: '{user_input}'! Vui lòng gõ /shop trên Discord trước hoặc nhập Discord ID số."
                }, status_code=400)
        except Exception:
            return JSONResponse({
                "success": False, 
                "message": f"Không tìm thấy tài khoản Discord '{user_input}'. Hãy nhập Discord ID dạng số."
            }, status_code=400)
    else:
        user_id = user_data["user_id"]

    order = await payment_manager.create_deposit_order(user_id, amount_vnd)
    return JSONResponse(order)

async def send_deposit_success_dm(user_id: int, amount_vnd: float, new_balance: float):
    try:
        import discord
        from main import bot
        if bot and bot.is_ready():
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            if user:
                embed = discord.Embed(
                    title="🎉 GIAO DỊCH NẠP TIỀN THÀNH CÔNG!",
                    description=(
                        f"Chào **{user.name}**! Hệ thống đã nhận được tiền nạp của ngài:\n\n"
                        f"💵 **Số tiền vừa nạp:** `{int(amount_vnd):,} VNĐ`\n"
                        f"💰 **Số dư tài khoản mới:** `{int(new_balance):,} VNĐ`\n\n"
                        f"Cảm ơn ngài đã tin tưởng ủng hộ cửa hàng!"
                    ),
                    color=discord.Color.green()
                )
                embed.set_footer(text="Gõ !setup hoặc /shop trên Discord để tiến hành mua hàng ngay!")
                await user.send(embed=embed)
    except Exception as e:
        logger.error(f"Lỗi gửi DM nạp tiền: {e}")

@web_app.get("/api/payment/check/{memo}")
async def api_payment_check(memo: str):
    deposit = await db.get_deposit_by_memo(memo)
    if not deposit:
        return JSONResponse({"success": False, "message": "Đơn không tồn tại"}, status_code=404)
    
    new_bal = await db.get_user_balance(deposit["user_id"])
    return JSONResponse({
        "success": True,
        "status": deposit["status"],
        "user_id": deposit["user_id"],
        "amount_vnd": deposit["amount_vnd"],
        "new_balance": new_bal
    })

# Webhook nhận thông báo tự động từ Ngân Hàng (SePay/Casso) - Hỗ trợ GET/POST/OPTIONS/HEAD & Luôn trả 200 HTTP OK
@web_app.api_route("/api/payment/webhook", methods=["GET", "POST", "PUT", "OPTIONS", "HEAD"])
async def api_payment_webhook(request: Request):
    try:
        data = {}
        content_type = request.headers.get("content-type", "").lower()

        if "json" in content_type:
            data = await request.json()
        elif "form" in content_type:
            form_data = await request.form()
            data = dict(form_data)
        else:
            try:
                data = await request.json()
            except Exception:
                try:
                    form_data = await request.form()
                    data = dict(form_data)
                except Exception:
                    body_bytes = await request.body()
                    try:
                        data = json.loads(body_bytes.decode('utf-8'))
                    except Exception:
                        data = {"raw": body_bytes.decode('utf-8', errors='ignore')}

        result = await payment_manager.handle_bank_webhook(data)
        if result.get("success") and not result.get("already_completed"):
            await send_deposit_success_dm(result["user_id"], result["amount_vnd"], result["new_balance"])
        
        # Luôn trả HTTP status 200 cho SePay để SePay không báo lỗi 400/422
        return JSONResponse({"success": True, "result": result}, status_code=200)

    except Exception as e:
        logger.error(f"Lỗi xử lý Webhook: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=200)

# API Giả Lập Thanh Toán Cho Test / Admin
@web_app.post("/api/payment/mock-pay")
async def api_payment_mock(request: Request, authenticated: bool = Depends(verify_session)):
    data = await request.json()
    memo = data.get("memo", "")
    if not memo:
        return JSONResponse({"success": False, "message": "Thiếu mã memo"}, status_code=400)

    result = await db.complete_deposit(memo)
    if result.get("success") and not result.get("already_completed"):
        await send_deposit_success_dm(result["user_id"], result["amount_vnd"], result["new_balance"])
    return JSONResponse(result)

@web_app.get("/api/payment/pending")
async def api_pending_deposits(authenticated: bool = Depends(verify_session)):
    deposits = await db.get_pending_deposits()
    return JSONResponse(deposits)

@web_app.post("/api/payment/approve-deposit")
async def api_approve_deposit(request: Request, authenticated: bool = Depends(verify_session)):
    data = await request.json()
    deposit_id = int(data.get("deposit_id", 0))

    if not deposit_id:
        return JSONResponse({"success": False, "message": "ID đơn nạp không hợp lệ"}, status_code=400)

    result = await db.complete_deposit_by_id(deposit_id)
    if result.get("success") and not result.get("already_completed"):
        await send_deposit_success_dm(result["user_id"], result["amount_vnd"], result["new_balance"])
    return JSONResponse(result)

# --- TRANG QUẢN TRỊ ADMIN DASHBOARD ---
@web_app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("session_token")
    if token and token in ACTIVE_SESSIONS:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@web_app.post("/login")
async def login_post(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        token = secrets.token_hex(32)
        ACTIVE_SESSIONS.add(token)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_token", value=token, httponly=True)
        return response
    return templates.TemplateResponse(request=request, name="login.html", context={"error": "Mật khẩu Admin không chính xác!"})

@web_app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS.remove(token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response

@web_app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, authenticated: bool = Depends(verify_session)):
    return templates.TemplateResponse(request=request, name="index.html", context={})

# --- REST API ENDPOINTS FOR DASHBOARD UI ---
@web_app.get("/api/stats")
async def api_stats(authenticated: bool = Depends(verify_session)):
    stats = await db.get_dashboard_stats()
    return JSONResponse(stats)

@web_app.get("/api/categories")
async def api_categories(authenticated: bool = Depends(verify_session)):
    cats = await db.get_categories()
    return JSONResponse(cats)

@web_app.post("/api/categories/add")
async def api_add_category(request: Request, authenticated: bool = Depends(verify_session)):
    data = await request.json()
    name = data.get("name")
    description = data.get("description", "")
    price = float(data.get("price", 0))

    if not name or price <= 0:
        return JSONResponse({"success": False, "message": "Dữ liệu không hợp lệ!"}, status_code=400)

    cat_id = await db.add_category(name, description, price)
    if cat_id:
        return JSONResponse({"success": True, "id": cat_id})
    return JSONResponse({"success": False, "message": "Tên danh mục đã tồn tại!"}, status_code=400)

@web_app.post("/api/categories/delete")
async def api_delete_category(request: Request, authenticated: bool = Depends(verify_session)):
    data = await request.json()
    cat_id = int(data.get("category_id", 0))

    if not cat_id:
        return JSONResponse({"success": False, "message": "ID danh mục không hợp lệ!"}, status_code=400)

    success = await db.delete_category(cat_id)
    if success:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False, "message": "Không thể xóa danh mục!"}, status_code=400)

@web_app.post("/api/stock/add")
async def api_add_stock(request: Request, authenticated: bool = Depends(verify_session)):
    data = await request.json()
    category_id = int(data.get("category_id", 0))
    raw_items = data.get("items", "")

    items = [x.strip() for x in raw_items.replace("\r\n", "\n").split("\n") if x.strip()]
    if not category_id or not items:
        return JSONResponse({"success": False, "message": "Dữ liệu kho hàng rỗng!"}, status_code=400)

    count = await db.add_stock_items(category_id, items)
    return JSONResponse({"success": True, "added_count": count})

@web_app.get("/api/users")
async def api_users(authenticated: bool = Depends(verify_session)):
    users = await db.get_all_users()
    return JSONResponse(users)

@web_app.post("/api/users/balance")
async def api_update_balance(request: Request, authenticated: bool = Depends(verify_session)):
    data = await request.json()
    user_id = int(data.get("user_id", 0))
    amount = float(data.get("amount", 0))

    if not user_id:
        return JSONResponse({"success": False, "message": "User ID không hợp lệ!"}, status_code=400)

    new_bal = await db.update_balance(user_id, amount)
    return JSONResponse({"success": True, "new_balance": new_bal})

@web_app.get("/api/orders")
async def api_orders(authenticated: bool = Depends(verify_session)):
    orders = await db.get_recent_orders(limit=50)
    return JSONResponse(orders)

@web_app.get("/api/settings/store")
async def api_get_store_settings(authenticated: bool = Depends(verify_session)):
    st = await db.get_store_settings()
    return JSONResponse(st)

@web_app.post("/api/settings/store")
async def api_save_store_settings(request: Request, authenticated: bool = Depends(verify_session)):
    data = await request.json()
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    footer = data.get("footer", "").strip()
    banner_url = data.get("banner_url", "").strip()

    if title:
        await db.set_setting("store_title", title)
    if description:
        await db.set_setting("store_description", description)
    if footer is not None:
        await db.set_setting("store_footer", footer)
    if banner_url is not None:
        await db.set_setting("store_banner_url", banner_url)

    new_st = await db.get_store_settings()
    return JSONResponse({"success": True, "settings": new_st})
