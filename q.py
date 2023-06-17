import time
from typing import List, Optional

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


class Calculations:
    """Calculations for trade and order size, price, and margin"""

    def __init__(self, pair):
        self.pair: Pair = pair
        self.price = self.pair.price
        self.update()

    def update(self):
        self.price = self.pair.price

    @staticmethod
    def gap_size(value1, value2) -> float:
        _max = max(value1, value2)
        _min = min(value1, value2)
        return _max - _min if _min > 0 or _max < 0 else abs(_min) + _max

    def profit(self, entry_price, exit_price) -> float:
        return (exit_price / entry_price - 1) * self * entry_price

    def entry_value(self, entry_price) -> float:
        return self * entry_price

    @staticmethod
    def margin(size, price, leverage) -> float:
        return abs(size) * price / leverage

    @staticmethod
    def profit_factor(avg_win: float, avg_loss: float) -> float:
        return avg_win / avg_loss

    @staticmethod
    def fee(size, price, fee) -> float:
        return price * size * fee

    @staticmethod
    def value(price, size) -> float:
        return size * price

    @classmethod
    def net_profit(cls, size, entry_price, exit_price, fee_pct) -> float:
        return (exit_price - entry_price) * size - cls.fee(size, exit_price, fee_pct)

    @staticmethod
    def scaled_sizes(total_size, count, weight, min_size, as_percent=False) -> List[float]:
        sizes = [total_size / count] * count
        sizes = [max(min_size, sizes[i] * weight ** (i + 1)) for i in range(len(sizes))]
        total = sum(sizes)
        sizes = [size / total * (1 if as_percent else total_size) for size in sizes]
        return sizes

    @classmethod
    def scaled_targets(cls, count, weight, minimum, maximum) -> List[float]:
        split = cls.scaled_sizes(gap_size(maximum, minimum), count - 1, weight, 0)
        targets = [0] * count
        for i in range(count):
            targets[i] = minimum + sum(split[:i])
        return targets


class Pair:
    def __init__(self):
        self.closed_trades: List[Trade] = []
        self.long_trades: List[Trade] = []
        self.short_trades: List[Trade] = []
        self.open_trades: List[Trade] = []
        self.open_orders: List[Order] = []
        self.price: float = 0.0
        self.time: int = int(time.time())
        self.order_ids: int = 0
        self.trade_ids: int = 0
        self.bar_index: int = 0
        self.config: Config = Config()
        self.funds: Funds = Funds()
        self.tracking: Tracking = Tracking()
        self.strategy: Strategy = strat(self)

    def get_last_trade(self, direction: str):
        if direction == LONG:
            if len(self.long_trades) == 0:
                return self.new_trade_id()

            return self.long_trades[-1].id
        if direction == SHORT:
            if len(self.short_trades) == 0:
                return self.new_trade_id()

            return self.short_trades[-1].id

    def new_trade_id(self):
        self.trade_ids = len(self.closed_trades) + len(self.open_trades) + 1
        return str(self.trade_ids)


