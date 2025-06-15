"""
Deep Trie Pytest Fixture

Pytest fixtures for creating deep trie test conditions.
Integrates with existing pytest fixture system to provide pre-configured
state allocations that stress the Ethereum state trie.
"""

import pytest
from typing import Dict, List

from ethereum_test_base_types import ZeroPaddedHexNumber
from ethereum_test_tools import (
    Account,
    Storage,
    Alloc,
    Bytes,
)


class DeepTrieFixture:
    """
    Test fixture generator for creating deep trie structures.
    """

    def __init__(
        self,
        account_count: int = 1000,
        storage_keys_per_account: int = 25,
        contract_count: int = 50,
        cluster_count: int = 10,
    ):
        self.account_count = account_count
        self.storage_keys_per_account = storage_keys_per_account
        self.contract_count = contract_count
        self.cluster_count = cluster_count

    def setup_deep_trie_pre(self, pre: Alloc) -> Dict[str, List[str]]:
        """
        Set up a complete deep trie pre-allocation.

        Args:
            pre: The Alloc object to populate with deep trie accounts

        Returns:
            Dictionary containing lists of addresses by category
        """
        result = {}

        # Create spread accounts across address space
        result["spread"] = self._create_spread_accounts(pre)

        # Create clustered accounts in dense regions
        result["clustered"] = self._create_clustered_accounts(pre)

        # Create contract accounts with code and storage
        result["contracts"] = self._create_contract_accounts(pre)

        # Add funded test account for transactions
        test_account_address = pre.fund_eoa(amount=10**23)  # 100,000 ETH
        result["test_account"] = [test_account_address]

        return result

    def _create_spread_accounts(self, pre: Alloc) -> List[str]:
        """Create accounts that force deep trie paths where CREATE contracts will land."""
        addresses = []
        
        # Strategy: Calculate where CREATE operations will place new contracts
        # and engineer the trie to have maximum depth at those locations
        
        # Factory will be at 0x1234567890123456789012345678901234567890 with nonce starting at 2
        factory_addr = 0x1234567890123456789012345678901234567890
        
        # Pre-calculate the first several CREATE addresses from this factory
        # CREATE address = keccak256(rlp([creator_address, nonce]))[-20:]
        # We'll create accounts that share long prefixes with these CREATE addresses
        
        import rlp
        from Crypto.Hash import keccak
        
        create_addresses = []
        for nonce in range(2, 2 + 166):  # Factory starts at nonce 2, creates 166 contracts
            # RLP encode [address, nonce]
            addr_bytes = factory_addr.to_bytes(20, 'big')
            rlp_data = rlp.encode([addr_bytes, nonce])
            
            # Keccak256 and take last 20 bytes
            hash_obj = keccak.new(digest_bits=256)
            hash_obj.update(rlp_data)
            create_addr = int.from_bytes(hash_obj.digest()[-20:], 'big')
            create_addresses.append(create_addr)
        
        # Now create accounts that share long prefixes with these CREATE addresses
        # This will force the trie to be deep where the new contracts will be inserted
        for i, create_addr in enumerate(create_addresses[:self.account_count]):
            # Create an account that shares a long prefix with this CREATE address
            # but differs in the last few nibbles to force deep branching
            
            # Use the CREATE address as base but modify last nibble to create collision
            collision_addr = create_addr ^ (i % 16)  # Modify last nibble
            address_str = f"0x{collision_addr:040x}"

            storage = Storage()
            # Create storage that will also collide with contract storage
            for j in range(self.storage_keys_per_account):
                # Base storage key that might collide with new contract storage
                storage_key = j  # Simple incrementing keys
                storage[f"0x{storage_key:064x}"] = j

            account = Account(
                nonce=ZeroPaddedHexNumber(0),
                balance=ZeroPaddedHexNumber(10**20),
                code=Bytes(b""),
                storage=storage,
            )

            pre[address_str] = account
            addresses.append(address_str)
        
        # Fill remaining accounts with spread pattern if needed
        for i in range(len(create_addresses), self.account_count):
            base_addr = 0x1000000000000000000000000000000000000000 + (i * 0x1000)
            address_str = f"0x{base_addr:040x}"
            
            account = Account(
                nonce=ZeroPaddedHexNumber(0),
                balance=ZeroPaddedHexNumber(10**20),
                code=Bytes(b""),
                storage=Storage(),
            )
            
            pre[address_str] = account
            addresses.append(address_str)

        return addresses

    def _create_clustered_accounts(self, pre: Alloc) -> List[str]:
        """Create dense clusters of accounts."""
        addresses = []
        accounts_per_cluster = self.account_count // self.cluster_count

        for cluster in range(self.cluster_count):
            base_addr = 0x1000000000000000000000000000000000000000 + (
                cluster * 0x1000000000000000
            )

            for i in range(accounts_per_cluster):
                address_str = f"0x{base_addr + i:040x}"

                storage = Storage()
                for j in range(self.storage_keys_per_account):
                    storage[f"0x{j:064x}"] = cluster * 1000 + i * 100 + j

                account = Account(
                    nonce=ZeroPaddedHexNumber(0),
                    balance=ZeroPaddedHexNumber(10**20),
                    code=Bytes(b""),
                    storage=storage,
                )

                pre[address_str] = account
                addresses.append(address_str)

        return addresses

    def _create_contract_accounts(self, pre: Alloc) -> List[str]:
        """Create contract accounts with code and storage."""
        addresses = []

        contract_code_hex = (
            "608060405234801561001057600080fd5b50600436106100365760003560e01c8063371303c0"
            "1461003b5780639ae1e92714610057575b600080fd5b610055600480360381019061005091"
            "906100a4565b610073565b005b61005f61007d565b60405161006a91906100e3565b604051"
            "80910390f35b8060008190555050565b60008054905090565b600080fd5b6000819050919050"
        )

        for i in range(self.contract_count):
            address_str = f"0x2000000000000000000000000000000000{i:06x}"

            storage = Storage()
            for j in range(self.storage_keys_per_account // 2):
                storage[f"0x{j:064x}"] = i * 1000 + j

            account = Account(
                nonce=ZeroPaddedHexNumber(1),
                balance=ZeroPaddedHexNumber(0),
                code=Bytes(bytes.fromhex(contract_code_hex)),
                storage=storage,
            )

            pre[address_str] = account
            addresses.append(address_str)

        return addresses


# Pytest fixtures that build on the existing 'pre' fixture


@pytest.fixture
def pre_deep_trie(pre):
    """
    Pytest fixture that extends the base 'pre' fixture with deep trie complexity.

    Use this when you want the standard deep trie setup.
    """
    fixture = DeepTrieFixture()
    addresses = fixture.setup_deep_trie_pre(pre)

    # Add metadata to the pre object for test access
    pre._deep_trie_addresses = addresses
    pre._deep_trie_stats = {
        "total_accounts": len(addresses["spread"])
        + len(addresses["clustered"])
        + len(addresses["contracts"])
        + len(addresses["test_account"]),
        "test_account": addresses["test_account"][0],
    }

    return pre


@pytest.fixture
def pre_deep_trie_small(pre):
    """
    Pytest fixture with smaller deep trie setup for faster tests.
    """
    fixture = DeepTrieFixture(
        account_count=250,  # Smaller for faster execution
        storage_keys_per_account=15,
        contract_count=10,
        cluster_count=5,
    )
    addresses = fixture.setup_deep_trie_pre(pre)

    pre._deep_trie_addresses = addresses
    pre._deep_trie_stats = {
        "total_accounts": len(addresses["spread"])
        + len(addresses["clustered"])
        + len(addresses["contracts"])
        + len(addresses["test_account"]),
        "test_account": addresses["test_account"][0],
    }

    return pre


@pytest.fixture
def pre_deep_trie_large(pre):
    """
    Pytest fixture with large deep trie setup for stress testing.
    """
    fixture = DeepTrieFixture(
        account_count=2000,  # Larger for maximum stress
        storage_keys_per_account=40,
        contract_count=100,
        cluster_count=20,
    )
    addresses = fixture.setup_deep_trie_pre(pre)

    pre._deep_trie_addresses = addresses
    pre._deep_trie_stats = {
        "total_accounts": len(addresses["spread"])
        + len(addresses["clustered"])
        + len(addresses["contracts"])
        + len(addresses["test_account"]),
        "test_account": addresses["test_account"][0],
    }

    return pre


@pytest.fixture
def pre_deep_trie_custom():
    """
    Pytest fixture factory for custom deep trie configurations.

    Usage:
        @pytest.mark.parametrize("config", [
            {"account_count": 500, "storage_keys_per_account": 20},
            {"account_count": 1000, "storage_keys_per_account": 30},
        ])
        def test_something(pre, pre_deep_trie_custom, config):
            deep_pre = pre_deep_trie_custom(pre, **config)
            # test with deep_pre
    """

    def _setup_custom(pre, **kwargs):
        fixture = DeepTrieFixture(**kwargs)
        addresses = fixture.setup_deep_trie_pre(pre)

        pre._deep_trie_addresses = addresses
        pre._deep_trie_stats = {
            "total_accounts": len(addresses["spread"])
            + len(addresses["clustered"])
            + len(addresses["contracts"])
            + len(addresses["test_account"]),
            "test_account": addresses["test_account"][0],
        }

        return pre

    return _setup_custom


# Utility functions for tests


def get_test_account(pre_with_deep_trie):
    """Get the funded test account from a deep trie pre allocation."""
    return pre_with_deep_trie._deep_trie_stats["test_account"]


def get_deep_trie_stats(pre_with_deep_trie):
    """Get statistics about the deep trie allocation."""
    return pre_with_deep_trie._deep_trie_stats


def get_deep_trie_addresses(pre_with_deep_trie):
    """Get the address lists by category."""
    return pre_with_deep_trie._deep_trie_addresses


# For direct usage without pytest fixtures
def setup_deep_trie_pre(pre, **kwargs):
    """
    Direct function to set up deep trie pre-allocation.

    Use this if you need to set up deep trie state outside of pytest fixtures.
    """
    fixture = DeepTrieFixture(**kwargs)
    return fixture.setup_deep_trie_pre(pre)
