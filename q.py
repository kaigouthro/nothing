import datetime
import time
from typing import List

import numpy as np
import pandas as pd
import streamlit as st

BUY   = "buu"
SELL  = "sell"
UPDATE= "update"

LONG = "long"
SHORT= "short"
BOTH = "both"

LIMIT        = "lmt"
MARKET       = "mkt"
STOP         = "stop"
STOP_LOSS    = "stp loss"
TRAILING_STOP= "trailing stop"
TAKE_PROFIT  = "take profit"

CREATED  = "created"
IMMEDIATE= "immediate"
PENDING  = "pending"


class Calculations:
    """ calculations for Trade and Order size, price, and margin """

    def __init__( self, _pair ):
        self.pair: Pair= _pair
        self.price = self.pair.price
        self.update()

    def update( self ):
        self.price= self.pair.price

    @staticmethod
    def gap_size(_value1, _value2) -> float:
        _max= max(_value1, _value2)
        _min= min(_value1, _value2)
        return _max - _min if _min > 0 or _max < 0 else abs(_min) + _max

    def profit( self, entry_price, exit_price ) -> float:
        return (exit_price / entry_price - 1) * self * entry_price

    def entry_value( self, entry_price ) -> float:
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
        sizes= [total_size / count] * count
        sizes= [max(min_size, sizes[i] * weight ** (i + 1)) for i in range(len(sizes))]
        total= sum(sizes)
        sizes= [size / total * (1 if as_percent else total_size) for size in sizes]
        return sizes

    @classmethod
    def scaled_targets(cls, count, weight, minimum, maximum) -> List[float]:
        split  = cls.scaled_sizes(gap_size(maximum, minimum), count - 1, weight, 0)
        targets= [0] * count
        for i in range(count):
            targets[i]= minimum + sum(split[:i])
        return targets


class Pair:
    def __init__( self ):
        self.closed_trades: List[ Trade ] = [ ]
        self.long_trades  : List[ Trade ] = [ ]
        self.short_trades : List[ Trade ] = [ ]
        self.open_trades  : List[ Trade ] = [ ]
        self.open_orders  : List[ Order ] = [ ]
        self.price        : float = 0.
        self.time         : int = int(time.time())
        self.order_ids    : int = 0
        self.trade_ids    : int = 0
        self.bar_index    : int = 0
        self.config       : Config = Config()
        self.funds        : Funds = Funds
        self.tracking     : Tracking = Tracking()
        self.strategy     : Strategy = strat(self)

    def get_last_trade( self, direction: str ):
        if direction == LONG:
            if len(self.long_trades) == 0:
                return self.new_trade_id()

            return self.long_trades[ -1 ].id
        if direction == SHORT:
            if len(self.short_trades) == 0:
                return self.new_trade_id()

            return self.short_trades[ -1 ].id
    def new_trade_id( self ):
        self.trade_ids = len(self.closed_trades) + len(self.open_trades) + 1
        return str(self.trade_ids)


