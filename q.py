import time
import json
from typing import List, Optional

# Constants for trading operations
LONG = "long"
SHORT = "short"

BUY = "buy"
SELL = "sell"
UPDATE = "update"

LIMIT = "limit"
MARKET = "market"
STOP = "stop"
STOP_LOSS = "stop_loss"
TRAILING_STOP = "trailing_stop"
TAKE_PROFIT = "take_profit"

CREATED = "created"
IMMEDIATE = "immediate"
PENDING = "pending"

OPEN = "open"
CLOSED = "closed"


class Fee:
    """
    Represents a fee associated with a trade or order.

    Attributes:
        type (str): The type of fee (e.g., "commission" or "flat").
        value (float): The fee value.
    """

    def __init__(self, type: str = "commission", value: float = 0.0004):
        self.type: str = type
        self.value: float = value

    def calculate(self, size: float, price: float) -> float:
        """
        Calculates the fee based on the specified size and price.

        Args:
            size (float): The size of the trade or order.
            price (float): The price of the trade or order.

        Returns:
            float: The calculated fee amount.
        """
        if self.type == "commission":
            return size * price * self.value
        elif self.type == "flat":
            return self.value
        else:
            raise ValueError(f"Invalid fee type: {self.type}")


class Calculations:
    """Calculations for trade and order size, price, and margin"""

    @staticmethod
    def gap_size(value1: float, value2: float) -> float:
        _max = max(value1, value2)
        _min = min(value1, value2)
        return _max - _min if _min > 0 or _max < 0 else abs(_min) + _max

    @staticmethod
    def profit(size, entry_price: float, exit_price: float) -> float:
        return (exit_price / entry_price - 1) * size

    @staticmethod
    def margin(size: float, price: float, leverage: float) -> float:
        return abs(size) * price / leverage

    @staticmethod
    def profit_factor(avg_win: float, avg_loss: float) -> float:
        return avg_win / avg_loss

    @classmethod
    def net_profit(
        cls, size: float, entry_price: float, exit_price: float, fee: Fee
    ) -> float:
        return (exit_price - entry_price) * size - fee.calculate(size, exit_price)

    @staticmethod
    def scaled_sizes(
        total_size: float,
        count: int,
        weight: float,
        min_size: float,
        as_percent: bool = False,
    ) -> List[float]:
        sizes = [total_size / count] * count
        sizes = [max(min_size, sizes[i] * weight ** (i + 1)) for i in range(len(sizes))]
        total = sum(sizes)
        return [size / total * (1 if as_percent else total_size) for size in sizes]

    @classmethod
    def scaled_targets(
        cls, count: int, weight: float, minimum: float, maximum: float
    ) -> List[float]:
        split = cls.scaled_sizes(cls.gap_size(maximum, minimum), count - 1, weight, 0)
        targets = [0.0] * count
        for i in range(count):
            targets[i] = minimum + sum(split[:i])
        return targets


class Funds:
    # The Funds class is used to keep track of the current balance, equity, open profit, pending fees,
    # margin, pending margin and margin level of the Funds
    def __init__(self, initial: float = 1000.0):
        self.currency: str = "USD"  # the currency of the Funds
        self.balance: float = initial  # the initial balance of the Funds
        self.equity: float = initial  # the current equity of the Funds
        self.open_profit: float = 0.0  # the current open profit of the Funds
        self.pending_fees: float = 0.0  # the current pending fees of the Funds
        self.margin: float = 0.0  # the current margin of the Funds
        self.pending_margin: float = (
            0.0  # the current pending margin of opened orders not executed yet
        )
        self.margin_level: float = 0.0  # the current margin level in percentage
        self.commission_paid: float = 0.0  # the total commission paid by the Funds


class Tracking:
    def __init__(self):
        self.note: str = ""
        self.starting_balance: float = 0.0
        self.current_balance: float = 0.0
        self.peak_balance: float = 0.0
        self.low_balance: float = 0.0
        self.open_trades: int = 0
        self.total_trades: int = 0
        self.total_winning_trades: int = 0
        self.total_losing_trades: int = 0
        self.max_consecutive_wins: int = 0
        self.max_consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.consecutive_losses: int = 0
        self.gross_profit: float = 0.0
        self.gross_loss: float = 0.0
        self.avg_win: float = 0.0
        self.avg_loss: float = 0.0
        self.avg_profit_per_trade: float = 0.0
        self.win_loss_ratio: float = 0.0
        self.profit_factor: float = 0.0
        self.commission_paid: float = 0.0
        self.max_draw_down: float = 0.0
        self.max_run_up: float = 0.0
        self.net_profit: float = 0.0
        self.percent_profitable: float = 0.0
        self.price : float = 0.0

    def __str__(self):
        return str(self.__dict__)


