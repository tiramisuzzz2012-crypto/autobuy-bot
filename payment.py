import re
import random
import string
import logging
from typing import Dict, Any, Optional
from urllib.parse import quote

from config import BANK_ID, ACCOUNT_NO, ACCOUNT_NAME, EXCHANGE_RATE
from database import db

logger = logging.getLogger("AutoBuyPayment")

class PaymentManager:
    def __init__(self):
        self.bank_id = BANK_ID
        self.account_no = ACCOUNT_NO
        self.account_name = ACCOUNT_NAME
        self.rate = EXCHANGE_RATE

    def generate_vietqr_url(self, amount_vnd: float, memo: str) -> str:
        """Tạo đường dẫn ảnh mã VietQR Động chuẩn ngân hàng Việt Nam"""
        memo_encoded = quote(memo)
        name_encoded = quote(self.account_name)
        url = (
            f"https://img.vietqr.io/image/{self.bank_id}-{self.account_no}-compact2.png"
            f"?amount={int(amount_vnd)}&addInfo={memo_encoded}&accountName={name_encoded}"
        )
        return url

    async def create_deposit_order(self, user_id: int, amount_vnd: float) -> Dict[str, Any]:
        """Tạo lệnh nạp tiền mới và sinh mã VietQR"""
        random_suffix = ''.join(random.choices(string.digits, k=3))
        memo = f"NAP{user_id}{random_suffix}"
        amount_usd = amount_vnd / self.rate if self.rate > 0 else amount_vnd

        success = await db.create_deposit_request(user_id, amount_vnd, amount_usd, memo)
        if not success:
            memo = f"NAP{user_id}{random.randint(100, 999)}"
            await db.create_deposit_request(user_id, amount_vnd, amount_usd, memo)

        qr_url = self.generate_vietqr_url(amount_vnd, memo)

        return {
            "success": True,
            "user_id": user_id,
            "memo": memo,
            "amount_vnd": amount_vnd,
            "amount_usd": amount_usd,
            "bank_id": self.bank_id,
            "account_no": self.account_no,
            "account_name": self.account_name,
            "qr_url": qr_url
        }

    async def handle_bank_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Xử lý Webhook biến động số dư từ SePay / Casso / MBBank.
        Hỗ trợ duyệt tự động đa tầng: Memo nguyên vẹn, Đơn Pending khớp số tiền/User,
        và Tự động cộng tiền trực tiếp khi CK ghi nội dung NAP UserID/Username.
        """
        raw_text = (
            f"{webhook_data.get('transactionContent', '')} "
            f"{webhook_data.get('content', '')} "
            f"{webhook_data.get('description', '')} "
            f"{webhook_data.get('body', '')} "
            f"{webhook_data.get('code', '')} "
            f"{str(webhook_data)}"
        )
        content = raw_text.upper()

        amount_in = float(
            webhook_data.get("amountIn", 0) or 
            webhook_data.get("transferAmount", 0) or 
            webhook_data.get("amount", 0) or 
            0
        )

        logger.info(f"📩 [WEBHOOK SEPAY] Đã nhận tín hiệu: Content='{content[:120]}...', Amount={amount_in} VNĐ")

        # 1. Quét tìm mã memo NAP... nguyên vẹn trong DB
        nap_matches = re.findall(r"NAP\s*([A-Z0-9_]+)", content)
        for nap_str in nap_matches:
            clean_memo = f"NAP{nap_str}".replace(" ", "")
            deposit = await db.get_deposit_by_memo(clean_memo)
            if deposit:
                result = await db.complete_deposit(clean_memo)
                logger.info(f"✅ Auto duyệt thành công đơn nạp {clean_memo} ({deposit['amount_vnd']} VNĐ)!")
                return result

        # 2. Quét tìm theo danh sách đơn pending
        pending_deposits = await db.get_pending_deposits()
        if pending_deposits:
            # 2a. Ưu tiên đơnPending có User ID/Memo khớp VÀ số tiền khớp với amount_in
            if amount_in > 0:
                for dep in pending_deposits:
                    clean_memo = dep["memo"].strip().upper()
                    user_id_str = str(dep["user_id"])
                    if (clean_memo in content or user_id_str in content) and abs(dep["amount_vnd"] - amount_in) < 1.0:
                        result = await db.complete_deposit(clean_memo)
                        logger.info(f"✅ Auto duyệt khớp theo User ID {user_id_str} + Số tiền {amount_in} VNĐ đơn {clean_memo}!")
                        return result

            # 2b. Khớp theo User ID / Memo đơn pending gần nhất
            for dep in pending_deposits:
                clean_memo = dep["memo"].strip().upper()
                user_id_str = str(dep["user_id"])
                if clean_memo in content or user_id_str in content:
                    result = await db.complete_deposit(clean_memo)
                    logger.info(f"✅ Auto duyệt theo User ID {user_id_str} đơn {clean_memo}!")
                    return result

        # 3. CHẾ ĐỘ DỰ PHÒNG: Tự động cộng tiền trực tiếp khi nhận được số tiền > 0
        if amount_in > 0:
            # 3a. Tìm Discord User ID (17-20 chữ số) trong nội dung chuyển khoản
            id_matches = re.findall(r"\b(\d{17,20})\b", content)
            for uid_str in id_matches:
                uid = int(uid_str)
                user_data = await db.find_user_by_username_or_id(str(uid))
                if user_data:
                    random_suffix = ''.join(random.choices(string.digits, k=4))
                    auto_memo = f"AUTONAP_{uid}_{random_suffix}"
                    result = await db.direct_deposit(uid, amount_in, auto_memo)
                    logger.info(f"✅ Auto cộng tiền trực tiếp theo User ID {uid}: +{amount_in:,.0f} VNĐ!")
                    return result

            # 3b. Tìm Username Discord trong DB
            all_users = await db.get_all_users()
            for u in all_users:
                uname = u.get("username")
                if uname and len(uname) >= 3 and uname.upper() in content:
                    uid = u["user_id"]
                    random_suffix = ''.join(random.choices(string.digits, k=4))
                    auto_memo = f"AUTONAP_{uid}_{random_suffix}"
                    result = await db.direct_deposit(uid, amount_in, auto_memo)
                    logger.info(f"✅ Auto cộng tiền trực tiếp theo Username '{uname}': +{amount_in:,.0f} VNĐ!")
                    return result

        return {"success": False, "message": "Không tìm thấy đơn nạp khớp trong dữ liệu Webhook"}

payment_manager = PaymentManager()
