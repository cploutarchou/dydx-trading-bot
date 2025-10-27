from typing import Any, Dict, Optional

class DYDXKey:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.user_id: Optional[int] = kwargs.get("user_id")
        self.network: Optional[str] = kwargs.get("network")
        self.chain_address: Optional[str] = kwargs.get("chain_address")
        self.encrypted_secret: Optional[str] = kwargs.get("encrypted_secret")
        self.is_active: Optional[bool] = kwargs.get("is_active")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self, include_secret: bool = False) -> Dict[str, Any]:
        d = self.__dict__.copy()
        if not include_secret:
            d.pop("encrypted_secret", None)
        return d

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)


class DYDXKeySettings:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.user_id: Optional[int] = kwargs.get("user_id")
        self.default_network: Optional[str] = kwargs.get("default_network")
        self.auto_switch_testnet: Optional[bool] = kwargs.get("auto_switch_testnet")
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)