class Config:
    # A container for all the settings that are used by a Strategy
    """
    Configuration class for the Strategy

    This class contains all the settings that are used by a Strategy. It is used to store the settings that are used by
    the Strategy to make decisions about when to open and close trades. The settings are used to determine the size of the
    trades, the take profit and stop loss levels, and other parameters that are used to manage the risk and reward of the
    trades.

    Args:
        manager: The Strategy that this config belongs to
    """

    def __init__(
        self,
        symbol: str = "BTCUSDT",  # the symbol of the market
        initial_equity: float = 1000.0,  # the initial equity of the Funds
        initial_wallet: float = 1000.0,  # the initial wallet of the Funds
    ):
        # take profit settings
        self.symbol: str = symbol
        self.initial_equity: float = initial_equity
        self.initial_wallet: float = initial_wallet
        self.tp_enabled: bool = True  # enable the take profit by default
        self.tp_targets_count: int = (
            1  # the default number of targets to split take profit
        )
        self.tp_start: float = (
            0.005  # the default first percentage of the take profit steps (0-1)
        )
        self.tp_end: float = (
            0.01  # the default furthest percentage of the take profit steps (0-1)
        )
        self.tp_dist_weight: float = (
            0.5  # the weight of the distance from the first take profit to the last one
        )
        self.tp_size_weight: float = (
            0.5  # the weight of the size of the first take profit to the last one
        )
        self.tp_size_total: float = (
            1.0  # the percentage of the position size to be used for take profit
        )

        # stop loss settings
        self.sl_enabled: bool = True  # enable the stop loss by default
        self.sl_trig_dist: float = (
            0.005  # the distance from the entry price to activate the stop loss
        )
        self.sl_dist: float = (
            0.02  # the distance from the entry price to activate the stop loss
        )

        self.sl_trail_enabled: bool = True  # enable the trailing stop loss by default
        self.sl_trail_trig_dist: float = 0.005  # the distance from the entry price to activate the trailing stop loss
        self.sl_trail_dist: float = 0.005  # the call back percentage from the peak to execute the trailing stop loss

        # order settings
        self.ord_max_type: str = "usd"  # the type of the maximum (usd or percent of available balance or units) for an order
        self.ord_max_usd: float = (
            1000.0  # setting for the maximum USD amount for a single order
        )
        self.ord_max_units: float = (
            1.0  # setting for the maximum amount for a single order
        )
        self.ord_max_pct: float = (
            100.0  # setting for the maximum percent of equity amount for a single order
        )
        self.ord_max: float = (
            self.set_max_order()
        )  # the maximum amount for a single order

        # position settings
        self.position_max_type: str = "usd"  # the type of the maximum (usd or percent of available balance) for a position
        self.position_max_usd: float = (
            1000.0  # setting for the maximum USD amount for a single Position
        )
        self.position_max_pct: float = (
            1000.0  # setting for the maximum amount for a single Position
        )
        self.position_max_units: float = 1000.0  # setting for the maximum percent of equity amount for a single Position
        self.position_max: float = (
            self.set_max_order()
        )  # the maximum amount for a single order

        # default order settings
        self.default_type: str = "usd"  # the type of the default (usd or percent of available balance or units) for an order
        self.default_usd: float = (
            1000.0  # setting for the default USD amount for a single order
        )
        self.default_units: float = (
            1.0  # setting for the default amount for a single order
        )
        self.default_pct: float = (
            100.0  # setting for the default percent of equity amount for a single order
        )
        self.default_size: float = (
            self.set_default_order()
        )  # the default amount for a single order

        # trade settings
        self.leverage: float = (
            1.0  # the default leverage (1.0 forced if spot, no shorting)
        )
        self.hedge_mode: bool = False  # the default hedge mode (spot is always false)
        self.ord_minimum_usd: float = (
            10.0  # the minimum amount for a single open order in USD
        )
        self.ord_minimum_size: float = (
            10.0  # the minimum amount for a single open order in USD
        )
        self.risk: float = 0.05  # the default risk percentage (0-1)
        self.slippage: float = 0.0001  # the default slippage percentage (0-1)
        self.taker_fee: Fee = Fee()  # the default taker fee
        self.maker_fee: Fee = Fee(value=0.0002)  # the default maker fee

    def set_max_order(self, price: Optional[float] = None, funds_equity=None) -> float:
        """
        If the order max type is "usd", return the order max usd. If the order max type is "percent", return
        the order max percent. If the order max type is "units", return the order max units. Otherwise,
        return 0.0
        :  return: The value of the order max type.
        """
        if price is None:
            price = 0.0
        if price == 0.0:
            return 0.0
        if self.ord_max_type == "usd":
            self.ord_max_pct = self.ord_max_usd / self.initial_equity * 100
            self.ord_max_units = self.ord_max_usd / price
            return self.ord_max_usd

        if self.ord_max_type == "percent":
            self.ord_max_usd = (
                self.ord_max_pct / 100 * funds_equity
                if funds_equity is not None
                else 0.0
            )
            self.ord_max_units = self.ord_max_usd / price
            return self.ord_max_pct

        if self.ord_max_type == "units":
            self.ord_max_usd = self.ord_max_units * price
            self.ord_max_pct = self.ord_max_usd / self.initial_equity * 100
            return self.ord_max_units

        return 0.0

    def set_default_order(
        self, price: Optional[float] = None, funds_equity=None
    ) -> float:
        """
        Calculate from config and return the default order size for the strategy.
        :  return: The default order size for the strategy.
        """
        if price is None:
            price = 0.0
        if price == 0.0:
            return 0.0
        if self.default_type == "usd":
            self.default_pct = self.default_usd / self.initial_equity * 100
            self.default_units = self.default_usd / price
            return self.default_usd
        if self.default_type == "percent":
            self.default_usd = (
                self.default_pct / 100 * funds_equity
                if funds_equity is not None
                else 0.0
            )
            self.default_units = self.default_usd / price
            return self.default_pct
        if self.default_type == "units":
            self.default_usd = self.default_units * price
            self.default_pct = self.default_usd / self.initial_equity * 100
            return self.default_units
        return 0.0

    def set_max_position(
        self, price: Optional[float] = None, funds_equity=None
    ) -> float:
        """
        Calculate from config and return the maximum position size for the strategy.
        :  return: The maximum position size for the strategy.
        """
        if price is None:
            price = 0.0
        if price == 0.0:
            return 0.0
        if self.position_max_type == "usd":
            self.position_max_pct = self.position_max_usd / self.initial_equity * 100
            self.position_max_units = self.position_max_usd / price
            return self.position_max_usd
        if self.position_max_type == "percent":
            self.position_max_usd = (
                self.position_max_pct / 100 * funds_equity
                if funds_equity is not None
                else 0.0
            )
            self.position_max_units = self.position_max_usd / price
            return self.position_max_pct
        if self.position_max_type == "units":
            self.position_max_usd = self.position_max_units * price
            self.position_max_pct = self.position_max_usd / self.initial_equity * 100
            return self.position_max_units

        return 0.0


