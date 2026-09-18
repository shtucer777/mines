import asyncio
import logging
from dataclasses import dataclass

from .client import StakeClient
from .mines_bot import MinesBot, BotStats
from .strategies import get_strategy

logger = logging.getLogger(__name__)


@dataclass
class MultiBotConfig:
    token: str
    strategy: str = "conservative"
    bet_amount: float = 0.00001
    mines_count: int = 3
    max_rounds: int = 50
    delay: float = 2.0


class MultiBotRunner:
    """Run multiple bot instances with different tokens/strategies in parallel."""

    def __init__(self, configs: list[MultiBotConfig]):
        self.configs = configs
        self.bots: list[MinesBot] = []

    async def _run_single(self, idx: int, cfg: MultiBotConfig) -> BotStats:
        client = StakeClient(token=cfg.token)
        strategy = get_strategy(cfg.strategy)
        bot = MinesBot(client=client, strategy=strategy)
        self.bots.append(bot)

        logger.info(
            "Bot #%d starting: strategy=%s bet=%.8f",
            idx, cfg.strategy, cfg.bet_amount,
        )

        stats = await bot.run(
            max_rounds=cfg.max_rounds,
            bet_amount=cfg.bet_amount,
            mines_count=cfg.mines_count,
            delay=cfg.delay,
        )

        logger.info("Bot #%d finished: %s", idx, stats.summary())
        return stats

    async def run_all(self) -> list[BotStats]:
        tasks = [
            self._run_single(i, cfg)
            for i, cfg in enumerate(self.configs)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_stats: list[BotStats] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Bot #%d failed: %s", i, result)
            else:
                all_stats.append(result)

        if all_stats:
            total_profit = sum(s.total_profit for s in all_stats)
            total_wagered = sum(s.total_wagered for s in all_stats)
            total_rounds = sum(s.total_rounds for s in all_stats)
            logger.info(
                "All bots done — rounds=%d wagered=%.8f profit=%+.8f",
                total_rounds, total_wagered, total_profit,
            )

        return all_stats

    def stop_all(self) -> None:
        for bot in self.bots:
            bot._stop()
