import discord
from discord.ext import commands
from discord import app_commands
import logging
from database import db
from payment import payment_manager
from config import ADMIN_DISCORD_IDS, BANK_ID, ACCOUNT_NO, ACCOUNT_NAME

logger = logging.getLogger("AutoBuyStore")

def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not ADMIN_DISCORD_IDS:
            return True
        if interaction.user.id in ADMIN_DISCORD_IDS or interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("❌ Ngài không có quyền Admin!", ephemeral=True)
        return False
    return app_commands.check(predicate)

async def build_main_store_embed():
    st = await db.get_store_settings()
    try:
        color_val = int(st["color"].replace("#", "").replace("0x", ""), 16)
    except Exception:
        color_val = 0x3498db

    embed = discord.Embed(
        title=st["title"],
        description=st["description"],
        color=discord.Color(color_val)
    )
    if st["footer"]:
        embed.set_footer(text=st["footer"])
    if st["banner_url"]:
        embed.set_image(url=st["banner_url"])
    return embed

class BackToMainMenuButton(discord.ui.Button):
    def __init__(self, is_ephemeral: bool = True):
        super().__init__(
            label="◀️ Quay Lại Menu Chính",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_back_main_menu"
        )
        self.is_ephemeral = is_ephemeral

    async def callback(self, interaction: discord.Interaction):
        embed = await build_main_store_embed()
        view = MainMenuInteractiveView()
        await interaction.response.edit_message(embed=embed, view=view)

class BuyButton(discord.ui.Button):
    def __init__(self, category_id: int, category_name: str, price: float):
        super().__init__(
            label=f"🛒 Mua {category_name} ({int(price):,} VNĐ)",
            style=discord.ButtonStyle.success,
            custom_id=f"buy_{category_id}"
        )
        self.category_id = category_id
        self.category_name = category_name
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        await db.save_or_update_user(user_id, interaction.user.name)
        result = await db.process_purchase(user_id, self.category_id)

        if not result["success"]:
            embed_err = discord.Embed(
                title="❌ THẤT BẠI",
                description=result["message"],
                color=discord.Color.red()
            )
            view_err = discord.ui.View()
            view_err.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_err, view=view_err)
            return

        item_data = result["item_data"]
        # Gửi DM riêng tư chứa key
        try:
            embed_dm = discord.Embed(
                title="🎉 GIAO DỊCH THÀNH CÔNG!",
                description=f"Cảm ơn ngài **{interaction.user.name}** đã ủng hộ cửa hàng!",
                color=discord.Color.green()
            )
            embed_dm.add_field(name="📦 Sản Phẩm", value=f"`{result['category_name']}`", inline=True)
            embed_dm.add_field(name="💵 Giá Tiền", value=f"`{int(result['price']):,} VNĐ`", inline=True)
            embed_dm.add_field(name="💳 Số Dư Còn Lại", value=f"`{int(result['new_balance']):,} VNĐ`", inline=True)
            embed_dm.add_field(
                name="🔑 Nội Dung Key / Tài Khoản",
                value=f"```\n{item_data}\n```",
                inline=False
            )
            embed_dm.set_footer(text="Bảo quản dữ liệu cẩn thận - Đơn hàng đã ghi nhận vào hệ thống!")
            await interaction.user.send(embed=embed_dm)
        except discord.Forbidden:
            await db.update_balance(user_id, result["price"])
            embed_err = discord.Embed(
                title="⚠️ CHẶN DM",
                description="Không thể gửi tin nhắn riêng cho ngài! Hệ thống đã HOÀN TIỀN.",
                color=discord.Color.orange()
            )
            view_err = discord.ui.View()
            view_err.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_err, view=view_err)
            return

        # Cập nhật TRỰC TIẾP TRÊN CÙNG TIN NHẮN DISCORD
        embed_success = discord.Embed(
            title="🎉 MUA HÀNG THÀNH CÔNG!",
            description=(
                f"✅ **Đã hoàn tất giao dịch!** Vật phẩm đã được gửi vào **Tin Nhắn Riêng (DM)** của ngài.\n\n"
                f"📦 **Sản phẩm:** `{result['category_name']}`\n"
                f"💰 **Số dư còn lại:** `{int(result['new_balance']):,} VNĐ`"
            ),
            color=discord.Color.green()
        )
        view_success = discord.ui.View()
        view_success.add_item(BackToMainMenuButton())
        await interaction.response.edit_message(embed=embed_success, view=view_success)

