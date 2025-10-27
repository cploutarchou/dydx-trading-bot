from typing import Any, Dict, Optional

class BotSetting:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.section: Optional[str] = kwargs.get("section")
        self.key: Optional[str] = kwargs.get("key")
        self.value: Optional[str] = kwargs.get("value")
        self.value_type: Optional[str] = kwargs.get("value_type")
        self.description: Optional[str] = kwargs.get("description")
        self.default_value: Optional[str] = kwargs.get("default_value")
        self.is_active: Optional[bool] = kwargs.get("is_active")
        self.version: Optional[int] = kwargs.get("version")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class RedisSetting:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.enabled: Optional[bool] = kwargs.get("enabled")
        self.host: Optional[str] = kwargs.get("host")
        self.port: Optional[int] = kwargs.get("port")
        self.db: Optional[int] = kwargs.get("db")
        self.password: Optional[str] = kwargs.get("password")
        self.ssl: Optional[bool] = kwargs.get("ssl")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)