import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import ADMIN_DISCORD_IDS
from database import db

logger = logging.getLogger("AutoBuyAdmin")

def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not ADMIN_DISCORD_IDS:
            return True
        if interaction.user.id in ADMIN_DISCORD_IDS or interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("❌ Ngài không có quyền hạn Admin để dùng thuật pháp này!", ephemeral=True)
        return False
    return app_commands.check(predicate)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addcategory", description="[ADMIN] Tạo danh mục sản phẩm mới (Giá tính bằng VNĐ)")
    @is_admin()
    async def add_category(self, interaction: discord.Interaction, name: str, price: float, description: str = ""):
        cat_id = await db.add_category(name, description, price)
        if cat_id:
            await interaction.response.send_message(
                f"✅ **Đã tạo danh mục thành công!**\nID: `{cat_id}` | Tên: `{name}` | Giá: `{int(price):,} VNĐ`",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ Danh mục với tên `{name}` đã tồn tại!", ephemeral=True)

    @app_commands.command(name="deletecategory", description="[ADMIN] Xóa danh mục sản phẩm theo ID")
    @is_admin()
    async def delete_category(self, interaction: discord.Interaction, category_id: int):
        cat = await db.get_category_by_id(category_id)
        if not cat:
            await interaction.response.send_message(f"❌ Không tìm thấy danh mục có ID `{category_id}`!", ephemeral=True)
            return

        success = await db.delete_category(category_id)
        if success:
            await interaction.response.send_message(f"✅ **Đã xóa danh mục `{cat['name']}` (ID: {category_id}) thành công!**", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Không thể xóa danh mục ID `{category_id}`!", ephemeral=True)

    @app_commands.command(name="addstock", description="[ADMIN] Thêm key/tài khoản vào kho hàng (Phân tách bằng dấu phẩy hoặc |)")
    @is_admin()
    async def add_stock(self, interaction: discord.Interaction, category_id: int, items_data: str):
        items = [x.strip() for x in items_data.replace("|", ",").split(",") if x.strip()]
        if not items:
            await interaction.response.send_message("⚠️ Dữ liệu sản phẩm nhập vào không hợp lệ!", ephemeral=True)
            return

        cat = await db.get_category_by_id(category_id)
        if not cat:
            await interaction.response.send_message(f"❌ Không tìm thấy danh mục ID `{category_id}`!", ephemeral=True)
            return

        added_count = await db.add_stock_items(category_id, items)
        await interaction.response.send_message(
            f"✅ **Đã nạp {added_count} vật phẩm** vào danh mục `{cat['name']}`!",
            ephemeral=True
        )

    @app_commands.command(name="addbalance", description="[ADMIN] Cộng tiền VNĐ cho tài khoản người dùng")
    @is_admin()
    async def add_balance(self, interaction: discord.Interaction, user: discord.User, amount: float):
        new_bal = await db.update_balance(user.id, amount)
        await interaction.response.send_message(
            f"✅ Đã cộng `{int(amount):,} VNĐ` cho ngài **{user.name}**.\n💰 Số dư mới: `{int(new_bal):,} VNĐ`",
            ephemeral=True
        )

    @app_commands.command(name="checkstock", description="[ADMIN] Kiểm tra lượng hàng tồn trong kho")
    @is_admin()
    async def check_stock(self, interaction: discord.Interaction):
        categories = await db.get_categories()
        if not categories:
            await interaction.response.send_message("🏚️ Chưa có danh mục nào!", ephemeral=True)
            return

        embed = discord.Embed(title="📊 THỐNG KÊ KHO HÀNG", color=discord.Color.blue())
        for cat in categories:
            embed.add_field(
                name=f"ID [{cat['id']}] - {cat['name']}",
                value=f"Giá: `{int(cat['price']):,} VNĐ` | Tồn kho: **{cat['stock_count']}** món",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