class Config:
    # A container for all the settings that are used b a Strategy
    """ Configuration class for the Strategy """

    def __init__( self , manager ):
        self.strategy      : Strategy= manager  # the strategy that this config belongs to
        self.symbol        : str    = "BTCUSDT"  # the symbol of the market
        self.initial_equity: float  = 1000.0  # the initial equity of the Funds
        self.initial_wallet: float  = 1000.0  # the initial wallet of the Funds

        #  take profit settings
        self.tp_enabled      = True  # enable the take profit by default
        self.tp_targets_count= 1  # the default number of targets to split take profit
        self.tp_start        = 0.005  # the default first percentage of the take profit steps (0-1)
        self.tp_end          = 0.01  # the default furthest percentage of the take profit steps (0-1)
        self.tp_dist_weight  = 0.5  # the weight of the distance from the firs take profit to the last one
        self.tp_size_weight  = 0.5  # tthe weight of the size of the first take profit to the last one
        self.tp_size_total         = 1.0  # the percentage of the position size to be used for take profit

        #  stop loss settings
        self.sl_enabled  = True  # enable the stop loss by default
        self.sl_trig_dist= 0.005  # the distance from the entry price to activate the stop loss
        self.sl_dist     = 0.02  # the distance from the entry price to activate the stop loss

        self.sl_trail_enabled  = True  # enable the trailing stop loss by default
        self.sl_trail_trig_dist= 0.005  # the distance from the entry price to activate the trailing stop loss
        self.sl_trail_dist     = 0.005  # the call back percentage from the peak to execute the trailing stop loss

        # position settings
        self.position_max_type = "usd"  # the type of the maximum (usd or percent of available balance) for a position
        self.position_max_usd  = 1000.0  # setting for the maximum USD amount for a single Posiyion
        self.position_max_pct  = 1000.0  # setting for the maximum amount for a single Posiyion
        self.position_max_units= 1000.0  # setting for the maximum percent of equityy amount for a single Posiyion
        self.position_max      = self.set_max_order()  # the maximum amount for a single order

        # order settings
        self.ord_max_type = "usd"  # the type of the maximum (usd or percent of available balance or units) for an order
        self.ord_max_usd  = 1000.0  # setting for the maximum USD amount for a single order
        self.ord_max_units= 1.0  # setting for the maximum amount for a single order
        self.ord_max_pct  = 100.0  # setting for the maximum percent of equityy amount for a single order
        self.ord_max      = self.set_max_order()  # the maximum amount for a single order

        # defaul order settings
        self.default_type = "usd"  # the type of the defaultimum (usd or percent of available balance or units) for an order
        self.default_usd  = 1000.0  # setting for the defaultimum USD amount for a single order
        self.default_units= 1.0  # setting for the defaultimum amount for a single order
        self.default_pct  = 100.0  # setting for the defaultimum percent of equityy amount for a single order
        self.default_size = self.set_default_order()  # the defaultimum amount for a single order

        # trade settings
        self.leverage        = 1.0  # the default leverage (1.0 forced if spot, no shorting)
        self.hedge_mode      = False  # the default hedge mode (spot is alwaws false)
        self.ord_minimum_usd = 10.0  # the minimum amount for a single open order in USD
        self.ord_minimum_size= 10.0  # the minimum amount for a single open order in USD
        self.risk            = 0.05  # the default risk percentage (0-1)
        self.slippage        = 0.0001  # the default slippage percentage (0-1)
        self.taker_fee       = 0.0004  # the default taker fee percentage (0-1)
        self.maker_fee       = 0.0002  # the default maker fee percentage (0-1)

    def add_strategy( self, strategy ):
        self.strategy : Strategy = strategy

    def set_max_order( self, price=None ):
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

    def set_default_order( self, price=None ):
        """
         Calculatte from config and eturn the default order size for the strategy.
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

    def set_max_position( self, price=None ):
        """
        Calculatte from config and eturn the maximum position size for the strategy.
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
    def __init__( self, initial: float = 1000.0 ):
        self.currency = "USD"  # the currency of the Funds
        self.balance = initial  # the initial balance of the Funds
        self.equity = initial  # the current equity of the Funds
        self.open_profit = 0.0  # the current open profit of the Funds
        self.pending_fees = 0.0  # the current pending fees of the Funds
        self.margin = 0.0  # the current margin of the Funds
        self.pending_margin = 0.0  # the current pending margin of opened orders not eecuted yet
        self.margin_level = 0.0  # the current margin level in percenttage
        self.commission_paid = 0.0  # the total commission paid by the Funds


