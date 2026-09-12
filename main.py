import asyncio
import logging
import uvicorn
import discord
from discord.ext import commands

from config import BOT_TOKEN, WEB_HOST, WEB_PORT
from database import db
from web.dashboard import web_app

# Thiết lập hệ thống ghi nhung logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AutoBuyMain")

# Thiết lập Intents tiêu chuẩn cho Discord Bot (Không yêu cầu Privileged Intents)
intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

from cogs.store import PermanentStoreView

@bot.event
async def on_ready():
    bot.add_view(PermanentStoreView())
    logger.info(f"⚡ Discord Bot đã thức tỉnh thành công dưới tên: {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Đã đồng bộ {len(synced)} lệnh Slash toàn cầu!")
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info(f"✅ Đã đồng bộ lệnh Slash tức thì cho Server: {guild.name}")
    except Exception as e:
        logger.error(f"❌ Lỗi đồng bộ lệnh Slash: {e}")

async def main():
    # 1. Khởi tạo Giếng Ma Thuật (SQLite Database)
    await db.init_db()

    # 2. Nạp các Cogs phép thuật
    await bot.load_extension("cogs.store")
    await bot.load_extension("cogs.admin")

    # 3. Khởi tạo Uvicorn Server cho Web Dashboard
    config = uvicorn.Config(
        app=web_app, 
        host=WEB_HOST, 
        port=WEB_PORT, 
        log_level="info"
    )
    server = uvicorn.Server(config)

    logger.info(f"🌐 Huyết Cầu Quản Lý Web Dashboard đã kích hoạt tại: http://localhost:{WEB_PORT}")
    
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
        logger.warning("⚠️ CHƯA CẤU HÌNH BOT_TOKEN TRONG FILE .env! Đang chỉ kích hoạt Web Dashboard...")
        await server.serve()
    else:
        # Chạy song song Web Dashboard & Discord Bot trong cùng một Asyncio Loop
        await asyncio.gather(
            server.serve(),
            bot.start(BOT_TOKEN)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Đã ngừng hệ thống ma thuật an toàn.")