class Data:
    def __init__(
        self, size: float, price: float, direction: str, comment: str, **kwargs
    ):
        self.size: float = size
        self.direction: str = direction
        self.commission: float = 0.0
        self.entry_bar_index: int = 0
        self.entry_comment: str = comment
        self.entry_id: str = ""
        self.entry_price: float = price
        self.entry_time: float = time.time()
        self.exit_bar_index: int = 0
        self.exit_comment: str = ""
        self.exit_id: str = ""
        self.exit_price: float = 0.0
        self.exit_time: float = 0.0
        self.gross_profit: float = 0.0
        self.gross_loss: float = 0.0
        self.net_profit: float = 0.0
        self.open_fees: float = 0.0
        self.open_profit: float = 0.0
        self.max_draw_down: float = 0.0
        self.max_run_up: float = 0.0
        self.exit_type: str = ""

        self.__dict__.update(kwargs)


class Order:
    def __init__(
        self,
        symbol: str,
        config: Config,
        order_id: Optional[str] = None,
        direction: str = LONG,
        side: str = BUY,
        type: str = MARKET,
        size: Optional[float] = None,
        price: Optional[float] = None,
        leverage: Optional[float] = None,
        funds_equity: Optional[float] = None,
    ) -> None:
        self.symbol = symbol
        self.comment: str = "Order"
        self.side: str = side
        self.direction: str = direction
        self.id: str = order_id or ""
        self.leverage: float = config.leverage if leverage is None else leverage
        self.price: float = price if price is not None else 0.0
        self.size: float = (
            size or config.default_size / 100 * config.initial_wallet
            if size is not None
            else 0.0
        )

        self.value: float = self.size * self.price
        self.margin: float = self.get_margin()
        self.sl_dist: Optional[float] = config.sl_dist if config.sl_enabled else None
        self.fee: Fee = config.maker_fee if type == LIMIT else config.taker_fee
        self.time: float = time.time()
        self.order_type: str = MARKET if type is None else type
        self.status: str = IMMEDIATE if self.order_type == MARKET else PENDING

        self.te_active: bool = False
        self.te_enabled: bool = False
        self.te_trigger_dist: Optional[float] = None
        self.te_callback_dist: Optional[float] = None
        self.peak_price: Optional[float] = None

        self.sl_trig_dist: Optional[float] = None
        self.tp_targets: Optional[List[float]] = None
        self.tp_start: Optional[float] = None
        self.tp_end: Optional[float] = None
        self.tp_dist_weight: Optional[float] = None
        self.tp_size_pct: Optional[float] = None
        self.tp_size_weight: Optional[float] = None
        self.sl_trail_dist: Optional[float] = None
        self.sl_trail_trig_dist: Optional[float] = None

    def update_order(self, price: float) -> None:
        if self.status != PENDING:
            return
        if self.order_type == LIMIT:
            if (
                self.side == BUY
                and price <= self.price
                or self.side == SELL
                and price >= self.price
            ):
                self.status = IMMEDIATE

        elif self.order_type == TRAILING_STOP:
            if self.side == BUY:
                self.te_active = (
                    True
                    if self.te_active
                    else price < self.te_trigger_dist
                    if self.te_trigger_dist
                    else False
                )
                self.peak_price = min(self.peak_price or price, price)
                if self.te_active and price >= self.peak_price * (
                    1 + (self.te_callback_dist or 0)
                ):
                    self.status = IMMEDIATE
            else:
                self.te_active = (
                    True
                    if self.te_active
                    else price > self.te_trigger_dist
                    if self.te_trigger_dist
                    else False
                )
                self.peak_price = max(self.peak_price or price, price)
                if self.te_active and price <= self.peak_price * (
                    1 - (self.te_callback_dist or 0)
                ):
                    self.status = IMMEDIATE

    def get_margin(self) -> float:
        return 1 / self.leverage * self.value

    def max_size(self, price: float, funds_balance: float) -> float:
        return funds_balance

    def __bool__(self) -> bool:
        return self.status == PENDING