class Tracking:
    def __init__( self ):
        self.note: str = ""
        self.starting_balance: float = 0.
        self.current_balance: float = 0.
        self.peak_balance: float = 0.
        self.low_balance: float = 0.
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
    def __init__(self,pair: Pair):
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
        > Update the funds object with the current state of the account
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
        return (
            sum(self.closed_trades) / len(self.closed_trades) if len(self.closed_trades) > 0 else 0
        )
    def avg_loss(self):
        return (
            sum(self.closed_trades) / len(self.closed_trades) if len(self.closed_trades) > 0 else 0
        )
    def win_loss_ratio(self):
        return self.avg_win() / self.avg_loss() if self.avg_win() > 0 else 0

    def restrict_size(self, size: float, price: float, leverage: float):
        """Restrict the size of an order to the max order allowed by the config and within position max size"""
        # convert size to usd for max_position_size and get the lesser of the difference or the size limit
        self.config.set_max_position(price)
        self.config.set_default_order(price)
        self.config.set_max_order(price)
        margin_funds_available = self.funds.balance
        max_entry_margin_usd: float = (
            max(
                0.0,
                min(
                    self.config.ord_max_usd / leverage,
                    self.config.position_max_usd / leverage - self.funds.margin,
                    margin_funds_available,
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
                self.long_trades.remove(t) if t.direction == "long" else self.short_trades.remove(t)
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
                continue

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
        self.net_returns(self.price)
        self.profit_factor(self.price)
    def net_returns(self, price):
        self.tracking.net_returns = self.funds.equity - self.tracking.starting_bal

    def profit_factor(self, price):
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
        """execute open Trade from Order either from a market Order imediate open,
        or if triggered by a trailing entry or limit price met.
        the triggerss are in a seperate function
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
    def __init__( self, size: float, price: float, direction: str, comment: str ):
        self.size           : float = size
        self.direction      : str = direction
        self.commission     : float = 0.0
        self.entry_bar_index: int = 0
        self.entry_comment  : str = comment
        self.entry_id       : str = ''
        self.entry_price    : float = price
        self.entry_time     : float = time.time()
        self.exit_bar_index : int = 0
        self.exit_comment   : int = 0
        self.exit_id        : int = 0
        self.exit_price     : int = 0
        self.exit_time      : int = 0
        self.gross_profit   : float = 0.0
        self.gross_loss     : float = 0.0
        self.net_profit     : float = 0.0
        self.open_fees      : float = 0.0
        self.open_profit    : float = 0.0
        self.max_draw_down  : float = 0.0
        self.max_runup      : float = 0.0
        self.exit_type      : str = ''


# Trade Class objectt

class Trade:
    def __init__(
        self,
        pair              ,
        id                : str,
        direction         : str,
        size              : float,
        price             : float,
        leverage          : float,
        sl_dist           : float,
        sl_trig_dist      : float,
        tp_targets        : int,
        tp_start          : float,
        tp_end            : float,
        tp_dist_weight    : float,
        tp_size_pct       : float,
        tp_size_weight    : float,
        sl_trail_dist     : float,
        sl_trail_trig_dist: float,
        comment           : str = "",
    ):
        # parent pair
        self.pair: Pair = pair
        self.location: list[Trade] = ( self.pair.long_trades if direction == LONG else self.pair.short_trades )

        self.config  = pair.config
        self.tracking= pair.tracking
        self.funds   = pair.funds
        self.strategy= pair.strategy
        self.calc    = Calculations(self.pair, self)

        # trade basic data
        self.id         = id or pair.new_trade_id()
        self.entry_price= price or pair.price
        self.size       = size or 0.0
        self.value      = self.size * self.entry_price
        self.leverage   = leverage or self.config.leverage

        # tied up funds
        self.taker_fee= self.config.taker_fee
        self.margin   = self.calc_margin(self.size, self.leverage, self.entry_price)
        self.open_fees= self.calc_open_fee(self.size, self.entry_price, self.config.maker_fee)
        # Status
        self.direction= direction
        self.status   = "open"
        self.comment  = comment

        # take profit
        self.tp_enabled = bool((tp_targets > 1 or self.config.tp_enabled))
        self.tp_targets_count = (
            max(1, tp_targets or self.config.tp_targets_count)
            if self.tp_enabled and self.config.tp_targets_count > 0
            else 0
        )
        self.tp_start = (tp_start or self.config.tp_start) if self.tp_enabled else None
        self.tp_end = tp_end or self.config.tp_end if self.tp_enabled else None
        self.tp_dist_weight = (
            tp_dist_weight or self.config.tp_dist_weight or 1.0
            if self.tp_enabled and self.config.tp_start
            else None
        )
        self.tp_targets = self.calc_tp_targets() if self.tp_enabled else None
        self.tp_size_total = -self.size * (tp_size_pct or 1.0) if self.tp_enabled else 0.0
        self.tp_size_weight = (
            (-self.size * (tp_size_pct or 1.0) * (tp_size_weight or self.config.tp_size_weight))
            if self.tp_enabled
            else 0.0
        )
        self.tp_sizes = self.calc_tp_sizes() if self.tp_enabled else None

        # stop loss
        self.sl_enabled = bool((sl_dist > 0 or self.config.sl_enabled))
        self.sl_dist = sl_dist or self.config.sl_dist if self.sl_enabled else 0.0
        self.sl_trigger = sl_trig_dist or self.config.sl_trig_dist if self.sl_enabled else 0.0
        self.sl_activated = self.sl_trigger == 0

        # stop loss trailing
        self.sl_trail_enabled = bool(self.config.sl_trail_enabled)
        self.sl_trail_trigger = (
            sl_trail_trig_dist or self.config.sl_trail_trig_dist if self.sl_trail_enabled else None
        )
        self.sl_trail_activated = self.sl_trail_trigger == 0
        self.sl_trail_dist = (
            sl_trail_dist or self.config.sl_trail_dist if self.sl_trail_enabled else None
        )
        self.sl_trail_peak = self.entry_price if self.sl_trail_activated else None
        self.data = Data(self.size, self.entry_price, self.direction, self.comment)
    def calc_tp_targets(self):
        return self.calc.scaled_targets(
            self.tp_targets_count, self.tp_dist_weight, self.tp_start, self.tp_end
        )
    def calc_size(self):
        return self.size
    def calc_profit(self, price):
        self.data.open_profit = (price / self.entry_price - 1) * self.value
        return self.data.open_profit
    def calc_tp_sizes(self):
        return self.calc.scaled_sizes(
            self.tp_size_total, self.tp_targets_count, self.tp_size_weight, self.config.ord_minimum_size
        )
    def update_max_draw_down(self, price):
        self.data.max_draw_down = min(self.data.max_draw_down, self.calc_profit(price)) / self.value
    def update_max_runup(self, price):
        self.data.max_runup = max(self.data.max_runup, self.calc_profit(price)) / self.value
    def get_fees(self, price):
        self.data.open_fees = self.size * price * self.taker_fee
    def trade_close_finalize(self, comment: str = None):
        data               = self.data
        data.exit_bar_index= self.strategy.bar_index
        data.exit_comment  = self.comment if comment is None else comment
        data.exit_id       = self.id
        data.exit_price    = self.strategy.price
        data.exit_time     = time.time()
        # move to closed trades
        self.status = "closed"
        self.pair.closed_trades.append(self)
        self.location.remove(self)


    def size_gte_trade(self, trade_size ) -> float:
        return trade_size * self.size < 0 and abs(self.size) <= abs(trade_size)

    def close_trade_calc(self, size, close_type, comment):
        t = self
        data: Data = t.data
        funds: Funds = t.funds

        price            =  t.strategy.price
        market_order     =  close_type== "market"
        fee_percent      =  t.config.taker_fee if market_order else t.config.maker_fee
        close_is_total   =  t.size_gte_trade(size)
        close_amount     =  min(abs(size), abs(t.size)) * abs(size) / size
        close_profit     =  (price - t.entry_price) * close_amount
        close_commission =  abs(close_amount * price * fee_percent)
        close_net_profit =  close_profit - close_commission
        close_margin     =  (close_amount * t.entry_price) / t.leverage
        data.gross_profit+= close_profit
        data.net_profit  += close_net_profit
        data.commission  += close_commission
        funds.equity     += close_net_profit
        funds.margin     -= close_margin
        funds.balance    += close_margin + close_net_profit
        t.size           -= close_amount
        t.value          =  t.size * t.entry_price
        t.margin         =  t.value / t.leverage

        if close_is_total:
            data.exit_type = close_type
            t.trade_close_finalize(comment)

        return 0.0 if close_is_total else abs(size) - abs(close_amount)

    def get_targets(self):
        return self.calc.scaled_targets(self.tp_targets_count, self.tp_weight or 1, self.tp_start, self.tp_end)
    def get_size(self):
        return self.size
    def get_profit(self, price):
        self.profit = (price / self.entry_price - 1) * self.value
    def update_max_draw_down(self, price):
        self.max_draw_down = min(self.max_draw_down, self.calc_profit(self, price))
    def update_max_runup(self, price):
        self.max_runup = max(self.max_runup, self.calc_profit(self, price))
    def get_fees(self, price):
        return self.size * price * self.taker_fee
    def update(self, price):
        t = self
        s = t.strategy
        if t.status == "open":
            t.max_draw_down = max(t.max_draw_down, t.entry_price - price)
            t.max_runup = max(t.max_runup, price - t.entry_price)
            t.profit = t.calc_profit(price)
            if t.sl_trail_enabled:
                if t.size > 0:
                    if not t.sl_trail_activated:
                        t.sl_trail_activated = price > t.entry_price * (1 + t.sl_trig_pct)
                    if t.sl_trail_peak < price:
                        t.sl_trail_peak = price
                    if t.sl_trail_activated:
                        if price < t.sl_trail_peak * (1 - t.sl_trail_pct):
                            s.close_trade(t, t.size, TRAILING_STOP)
                else:
                    if not t.sl_trail_activated:
                        t.sl_trail_activated = price < t.entry_price * (1 - t.sl_trig_pct)
                    if t.sl_trail_peak > price:
                        t.sl_trail_peak = price
                    if t.sl_trail_activated:
                        if price > t.sl_trail_peak * (1 + t.sl_trail_pct):
                            s.close_trade(t, t.size, TRAILING_STOP)
            if t.tp_enabled:
                if t.size > 0:
                    if price > t.tp_targets[0]:
                        s.close_trade(t, t.size * t.tp_size_total, TAKE_PROFIT)
                        t.tp_targets.pop(0)
                else:
                    if price < t.tp_targets[0]:
                        s.close_trade(t, t.size * t.tp_size_total, TAKE_PROFIT)
                        t.tp_targets.pop(0)
            if t.sl_enabled:
                if t.size > 0:
                    if price < t.entry_price * (1 - t.sl_dist):
                        s.close_trade(t, t.size, TRAILING_STOP)
                else:
                    if price > t.entry_price * (1 + t.sl_dist):
                        s.close_trade(t, t.size, TRAILING_STOP)

    def update_on_trade( self):
        """
        When a trade is marked as closed, update the tracking stats

        : param trade: Trade = The trade object that is being updated
        : type trade : Trade
        """
        tracker = self.tracker
        trade = self
        tracker.total_trades += 1
        if trade.Data.net_profit > 0:
            tracker.total_winning_trades += 1

        else:
            tracker.total_losing_trades += 1

        tracker.consecutive_wins += 1
        tracker.gross_profit += max(0., trade.Data.gross_profit)

        tracker.consecutive_losses = 0
        tracker.gross_loss += min(0., trade.Data.gross_loss)
        tracker.commission_paid += trade.Data.commission
        tracker.net_profit += trade.Data.net_profit

        tracker.percent_profitable    = tracker.total_winning_trades / tracker.total_trades
        tracker.max_consecutive_wins  = max(tracker.max_consecutive_wins, tracker.consecutive_wins)
        tracker.max_consecutive_losses= max(tracker.max_consecutive_losses, tracker.consecutive_losses)
        tracker.avg_win               = tracker.gross_profit / tracker.total_winning_trades
        tracker.avg_loss              = tracker.gross_profit / tracker.total_losing_trades
        tracker.avg_profit_per_trade  = tracker.net_profit / tracker.total_trades
        tracker.win_loss_ratio        = tracker.total_winning_trades / tracker.total_losing_trades
        tracker.profit_factor         = tracker.avg_win / tracker.avg_loss
        tracker.current_balance       = tracker.starting_balance + tracker.net_profit
        tracker.peak_balance          = max(tracker.peak_balance, tracker.current_balance)
        tracker.low_balance           = min(tracker.low_balance, tracker.current_balance)


class Order:
    def __init__(
        self,
        pair: Pair,
        order_id: str,
        direction: str,
        side: str,
        type: str,
        size: float,
        price: float,
        leverage: float,
    ):
        self.pair     = pair
        self.comment  = "Order"
        self.side     = side
        self.direction= direction
        self.id       = order_id or self.pair.get_last_trade(direction)
        self.leverage = pair.config.leverage if leverage is None else leverage
        self.price    = price
        self.size     = pair.strategy.restrict_size(
            size if size is not None else pair.config.default_size / 100 * pair.funds.balance,
            price if price is not None else pair.price,
            leverage if leverage is not None else pair.config.leverage,
        )
        self.value     = self.size * self.price
        self.margin    = self.get_margin()
        self.sl_dist   = self.pair.config.sl_dist if pair.config.sl_enabled else None
        self.fee       = self.pair.config.maker_fee if type== LIMIT else pair.config.taker_fee
        self.time      = time.time()
        self.order_type= MARKET if type is None else type
        self.status    = IMMEDIATE if self.order_type      == MARKET else PENDING

        # trailing stop entry
        self.te_active       = False
        self.te_enabled      = False
        self.te_trigger_dist = None
        self.te_callback_dist= None
        self.peak_price      = None

        self.sl_trig_dist      = None
        self.tp_targets        = None
        self.tp_start          = None
        self.tp_end            = None
        self.tp_dist_weight    = None
        self.tp_size_pct       = None
        self.tp_size_weight    = None
        self.sl_trail_dist     = None
        self.sl_trail_trig_dist= None

    def update_order(self, price):
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

    def get_margin(self):
        return 1 / self.leverage * self.value

    def max_size(self, price):
        return self.pair.strategy.restrict_size(
            self.pair.strategy.config.default_size / 100 * self.pair.strategy.funds.balance,
            price,
            self.leverage,
        )
    def __bool__(self) -> bool:
        return self.status == PENDING


# a simulating backtest strategy to test the above functions by getting publiv binance BTCUSDT 1h candles historical data then testing itt updating on each bar:


st_state = st.session_state


class Backtester:
    """
    parameers and basic trigger functions for a simple backtest strategy
    to be used as decider of when to open and close trades from the indicator chosen
    simple strategy is to open a trade bbased on rsi and wma crossover
    macdd straegy is to open a trade based on macd crossover and signal divergence
    """

    def __init__( self ):
        self.trend_is = "up"
        self.buy_price = 0
        self.sell_price = 0
        self.send_signal = False
        self.signal_to_sesnd = ""

    @staticmethod
    def rsi_wma_crossover( df ):
        period = 14
        delta = df[ "close" ].diff()
        d_up, d_down = (delta.copy(), delta.copy())
        d_up[ d_up < 0 ] = 0
        d_down[ d_down > 0 ] = 0
        rol_up = d_up.rolling(window=period).mean()
        rol_down = d_down.rolling(window=period).mean().abs()
        rs = rol_up / rol_down
        rsi = 100.0 - 100.0 / (1.0 + rs)
        df[ "rsi" ] = rsi
        period = 9
        df[ "wma" ] = (df[ "close" ].rolling(window=period)
                       .apply(lambda prices: np.dot(prices, np.arange(1, period + 1)) / period * (
                    period + 1) / 2, raw=True,
        ))
        df[ "crossover" ] = np.where(df[ "wma" ] > df[ "rsi" ], 1, 0)
        df[ "crossover" ] = np.where(df[ "wma" ] < df[ "rsi" ], -1, df[ "crossover" ])
        df[ "crossover" ] = df[ "crossover" ].diff()
        df[ "signal" ] = np.where(df[ "crossover" ] == 1, "buy", "")
        df[ "signal" ] = np.where(df[ "crossover" ] == -1, "sell", df[ "signal" ])
        return df

    @staticmethod
    def macd_signal_divergence( df ):
        period_fast = 12
        period_slow = 26
        period_signal = 9
        ema_fast = df[ "close" ].ewm(span=period_fast, adjust=False).mean()
        ema_slow = df[ "close" ].ewm(span=period_slow, adjust=False).mean()
        df[ "macd" ] = ema_fast - ema_slow
        df[ "signal" ] = df[ "macd" ].ewm(span=period_signal, adjust=False).mean()
        df[ "histogram" ] = df[ "macd" ] - df[ "signal" ]
        df[ "signal" ] = np.where(df[ "histogram" ] > 0, "buy", "")
        df[ "signal" ] = np.where(df[ "histogram" ] < 0, "sell", df[ "signal" ])
        df[ "divergence" ] = np.where(df[ "histogram" ] > 0, 1, 0)
        df[ "divergence" ] = np.where(df[ "histogram" ] < 0, -1, df[ "divergence" ])
        df[ "divergence" ] = df[ "divergence" ].diff()
        return df


# a simulating backtest strategy to test the above functions by getting  binance BTCUSDT 1h candles  rom cct module ,  then testing itt updating on each bar:
class Backtest:
    """
    use streamlit  to create a simple backtest strategy and test it out
    stock price analysis app that can be used to analyze stock prices and get
    historical data for a given ticker symbol.

    """

    def __init__(
        self, pair, timeframe, start_date, end_date, initial_balance, leverage, hedge_mode
    ):
        self.manager = Strategy()
        self.manager.pair = pair
        self.manager.config = Config(
            pair, timeframe, start_date, end_date, initial_balance, leverage, hedge_mode
        )
        self.manager.config.add_strategy(self.manager)
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.hedge_mode = hedge_mode
        self.exchange = ccxt.binance()
        self.exchange.load_markets()
        self.exchange.verbose = False
        self.exchange.enableRateLimit = True
        self.exchange.options["adjustForTimeDifference"] = True
        self.exchange.options["defaultType"] = "future"
        self.exchange.options["defaultTimeInForce"] = "GTC"
        self.exchange.options["defaultLimitOrderType"] = "limit"
        self.exchange.options["defaultMarketOrderType"] = "market"
        self.exchange.options["defaultType"] = "future"
        self.exchange.options["fetchOHLCV"] = "emulated"
        self.exchange.options["fetchTickersMaxLength"] = 1000
        self.exchange.options["adjustForTimeDifference"] = True
        self.exchange.options["recvWindow"] = 5000
        self.exchange.options["timeDifference"] = 0
        self.exchange.load_markets()
        self.candles = self.exchange.fetch_ohlcv(
            self.pair, self.timeframe, self.start_date, self.end_date
        )
        self.candles = pd.DataFrame(
            self.candles, columns=["time", "open", "high", "low", "close", "volume"])
        self.candles["time"] = pd.to_datetime(self.candles["time"], unit="ms")
        self.candles.set_index("time", inplace=True)
        self.candles.index = pd.DatetimeIndex(self.candles.index)
        self.candles = self.candles.dropna()
        self.candles = self.candles.drop_duplicates()
        self.stratteg = Backtest()
        self.usestrat = "rsi"

        self.ticker = st.sidebar.text_input("Ticker", "AAPL")
        self.start_date = st.sidebar.date_input("Start date", datetime.date(2023, 1, 1))
        self.end_date = st.sidebar.date_input("End date", datetime.date(2023, 1, 31))
        self.chart_data_tracking = pd.DataFrame()
        self.chart_data_executions = pd.DataFrame()
    def run(self):
        for _ in range(len(self.candles)):
            if self.usestrat == "rsi":
                self.candles = self.stratteg.rsi_wma_crossover(self.candles)
            elif self.usestrat == "macd":
                self.candles = self.stratteg.macd_signal_crossover(self.candles)
        for i in range(len(self.candles)):
            if self.candles["signal"][i] == "buy":
                self.execue_buy(self.manager, self.candles["close"][i])
                self.pull_tracking_data(self.manager, self.candles["close"][i])
            elif self.candles["signal"][i] == "sell":
                self.execue_sell(self.manager, self.candles["close"][i])
                self.pull_tracking_data(self.manager, self.candles["close"][i])
        self.update_chart_data(Strategy)
    def execue_buy(self, manager, price):
        manager.buy(price)
        self.buy_price = price
        self.buy_time = datetime.datetime.now()
        self.send_signal = True

    def execue_sell(self, manager, price):
        manager.sell(price)
        self.sell_price = price
        self.sell_time = datetime.datetime.now()
        self.send_signal = True

    def pull_tracking_data(self, manager, price):
        self.chart_data_tracking = self.chart_data_tracking.append(
            {
                "time": datetime.datetime.now(),
                "balance": manager.balance,
                "equity": manager.equity,
                "price": price,
            },
            ignore_index=True,
        )
        self.chart_data_tracking.set_index("time", inplace=True)
        self.chart_data_tracking.index = pd.DatetimeIndex(self.chart_data_tracking.index)
    def update_chart_data(self, manager):
        self.chart_data_executions = self.chart_data_executions.append(
            {
                "time": datetime.datetime.now(),
                "balance": manager.balance,
                "equity": manager.equity,
                "price": manager.price,
            },
            ignore_index=True,
        )
        self.chart_data_executions.set_index("time", inplace=True)
        self.chart_data_executions.index = pd.DatetimeIndex(self.chart_data_executions.index)
    def plot_chart(self):
        st.line_chart(self.chart_data_tracking)
        st.line_chart(self.chart_data_executions)



if __name__ == "__main__":
    pair = Pair()
    timeframes = '15m'
    start_date = '2021-01-01 00:00:00'
    end_date = '2021-01-31 00:00:00'
    pair.set_pair('BTC/USDT', timeframes, start_date, end_date)
    bt = Backtest()
    bt(pair, '15m', '2021-01-01 00:00:00', '2021-01-31 00:00:00', 10000, 10, True)

    bt.run()