class DepositStatusCheckButton(discord.ui.Button):
    def __init__(self, memo: str):
        super().__init__(
            label="🔄 Kiểm Tra Số Dư",
            style=discord.ButtonStyle.primary,
            custom_id=f"check_dep_{memo}"
        )
        self.memo = memo

    async def callback(self, interaction: discord.Interaction):
        deposit = await db.get_deposit_by_memo(self.memo)
        if deposit and deposit["status"] == "completed":
            new_bal = await db.get_user_balance(interaction.user.id)
            embed_success = discord.Embed(
                title="🎉 GIAO DỊCH NẠP TIỀN THÀNH CÔNG!",
                description=(
                    f"✅ **Hệ thống đã nhận tiền thành công!**\n\n"
                    f"💵 **Số tiền vừa nạp:** `{int(deposit['amount_vnd']):,} VNĐ`\n"
                    f"💰 **Số dư tài khoản mới:** `{int(new_bal):,} VNĐ`\n\n"
                    f"Ngài có thể mua sắm ngay lập tức!"
                ),
                color=discord.Color.green()
            )
            view_success = discord.ui.View()
            view_success.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_success, view=view_success)
        else:
            await interaction.response.send_message("⌛ Giao dịch chưa hoàn tất. Vui lòng hoàn tất chuyển khoản đúng nội dung!", ephemeral=True)

