import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GameState:
    mines_count: int
    revealed: list[int] = field(default_factory=list)
    current_multiplier: float = 1.0
    bet_amount: float = 0.0


class Strategy(ABC):
    @abstractmethod
    def pick_tile(self, state: GameState) -> int:
        """Choose which tile to reveal next (0-24 on a 5x5 grid)."""

    @abstractmethod
    def should_cashout(self, state: GameState) -> bool:
        """Decide whether to cash out at current multiplier."""

    @abstractmethod
    def next_bet_amount(self, base_amount: float, wins: int, losses: int) -> float:
        """Calculate the bet amount for the next round."""


class ConservativeStrategy(Strategy):
    """Low risk: reveals few tiles, cashes out early."""

    def __init__(self, max_reveals: int = 2, cashout_multiplier: float = 1.3):
        self.max_reveals = max_reveals
        self.cashout_multiplier = cashout_multiplier

    def pick_tile(self, state: GameState) -> int:
        available = [i for i in range(25) if i not in state.revealed]
        return random.choice(available)

    def should_cashout(self, state: GameState) -> bool:
        return (
            len(state.revealed) >= self.max_reveals
            or state.current_multiplier >= self.cashout_multiplier
        )

    def next_bet_amount(self, base_amount: float, wins: int, losses: int) -> float:
        return base_amount


class ModerateStrategy(Strategy):
    """Medium risk: reveals more tiles with a higher target."""

    def __init__(self, max_reveals: int = 4, cashout_multiplier: float = 2.0):
        self.max_reveals = max_reveals
        self.cashout_multiplier = cashout_multiplier

    def pick_tile(self, state: GameState) -> int:
        available = [i for i in range(25) if i not in state.revealed]
        return random.choice(available)

    def should_cashout(self, state: GameState) -> bool:
        return (
            len(state.revealed) >= self.max_reveals
            or state.current_multiplier >= self.cashout_multiplier
        )

    def next_bet_amount(self, base_amount: float, wins: int, losses: int) -> float:
        return base_amount


class AggressiveStrategy(Strategy):
    """High risk: reveals many tiles aiming for big multipliers."""

    def __init__(self, max_reveals: int = 7, cashout_multiplier: float = 4.0):
        self.max_reveals = max_reveals
        self.cashout_multiplier = cashout_multiplier

    def pick_tile(self, state: GameState) -> int:
        available = [i for i in range(25) if i not in state.revealed]
        return random.choice(available)

    def should_cashout(self, state: GameState) -> bool:
        return (
            len(state.revealed) >= self.max_reveals
            or state.current_multiplier >= self.cashout_multiplier
        )

    def next_bet_amount(self, base_amount: float, wins: int, losses: int) -> float:
        return base_amount


class MartingaleStrategy(Strategy):
    """Doubles bet after a loss, resets after a win."""

    def __init__(
        self,
        max_reveals: int = 3,
        cashout_multiplier: float = 1.5,
        max_double: int = 5,
    ):
        self.max_reveals = max_reveals
        self.cashout_multiplier = cashout_multiplier
        self.max_double = max_double
        self._consecutive_losses = 0

    def pick_tile(self, state: GameState) -> int:
        available = [i for i in range(25) if i not in state.revealed]
        return random.choice(available)

    def should_cashout(self, state: GameState) -> bool:
        return (
            len(state.revealed) >= self.max_reveals
            or state.current_multiplier >= self.cashout_multiplier
        )

    def next_bet_amount(self, base_amount: float, wins: int, losses: int) -> float:
        if losses > 0 and wins == 0:
            self._consecutive_losses = min(losses, self.max_double)
        elif wins > 0:
            self._consecutive_losses = 0
        return base_amount * (2 ** self._consecutive_losses)


class PatternStrategy(Strategy):
    """Reveals tiles in a fixed diagonal pattern to avoid clustering."""

    PATTERN = [0, 6, 12, 18, 24, 4, 8, 16, 20, 2, 10, 14, 22]

    def __init__(self, max_reveals: int = 4, cashout_multiplier: float = 2.0):
        self.max_reveals = max_reveals
        self.cashout_multiplier = cashout_multiplier

    def pick_tile(self, state: GameState) -> int:
        for tile in self.PATTERN:
            if tile not in state.revealed:
                return tile
        available = [i for i in range(25) if i not in state.revealed]
        return random.choice(available)

    def should_cashout(self, state: GameState) -> bool:
        return (
            len(state.revealed) >= self.max_reveals
            or state.current_multiplier >= self.cashout_multiplier
        )

    def next_bet_amount(self, base_amount: float, wins: int, losses: int) -> float:
        return base_amount


STRATEGIES: dict[str, type[Strategy]] = {
    "conservative": ConservativeStrategy,
    "moderate": ModerateStrategy,
    "aggressive": AggressiveStrategy,
    "martingale": MartingaleStrategy,
    "pattern": PatternStrategy,
}


def get_strategy(name: str) -> Strategy:
    cls = STRATEGIES.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(STRATEGIES)}")
    return cls()
