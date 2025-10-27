from typing import Any, Dict, Optional

class BacktestStrategy:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.name: Optional[str] = kwargs.get("name")
        self.user_id: Optional[int] = kwargs.get("user_id")
        self.zscore_threshold: Optional[float] = kwargs.get("zscore_threshold")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class StrategyVersionHistory:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.strategy_id: Optional[int] = kwargs.get("strategy_id")
        self.version_number: Optional[int] = kwargs.get("version_number")
        self.config_snapshot = kwargs.get("config_snapshot")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class StrategyExecutionState:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.strategy_id: Optional[int] = kwargs.get("strategy_id")
        self.enabled: Optional[bool] = kwargs.get("enabled")
        self.status: Optional[str] = kwargs.get("status")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)