class DepositModal(discord.ui.Modal, title="🏦 AUTO NẠP TIỀN VIETQR BANK"):
    amount_input = discord.ui.TextInput(
        label="Số tiền VNĐ muốn nạp",
        placeholder="VD: 50000 (Tối thiểu 1,000 VNĐ)",
        min_length=4,
        max_length=9,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            amount_vnd = float(self.amount_input.value.strip())
            if amount_vnd < 1000:
                await interaction.followup.send("❌ Số tiền nạp tối thiểu là 1,000 VNĐ!", ephemeral=True)
                return

            order = await payment_manager.create_deposit_order(interaction.user.id, amount_vnd)

            embed = discord.Embed(
                title="🏦 MÃ VIETQR NẠP TIỀN TỰ ĐỘNG",
                description=(
                    f"Chào **{interaction.user.name}**! Vui lòng quét mã QR bên dưới hoặc chuyển khoản theo đúng thông tin:\n\n"
                    f"🏦 **Ngân Hàng:** `{order['bank_id']}`\n"
                    f"💳 **Số Tài Khoản:** `{order['account_no']}`\n"
                    f"👤 **Chủ Tài Khoản:** `{order['account_name']}`\n"
                    f"💵 **Số Tiền Nạp:** `{int(order['amount_vnd']):,} VNĐ`\n"
                    f"📝 **Nội Dung Chuyển Khoản:** ||`{order['memo']}`||\n\n"
                    f"⚠️ **LƯU Ý:** Phải điền đúng **Nội Dung Chuyển Khoản** ở trên để hệ thống tự động cộng tiền trong 5 giây!"
                ),
                color=discord.Color.green()
            )
            embed.set_image(url=order['qr_url'])
            embed.set_footer(text="Hệ thống tự động kiểm tra số dư và cộng tiền 24/7!")

            view = discord.ui.View()
            view.add_item(DepositStatusCheckButton(order['memo']))
            view.add_item(BackToMainMenuButton())
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            # Tự động quét vòng lặp 3s/lần. Khi xong sẽ tự ĐỔI ẢNH QR THÀNH THÔNG BÁO THÀNH CÔNG
            memo_code = order['memo']
            user_id = interaction.user.id

            async def auto_poll_discord():
                import asyncio
                for _ in range(100):
                    await asyncio.sleep(3)
                    dep = await db.get_deposit_by_memo(memo_code)
                    if dep and dep["status"] == "completed":
                        new_bal = await db.get_user_balance(user_id)
                        embed_done = discord.Embed(
                            title="🎉 GIAO DỊCH NẠP TIỀN THÀNH CÔNG!",
                            description=(
                                f"✅ **Hệ thống đã nhận tiền thành công!**\n\n"
                                f"💵 **Số tiền vừa nạp:** `{int(dep['amount_vnd']):,} VNĐ`\n"
                                f"💰 **Số dư tài khoản mới:** `{int(new_bal):,} VNĐ`\n\n"
                                f"Ngài có thể mua sắm ngay lập tức!"
                            ),
                            color=discord.Color.green()
                        )
                        view_done = discord.ui.View()
                        view_done.add_item(BackToMainMenuButton())
                        try:
                            await interaction.edit_original_response(embed=embed_done, view=view_done)
                        except Exception:
                            pass
                        break

            import asyncio
            asyncio.create_task(auto_poll_discord())

        except ValueError:
            await interaction.followup.send("❌ Số tiền không hợp lệ! Vui lòng chỉ nhập số.", ephemeral=True)

class ConfirmPurchaseButton(discord.ui.Button):
    def __init__(self, cat_id: int):
        super().__init__(
            label="✅ Xác Nhận Mua",
            style=discord.ButtonStyle.success,
            custom_id=f"confirm_buy_{cat_id}"
        )
        self.cat_id = cat_id

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        await db.save_or_update_user(user_id, interaction.user.name)
        result = await db.process_purchase(user_id, self.cat_id)

        if not result["success"]:
            embed_err = discord.Embed(
                title="❌ GIAO DỊCH THẤT BẠI",
                description=result["message"],
                color=discord.Color.red()
            )
            view_err = discord.ui.View()
            view_err.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_err, view=view_err)
            return

        item_data = result["item_data"]
        # Gửi DM riêng tư chứa key
        try:
            embed_dm = discord.Embed(
                title="🎉 GIAO DỊCH MUA HÀNG THÀNH CÔNG!",
                description=f"Cảm ơn ngài **{interaction.user.name}** đã ủng hộ cửa hàng!",
                color=discord.Color.green()
            )
            embed_dm.add_field(name="📦 Sản Phẩm", value=f"`{result['category_name']}`", inline=True)
            embed_dm.add_field(name="💵 Giá Tiền", value=f"`{int(result['price']):,} VNĐ`", inline=True)
            embed_dm.add_field(name="💳 Số Dư Còn Lại", value=f"`{int(result['new_balance']):,} VNĐ`", inline=True)
            embed_dm.add_field(
                name="🔑 Nội Dung Key / Tài Khoản Khách Hàng nhận được:",
                value=f"```\n{item_data}\n```",
                inline=False
            )
            embed_dm.set_footer(text="Bảo quản dữ liệu cẩn thận - Đơn hàng đã ghi nhận vào hệ thống!")
            await interaction.user.send(embed=embed_dm)
        except discord.Forbidden:
            await db.update_balance(user_id, result["price"])
            embed_err = discord.Embed(
                title="⚠️ CHẶN DM",
                description="Không thể gửi tin nhắn riêng cho ngài! Hệ thống đã HOÀN TIỀN.",
                color=discord.Color.orange()
            )
            view_err = discord.ui.View()
            view_err.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_err, view=view_err)
            return

        embed_success = discord.Embed(
            title="🎉 MUA HÀNG THÀNH CÔNG!",
            description=(
                f"✅ **Đã hoàn tất giao dịch!** Vật phẩm đã được gửi vào **Tin Nhắn Riêng (DM)** của ngài.\n\n"
                f"📦 **Sản phẩm:** `{result['category_name']}`\n"
                f"💰 **Số dư còn lại:** `{int(result['new_balance']):,} VNĐ`\n\n"
                f"⌛ *Tự động quay lại Menu Chính sau 4 giây...*"
            ),
            color=discord.Color.green()
        )
        view_success = discord.ui.View()
        view_success.add_item(BackToMainMenuButton())
        await interaction.response.edit_message(embed=embed_success, view=view_success)

        # Tự động quay lại Menu Chính sau 4 giây
        async def auto_return_success():
            import asyncio
            await asyncio.sleep(4)
            try:
                main_embed = await build_main_store_embed()
                main_view = await build_main_store_view()
                await interaction.edit_original_response(embed=main_embed, view=main_view)
            except Exception:
                pass

        import asyncio
        asyncio.create_task(auto_return_success())

class CancelPurchaseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="❌ Hủy Bỏ",
            style=discord.ButtonStyle.danger,
            custom_id="cancel_buy"
        )

    async def callback(self, interaction: discord.Interaction):
        embed_cancel = discord.Embed(
            title="🚫 ĐÃ HỦY GIAO DỊCH",
            description="Ngài đã hủy bỏ thao tác mua hàng.\n\n⌛ *Tự động quay lại Menu Chính sau 3 giây...*",
            color=discord.Color.slate_grey()
        )
        view_cancel = discord.ui.View()
        view_cancel.add_item(BackToMainMenuButton())
        await interaction.response.edit_message(embed=embed_cancel, view=view_cancel)

        # Tự động quay lại Menu Chính sau 3 giây khi bấm Hủy
        async def auto_return_cancel():
            import asyncio
            await asyncio.sleep(3)
            try:
                main_embed = await build_main_store_embed()
                main_view = await build_main_store_view()
                await interaction.edit_original_response(embed=main_embed, view=main_view)
            except Exception:
                pass

        import asyncio
        asyncio.create_task(auto_return_cancel())

class CategorySelectMenu(discord.ui.Select):
    def __init__(self, categories: list):
        options = []
        if not categories:
            options.append(discord.SelectOption(
                label="🏚️ Hiện chưa có sản phẩm nào",
                value="none",
                description="Vui lòng quay lại sau khi Admin nạp hàng!"
            ))
        else:
            for cat in categories:
                stock_count = cat.get("stock_count", 0)
                price_fmt = f"{int(cat['price']):,} VNĐ"
                stock_txt = f"Còn {stock_count} món" if stock_count > 0 else "🔴 HẾT HÀNG"
                desc_txt = f"Giá: {price_fmt} | {stock_txt}"
                if cat.get("description"):
                    desc_txt = f"{cat['description'][:40]} | {stock_txt}"

                options.append(discord.SelectOption(
                    label=f"📦 {cat['name']} - {price_fmt}",
                    value=str(cat["id"]),
                    description=desc_txt[:100],
                    emoji="🛒"
                ))

        super().__init__(
            placeholder="🛒 Chọn gói sản phẩm bạn muốn mua...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_store_category"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            embed_none = discord.Embed(
                title="❌ KHÔNG CÓ SẢN PHẨM",
                description="Cửa hàng hiện tại chưa có sản phẩm nào!",
                color=discord.Color.red()
            )
            view_none = discord.ui.View()
            view_none.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_none, view=view_none)
            return

        cat_id = int(self.values[0])
        user_id = interaction.user.id
        user_balance = await db.save_or_update_user(user_id, interaction.user.name)
        cat = await db.get_category_by_id(cat_id)

        if not cat:
            embed_err = discord.Embed(
                title="❌ LỖI",
                description="Danh mục sản phẩm không tồn tại!",
                color=discord.Color.red()
            )
            view_err = discord.ui.View()
            view_err.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_err, view=view_err)
            return

        available_stock = await db.get_available_stock(cat_id)
        if available_stock <= 0:
            embed_out = discord.Embed(
                title="🔴 HẾT HÀNG",
                description=f"Sản phẩm **{cat['name']}** hiện tại đã HẾT HÀNG!",
                color=discord.Color.red()
            )
            view_out = discord.ui.View()
            view_out.add_item(BackToMainMenuButton())
            await interaction.response.edit_message(embed=embed_out, view=view_out)
            return

        price = cat["price"]
        balance_after = user_balance - price
        is_enough = user_balance >= price

        embed_confirm = discord.Embed(
            title="🛒 XÁC NHẬN ĐƠN MUA HÀNG",
            description=(
                f"Ngài có chắc chắn muốn mua gói **{cat['name']}** không?\n\n"
                f"📦 **Sản phẩm:** `{cat['name']}`\n"
                f"📝 **Mô tả:** `{cat['description'] or 'Không có'}`\n"
                f"💵 **Giá bán:** `{int(price):,} VNĐ`\n"
                f"💰 **Số dư hiện tại:** `{int(user_balance):,} VNĐ`\n"
                f"💳 **Số dư sau khi mua:** `{int(balance_after):,} VNĐ`\n\n"
                + ("✅ *Số dư đủ để mua hàng. Bấm **Xác Nhận Mua** bên dưới.*" if is_enough else "🔴 **CẢNH BÁO:** Số dư của ngài không đủ! Vui lòng nạp thêm tiền trước.")
            ),
            color=discord.Color.gold() if is_enough else discord.Color.red()
        )

        view_confirm = discord.ui.View()
        if is_enough:
            view_confirm.add_item(ConfirmPurchaseButton(cat_id))
        view_confirm.add_item(CancelPurchaseButton())
        view_confirm.add_item(BackToMainMenuButton())

        # CHỈNH SỬA TRỰC TIẾP TRÊN 1 TIN NHẮN CỦ DỰA THEO TƯ TƯỞNG SINGLE-MESSAGE DYNAMIC UI
        await interaction.response.edit_message(embed=embed_confirm, view=view_confirm)

class StoreDepositButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="💳 Auto Nạp Tiền VietQR", style=discord.ButtonStyle.success, custom_id="btn_store_deposit")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DepositModal())

class StoreBalanceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="💰 Ví Của Tôi", style=discord.ButtonStyle.secondary, custom_id="btn_store_balance")

    async def callback(self, interaction: discord.Interaction):
        bal = await db.save_or_update_user(interaction.user.id, interaction.user.name)
        embed = discord.Embed(
            title="💳 SỐ DƯ TÀI KHOẢN",
            description=f"Ví của ngài **{interaction.user.name}** hiện có: `{int(bal):,} VNĐ`",
            color=discord.Color.gold()
        )
        view = discord.ui.View()
        view.add_item(BackToMainMenuButton())
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def build_main_store_view():
    categories = await db.get_categories()
    view = discord.ui.View(timeout=None)
    view.add_item(CategorySelectMenu(categories))
    view.add_item(StoreDepositButton())
    view.add_item(StoreBalanceButton())
    return view

class BackToMainMenuButton(discord.ui.Button):
    def __init__(self, is_ephemeral: bool = True):
        super().__init__(
            label="◀️ Quay Lại Menu Chính",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_back_main_menu"
        )
        self.is_ephemeral = is_ephemeral

    async def callback(self, interaction: discord.Interaction):
        embed = await build_main_store_embed()
        view = await build_main_store_view()
        await interaction.response.edit_message(embed=embed, view=view)

