"""Account structure of ethereum/tests fillers."""

from typing import Any, Dict, Set

from pydantic import BaseModel

from ethereum_test_base_types import EthereumTestRootModel
from ethereum_test_types import Alloc

from .common import CodeInFiller, ValueInFiller, ValueOrTagInFiller
from .common.common import AddressOrTagInFiller
from .common.tags import ContractTag, SenderTag, Tag, TagDependentData, TagDict


class StorageInPre(EthereumTestRootModel):
    """Class that represents a storage in pre-state."""

    root: Dict[ValueInFiller, ValueOrTagInFiller]

    def dependencies(self) -> Set[str]:
        """Get dependencies."""
        dependencies = set()
        for k, v in self.root.items():
            if isinstance(k, Tag):
                dependencies.add(k.name)
            if isinstance(v, Tag):
                dependencies.add(v.name)
        return dependencies

    def resolve(self, tags: TagDict) -> Dict[ValueInFiller, ValueInFiller]:
        """Resolve the storage."""
        resolved_storage = {}
        for key, value in self.root.items():
            if isinstance(value, Tag):
                resolved_storage[key] = int.from_bytes(value.resolve(tags), "big")
            else:
                resolved_storage[key] = value
        return resolved_storage


class AccountInFiller(BaseModel, TagDependentData):
    """Class that represents an account in filler."""

    balance: ValueInFiller
    code: CodeInFiller
    nonce: ValueInFiller
    storage: StorageInPre

    class Config:
        """Model Config."""

        extra = "forbid"
        arbitrary_types_allowed = True  # For CodeInFiller

    def dependencies(self) -> Set[str]:
        """Get dependencies."""
        dependencies = set()
        dependencies.update(self.storage.dependencies())
        if isinstance(self.code, CodeInFiller):
            dependencies.update(self.code.dependencies())
        return dependencies

    def resolve(self, tags: TagDict) -> Dict[str, Any]:
        """Resolve the account."""
        account_properties = {}
        if self.balance > 0:
            account_properties["balance"] = self.balance
        if compiled_code := self.code.compiled(tags):
            account_properties["code"] = compiled_code
        if self.nonce > 0:
            account_properties["nonce"] = self.nonce
        if resolved_storage := self.storage.resolve(tags):
            account_properties["storage"] = resolved_storage
        return account_properties


class PreInFiller(EthereumTestRootModel):
    """Class that represents a pre-state in filler."""

    root: Dict[AddressOrTagInFiller, AccountInFiller]

    def setup(self, pre: Alloc) -> TagDict:
        """Resolve the pre-state."""
        max_tries = len(self.root)

        unresolved_accounts = dict(self.root)
        resolved_accounts: TagDict = {}

        while max_tries > 0:
            # Naive approach to resolve accounts
            unresolved_accounts_keys = list(unresolved_accounts.keys())
            for address_or_tag in unresolved_accounts_keys:
                account = unresolved_accounts[address_or_tag]
                dependencies = account.dependencies()
                # check if all dependencies are resolved
                if all(dependency in resolved_accounts for dependency in dependencies):
                    account_properties = account.resolve(resolved_accounts)
                    if isinstance(address_or_tag, Tag):
                        if isinstance(address_or_tag, ContractTag):
                            resolved_accounts[address_or_tag.name] = pre.deploy_contract(
                                **account_properties
                            )
                        elif isinstance(address_or_tag, SenderTag):
                            if "balance" in account_properties:
                                account_properties["amount"] = account_properties.pop("balance")
                            resolved_accounts[address_or_tag.name] = pre.fund_eoa(
                                **account_properties
                            )
                        else:
                            raise ValueError(f"Unknown tag type: {address_or_tag}")
                    else:
                        raise ValueError(f"Unknown tag type: {address_or_tag}")
                    del unresolved_accounts[address_or_tag]

            max_tries -= 1
        assert len(unresolved_accounts) == 0, (
            f"Unresolved accounts: {unresolved_accounts}, probably a circular dependency"
        )
        return resolved_accounts