class Trade:
    """
    Represents a trade in a trading system.

    Attributes:
        pair (Pair)      : The trading pair associated with the trade.
        id (str)       : The unique identifier of the trade.
        direction (str)     : The direction of the trade (e.g., "long" or "short").
        size (float)      : The size of the trade.
        price (float)      : The entry price of the trade.
        leverage (float)     : The leverage used for the trade.
        sl_dist (float)     : The stop loss distance for the trade.
        sl_trig_dist (float)  : The stop loss trigger distance for the trade.
        tp_targets (int)     : The number of take profit targets for the trade.
        tp_start (float)     : The starting price for calculating take profit targets.
        tp_end (float)     : The ending price for calculating take profit targets.
        tp_dist_weight (float) : The weight for calculating take profit target distances.
        tp_size_pct (float)    : The percentage of trade size to use for calculating take profit sizes.
        tp_size_weight (float) : The weight for calculating take profit sizes.
        sl_trail_dist (float)  : The trailing stop distance for the trade.
        sl_trail_trig_dist (float): The trailing stop trigger distance for the trade.
        comment (str)      : Additional comment or description for the trade.
    """

    def __init__(
        self,
        symbol: str,
        config: Config,
        funds: Funds,
        tracking: Tracking,
        id: Optional[str] = None,
        direction: str = LONG,
        size: Optional[float] = None,
        price: Optional[float] = None,
        leverage: Optional[float] = None,
        sl_dist: Optional[float] = None,
        sl_trig_dist: Optional[float] = None,
        tp_targets: int = 1,
        tp_start: Optional[float] = None,
        tp_end: Optional[float] = None,
        tp_dist_weight: float = 1.0,
        tp_size_pct: float = 1.0,
        tp_size_weight: float = 1.0,
        sl_trail_dist: Optional[float] = None,
        sl_trail_trig_dist: Optional[float] = None,
        comment: str = "",
        ) -> None:
        """
        Initializes a new instance of the Trade class.

        Args:
        pair (Pair): The trading pair associated with the trade.
        id (str): The unique identifier of the trade.
        direction (str): The direction of the trade (e.g., "long" or "short").
        size (float): The size of the trade.
        price (float): The entry price of the trade.
        leverage (float): The leverage used for the trade.
        sl_dist (float): The stop loss distance for the trade.
        sl_trig_dist (float): The stop loss trigger distance for the trade.
        tp_targets (int): The number of take profit targets for the trade.
        tp_start (float): The starting price for calculating take profit targets.
        tp_end (float): The ending price for calculating take profit targets.
        tp_dist_weight (float): The weight for calculating take profit target distances.
        tp_size_pct (float): The percentage of trade size to use for calculating take profit sizes.
        tp_size_weight (float): The weight for calculating take profit sizes.
        sl_trail_dist (float): The trailing stop distance for the trade.
        sl_trail_trig_dist (float): The trailing stop trigger distance for the trade.
        comment (str, optional): Additional comment or description for the trade. Defaults to "".
        """
        self.symbol = symbol
        self.calc: Calculations = Calculations()
        self.config: Config = config
        self.tracking: Tracking = tracking
        self.funds: Funds = funds
        self.calc: Calculations = Calculations()
        self.id: str = id or ""
        self.entry_price: float = price or 0.0
        self.size: float = size or 0.0
        self.value: float = self.size * self.entry_price
        self.leverage: float = leverage or self.config.leverage
        self.taker_fee: Fee = self.config.taker_fee
        self.margin: float = self.calc_margin(
            self.size, self.leverage, self.entry_price
        )
        self.open_fees: float = self.calc_open_fee(
            self.size, self.entry_price, self.config.maker_fee
        )
        self.direction: str = direction
        self.status: str = "open"
        self.comment: str = comment
        self.tp_dist_weight: float = tp_dist_weight
        self.set_tp(
            tp_targets, tp_start, tp_end, tp_dist_weight, tp_size_pct, tp_size_weight
        )
        self.sl_enabled: bool = (
            sl_dist is not None and sl_dist > 0 or self.config.sl_enabled
        )
        self.sl_dist: float = sl_dist or self.config.sl_dist if self.sl_enabled else 0.0
        self.sl_trigger_pct: float = (
            sl_trig_dist or self.config.sl_trig_dist if self.sl_enabled else 0.0
        )
        self.sl_activated: bool = not self.sl_trigger_pct
        self.sl_trail_enabled: bool = self.config.sl_trail_enabled
        self.sl_trail_trigger: Optional[float] = (
            sl_trail_trig_dist or self.config.sl_trail_trig_dist
            if self.sl_trail_enabled
            else None
        )
        self.sl_trail_activated: bool = not self.sl_trail_trigger
        self.sl_trail_dist: Optional[float] = (
            sl_trail_dist or self.config.sl_trail_dist
            if self.sl_trail_enabled
            else None
        )
        self.sl_trail_peak: Optional[float] = (
            self.entry_price if self.sl_trail_activated else None
        )
        self.data: Data = Data(
            self.size, self.entry_price, self.direction, self.comment
        )

    def calc_open_fee(self, size: float, price: float, fee: Fee) -> float:
        """
        Calculates the open fee for the trade.

        Args:
            size (float): The size of the trade.
            price (float): The price of the trade.
            fee (Fee): The fee object.

        Returns:
            float: The open fee for the trade.
        """

        return fee.calculate(size, price)

    def set_tp(
        self,
        tp_targets: int,
        tp_start: Optional[float],
        tp_end: Optional[float],
        tp_dist_weight: float = 1.0,
        tp_size_pct: float = 1.0,
        tp_size_weight: float = 1.0,
        ) -> None:
        """
        Sets the take profit (TP) parameters for the trade.

        Args:
            tp_targets (int): The number of TP targets.
            tp_start (float): The starting TP value.
            tp_end (float): The ending TP value.
            tp_dist_weight (float, optional): The weight for TP distance. Defaults to 1.
            tp_size_pct (float, optional): The percentage of trade size for TP. Defaults to 1.
            tp_size_weight (float, optional): The weight for TP size. Defaults to 1.
        """
        self.tp_size_pct: float = tp_size_pct
        self.tp_enabled: bool = bool((tp_targets > 1 or self.config.tp_enabled))
        self.tp_targets_count: int = (
            max(1, tp_targets or self.config.tp_targets_count)
            if self.tp_enabled and self.config.tp_targets_count > 0
            else 0
        )
        self.tp_start: Optional[float] = (
            (tp_start or self.config.tp_start) if self.tp_enabled else None
        )
        self.tp_end: Optional[float] = (
            tp_end or self.config.tp_end if self.tp_enabled else None
        )
        self.tp_dist_weight: float = (
            self.tp_dist_weight if self.tp_enabled and self.config.tp_start else 0.0
        )
        self.tp_targets: Optional[List[float]] = (
            self.calc_tp_targets() if self.tp_enabled else None
        )
        self.tp_size_total: float = (
            -self.size * self.tp_size_pct if self.tp_enabled else 0.0
        )
        self.tp_size_weight: float = (
            (
                -self.size
                * self.tp_size_pct
                * (tp_size_weight or self.config.tp_size_weight)
            )
            if self.tp_enabled
            else 0.0
        )
        self.tp_sizes: Optional[List[float]] = (
            self.calc_tp_sizes() if self.tp_enabled else None
        )

    def calc_tp_targets(self) -> List[float]:
        """
        Calculates the take profit target prices for the trade.

        Returns:
            List[float]: A list of take profit target prices.
        """
        if self.tp_start is not None and self.tp_end is not None:
            return self.calc.scaled_targets(
                self.tp_targets_count, self.tp_dist_weight, self.tp_start, self.tp_end
            )
        return []

    def calc_size(self) -> float:
        return self.size

    def calc_profit(self, price: float) -> float:
        self.data.open_profit = (price / self.entry_price - 1) * self.value
        return self.data.open_profit

    def calc_tp_sizes(self) -> List[float]:
        """
        Calculates the take profit sizes for the trade.

        Returns:
            List[float]: A list of take profit sizes.
        """

        return self.calc.scaled_sizes(
            self.tp_size_total,
            self.tp_targets_count,
            self.tp_size_weight,
            self.config.ord_minimum_size,
        )

    def update_max_draw_down(self, price: float) -> float:
        """
        Updates the maximum drawdown for the trade.

        Args:
            price (float): The current price.

        Returns:
            float: The maximum drawdown for the trade.
        """

        self.data.max_draw_down = (
            min(self.data.max_draw_down, self.calc_profit(price)) / self.value
        )
        return self.data.max_draw_down

    def update_max_runup(self, price: float) -> float:
        """
        Updates the maximum runup for the trade.

        Args:
            price (float): The current price.

        Returns:
            float: The maximum runup for the trade.
        """

        self.data.max_run_up = (
            max(self.data.max_run_up, self.calc_profit(price)) / self.value
        )
        return self.data.max_run_up

    def get_fees(self, price: float) -> float:
        """
        Calculates the fees for the trade.

        Args:
        price (float): The price of the trade.

        Returns:
        float: The fees for the trade.
        """

        self.data.open_fees = self.taker_fee.calculate(self.size, price)
        return self.data.open_fees


    def trade_close_finalize(self, comment: Optional[str] = None) -> None:
        """
         Finalizes the closing of the trade.
        comment (str, optional): Additional comment or description for the trade close. Defaults to None.
        """
        self.data.exit_bar_index= 0
        self.data.exit_comment  = comment or ""
        self.data.exit_id       = self.data.entry_id or ""
        self.data.exit_price    = self.tracking.price
        self.data.exit_time     = time.time()
        self.status             = "closed"

    def size_gte_trade(self, trade_size: float) -> float:
        """
        Checks if the trade size is greater than or equal to the trade size.

        Args:
          trade_size (float): The size of the trade.

        Returns:
          float: The absolute value of the trade size.
        """

        return trade_size * self.size < 0 and abs(self.size) <= abs(trade_size)

    # def update_data(self, price: float) -> None:

    def close_trade_calc(self, size: float, price: float, close_type: str, comment: str ) -> float:
        """
        Calculates the close trade parameters.

        Args:
            size (float): The size of the trade.
            close_type (str): The type of close (e.g., "market" or "limit").
            comment (str): Additional comment or description for the trade close.

        Returns:
            float: The remaining size after closing the trade.
        """
        market_order    = close_type== MARKET
        fee_percent     = self.config.taker_fee if market_order else self.config.maker_fee
        close_amount    = min(abs(size), abs(self.size)) * abs(size) / size
        close_is_total  = self.size_gte_trade(close_amount)
        close_profit    = (price - self.entry_price) * close_amount
        close_commission= abs(close_amount * price * fee_percent.value)
        close_net_profit= close_profit - close_commission
        close_margin    = (close_amount * self.entry_price) / self.leverage

        # Correctly update gross profit/loss in the Data object
        if close_profit > 0:
            self.data.gross_profit += close_profit
        else:
            self.data.gross_loss += -close_profit # Add as a positive value

        self.data.net_profit+= close_net_profit
        self.data.commission+= close_commission
        self.funds.equity   += close_net_profit
        self.funds.margin   -= close_margin
        self.funds.balance  += close_margin + close_net_profit
        self.size           -= close_amount
        self.value          =  self.size * self.entry_price
        self.margin         =  self.value / self.leverage

        if close_is_total:
            self.data.exit_type = close_type
            self.trade_close_finalize(comment)
        return 0.0 if close_is_total else abs(size) - abs(close_amount)


    def open_trade_calc(self, size: float, price: float, comment: str) -> None:
        """
        Calculates the open trade parameters.

        Args:
          size (float): The size of the trade.
          price (float): The price of the trade.
          comment (str): Additional comment or description for the trade open.
        """

        self.size = size
        self.value = self.size * price
        self.margin = self.value / self.leverage
        self.data.entry_price = price
        self.data.entry_time = time.time()
        self.data.entry_comment = comment
        self.data.entry_id = self.id

        self.status = "open"

    def get_targets(self) -> List[float]:
        """
        Gets the take profit target prices for the trade.

        Returns:
          List[float]: A list of take profit target prices.
        """
        if self.tp_start and self.tp_end:
            return self.calc.scaled_targets(
                self.tp_targets_count, self.tp_dist_weight, self.tp_start, self.tp_end
            )
        return []

    def get_profit(self, price: float) -> float:
        """
        Calculates the profit for the trade.

        Args:
          price (float): The current price.

        Returns:
          float: The profit for the trade.
        """
        self.profit: float = (price / self.entry_price - 1) * self.value
        return self.profit

    def calc_margin(self, size: float, leverage: float, entry_price: float) -> float:
        """
        Calculates the margin for the trade.

        Args:
          size (float): The size of the trade.
          leverage (float): The leverage used for the trade.
          entry_price (float): The entry price of the trade.

        Returns:
          float: The margin for the trade.
        """
        return abs(size) * entry_price / leverage

    def update(self, price: float):
        if self.status != "open":
            return
        self.update_max_draw_down(price)
        self.update_max_runup(price)
        self.calc_profit(price)

        if self.sl_trail_enabled and self.sl_trail_dist:
            self.update_sl_trail(price)

        if (
            self.tp_targets
            and self.tp_enabled
            and (
                (self.size > 0 and price > self.tp_targets[0])
                or (self.size <= 0 and price < self.tp_targets[0])
            )
        ):
            self.close_trade_calc(self.tp_size_total, price, TAKE_PROFIT, "take profit")
            self.tp_targets.pop(0)

        if self.sl_enabled and (
            (self.size > 0 and price < self.entry_price * (1 - self.sl_dist))
            or (self.size <= 0 and price > self.entry_price * (1 + self.sl_dist))
        ):
            self.close_trade_calc(self.size, price, TRAILING_STOP, "trailing stop")

    def update_sl_trail(self, price: float) -> None:
        trigger_condition: bool = (
            (price > self.entry_price * (1 + self.sl_trigger_pct))
            if self.size > 0
            else (price < self.entry_price * (1 - self.sl_trigger_pct))
        )
        self.sl_trail_activated = self.sl_trail_activated or trigger_condition
        self.sl_trail_peak = (
            max(self.sl_trail_peak or price, price)
            if self.size > 0
            else min(self.sl_trail_peak or price, price)
        )
        if (
            self.sl_trail_activated
            and self.sl_trail_dist
            and (
                (price < self.sl_trail_peak * (1 - self.sl_trail_dist))
                if self.size > 0
                else (price > self.sl_trail_peak * (1 + self.sl_trail_dist))
            )
        ):
            self.close_trade_calc(self.size, price, TRAILING_STOP, "trailing stop")

    def update_on_trade(self) -> None:
        """
        Updates the trade tracker after a trade is closed.
        """
        self.tracking.total_trades += 1
        if self.data.net_profit > 0:
            self.tracking.total_winning_trades += 1
            self.tracking.consecutive_wins += 1
            self.tracking.consecutive_losses = 0  # Reset consecutive losses
        else:
            self.tracking.total_losing_trades += 1
            self.tracking.consecutive_losses += 1
            self.tracking.consecutive_wins = 0  # Reset consecutive wins

        self.tracking.gross_profit += max(0.0, self.data.gross_profit)
        self.tracking.gross_loss += min(0.0, self.data.gross_loss)
        self.tracking.commission_paid += self.data.commission
        self.tracking.net_profit += self.data.net_profit

        self.tracking.percent_profitable = (
            self.tracking.total_winning_trades / self.tracking.total_trades
        )
        self.tracking.max_consecutive_wins = max(
            self.tracking.max_consecutive_wins, self.tracking.consecutive_wins
        )
        self.tracking.max_consecutive_losses = max(
            self.tracking.max_consecutive_losses, self.tracking.consecutive_losses
        )
        self.tracking.avg_win = (
            self.tracking.gross_profit / self.tracking.total_winning_trades
            if self.tracking.total_winning_trades > 0
            else 0.0
        )
        self.tracking.avg_loss = (
            self.tracking.gross_profit / self.tracking.total_losing_trades
            if self.tracking.total_losing_trades > 0
            else 0.0
        )
        self.tracking.avg_profit_per_trade = (
            self.tracking.net_profit / self.tracking.total_trades
        )
        self.tracking.win_loss_ratio = (
            self.tracking.total_winning_trades / self.tracking.total_losing_trades
            if self.tracking.total_losing_trades > 0
            else 0.0
        )
        self.tracking.profit_factor = (
            self.tracking.avg_win / self.tracking.avg_loss
            if self.tracking.avg_loss > 0
            else 0.0
        )
        self.tracking.current_balance = (
            self.tracking.starting_balance + self.tracking.net_profit
        )
        self.tracking.peak_balance = max(
            self.tracking.peak_balance, self.tracking.current_balance
        )
        self.tracking.low_balance = min(
            self.tracking.low_balance, self.tracking.current_balance
        )


