import logging
import os
import time

from .bot import TraderBot
from .config import Settings
from .server import start_server


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> None:
    settings = Settings.from_env()
    setup_logging(settings.log_level)

    # Iniciar servidor HTTP para el panel web
    port = int(os.getenv("PORT", "8080"))
    start_server(port)
    logging.info("Servidor HTTP iniciado en puerto %d", port)

    bot = TraderBot(settings)
    logging.warning("Bot Roots iniciado en PAPER para %s", settings.symbol)

    while True:
        try:
            bot.run_once()
        except Exception as e:
            logging.exception("Error en ciclo del bot: %s", e)
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
