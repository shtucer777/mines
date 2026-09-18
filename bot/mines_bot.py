import asyncio
import logging
import signal
import time
from dataclasses import dataclass

from .client import StakeClient, StakeAPIError
from .config import settings
from .strategies import GameState, Strategy, get_strategy

logger = logging.getLogger(__name__)


@dataclass
class BotStats:
    total_rounds: int = 0
    wins: int = 0
    losses: int = 0
    total_wagered: float = 0.0
    total_profit: float = 0.0
    peak_profit: float = 0.0
    start_time: float = 0.0

    @property
    def win_rate(self) -> float:
        if self.total_rounds == 0:
            return 0.0
        return self.wins / self.total_rounds * 100

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def summary(self) -> str:
        return (
            f"Rounds: {self.total_rounds} | "
            f"W/L: {self.wins}/{self.losses} ({self.win_rate:.1f}%) | "
            f"Wagered: {self.total_wagered:.8f} | "
            f"Profit: {self.total_profit:+.8f} | "
            f"Peak: {self.peak_profit:+.8f} | "
            f"Time: {self.elapsed:.0f}s"
        )


class MinesBot:
    def __init__(
        self,
        client: StakeClient | None = None,
        strategy: Strategy | None = None,
    ):
        self.client = client or StakeClient()
        self.strategy = strategy or get_strategy(settings.strategy)
        self.stats = BotStats()
        self._running = False

    async def play_round(self, bet_amount: float, mines_count: int) -> bool:
        game = await self.client.place_bet(bet_amount, mines_count)
        game_id = game["id"]
        state = GameState(
            mines_count=mines_count,
            bet_amount=bet_amount,
        )

        logger.info(
            "Game %s started: bet=%.8f mines=%d",
            game_id, bet_amount, mines_count,
        )

        won = False
        while game["active"]:
            if self.strategy.should_cashout(state):
                result = await self.client.cashout(game_id)
                payout = float(result.get("payout", 0))
                profit = payout - bet_amount
                logger.info(
                    "Cashout: payout=%.8f profit=%+.8f (x%.2f)",
                    payout, profit, state.current_multiplier,
                )
                won = True
                break

            tile = self.strategy.pick_tile(state)
            try:
                game = await self.client.reveal_tile(game_id, tile)
            except StakeAPIError as e:
                if "mine" in str(e).lower() or "boom" in str(e).lower():
                    logger.info("Hit a mine on tile %d!", tile)
                    break
                raise

            if not game["active"]:
                logger.info("Hit a mine on tile %d!", tile)
                break

            rounds = game.get("state", {}).get("rounds", [])
            if rounds:
                last = rounds[-1]
                state.current_multiplier = float(last.get("payoutMultiplier", 1.0))
            state.revealed.append(tile)
            logger.debug(
                "Tile %d safe, multiplier=%.2fx, revealed=%d",
                tile, state.current_multiplier, len(state.revealed),
            )

        return won

    async def run(
        self,
        max_rounds: int | None = None,
        bet_amount: float | None = None,
        mines_count: int | None = None,
        delay: float | None = None,
    ) -> BotStats:
        max_rounds = max_rounds or settings.max_rounds
        base_bet = bet_amount or settings.bet_amount
        mines = mines_count or settings.mines_count
        delay = delay or settings.bet_delay

        self.stats = BotStats(start_time=time.time())
        self._running = True

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self._stop)
        loop.add_signal_handler(signal.SIGTERM, self._stop)

        logger.info(
            "Bot started: strategy=%s base_bet=%.8f mines=%d max_rounds=%d delay=%.1fs",
            type(self.strategy).__name__, base_bet, mines, max_rounds, delay,
        )

        try:
            for i in range(max_rounds):
                if not self._running:
                    logger.info("Bot stopped by signal.")
                    break

                current_bet = self.strategy.next_bet_amount(
                    base_bet, self.stats.wins, self.stats.losses,
                )
                self.stats.total_wagered += current_bet

                try:
                    won = await self.play_round(current_bet, mines)
                except StakeAPIError as e:
                    logger.error("API error: %s", e)
                    await asyncio.sleep(delay * 3)
                    continue
                except httpx_errors():
                    logger.error("Network error, retrying after delay...")
                    await asyncio.sleep(delay * 5)
                    continue

                self.stats.total_rounds += 1
                if won:
                    self.stats.wins += 1
                    self.stats.total_profit += current_bet * (
                        settings.auto_cashout_multiplier - 1
                    )
                else:
                    self.stats.losses += 1
                    self.stats.total_profit -= current_bet

                self.stats.peak_profit = max(
                    self.stats.peak_profit, self.stats.total_profit,
                )

                if (i + 1) % 10 == 0:
                    logger.info("[%d/%d] %s", i + 1, max_rounds, self.stats.summary())

                await asyncio.sleep(delay)

        finally:
            await self.client.close()
            logger.info("Final: %s", self.stats.summary())

        return self.stats

    def _stop(self) -> None:
        logger.info("Stop signal received, finishing current round...")
        self._running = False


def httpx_errors():
    import httpx
    return (httpx.NetworkError, httpx.TimeoutException)