class Strategy:
    def __init__(self, config: Config, funds: Funds, tracking: Tracking):
        self.price: float = 0.0
        self.config: Config = config
        self.funds: Funds = funds
        self.tracking: Tracking = tracking
        self.closed_trades: List[Trade] = []
        self.open_trades: List[Trade] = []
        self.open_orders: List[Order] = []
        self.bar_index: int = 0
        self.order_ids: int = 0
        self.trade_ids: int = 0

    def update_funds(self) -> None:
        """
        Update the funds object with the current state of the account
        """
        trades: List[Trade] = self.open_trades
        if len(self.open_trades) > 0:
            self.funds.pending_fees = sum(
                t.taker_fee.calculate(abs(t.size), self.price) for t in trades
            )
            self.funds.margin = sum(t.margin for t in trades)
            self.funds.open_profit = sum(
                t.size * (self.price - t.entry_price) for t in trades
            )
        if len(self.open_orders) > 0:
            self.funds.pending_margin = sum(o.margin for o in self.open_orders)
        self.funds.balance = (
            self.funds.open_profit
            + self.funds.equity
            - (self.funds.pending_fees + self.funds.margin + self.funds.pending_margin)
        )
        self.funds.margin_level = (
            1 - (self.funds.equity - self.funds.margin) / self.funds.equity
            if self.funds.equity > 0
            else 0
        )

    def max_draw_down(self) -> float:
        trades: List[Trade] = self.open_trades
        self.tracking.max_draw_down = min(
            self.tracking.max_draw_down,
            sum(t.calc_profit(self.price) for t in trades),
        )
        return self.tracking.max_draw_down

    def max_run_up(self) -> float:
        trades: List[Trade] = self.open_trades
        self.tracking.max_run_up = max(
            self.tracking.max_draw_down,
            sum(t.calc_profit(self.price) for t in trades),
        )
        return self.tracking.max_run_up

    def avg_win(self) -> float:
        """returns the average win amount, adds up win amounts of winning trades from closed trades
        and divides by the number of wins"""
        wins: int = 0
        win_amount: float = 0.0
        for trade in self.closed_trades:
            prof: float = trade.data.net_profit
            wins += 1 if prof > 0 else 0
            win_amount += max(prof, 0)
        return win_amount / wins if wins > 0 else 0

    def avg_loss(self) -> float:
        """returns the average loss amount, adds up loss amounts of losing trades from closed trades
        and divides by the number of losses"""
        losses: int = 0
        loss_amount: float = 0.0
        for trade in self.closed_trades:
            prof: float = trade.data.net_profit
            losses += 1 if prof < 0 else 0
            loss_amount += min(prof, 0)
        return loss_amount / losses if losses > 0 else 0

    def win_loss_ratio(self) -> float:
        return (
            self.avg_win() / self.avg_loss()
            if self.avg_win() > 0 and self.avg_loss() > 0
            else 0.0
        )

    def restrict_size(self, size: float, price: float, leverage: float) -> float:
        """Restrict the size of an order to the max order allowed by the config and within position max size"""
        # convert size to usd for max_position_size and get the lesser of the difference or the size limit
        self.config.set_max_position(price, self.funds.equity)
        self.config.set_default_order(price, self.funds.equity)
        self.config.set_max_order(price, self.funds.equity)
        requested_size_usd: float = abs(size * price)
        margin_funds_available: float = self.funds.balance
        max_entry_margin_usd: float = (
            max(
                0.0,
                min(
                    self.config.ord_max_usd / leverage,
                    self.config.position_max_usd / leverage - self.funds.margin,
                    margin_funds_available,
                    requested_size_usd,
                ),
            )
            * leverage
        )
        max_funds_net_fee: float = max_entry_margin_usd * (
            1 - self.config.taker_fee.value
        )
        return max_funds_net_fee / price

    def update_tracking_on_close(self, trade: Trade) -> None:
        """
        update tracking on close of trade

            current_balance
            peak_balance
            low_balance
            open_trades
            total_trades
            total_winning_trades
            total_losing_trades
            max_consecutive_wins
            max_consecutive_losses
            consecutive_wins
            consecutive_losses
            gross_profit
            gross_loss
            avg_win
            avg_loss
            avg_profit_per_trade
            win_loss_ratio
            profit_factor
            commission_paid
            max_draw_down
            max_run_up
            net_profit
            percent_profitable
            net_returns

        """
        self.tracking.max_draw_down = max(
            self.tracking.max_draw_down, trade.data.net_profit
        )
        self.tracking.max_run_up = max(self.tracking.max_run_up, trade.data.net_profit)
        self.tracking.gross_profit += trade.data.gross_profit
        self.tracking.gross_loss += trade.data.gross_loss
        self.tracking.net_profit += trade.data.net_profit

    def update_trades(self, price) -> None:
        self.price = price
        trades: list[Trade] = self.open_trades

        for t in trades:
            t.update(self.price)
            if t.status == "closed":
                self.closed_trades.append(t)
                self.open_trades.remove(t)

        self.funds.open_profit = sum(t.calc_profit(self.price) for t in trades)
        self.funds.pending_fees = sum(t.get_fees(self.price) for t in trades)

    def update_orders(self) -> None:
        ids: List[str] = [t.id for t in self.open_trades]
        long_trades: List[Trade] = [t for t in self.open_trades if t.direction == LONG]
        short_trades: List[Trade] = [
            t for t in self.open_trades if t.direction == SHORT
        ]
        for o in self.open_orders:
            id_match: bool = o.id in ids
            direction: str = o.direction

            if o.status == PENDING:
                o.update_order(self.price)
            if o.status == IMMEDIATE:
                if id_match:
                    if (
                        direction == LONG
                        and long_trades
                        or direction == SHORT
                        and short_trades
                    ):
                        self.execute_order(o)
                elif (direction == LONG and not long_trades) or (
                    direction == SHORT and not short_trades
                ):
                    self.open_new_from_order(o)
            if o.status == "failed":
                self.cancel(o.id)

    def update_tracker(self) -> None:
        tracker: Tracking = self.tracking
        self.tracking.current_balance = self.funds.balance
        self.tracking.peak_balance = max(tracker.peak_balance, self.funds.balance)
        self.tracking.low_balance = min(tracker.low_balance, self.funds.balance)
        self.tracking.total_trades = len(self.closed_trades) + len(self.open_trades)
        self.tracking.avg_win = self.avg_win()
        self.tracking.avg_loss = self.avg_loss()
        self.tracking.avg_profit_per_trade = (tracker.avg_win + tracker.avg_loss) / 2
        self.tracking.win_loss_ratio = self.win_loss_ratio()
        self.tracking.commission_paid = self.funds.commission_paid
        self.max_draw_down()
        self.max_run_up()
        self.profit_factor()

    def profit_factor(self) -> None:
        self.tracking.profit_factor = (
            self.tracking.gross_profit / self.tracking.gross_loss
            if self.tracking.gross_loss > 0
            else 0.0
        )

    def cancel_all(self) -> None:
        for o in self.open_orders:
            self.cancel(o.id)

    def cancel(self, id: str) -> None:
        for o in self.open_orders:
            if o.id != id:
                continue
            self.open_orders.remove(o)
            self.funds.margin -= o.margin
            self.funds.balance += o.margin
            self.funds.pending_fees -= o.value * self.config.maker_fee.value
            break

    @staticmethod
    def size_gte_trade(t: Trade, size: float) -> bool:
        return t.size * size < 0 and abs(size) >= abs(t.size)

    def get_trade_by_id(self, id: str) -> Optional[Trade]:
        trades: List[Trade] = self.open_trades
        trade: Optional[Trade] = None
        if trades:
            for t in trades:
                if t.id == id:
                    trade = t
                    break
            trade = trades[0] if trade is None else trade
        return trade

    def open_new_from_order(self, o: Order) -> None:
        """execute open Trade from Order either from a market Order immediate open,
        or if triggered by a trailing entry or limit price met.
        the triggers are in a separate function
        get values from order and use new_entry to open new trade
        """
        if o.status == IMMEDIATE:
            self.new_entry(o.side, o.size, o.price, o.leverage, o.comment, o.symbol)
            self.open_orders.remove(o)

    def new_entry(
        self,
        side: str,
        size: float,
        price: float,
        leverage: float,
        comment: str = "",
        symbol: str = "",
    ) -> None:
        """Open a new trade with a specified size and type"""
        size = self.restrict_size(size, price, leverage)  # Restrict size here!
        trade: Trade = Trade(
            symbol,
            self.config,
            self.funds,
            self.tracking,
            direction=side,
            size=size,  # Use restricted size
            price=price,
            leverage=leverage,
            comment=comment,
            tp_targets=5,
            tp_size_pct=0.75,
            tp_dist_weight=0.5,
            tp_start=price,
            tp_end=price * (1 + (0.05 if size > 0 else -0.05)),
        )
        trade.open_trade_calc(size, price, comment)
        self.open_trades.append(trade)

    def close_trade(
        self,
        trade: Trade,
        size: float,
        close_type: str,
        comment: str = "",
    ) -> None:
        """Close a trade with a specified size and type"""
        trade.close_trade_calc(
            size, price=self.price, close_type=close_type, comment=comment
        )
        self.closed_trades.append(trade)
        self.open_trades.remove(trade)
        trade.update_on_trade()

    def close_all_trades(self) -> None:
        """Close all open trades"""
        for t in self.open_trades:
            self.close_trade(t, t.size, MARKET)

    def execute_order(self, order: Order) -> None:
        """Execute an existing order"""
        if order.status == IMMEDIATE:
            if trade := self.get_trade_by_id(order.id):
                if order.side == BUY:
                    trade.size += order.size
                else:
                    trade.size -= order.size
                trade.value = trade.size * order.price
                trade.margin = trade.value / order.leverage
                self.open_orders.remove(order)

    def update(self, time_is, bar_idnex, price) -> None:
        self.time = time_is
        self.bar_index = bar_idnex
        self.price = price
        self.update_trades(price)
        self.update_funds()
        self.update_tracker()