class EditStoreTextModal(discord.ui.Modal, title="⚙️ CẤU HÌNH CHỮ CỬA HÀNG DISCORD"):
    title_input = discord.ui.TextInput(
        label="Tiêu đề Bảng Cửa Hàng (Title)",
        placeholder="VD: ⚡ HỆ THỐNG CỬA HÀNG TỰ ĐỘNG - AUTOBUY STORE 24/7",
        min_length=3,
        max_length=256,
        required=True
    )
    desc_input = discord.ui.TextInput(
        label="Nội dung mô tả (Description)",
        style=discord.TextStyle.paragraph,
        placeholder="Nhập nội dung mô tả cửa hàng tùy ý tại đây...",
        min_length=5,
        max_length=2000,
        required=True
    )
    footer_input = discord.ui.TextInput(
        label="Chân trang (Footer)",
        placeholder="VD: AutoBuy Bot Engine © 2026",
        max_length=2048,
        required=False
    )
    banner_input = discord.ui.TextInput(
        label="Link ảnh Banner (Optional URL)",
        placeholder="https://example.com/banner.png",
        max_length=500,
        required=False
    )

    def __init__(self, current_st: dict):
        super().__init__()
        self.title_input.default = current_st.get("title", "")
        self.desc_input.default = current_st.get("description", "")
        self.footer_input.default = current_st.get("footer", "")
        self.banner_input.default = current_st.get("banner_url", "")

    async def on_submit(self, interaction: discord.Interaction):
        await db.set_setting("store_title", self.title_input.value.strip())
        await db.set_setting("store_description", self.desc_input.value.strip())
        await db.set_setting("store_footer", self.footer_input.value.strip())
        await db.set_setting("store_banner_url", self.banner_input.value.strip())

        embed = await build_main_store_embed()
        view = await build_main_store_view()
        await interaction.response.send_message(
            content="✅ **Đã cập nhật chữ Bảng Cửa Hàng thành công!** Ngài dùng `/setupstore` hoặc `!setup` để phát hành bảng mới.",
            embed=embed,
            view=view,
            ephemeral=True
        )

class PermanentStoreView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

class StoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _send_store_panel(self, channel):
        embed = await build_main_store_embed()
        view = await build_main_store_view()
        await channel.send(embed=embed, view=view)

    @app_commands.command(name="setstoretext", description="[ADMIN] Tùy chỉnh Tiêu đề, Mô tả, Footer và Banner của Bảng Cửa Hàng Discord")
    @is_admin()
    async def set_store_text(self, interaction: discord.Interaction):
        st = await db.get_store_settings()
        await interaction.response.send_modal(EditStoreTextModal(st))

    @app_commands.command(name="setupstore", description="[ADMIN] Khởi tạo Bảng Cửa Hàng AutoBuy cố định vào kênh này")
    @is_admin()
    async def setup_store(self, interaction: discord.Interaction):
        await self._send_store_panel(interaction.channel)
        await interaction.response.send_message("✅ Đã khởi tạo Bảng Cửa Hàng AutoBuy thành công vào kênh này!", ephemeral=True)

    @commands.command(name="setupstore", aliases=["setup", "shopsetup"])
    async def setup_store_prefix(self, ctx):
        await self._send_store_panel(ctx.channel)
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @app_commands.command(name="shop", description="Hiển thị Cửa Hàng AutoBuy")
    async def shop(self, interaction: discord.Interaction):
        embed = await build_main_store_embed()
        view = await build_main_store_view()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="balance", description="Xem số dư hiện tại của ngài")
    async def balance(self, interaction: discord.Interaction):
        bal = await db.save_or_update_user(interaction.user.id, interaction.user.name)
        embed = discord.Embed(
            title="💳 SỐ DƯ TÀI KHOẢN",
            description=f"Ví của ngài **{interaction.user.name}** hiện có: `{int(bal):,} VNĐ`",
            color=discord.Color.gold()
        )
        view = discord.ui.View()
        view.add_item(BackToMainMenuButton())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(StoreCog(bot))