class Config:
    # A container for all the settings that are used by a Strategy
    """Configuration class for the Strategy"""

    def __init__(self, manager):
        self.strategy: Strategy = manager  # the strategy that this config belongs to
        self.symbol: str = "BTCUSDT"  # the symbol of the market
        self.initial_equity: float = 1000.0  # the initial equity of the Funds
        self.initial_wallet: float = 1000.0  # the initial wallet of the Funds

        # take profit settings
        self.tp_enabled = True  # enable the take profit by default
        self.tp_targets_count = 1  # the default number of targets to split take profit
        self.tp_start = 0.005  # the default first percentage of the take profit steps (0-1)
        self.tp_end = 0.01  # the default furthest percentage of the take profit steps (0-1)
        self.tp_dist_weight = 0.5  # the weight of the distance from the first take profit to the last one
        self.tp_size_weight = 0.5  # the weight of the size of the first take profit to the last one
        self.tp_size_total = 1.0  # the percentage of the position size to be used for take profit

        # stop loss settings
        self.sl_enabled = True  # enable the stop loss by default
        self.sl_trig_dist = 0.005  # the distance from the entry price to activate the stop loss
        self.sl_dist = 0.02  # the distance from the entry price to activate the stop loss

        self.sl_trail_enabled = True  # enable the trailing stop loss by default
        self.sl_trail_trig_dist = 0.005  # the distance from the entry price to activate the trailing stop loss
        self.sl_trail_dist = 0.005  # the call back percentage from the peak to execute the trailing stop loss

        # position settings
        self.position_max_type = "usd"  # the type of the maximum (usd or percent of available balance) for a position
        self.position_max_usd = 1000.0  # setting for the maximum USD amount for a single Position
        self.position_max_pct = 1000.0  # setting for the maximum amount for a single Position
        self.position_max_units = 1000.0  # setting for the maximum percent of equity amount for a single Position
        self.position_max = self.set_max_order()  # the maximum amount for a single order

        # order settings
        self.ord_max_type = "usd"  # the type of the maximum (usd or percent of available balance or units) for an order
        self.ord_max_usd = 1000.0  # setting for the maximum USD amount for a single order
        self.ord_max_units = 1.0  # setting for the maximum amount for a single order
        self.ord_max_pct = 100.0  # setting for the maximum percent of equity amount for a single order
        self.ord_max = self.set_max_order()  # the maximum amount for a single order

        # default order settings
        self.default_type = "usd"  # the type of the defaultimum (usd or percent of available balance or units) for an order
        self.default_usd = 1000.0  # setting for the defaultimum USD amount for a single order
        self.default_units = 1.0  # setting for the defaultimum amount for a single order
        self.default_pct = 100.0  # setting for the defaultimum percent of equity amount for a single order
        self.default_size = self.set_default_order()  # the defaultimum amount for a single order

        # trade settings
        self.leverage = 1.0  # the default leverage (1.0 forced if spot, no shorting)
        self.hedge_mode = False  # the default hedge mode (spot is always false)
        self.ord_minimum_usd = 10.0  # the minimum amount for a single open order in USD
        self.ord_minimum_size = 10.0  # the minimum amount for a single open order in USD
        self.risk = 0.05  # the default risk percentage (0-1)
        self.slippage = 0.0001  # the default slippage percentage (0-1)
        self.taker_fee = 0.0004  # the default taker fee percentage (0-1)
        self.maker_fee = 0.0002  # the default maker fee percentage (0-1)

    def add_strategy(self, strategy):
        self.strategy: Strategy = strategy

    def set_max_order(self, price=None):
        """
        If the order max type is "usd", return the order max usd. If the order max type is "percent", return
        the order max percent. If the order max type is "units", return the order max units. Otherwise,
        return 0.0
        : return: The value of the order max type.
        """
        if price is None:
            price = self.strategy.price
        if self.ord_max_type == "usd":
            self.ord_max_pct = self.ord_max_usd / self.initial_equity * 100
            self.ord_max_units = self.ord_max_usd / price
            return self.ord_max_usd

        if self.ord_max_type == "percent":
            self.ord_max_usd = self.ord_max_pct / 100 * self.strategy.funds.equity
            self.ord_max_units = self.ord_max_usd / price
            return self.ord_max_pct

        if self.ord_max_type == "units":
            self.ord_max_usd = self.ord_max_units * price
            self.ord_max_pct = self.ord_max_usd / self.initial_equity * 100
            return self.ord_max_units

        return 0.0

    def set_default_order(self, price=None):
        """
         Calculate from config and return the default order size for the strategy.
        : return: The default order size for the strategy.
        """
        if price is None:
            price = self.strategy.price
        if self.default_type == "usd":
            self.default_pct = self.default_usd / self.initial_equity * 100
            self.default_units = self.default_usd / price
            return self.default_usd
        if self.default_type == "percent":
            self.default_usd = self.default_pct / 100 * self.strategy.funds.equity
            self.default_units = self.default_usd / price
            return self.default_pct
        if self.default_type == "units":
            self.default_usd = self.default_units * price
            self.default_pct = self.default_usd / self.initial_equity * 100
            return self.default_units

    def set_max_position(self, price=None):
        """
        Calculate from config and return the maximum position size for the strategy.
        : return: The maximum position size for the strategy.
        """
        if price is None:
            price = self.strategy.price
        if self.position_max_type == "usd":
            self.position_max_pct = self.position_max_usd / self.initial_equity * 100
            self.position_max_units = self.position_max_usd / price
            return self.position_max_usd
        if self.position_max_type == "percent":
            self.position_max_usd = self.position_max_pct / 100 * self.strategy.funds.equity
            self.position_max_units = self.position_max_usd / price
            return self.position_max_pct
        if self.position_max_type == "units":
            self.position_max_usd = self.position_max_units * price
            self.position_max_pct = self.position_max_usd / self.initial_equity * 100
            return self.position_max_units

        return 0.0