class Pair:
    def __init__(self, symbol: str, config: Config, initiial_funds: float = 100.0):
        self.symbol: str = symbol
        self.config: Config = config
        self.funds: Funds = Funds(initial=initiial_funds)
        self.tracking: Tracking = Tracking()
        self.strategy: Strategy = Strategy(self.config, self.funds, self.tracking)
        self.price: float = 0.0
        self.time: int = int(time.time())
        self.order_ids: int = 0
        self.trade_ids: int = 0
        self.bar_index: int = 0


import math
import random

from numpy import average


class Price:
    def __init__(self, starting):
        self.prices = []
        # random sweep up in random increments by 0.1 to 0.5% then back down by same random per step
        price = starting
        for i in range(10):
            polarity = 1 if i < 5 else -1
            price = price * (1 + polarity * 0.01 * random.uniform(0.001, 1))
            self.prices.append(price)
        self.bias = 0.5  # 50% bias,if it gets too high , prefer negative price  on randomness, too low, positive

    def update(self):
        """
        generate the price action for 1 new item in the price list 0 index
        ensure that it usually conntinues for 4-6 in  a row in the same direction before changing..
        and vary the amounts semi-stabe like
        """
        leaning = (average(self.prices) - min(self.prices)) / (
            max(self.prices) - min(self.prices)
        )
        self.bias = self.bias * 0.9 + leaning * 0.1
        new_price = self.prices[0] * (
            1 + (self.bias - 0.5) / 1000 * random.uniform(0.1, 0.5)
        )
        self.prices = self.prices[1:]
        self.prices.insert(0, new_price)
        return new_price


