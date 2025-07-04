"""Classes to manage tags in static state tests."""

import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Generic, TypeVar

from pydantic import BaseModel, model_validator

from ethereum_test_base_types import Address, Hash
from ethereum_test_types import EOA

TagDict = Dict[str, Address | EOA]

T = TypeVar("T", bound=Address | Hash)


class Tag(BaseModel, Generic[T]):
    """Tag."""

    name: str
    type: ClassVar[str] = ""
    regex_pattern: ClassVar[re.Pattern] = re.compile(r"<\w+:(\w+)(:0x.+)?>")

    def __hash__(self) -> int:
        """Hash based on original string for use as dict key."""
        return hash(f"{self.type}:{self.name}")

    @model_validator(mode="before")
    @classmethod
    def validate_from_string(cls, data: Any) -> Any:
        """Validate the sender tag from string: <eoa:name:0x...>."""
        if isinstance(data, str):
            if m := cls.regex_pattern.match(data):
                name = m.group(1)
                return {"name": name}
        return data

    def resolve(self, tags: TagDict) -> T:
        """Resolve the tag."""
        raise NotImplementedError("Subclasses must implement this method")


class TagDependentData(ABC):
    """Data for resolving tags."""

    @abstractmethod
    def tag_dependencies(self) -> Dict[str, Tag]:
        """Get tag dependencies."""
        pass


class AddressTag(Tag[Address]):
    """Address tag."""

    def resolve(self, tags: TagDict) -> Address:
        """Resolve the tag."""
        assert self.name in tags, f"Tag {self.name} not found in tags"
        return Address(tags[self.name])


class ContractTag(AddressTag):
    """Contract tag."""

    type: ClassVar[str] = "contract"
    resolved_address: Address | None = None
    regex_pattern: ClassVar[re.Pattern] = re.compile(r"<contract:(\w+)(:0x.+)?>")


class SenderTag(AddressTag):
    """Sender tag."""

    type: ClassVar[str] = "eoa"
    regex_pattern: ClassVar[re.Pattern] = re.compile(r"<eoa:(\w+)(:0x.+)?>")


class SenderKeyTag(Tag[EOA]):
    """Sender eoa tag."""

    type: ClassVar[str] = "eoa"
    regex_pattern: ClassVar[re.Pattern] = re.compile(r"<eoa:(\w+)(:0x.+)?>")

    def resolve(self, tags: TagDict) -> EOA:
        """Resolve the tag."""
        assert self.name in tags, f"Tag {self.name} not found in tags"
        eoa = tags[self.name]
        assert isinstance(eoa, EOA), f"Tag {self.name} is not an EOA"
        return eoa