class Funds:
    # The Funds class is used to keep track of the current balance, equity, open profit, pending fees,
    # margin, pending margin and margin level of the Funds
    def __init__(self, initial: float = 1000.0):
        self.currency = "USD"  # the currency of the Funds
        self.balance = initial  # the initial balance of the Funds
        self.equity = initial  # the current equity of the Funds
        self.open_profit = 0.0  # the current open profit of the Funds
        self.pending_fees = 0.0  # the current pending fees of the Funds
        self.margin = 0.0  # the current margin of the Funds
        self.pending_margin = 0.0  # the current pending margin of opened orders not executed yet
        self.margin_level = 0.0  # the current margin level in percentage
        self.commission_paid = 0.0  # the total commission paid by the Funds


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
        self.net_profit: float = 0.0
        self.percent_profitable: float = 0.0
        self.net_returns: float = 0.0


class Strategy:
    def __init__(self, pair: Pair):
        self.pair: Pair = pair
        self.funds: Funds = self.pair.funds
        self.config: Config = self.pair.config
        self.tracking: Tracking = self.pair.tracking
        self.closed_trades: List[Trade] = self.pair.closed_trades
        self.long_trades: List[Trade] = self.pair.long_trades
        self.short_trades: List[Trade] = self.pair.short_trades
        self.open_orders: List[Order] = self.pair.open_orders
        self.bar_index: int = self.pair.bar_index
        self.price: float = self.pair.price
        self.order_ids: int = self.pair.order_ids
        self.trade_ids: int = self.pair.trade_ids

    def open_trades(self):
        return [self.long_trades + self.short_trades]
    def update_funds(self):
        """
        Update the funds object with the current state of the account
        """
        trades = self.open_trades()
        if len(self.open_trades()) > 0:
            self.funds.pending_fees = sum(t.taker_fee * abs(t.size) * self.price for t in trades)
            self.funds.margin = sum(t.margin for t in trades)
            self.funds.open_profit = sum(t.size * (self.price - t.entry_price) for t in trades)
        if len(self.open_orders) > 0:
            self.funds.pending_margin = sum(o.margin for o in self.open_orders)
        self.funds.balance = (
            self.funds.open_profit
            + self.funds.equity
            - (self.funds.pending_fees + self.funds.margin + self.funds.pending_margin))
        self.funds.margin_level = (
            1 - (self.funds.equity - self.funds.margin) / self.funds.equity
            if self.funds.equity > 0
            else 0
        )
    def max_draw_down(self):
        trades = self.open_trades()
        self.tracking.max_draw_down = min(
            self.tracking.max_draw_down,
            sum(t.calc_profit(self.price) for t in trades),)
        return self.tracking.max_draw_down

    def max_run_up(self):
        trades = self.open_trades()
        self.tracking.max_run_up = max(
            self.tracking.max_draw_down,
            sum(t.calc_profit(self.price) for t in trades),)
        return self.tracking.max_run_up

    def avg_win(self):
        """returns the average win amount, adds up win amounts of winning trades from closed trades and divides by number of wins"""
        wins = 0
        win_amount = 0
        for trade in self.closed_trades:
            prof = trade.data.net_profit
            wins += 1 if prof > 0 else 0
            win_amount += max(prof, 0)
        return win_amount / wins if wins > 0 else 0

    def avg_loss(self):
        """returns the average loss amount, adds up loss amounts of losing trades from closed trades and divides by number of losses"""
        losses = 0
        loss_amount = 0
        for trade in self.closed_trades:
            prof = trade.data.net_profit
            losses += 1 if prof < 0 else 0
            loss_amount += min(prof, 0)
        return loss_amount / losses if losses > 0 else 0

    def win_loss_ratio(self):
        return self.avg_win() / self.avg_loss() if self.avg_win() > 0 else 0

    def restrict_size(self, size: float, price: float, leverage: float):
        """Restrict the size of an order to the max order allowed by the config and within position max size"""
        # convert size to usd for max_position_size and get the lesser of the difference or the size limit
        self.config.set_max_position(price)
        self.config.set_default_order(price)
        self.config.set_max_order(price)
        requested_size_usd = size * price
        margin_funds_available = self.funds.balance
        max_entry_margin_usd: float = (
            max(
                0.0,
                min(
                    self.config.ord_max_usd / leverage,
                    self.config.position_max_usd / leverage - self.funds.margin,
                    margin_funds_available,
                    requested_size_usd,
                ),)
            * leverage
        )
        max_funds_net_fee = max_entry_margin_usd * (1 - self.config.taker_fee)
        return max_funds_net_fee / price

    def update_trades(self):
        trades: list[Trade] = self.open_trades()
        for t in trades:
            t.update(self.price)
            if t.status == "closed":
                self.closed_trades.append(t)
                if t.direction == "long":
                    self.long_trades.remove(t)
                else:
                    self.short_trades.remove(t)
        self.funds.open_profit = sum(t.calc_profit(self.price) for t in trades)
        self.funds.pending_fees = sum(t.get_fees(self.price) for t in trades)
    def update_orders(self):
        trades = self.open_trades()
        ids = [t.id for t in trades]
        long_trades = [t for t in trades if t.direction == "LONG"]
        short_trades = [t for t in trades if t.direction == "SHORT"]
        for o in self.open_orders:
            id_match = o.id in ids
            direction = o.direction

            if o.status == PENDING:
                o.update_order(self.price)
            if o.status == IMMEDIATE:
                if direction == "LONG" and long_trades:
                    t = self.get_trade_by_id(o.id) if id_match else long_trades[-1]
                    t.execute_order(o)
                if direction == "SHORT" and short_trades:
                    t = self.get_trade_by_id(o.id) if id_match else short_trades[-1]
                    t.execute_order(o)
                if (direction == "LONG" and not long_trades) or (
                    direction == "SHORT" and not short_trades
                ):
                    self.open_new_from_order(o)
            if o.status == "failed":
                self.cancel(o)
    def update_tracker(self):
        tracker = self.tracking

        tracker.current_balance = self.funds.balance
        tracker.peak_balance = max(tracker.peak_balance, self.funds.balance)
        tracker.low_balance = min(tracker.low_balance, self.funds.balance)
        tracker.total_trades = len(self.closed_trades) + len(self.open_trades())
        tracker.avg_win = self.avg_win()
        tracker.avg_loss = self.avg_loss()
        tracker.avg_profit_trade = (tracker.avg_win + tracker.avg_loss) / 2
        tracker.win_loss_ratio = self.win_loss_ratio()
        tracker.comission_paid = self.funds.commission_paid
        self.max_draw_down()
        self.max_run_up()
        self.net_returns()
        self.profit_factor()
    def net_returns(self):
        self.tracking.net_returns = self.funds.equity - self.tracking.starting_balance

    def profit_factor(self):
        self.tracking.profit_factor = self.tracking.gross_profit / self.tracking.gross_loss

    def cancel_all(self):
        for o in self.open_orders:
            self.cancel(o.id)
    def cancel(self, id):
        for o in self.open_orders:
            if o.id != id:
                continue
            self.open_orders.remove(o)
            self.funds.margin -= o.margin
            self.funds.balance += o.margin
            self.funds.pending_fees -= o.value * self.config.maker_fee
            break

    @staticmethod
    def size_gte_trade(t: Trade, size):
        return t.size * size < 0 and abs(size) >= abs(t.size)
    def get_trade_by_id(self, id: str):
        trades: List[Trade] = self.open_trades()
        trade = None
        if trades:
            for t in trades:
                if t.id == id:
                    trade = t
                    break
            trade = trades[0] if trade is None else trade
        return trade

    def open_new_from_order(self, o: Order):
        """execute open Trade from Order either from a market Order immediate open,
        or if triggered by a trailing entry or limit price met.
        the triggers are in a separate function
        get values from order and use new_entry to open new trade
        """
        self.execute_new_entry(
            o.id,
            o.direction,
            o.size,
            o.price,
            o.leverage,
            o.sl_dist,
            o.sl_trig_dist,
            o.tp_targets,
            o.tp_start,
            o.tp_end,
            o.tp_dist_weight,
            o.tp_size_pct,
            o.tp_size_weight,
            o.sl_trail_dist,
            o.sl_trail_trig_dist,
            o.comment,
        )



