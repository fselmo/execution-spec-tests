"""Account structure of ethereum/tests fillers."""

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Set, Tuple

from pydantic import BaseModel

if TYPE_CHECKING:
    from .environment import EnvironmentInStateTestFiller
    from .expect_section import ResultInFiller

from ethereum_test_base_types import (
    Account,
    Address,
    Bytes,
    EthereumTestRootModel,
    HexNumber,
    Storage,
)
from ethereum_test_types import Alloc
from ethereum_test_types.block_types import EnvironmentGeneric

from .common import (
    AddressOrTagInFiller,
    CodeInFiller,
    ContractTag,
    SenderTag,
    Tag,
    TagDependentData,
    TagDict,
    ValueInFiller,
    ValueOrTagInFiller,
)


class StorageInPre(EthereumTestRootModel):
    """Class that represents a storage in pre-state."""

    root: Dict[ValueInFiller, ValueOrTagInFiller]

    def tag_dependencies(self) -> Mapping[str, Tag]:
        """Get tag dependencies."""
        tag_dependencies: Dict[str, Tag] = {}
        for k, v in self.root.items():
            if isinstance(k, Tag):
                tag_dependencies[k.name] = k
            if isinstance(v, Tag):
                tag_dependencies[v.name] = v
        return tag_dependencies

    def resolve(self, tags: TagDict) -> Dict[ValueInFiller, ValueInFiller]:
        """Resolve the storage."""
        resolved_storage: Dict[ValueInFiller, ValueInFiller] = {}
        for key, value in self.root.items():
            if isinstance(value, Tag):
                resolved_storage[key] = HexNumber(int.from_bytes(value.resolve(tags), "big"))
            else:
                resolved_storage[key] = value
        return resolved_storage


class AccountInFiller(BaseModel, TagDependentData):
    """Class that represents an account in filler."""

    balance: ValueInFiller | None = None
    code: CodeInFiller | None = None
    nonce: ValueInFiller | None = None
    storage: StorageInPre | None = None

    class Config:
        """Model Config."""

        extra = "forbid"
        arbitrary_types_allowed = True  # For CodeInFiller

    def tag_dependencies(self) -> Mapping[str, Tag]:
        """Get tag dependencies."""
        tag_dependencies: Dict[str, Tag] = {}
        if self.storage is not None:
            tag_dependencies.update(self.storage.tag_dependencies())
        if self.code is not None and isinstance(self.code, CodeInFiller):
            tag_dependencies.update(self.code.tag_dependencies())
        return tag_dependencies

    def resolve(self, tags: TagDict) -> Dict[str, Any]:
        """Resolve the account."""
        account_properties: Dict[str, Any] = {}
        if self.balance is not None:
            account_properties["balance"] = self.balance
        if self.code is not None:
            if compiled_code := self.code.compiled(tags):
                account_properties["code"] = compiled_code
        if self.nonce is not None:
            account_properties["nonce"] = self.nonce
        if self.storage is not None:
            if resolved_storage := self.storage.resolve(tags):
                account_properties["storage"] = resolved_storage
        return account_properties

    def __hash__(self) -> int:
        """Generate deterministic hash for the account."""
        # Create a tuple of hashable representations
        hash_tuple = (
            self.balance if self.balance is not None else None,
            str(self.code) if self.code is not None else None,
            self.nonce if self.nonce is not None else None,
            str(self.storage) if self.storage is not None else None,
        )
        return hash(hash_tuple)


