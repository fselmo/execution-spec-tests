"""Expect section structure of ethereum/tests fillers."""

from enum import Enum
from typing import Any, Dict, List, Literal, Union

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_validator,
)

from ethereum_test_base_types import Account, Address, CamelModel, EthereumTestRootModel, Storage
from ethereum_test_exceptions import TransactionExceptionInstanceOrList
from ethereum_test_forks import get_forks
from ethereum_test_types import Alloc

from .common import AddressOrTagInFiller, CodeInFiller, ValueInFiller, ValueOrTagInFiller
from .common.tags import Tag, TagDependentData, TagDict


class Indexes(BaseModel):
    """Class that represents an index filler."""

    data: int | List[Union[int, str]] | List[int] | str = Field(-1)
    gas: int | List[Union[int, str]] | List[int] | str = Field(-1)
    value: int | List[Union[int, str]] | List[int] | str = Field(-1)

    class Config:
        """Model Config."""

        extra = "forbid"


class AccountInExpectSection(BaseModel, TagDependentData):
    """Class that represents an account in expect section filler."""

    balance: ValueInFiller | None = Field(None)
    code: CodeInFiller | None = Field(None)
    nonce: ValueInFiller | None = Field(None)
    storage: Dict[ValueOrTagInFiller, ValueOrTagInFiller | Literal["ANY"]] | None = Field(None)

    @model_validator(mode="wrap")
    @classmethod
    def validate_fork_range_descriptor(cls, v: Any, handler: ValidatorFunctionWrapHandler):
        """Validate the "shouldnotexist" field, which makes this validator return `None`."""
        if isinstance(v, dict):
            if "shouldnotexist" in v:
                return None
        return handler(v)

    def tag_dependencies(self) -> Dict[str, Tag]:
        """Get tag dependencies."""
        tag_dependencies = {}
        if self.code is not None:
            tag_dependencies.update(self.code.tag_dependencies())
        if self.storage is not None:
            for key, value in self.storage.items():
                if isinstance(key, Tag):
                    tag_dependencies[key.name] = key
                if isinstance(value, Tag):
                    tag_dependencies[value.name] = value
        return tag_dependencies


class CMP(Enum):
    """Comparison action."""

    GT = 1
    LT = 2
    LE = 3
    GE = 4
    EQ = 5


def parse_networks(fork_with_operand: str) -> List[str]:
    """Parse fork_with_operand `>=Cancun` into [Cancun, Prague, ...]."""
    parsed_forks: List[str] = []
    all_forks_by_name = [fork.name() for fork in get_forks()]

    action: CMP = CMP.EQ
    fork: str = fork_with_operand
    if fork_with_operand[:1] == "<":
        action = CMP.LT
        fork = fork_with_operand[1:]
    if fork_with_operand[:1] == ">":
        action = CMP.GT
        fork = fork_with_operand[1:]
    if fork_with_operand[:2] == "<=":
        action = CMP.LE
        fork = fork_with_operand[2:]
    if fork_with_operand[:2] == ">=":
        action = CMP.GE
        fork = fork_with_operand[2:]

    if action == CMP.EQ:
        fork = fork_with_operand

    # translate unsupported fork names
    if fork == "EIP158":
        fork = "Byzantium"

    if action == CMP.EQ:
        parsed_forks.append(fork)
        return parsed_forks

    try:
        # print(all_forks_by_name)
        idx = all_forks_by_name.index(fork)
        # ['Frontier', 'Homestead', 'Byzantium', 'Constantinople', 'ConstantinopleFix',
        #  'Istanbul', 'MuirGlacier', 'Berlin', 'London', 'ArrowGlacier', 'GrayGlacier',
        #  'Paris', 'Shanghai', 'Cancun', 'Prague', 'Osaka']
    except ValueError:
        raise ValueError(f"Unsupported fork: {fork}") from Exception

    if action == CMP.GE:
        parsed_forks = all_forks_by_name[idx:]
    elif action == CMP.GT:
        parsed_forks = all_forks_by_name[idx + 1 :]
    elif action == CMP.LE:
        parsed_forks = all_forks_by_name[: idx + 1]
    elif action == CMP.LT:
        parsed_forks = all_forks_by_name[:idx]

    return parsed_forks