class Data:
    def __init__(self, size: float, price: float, direction: str, comment: str):
        self.size: float = size
        self.direction: str = direction
        self.commission: float = 0.0
        self.entry_bar_index: int = 0
        self.entry_comment: str = comment
        self.entry_id: str = ''
        self.entry_price: float = price
        self.entry_time: float = time.time()
        self.exit_bar_index: int = 0
        self.exit_comment: int = 0
        self.exit_id: int = 0
        self.exit_price: int = 0
        self.exit_time: int = 0
        self.gross_profit: float = 0.0
        self.gross_loss: float = 0.0
        self.net_profit: float = 0.0
        self.open_fees: float = 0.0
        self.open_profit: float = 0.0
        self.max_draw_down: float = 0.0
        self.max_runup: float = 0.0
        self.exit_type: str = ''




class Trade:
    def __init__(
        self,
        pair: "Pair",
        id: str,
        direction: str,
        size: float,
        price: float,
        leverage: float,
        sl_dist: float,
        sl_trig_dist: float,
        tp_targets: int,
        tp_start: float,
        tp_end: float,
        tp_dist_weight: float,
        tp_size_pct: float,
        tp_size_weight: float,
        sl_trail_dist: float,
        sl_trail_trig_dist: float,
        comment: str = "",
    ) -> None:
        self.pair: "Pair" = pair
        self.location: List["Trade"] = (
            self.pair.long_trades if direction == LONG else self.pair.short_trades
        )
        self.config = pair.config
        self.tracking = pair.tracking
        self.funds = pair.funds
        self.strategy = pair.strategy
        self.calc = Calculations(self.pair, self)
        self.id: str = id or pair.new_trade_id()
        self.entry_price: float = price or pair.price
        self.size: float = size or 0.0
        self.value: float = self.size * self.entry_price
        self.leverage: float = leverage or self.config.leverage
        self.taker_fee: float = self.config.taker_fee
        self.margin: float = self.calc_margin(self.size, self.leverage, self.entry_price)
        self.open_fees: float = self.calc_open_fee(
            self.size, self.entry_price, self.config.maker_fee
        )
        self.direction: str = direction
        self.status: str = "open"
        self.comment: str = comment

        self.set_tp(tp_targets, tp_start, tp_end, tp_dist_weight, tp_size_pct, tp_size_weight)
        self.sl_enabled: bool = bool((sl_dist > 0 or self.config.sl_enabled))
        self.sl_dist: float = sl_dist or self.config.sl_dist if self.sl_enabled else 0.0
        self.sl_trigger: float = (
            sl_trig_dist or self.config.sl_trig_dist if self.sl_enabled else 0.0
        )
        self.sl_activated: bool = self.sl_trigger == 0

        self.sl_trail_enabled: bool = bool(self.config.sl_trail_enabled)
        self.sl_trail_trigger: Optional[float] = (
            sl_trail_trig_dist or self.config.sl_trail_trig_dist if self.sl_trail_enabled else None
        )
        self.sl_trail_activated: bool = self.sl_trail_trigger == 0
        self.sl_trail_dist: Optional[float] = (
            sl_trail_dist or self.config.sl_trail_dist if self.sl_trail_enabled else None
        )
        self.sl_trail_peak: Optional[float] = self.entry_price if self.sl_trail_activated else None
        self.data = Data(self.size, self.entry_price, self.direction, self.comment)

    def set_tp(
        self,
        tp_targets: int,
        tp_start: float,
        tp_end: float,
        tp_dist_weight: float = 1,
        tp_size_pct: float = 1,
        tp_size_weight: float = 1,
    ) -> None:
        self.tp_enabled: bool = bool((tp_targets > 1 or self.config.tp_enabled))
        self.tp_targets_count: int = (
            max(1, tp_targets or self.config.tp_targets_count)
            if self.tp_enabled and self.config.tp_targets_count > 0
            else 0
        )
        self.tp_start: Optional[float] = (
            (tp_start or self.config.tp_start) if self.tp_enabled else None
        )
        self.tp_end: Optional[float] = tp_end or self.config.tp_end if self.tp_enabled else None
        self.tp_dist_weight: Optional[float] = (
            True if self.tp_enabled and self.config.tp_start else None
        )
        self.tp_targets: Optional[List[float]] = self.calc_tp_targets() if self.tp_enabled else None
        self.tp_size_total: float = -self.size * (True) if self.tp_enabled else 0.0
        self.tp_size_weight: float = (
            (-self.size * (True) * (tp_size_weight or self.config.tp_size_weight))
            if self.tp_enabled
            else 0.0
        )
        self.tp_sizes: Optional[List[float]] = self.calc_tp_sizes() if self.tp_enabled else None

    def calc_tp_targets(self) -> List[float]:
        return self.calc.scaled_targets(
            self.tp_targets_count, self.tp_dist_weight, self.tp_start, self.tp_end
        )

    def calc_size(self) -> float:
        return self.size

    def calc_profit(self, price: float) -> float:
        self.data.open_profit = (price / self.entry_price - 1) * self.value
        return self.data.open_profit

    def calc_tp_sizes(self) -> List[float]:
        return self.calc.scaled_sizes(
            self.tp_size_total,
            self.tp_targets_count,
            self.tp_size_weight,
            self.config.ord_minimum_size,
        )

    def update_max_draw_down(self, price: float) -> None:
        self.data.max_draw_down = min(self.data.max_draw_down, self.calc_profit(price)) / self.value

    def update_max_runup(self, price: float) -> None:
        self.data.max_runup = max(self.data.max_runup, self.calc_profit(price)) / self.value

    def get_fees(self, price: float) -> None:
        self.data.open_fees = self.size * price * self.taker_fee

    def trade_close_finalize(self, comment: Optional[str] = None) -> None:
        data = self.data
        data.exit_bar_index = self.strategy.bar_index
        data.exit_comment = self.comment if comment is None else comment
        data.exit_id = self.id
        data.exit_price = self.strategy.price
        data.exit_time = time.time()
        self.status = "closed"
        self.pair.closed_trades.append(self)
        self.location.remove(self)

    def size_gte_trade(self, trade_size: float) -> float:
        return trade_size * self.size < 0 and abs(self.size) <= abs(trade_size)

    def close_trade_calc(self, size: float, close_type: str, comment: str) -> float:
        t: Trade = self
        data: Data = t.data
        funds: Funds = t.funds

        price = t.strategy.price
        market_order = close_type == "market"
        fee_percent = t.config.taker_fee if market_order else t.config.maker_fee
        close_is_total = t.size_gte_trade(size)
        close_amount = min(abs(size), abs(t.size)) * abs(size) / size
        close_profit = (price - t.entry_price) * close_amount
        close_commission = abs(close_amount * price * fee_percent)
        close_net_profit = close_profit - close_commission
        close_margin = (close_amount * t.entry_price) / t.leverage
        data.gross_profit += close_profit
        data.net_profit += close_net_profit
        data.commission += close_commission
        funds.equity += close_net_profit
        funds.margin -= close_margin
        funds.balance += close_margin + close_net_profit
        t.size -= close_amount
        t.value = t.size * t.entry_price
        t.margin = t.value / t.leverage

        if close_is_total:
            data.exit_type = close_type
            t.trade_close_finalize(comment)
        return 0.0 if close_is_total else abs(size) - abs(close_amount)

    def get_targets(self) -> List[float]:
        return self.calc.scaled_targets(self.tp_targets_count, True, self.tp_start, self.tp_end)

    def get_size(self) -> float:
        return self.size

    def get_profit(self, price: float) -> None:
        self.profit = (price / self.entry_price - 1) * self.value

    def update_max_draw_down(self, price: float) -> None:
        self.max_draw_down = min(self.max_draw_down, self.calc_profit(self, price))

    def update_max_runup(self, price: float) -> None:
        self.max_runup = max(self.max_runup, self.calc_profit(self, price))

    def get_fees(self, price: float) -> float:
        return self.size * price * self.taker_fee

    def update(self, price: float) -> None:
        t: Trade = self
        if t.status == "open":
            t.max_draw_down = max(t.max_draw_down, t.entry_price - price)
            t.max_runup = max(t.max_runup, price - t.entry_price)
            t.profit = t.calc_profit(price)
            s = t.strategy
            if t.sl_trail_enabled:
                if t.size > 0:
                    if not t.sl_trail_activated:
                        t.sl_trail_activated = price > t.entry_price * (1 + t.sl_trig_pct)
                    t.sl_trail_peak = max(t.sl_trail_peak, price)
                    if t.sl_trail_activated and price < t.sl_trail_peak * (1 - t.sl_trail_pct):
                        s.close_trade(t, t.size, TRAILING_STOP)
                else:
                    if not t.sl_trail_activated:
                        t.sl_trail_activated = price < t.entry_price * (1 - t.sl_trig_pct)
                    t.sl_trail_peak = min(t.sl_trail_peak, price)
                    if t.sl_trail_activated and price > t.sl_trail_peak * (1 + t.sl_trail_pct):
                        s.close_trade(t, t.size, TRAILING_STOP)
            if t.tp_enabled and (
                t.size > 0 and price > t.tp_targets[0] or t.size <= 0 and price < t.tp_targets[0]
            ):
                s.close_trade(t, t.size * t.tp_size_total, TAKE_PROFIT)
                t.tp_targets.pop(0)
            if t.size > 0:
                if t.sl_enabled and price < t.entry_price * (1 - t.sl_dist):
                    s.close_trade(t, t.size, TRAILING_STOP)
            elif price > t.entry_price * (1 + t.sl_dist):
                if t.sl_enabled:
                    s.close_trade(t, t.size, TRAILING_STOP)

    def update_on_trade(self) -> None:
        tracker = self.tracker
        trade = self
        tracker.total_trades += 1
        if trade.Data.net_profit > 0:
            tracker.total_winning_trades += 1
        else:
            tracker.total_losing_trades += 1
        tracker.consecutive_wins += 1
        tracker.gross_profit += max(0.0, trade.Data.gross_profit)
        tracker.consecutive_losses = 0
        tracker.gross_loss += min(0.0, trade.Data.gross_loss)
        tracker.commission_paid += trade.Data.commission
        tracker.net_profit += trade.Data.net_profit

        tracker.percent_profitable = tracker.total_winning_trades / tracker.total_trades
        tracker.max_consecutive_wins = max(tracker.max_consecutive_wins, tracker.consecutive_wins)
        tracker.max_consecutive_losses = max(
            tracker.max_consecutive_losses, tracker.consecutive_losses
        )
        tracker.avg_win = tracker.gross_profit / tracker.total_winning_trades
        tracker.avg_loss = tracker.gross_profit / tracker.total_losing_trades
        tracker.avg_profit_per_trade = tracker.net_profit / tracker.total_trades
        tracker.win_loss_ratio = tracker.total_winning_trades / tracker.total_losing_trades
        tracker.profit_factor = tracker.avg_win / tracker.avg_loss
        tracker.current_balance = tracker.starting_balance + tracker.net_profit
        tracker.peak_balance = max(tracker.peak_balance, tracker.current_balance)
        tracker.low_balance = min(tracker.low_balance, tracker.current_balance)


