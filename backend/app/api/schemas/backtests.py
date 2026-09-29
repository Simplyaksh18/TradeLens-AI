from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel

from app.backtesting.models import BacktestConfig, BacktestResult, EquityPoint, ExecutedTrade, OpenPosition


class BacktestConfigSchema(BaseModel):
    initial_capital: float
    transaction_cost: float
    slippage: float

    @classmethod
    def from_domain(cls, config: BacktestConfig) -> "BacktestConfigSchema":
        return cls(initial_capital=config.initial_capital, transaction_cost=config.transaction_cost, slippage=config.slippage)


class ExecutedTradeSchema(BaseModel):
    entry_signal_date: Date
    entry_date: Date
    entry_price: float
    exit_signal_date: Date
    exit_date: Date
    exit_price: float
    quantity: int
    gross_pnl: float
    gross_return: float
    net_pnl: float

    @classmethod
    def from_domain(cls, trade: ExecutedTrade) -> "ExecutedTradeSchema":
        return cls(
            entry_signal_date=trade.entry_signal_date,
            entry_date=trade.entry_date,
            entry_price=trade.entry_price,
            exit_signal_date=trade.exit_signal_date,
            exit_date=trade.exit_date,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            gross_pnl=trade.gross_pnl,
            gross_return=trade.gross_return,
            net_pnl=trade.net_pnl,
        )


class OpenPositionSchema(BaseModel):
    entry_signal_date: Date
    entry_date: Date
    entry_price: float
    quantity: int
    pending_exit_signal_date: Optional[Date]

    @classmethod
    def from_domain(cls, position: OpenPosition) -> "OpenPositionSchema":
        return cls(
            entry_signal_date=position.entry_signal_date,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            quantity=position.quantity,
            pending_exit_signal_date=position.pending_exit_signal_date,
        )


class EquityPointSchema(BaseModel):
    date: Date
    cash: float
    position_quantity: int
    position_market_value: float
    equity: float

    @classmethod
    def from_domain(cls, point: EquityPoint) -> "EquityPointSchema":
        return cls(
            date=point.date,
            cash=point.cash,
            position_quantity=point.position_quantity,
            position_market_value=point.position_market_value,
            equity=point.equity,
        )


class BacktestResultResponse(BaseModel):
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    config: BacktestConfigSchema
    trades: list[ExecutedTradeSchema]
    open_position: Optional[OpenPositionSchema]
    pending_entry_signal_date: Optional[Date]
    equity_curve: list[EquityPointSchema]

    @classmethod
    def from_domain(cls, result: BacktestResult) -> "BacktestResultResponse":
        return cls(
            provider_symbol=result.provider_symbol,
            interval=result.interval,
            strategy_id=result.strategy_id,
            strategy_name=result.strategy_name,
            config=BacktestConfigSchema.from_domain(result.config),
            trades=[ExecutedTradeSchema.from_domain(t) for t in result.trades],
            open_position=OpenPositionSchema.from_domain(result.open_position) if result.open_position else None,
            pending_entry_signal_date=result.pending_entry_signal_date,
            equity_curve=[EquityPointSchema.from_domain(p) for p in result.equity_curve],
        )