class PreInFiller(EthereumTestRootModel):
    """Class that represents a pre-state in filler."""

    root: Dict[AddressOrTagInFiller, AccountInFiller]

    def _build_dependency_graph(
        self,
    ) -> Tuple[Dict[str, Set[str]], Dict[str, AddressOrTagInFiller]]:
        """Build a dependency graph for all tags."""
        dep_graph: Dict[str, Set[str]] = {}
        tag_to_address: Dict[str, AddressOrTagInFiller] = {}

        # First pass: identify all tags and their dependencies
        for address_or_tag, account in self.root.items():
            if isinstance(address_or_tag, Tag):
                tag_name = address_or_tag.name
                tag_to_address[tag_name] = address_or_tag
                dep_graph[tag_name] = set()

                # Get dependencies from account properties
                dependencies = account.tag_dependencies()
                for dep_name in dependencies:
                    if dep_name != tag_name:  # Ignore self-references
                        dep_graph[tag_name].add(dep_name)

        return dep_graph, tag_to_address

    def _topological_sort(self, dep_graph: Dict[str, Set[str]]) -> List[str]:
        """Perform topological sort on dependency graph."""
        # Create a copy to modify
        graph = {node: deps.copy() for node, deps in dep_graph.items()}

        # Find nodes with no dependencies
        no_deps = [node for node, deps in graph.items() if not deps]
        sorted_nodes = []

        while no_deps:
            # Process a node with no dependencies
            node = no_deps.pop()
            sorted_nodes.append(node)

            # Remove this node from other nodes' dependencies
            for other_node, deps in graph.items():
                if node in deps:
                    deps.remove(node)
                    if not deps and other_node not in sorted_nodes:
                        no_deps.append(other_node)

        # Check for cycles
        remaining = [node for node in graph if node not in sorted_nodes]
        if remaining:
            # Handle cycles by processing remaining nodes in any order
            # This works because self-references are allowed
            sorted_nodes.extend(remaining)

        return sorted_nodes

    def setup(
        self,
        pre: Alloc,
        all_dependencies: Dict[str, Tag],
        env: "EnvironmentInStateTestFiller | None" = None,
        expect_result: "ResultInFiller | None" = None,
        request: Any = None,
    ) -> TagDict:
        """Resolve the pre-state with improved tag resolution."""
        resolved_accounts: TagDict = {}

        # Separate tagged and non-tagged accounts
        tagged_accounts = {}
        non_tagged_accounts = {}

        for address_or_tag, account in self.root.items():
            if isinstance(address_or_tag, Tag):
                tagged_accounts[address_or_tag] = account
            else:
                non_tagged_accounts[address_or_tag] = account

        # Step 1: Process non-tagged accounts but don't compile code yet
        # We'll compile code later after all tags are resolved
        non_tagged_to_process = []
        for address, account in non_tagged_accounts.items():
            non_tagged_to_process.append((address, account))
            resolved_accounts[address.hex()] = address

        # Step 2: Build dependency graph for tagged accounts
        dep_graph, tag_to_address = self._build_dependency_graph()

        # Step 3: Get topological order
        resolution_order = self._topological_sort(dep_graph)

        # Step 4: Pre-deploy all contract tags and pre-fund EOAs to get addresses
        for tag_name in resolution_order:
            if tag_name in tag_to_address:
                tag = tag_to_address[tag_name]
                if isinstance(tag, ContractTag):
                    # Check if this is a coinbase tag during pre-alloc generation
                    is_coinbase = (
                        env is not None
                        and isinstance(env.current_coinbase, Tag)
                        and env.current_coinbase.name == tag_name
                    )

                    if is_coinbase and expect_result is not None and request is not None:
                        # Check if we're in pre-alloc generation or usage mode
                        generate_groups = request.config.getoption(
                            "generate_pre_alloc_groups", False
                        )
                        use_groups = request.config.getoption("use_pre_alloc_groups", False)
                        if generate_groups or use_groups:
                            # Get pre-state account
                            coinbase_account = tagged_accounts.get(tag)

                            # Check if account has any pre-state
                            has_pre_state = coinbase_account is not None and (
                                coinbase_account.code is not None
                                or coinbase_account.storage is not None
                                or coinbase_account.balance is not None
                                or coinbase_account.nonce is not None
                            )

                            # Find post-state expectations for this coinbase
                            coinbase_post_account = None
                            has_post_state = False
                            for addr_or_tag, result_account in expect_result.root.items():
                                if isinstance(addr_or_tag, Tag) and addr_or_tag.name == tag_name:
                                    if result_account is not None:
                                        has_post_state = True
                                        coinbase_post_account = result_account
                                    break

                            # If no state changes, use the default fee_recipient
                            if not has_pre_state and not has_post_state:
                                deployed_address = EnvironmentGeneric.model_fields[
                                    "fee_recipient"
                                ].default
                                resolved_accounts[tag_name] = deployed_address
                            else:
                                # Use hash to create deterministic address
                                # Combine pre and post hashes
                                pre_hash = hash(coinbase_account) if coinbase_account else 0
                                post_hash = (
                                    hash(coinbase_post_account) if coinbase_post_account else 0
                                )
                                combined_hash = hash((pre_hash, post_hash))

                                hash_bytes = abs(combined_hash).to_bytes(32, byteorder="big")
                                # Start with 0xc01b (coinbase) prefix
                                address_bytes = b"\xc0\x1b" + hash_bytes[:18]
                                deployed_address = Address(address_bytes)
                                resolved_accounts[tag_name] = deployed_address
                                # Manually add to pre-alloc if it doesn't exist
                                if deployed_address not in pre:
                                    pre[deployed_address] = Account()
                        else:
                            # Not in pre-alloc generation, normal deployment
                            deployed_address = pre.deploy_contract(
                                code=b"",  # Temporary placeholder
                                label=tag_name,
                            )
                            resolved_accounts[tag_name] = deployed_address
                    else:
                        # Not a coinbase tag, normal deployment
                        deployed_address = pre.deploy_contract(
                            code=b"",  # Temporary placeholder
                            label=tag_name,
                        )
                        resolved_accounts[tag_name] = deployed_address
                elif isinstance(tag, SenderTag):
                    # Create EOA to get address - use amount=1 to ensure account is created
                    eoa = pre.fund_eoa(amount=1, label=tag_name)
                    # Store the EOA object for SenderKeyTag resolution
                    resolved_accounts[tag_name] = eoa

        # Step 5: Now resolve all properties with all addresses available
        for tag_name in resolution_order:
            if tag_name in tag_to_address:
                tag = tag_to_address[tag_name]
                assert isinstance(tag, (ContractTag, SenderTag)), (
                    f"Tag {tag_name} is not a contract or sender"
                )
                account = tagged_accounts[tag]

                # All addresses are now available, so resolve properties
                account_properties = account.resolve(resolved_accounts)

                if isinstance(tag, ContractTag):
                    # Update the already-deployed contract
                    deployed_address = resolved_accounts[tag_name]
                    deployed_account = pre[deployed_address]

                    if deployed_account is not None:
                        if "code" in account_properties:
                            deployed_account.code = Bytes(account_properties["code"])
                        if "balance" in account_properties:
                            deployed_account.balance = account_properties["balance"]
                        if "nonce" in account_properties:
                            deployed_account.nonce = account_properties["nonce"]
                        if "storage" in account_properties:
                            deployed_account.storage = Storage(root=account_properties["storage"])

                elif isinstance(tag, SenderTag):
                    eoa_account = pre[resolved_accounts[tag_name]]

                    if eoa_account is not None:
                        if "balance" in account_properties:
                            eoa_account.balance = account_properties["balance"]
                        if "nonce" in account_properties:
                            eoa_account.nonce = account_properties["nonce"]
                        if "code" in account_properties:
                            eoa_account.code = Bytes(account_properties["code"])
                        if "storage" in account_properties:
                            eoa_account.storage = Storage(root=account_properties["storage"])

        # Step 6: Now process non-tagged accounts (including code compilation)
        for address, account in non_tagged_to_process:
            account_properties = account.resolve(resolved_accounts)
            if "balance" in account_properties:
                pre.fund_address(address, account_properties["balance"])

            existing_account = pre[address]
            if existing_account is not None:
                if "code" in account_properties:
                    existing_account.code = Bytes(account_properties["code"])
                if "nonce" in account_properties:
                    existing_account.nonce = account_properties["nonce"]
                if "storage" in account_properties:
                    existing_account.storage = Storage(root=account_properties["storage"])

        # Step 7: Handle any extra dependencies not in pre
        for extra_dependency in all_dependencies:
            if extra_dependency not in resolved_accounts:
                if all_dependencies[extra_dependency].type != "eoa":
                    raise ValueError(f"Contract dependency {extra_dependency} not found in pre")

                # Create new EOA - this will have a dynamically generated key and address
                eoa = pre.fund_eoa(amount=0, label=extra_dependency)
                resolved_accounts[extra_dependency] = eoa

        return resolved_accounts