def main() -> None:
    pair = Pair("BTCUSDT", Config(), 1000)
    pair.time = int(time.time())
    price = Price(starting=1)

    for i in range(100):
        price.update()
        pair.price = price.prices[0]
        pair.tracking.price = pair.price
        if i % 10 == 0:
            if pair.price > average(price.prices):
                pair.strategy.new_entry(SHORT, 1, pair.price, 1, f"entry{i}")
            elif pair.price < average(price.prices):
                pair.strategy.new_entry(LONG, 1, pair.price, 1, f"entry{i}")
        pair.strategy.update(pair.time, pair.bar_index, pair.price)
        # check for profits if there are any, close them
        if pair.strategy.open_trades is not None:
            for t in pair.strategy.open_trades:
                if t.calc_profit(pair.price) > 0:
                    pair.strategy.close_trade(t, t.size, MARKET)

        pair.time += 10000
        pair.bar_index += 1
    pair.strategy.close_all_trades()
    print(json.dumps(pair.funds.__dict__, indent=4))

    print(json.dumps(pair.strategy.tracking.__dict__, indent=4))


import time

start_time = start_time = time.process_time()
print("Hello World")
end_time = start_time = time.process_time()

print(f"Start Time : {start_time}")
print(f"End Time : {end_time}")
print(f"Execution Time : {end_time - start_time:0.6f}")

print()
start_time = time.process_time()
main()
end_time = time.process_time()

print(f"Start Time : {start_time}")
print(f"End Time : {end_time}")
print(f"Execution Time  : {end_time - start_time}")
