from typing import Optional

from aiohttp import web

from app.config import logger


async def start_health_server(port: str) -> Optional[web.AppRunner]:
    """Запускает мини-веб-сервер для прохождения healthcheck на Render.com."""
    if not port:
        return None

    try:
        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="Reminder Bot is running!"))
        app.router.add_get("/health", lambda r: web.Response(text="OK"))

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(port))
        await site.start()
        logger.info(f"Веб-сервер Render healthcheck запущен на порту {port}")
        return runner
    except Exception as e:
        logger.warning(f"Не удалось запустить веб-сервер на порту {port}: {e}")
        return None
