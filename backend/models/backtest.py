from datetime import datetime
from typing import Any, Dict, List, Optional


class BacktestRun:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.run_id: Optional[str] = kwargs.get("run_id")
        self.status: Optional[str] = kwargs.get("status", "running")
        self.created_at: Optional[datetime] = kwargs.get("created_at")
        self.start_date: Optional[str] = kwargs.get("start_date")
        self.end_date: Optional[str] = kwargs.get("end_date")
        self.num_pairs: Optional[int] = kwargs.get("num_pairs")
        self.total_markets: Optional[int] = kwargs.get("total_markets")
        self.user_id: Optional[int] = kwargs.get("user_id")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class BacktestResult:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.market_1: Optional[str] = kwargs.get("market_1")
        self.market_2: Optional[str] = kwargs.get("market_2")
        self.run_id_fk: Optional[int] = kwargs.get("run_id_fk")
        self.created_at: Optional[datetime] = kwargs.get("created_at")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class BacktestLog:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.run_id_fk: Optional[int] = kwargs.get("run_id_fk")
        self.message: Optional[str] = kwargs.get("message")
        self.level: Optional[str] = kwargs.get("level")
        self.created_at: Optional[datetime] = kwargs.get("created_at")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class BacktestTrade:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.trade_id: Optional[str] = kwargs.get("trade_id")
        self.run_id_fk: Optional[int] = kwargs.get("run_id_fk")
        self.market_1: Optional[str] = kwargs.get("market_1")
        self.market_2: Optional[str] = kwargs.get("market_2")
        self.entry_timestamp = kwargs.get("entry_timestamp")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class BacktestPosition:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.position_id: Optional[str] = kwargs.get("position_id")
        self.run_id_fk: Optional[int] = kwargs.get("run_id_fk")
        self.market_1: Optional[str] = kwargs.get("market_1")
        self.market_2: Optional[str] = kwargs.get("market_2")
        self.status: Optional[str] = kwargs.get("status")
        self.entry_timestamp = kwargs.get("entry_timestamp")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class BacktestCandle:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.run_id_fk: Optional[int] = kwargs.get("run_id_fk")
        self.market: Optional[str] = kwargs.get("market")
        self.timestamp = kwargs.get("timestamp")
        self.resolution: Optional[str] = kwargs.get("resolution")
        self.open_price: Optional[float] = kwargs.get("open_price")
        self.high_price: Optional[float] = kwargs.get("high_price")
        self.low_price: Optional[float] = kwargs.get("low_price")
        self.close_price: Optional[float] = kwargs.get("close_price")
        self.volume: Optional[float] = kwargs.get("volume")
        self.trades_count: Optional[int] = kwargs.get("trades_count")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class BacktestComparison:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.name: Optional[str] = kwargs.get("name")
        self.description: Optional[str] = kwargs.get("description")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)