class ResultInFiller(EthereumTestRootModel, TagDependentData):
    """
    Post section in state test filler.

    A value of `None` for an address means that the account should not be in the state trie
    at the end of the test.
    """

    root: Dict[AddressOrTagInFiller, AccountInExpectSection | None]

    def tag_dependencies(self) -> Dict[str, Tag]:
        """Return all tags used in the result."""
        tag_dependencies: Dict[str, Tag] = {}
        for address, account in self.root.items():
            if isinstance(address, Tag):
                tag_dependencies[address.name] = address

            if account is None:
                continue

            tag_dependencies.update(account.tag_dependencies())

        return tag_dependencies

    def resolve(self, tags: TagDict) -> Alloc:
        """Resolve the post section."""
        post = Alloc()
        for address, account in self.root.items():
            if isinstance(address, Tag):
                address = address.resolve(tags)
            else:
                address = Address(address)

            if account is None:
                continue

            account_kwargs: Dict[str, Any] = {}
            if account.storage is not None:
                storage = Storage()
                for key, value in account.storage.items():
                    if isinstance(key, Tag):
                        key = key.resolve(tags)
                    if isinstance(value, Tag):
                        value = value.resolve(tags)
                    if value != "ANY":
                        storage[key] = value
                    else:
                        storage.set_expect_any(key)
                account_kwargs["storage"] = storage
            if account.code is not None:
                account_kwargs["code"] = account.code.compiled(tags)
            if account.balance is not None:
                account_kwargs["balance"] = account.balance
            if account.nonce is not None:
                account_kwargs["nonce"] = account.nonce

            post[address] = Account(**account_kwargs)
        return post


class ExpectSectionInStateTestFiller(CamelModel):
    """Expect section in state test filler."""

    indexes: Indexes = Field(default_factory=Indexes)
    network: List[str]
    result: ResultInFiller
    expect_exception: Dict[str, TransactionExceptionInstanceOrList] | None = None

    class Config:
        """Model Config."""

        extra = "forbid"

    @field_validator("network", mode="before")
    @classmethod
    def parse_networks(cls, network: List[str], info: ValidationInfo) -> List[str]:
        """Parse networks into array of forks."""
        forks: List[str] = []
        for net in network:
            forks.extend(parse_networks(net))
        return forks

    @field_validator("expect_exception", mode="before")
    @classmethod
    def parse_expect_exception(
        cls, expect_exception: Dict[str, str] | None, info: ValidationInfo
    ) -> Dict[str, str] | None:
        """Parse operand networks in exceptions."""
        if expect_exception is None:
            return expect_exception

        parsed_expect_exception: Dict[str, str] = {}
        for fork_with_operand, exception in expect_exception.items():
            forks: List[str] = parse_networks(fork_with_operand)
            for fork in forks:
                if fork in parsed_expect_exception:
                    raise ValueError(
                        "Expect exception has redundant fork with multiple exceptions!"
                    )
                parsed_expect_exception[fork] = exception

        return parsed_expect_exception

    def has_index(self, d: int, g: int, v: int) -> bool:
        """Check if there is index set in indexes."""
        d_match: bool = False
        g_match: bool = False
        v_match: bool = False

        # Check if data index match
        if isinstance(self.indexes.data, int):
            d_match = True if self.indexes.data == -1 or self.indexes.data == d else False
        elif isinstance(self.indexes.data, list):
            d_match = True if self.indexes.data.count(d) else False

        # Check if gas index match
        if isinstance(self.indexes.gas, int):
            g_match = True if self.indexes.gas == -1 or self.indexes.gas == g else False
        elif isinstance(self.indexes.gas, list):
            g_match = True if self.indexes.gas.count(g) else False

        # Check if value index match
        if isinstance(self.indexes.value, int):
            v_match = True if self.indexes.value == -1 or self.indexes.value == v else False
        elif isinstance(self.indexes.value, list):
            v_match = True if self.indexes.value.count(v) else False

        return d_match and g_match and v_match