class Order:
    def __init__(
        self,
        pair: "Pair",
        order_id: str,
        direction: str,
        side: str,
        type: str,
        size: float,
        price: float,
        leverage: float,
    ) -> None:
        self.pair: "Pair" = pair
        self.comment: str = "Order"
        self.side: str = side
        self.direction: str = direction
        self.id: str = order_id or self.pair.get_last_trade(direction)
        self.leverage: float = pair.config.leverage if leverage is None else leverage
        self.price: float = price
        self.size: float = pair.strategy.restrict_size(
            size if size is not None else pair.config.default_size / 100 * pair.funds.balance,
            price if price is not None else pair.price,
            leverage if leverage is not None else pair.config.leverage,
        )
        self.value: float = self.size * self.price
        self.margin: float = self.get_margin()
        self.sl_dist: Optional[float] = self.pair.config.sl_dist if pair.config.sl_enabled else None
        self.fee: float = self.pair.config.maker_fee if type == LIMIT else pair.config.taker_fee
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
                self.te_active = True if self.te_active else price < self.te_trigger_dist
                self.peak_price = min(self.peak_price, price)
                if self.te_active and price >= self.peak_price * (1 + self.te_callback_dist):
                    self.status = IMMEDIATE
            else:
                self.te_active = True if self.te_active else price > self.te_trigger_dist
                self.peak_price = max(self.peak_price, price)
                if self.te_active and price <= self.peak_price * (1 - self.te_callback_dist):
                    self.status = IMMEDIATE

    def get_margin(self) -> float:
        return 1 / self.leverage * self.value

    def max_size(self, price: float) -> float:
        return self.pair.strategy.restrict_size(
            self.pair.strategy.config.default_size / 100 * self.pair.strategy.funds.balance,
            price,
            self.leverage,
        )

    def __bool__(self) -> bool:
        return self.status == PENDING
