from datetime import datetime
from typing import Any, Dict, Optional

class TradeLog:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.result_id_fk: Optional[int] = kwargs.get("result_id_fk")
        self.trade_number: Optional[int] = kwargs.get("trade_number")
        self.entry_timestamp = kwargs.get("entry_timestamp")
        self.exit_timestamp = kwargs.get("exit_timestamp")
        self.entry_price_1 = kwargs.get("entry_price_1")
        self.entry_price_2 = kwargs.get("entry_price_2")
        self.quantity_1 = kwargs.get("quantity_1")
        self.quantity_2 = kwargs.get("quantity_2")
        self.side_1 = kwargs.get("side_1")
        self.side_2 = kwargs.get("side_2")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)