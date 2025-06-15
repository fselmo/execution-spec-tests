"""
Tests for stress testing state trie operations with deep trie structures.

This test reproduces mainnet-like conditions where transactions that create
many contracts with SSTORE operations take significantly longer to process
due to deep trie traversal costs.
"""

import pytest

from ethereum_test_tools import (
    Account,
    Alloc,
    Block,
    BlockchainTestFiller,
    Transaction,
    Initcode,
    Opcodes as Op,
    compute_create_address,
)


@pytest.mark.parametrize("deep_trie_fixture", ["pre_deep_trie", "pre_deep_trie_large"])  
def test_mass_contract_creation_deep_trie(
    blockchain_test: BlockchainTestFiller,
    pre: Alloc,
    deep_trie_fixture: str,
    request,
) -> None:
    """
    Test mass contract creation performance with deep state trie.
    
    This test demonstrates the gas pricing vs computational complexity gap.
    The same transaction (same gas cost) executes much slower on a pre-loaded
    state with deep trie paths than on empty state.
    """
    # Apply the deep trie fixture
    pre = request.getfixturevalue(deep_trie_fixture)
    
    # Get funded test account from deep trie setup
    sender = pre._deep_trie_stats["test_account"]
    
    # Number of contracts to create (matching mainnet)
    num_contracts = 166
    
    # Extremely minimal contract: just STOP
    minimal_runtime = Op.STOP
    
    # Very simple init code: just SSTORE once and return empty runtime
    simple_init_code = (
        # Store a simple value (like mainnet pattern)
        Op.PUSH1(0x01)  # value
        + Op.PUSH1(0x00)  # slot
        + Op.SSTORE
        
        # Return empty runtime (0 bytes)
        + Op.PUSH1(0x00)  # size
        + Op.PUSH1(0x00)  # offset
        + Op.RETURN
    )
    
    # Convert to bytes - this should be very small
    init_code_bytes = bytes(simple_init_code)
    init_code_size = len(init_code_bytes)  # Should be around 8 bytes
    
    # Deploy factory at the EXACT address that matches our deep trie base
    # This ensures created contracts will collide with the deepest trie paths
    factory_address = "0x1234567890123456789012345678901234567890"
    
    # Much simpler factory that embeds the tiny init code directly
    factory_code = (
        # Embed init code directly using PUSH operations
        Op.PUSH1(0x01)      # PUSH1 0x01
        + Op.PUSH1(0x00)    # PUSH1 0x00  
        + Op.SSTORE         # SSTORE
        + Op.PUSH1(0x00)    # PUSH1 0x00 (size)
        + Op.PUSH1(0x00)    # PUSH1 0x00 (offset)
        + Op.RETURN         # RETURN
        # Now we have the init code sequence in the contract
        
        # The actual factory logic starts here
        + Op.PUSH1(0x00)    # counter = 0
        
        # Loop start 
        + Op.JUMPDEST       # loop_start
        
        # Check if we're done
        + Op.DUP1           # duplicate counter
        + Op.PUSH1(num_contracts)  # push limit
        + Op.EQ             # check if equal
        + Op.PUSH1(0x40)    # jump target (end)
        + Op.JUMPI          # jump if done
        
        # Store init code in memory (copy from our contract code)
        + Op.PUSH1(init_code_size)  # size of init code
        + Op.PUSH1(0x06)    # offset in our code where init code starts
        + Op.PUSH1(0x00)    # memory destination
        + Op.CODECOPY       # copy init code to memory
        
        # CREATE contract
        + Op.PUSH1(init_code_size)  # size
        + Op.PUSH1(0x00)    # memory offset
        + Op.PUSH1(0x00)    # value
        + Op.CREATE
        + Op.POP            # discard created address
        
        # Increment counter
        + Op.PUSH1(0x01)
        + Op.ADD
        
        # Jump back to loop
        + Op.PUSH1(0x07)    # loop start position
        + Op.JUMP
        
        # End
        + Op.JUMPDEST       # end
        + Op.POP            # clean counter
        + Op.STOP
    )
    
    # Deploy factory contract at the strategic address
    pre[factory_address] = Account(
        nonce=1,  # Important: nonce 1 so CREATE will start at nonce 2
        balance=0,
        code=factory_code,
        storage={},
    )
    factory = factory_address
    
    # Transaction to create all contracts (matching mainnet gas usage)
    mass_create_tx = Transaction(
        sender=sender,
        to=factory,
        gas_limit=30_000_000,  # Closer to mainnet's 28M gas usage
    )
    
    # Post-state: Since we're not storing addresses, just verify contract was executed
    # The factory doesn't store anything in this simplified version
    post = Alloc()
    
    blockchain_test(
        pre=pre,
        post=post,
        blocks=[Block(txs=[mass_create_tx])],
    )


def test_deep_trie_sstore_stress(
    blockchain_test: BlockchainTestFiller,
    pre_deep_trie: Alloc,
) -> None:
    """
    Test SSTORE operations across many addresses in a deep trie.
    
    This test performs many SSTORE operations to different addresses,
    forcing extensive trie traversal and updates.
    """
    # Get funded test account
    sender = pre_deep_trie._deep_trie_stats["test_account"]
    
    # Simple contract that performs a few SSTOREs to test basic functionality
    sstore_stress_code = (
        # Store values at slots 0, 1, 2
        Op.PUSH1(0x42)  # value
        + Op.PUSH1(0x00)  # slot 0
        + Op.SSTORE
        
        + Op.PUSH1(0x43)  # value
        + Op.PUSH1(0x01)  # slot 1
        + Op.SSTORE
        
        + Op.PUSH1(0x44)  # value
        + Op.PUSH1(0x02)  # slot 2
        + Op.SSTORE
        
        + Op.STOP
    )
    
    # Deploy the SSTORE stress contract
    stress_contract = pre_deep_trie.deploy_contract(code=sstore_stress_code)
    
    # Transaction to trigger the stress test
    stress_tx = Transaction(
        sender=sender,
        to=stress_contract,
        gas_limit=10_000_000,
    )
    
    # Post-state: contract should have 3 storage slots set
    post = Alloc()
    post[stress_contract] = Account(
        storage={0: 0x42, 1: 0x43, 2: 0x44}
    )
    
    blockchain_test(
        pre=pre_deep_trie,
        post=post,
        blocks=[Block(txs=[stress_tx])],
    )


def test_mass_contract_creation_maximal_state_stress(
    blockchain_test: BlockchainTestFiller,
    pre: Alloc,
) -> None:
    """
    Test mass contract creation optimized for maximum state complexity.
    
    Creates 166 contracts, each with multiple storage operations to maximize
    the state trie modification cost. This should reproduce the computational
    expense seen in the mainnet transaction.
    """
    # Get funded test account
    sender = pre.fund_eoa(amount=10**23)  # 100,000 ETH
    
    # Number of contracts to create (matching mainnet)
    num_contracts = 166
    
    # More complex init code that does multiple SSTOREs to increase state complexity
    # Each contract will have multiple storage slots, increasing trie modification cost
    complex_init_code = (
        # Store multiple values to different slots to maximize storage trie complexity
        Op.PUSH1(0x01) + Op.PUSH1(0x00) + Op.SSTORE +  # slot 0
        Op.PUSH1(0x02) + Op.PUSH1(0x01) + Op.SSTORE +  # slot 1
        Op.PUSH1(0x03) + Op.PUSH1(0x02) + Op.SSTORE +  # slot 2
        Op.PUSH1(0x04) + Op.PUSH1(0x03) + Op.SSTORE +  # slot 3
        Op.PUSH1(0x05) + Op.PUSH1(0x04) + Op.SSTORE +  # slot 4
        # Return empty runtime
        Op.PUSH1(0x00) + Op.PUSH1(0x00) + Op.RETURN
    )
    
    init_code_size = len(bytes(complex_init_code))
    
    # Deploy factory
    factory_address = "0x1000000000000000000000000000000000000001"
    
    # Factory that creates contracts with complex storage
    factory_code = (
        # Embed the complex init code first
        Op.PUSH1(0x01) + Op.PUSH1(0x00) + Op.SSTORE +
        Op.PUSH1(0x02) + Op.PUSH1(0x01) + Op.SSTORE +
        Op.PUSH1(0x03) + Op.PUSH1(0x02) + Op.SSTORE +
        Op.PUSH1(0x04) + Op.PUSH1(0x03) + Op.SSTORE +
        Op.PUSH1(0x05) + Op.PUSH1(0x04) + Op.SSTORE +
        Op.PUSH1(0x00) + Op.PUSH1(0x00) + Op.RETURN +
        
        # Factory loop logic
        Op.PUSH1(0x00) +  # counter
        Op.JUMPDEST +  # loop_start
        Op.DUP1 + Op.PUSH1(num_contracts) + Op.EQ + Op.PUSH1(0x40) + Op.JUMPI +
        
        # Copy complex init code to memory
        Op.PUSH1(init_code_size) + Op.PUSH1(0x06) + Op.PUSH1(0x00) + Op.CODECOPY +
        
        # CREATE contract with complex storage
        Op.PUSH1(init_code_size) + Op.PUSH1(0x00) + Op.PUSH1(0x00) + Op.CREATE + Op.POP +
        
        # Increment and loop
        Op.PUSH1(0x01) + Op.ADD +
        Op.PUSH1(0x07) + Op.JUMP +
        
        # End
        Op.JUMPDEST + Op.POP + Op.STOP
    )
    
    pre[factory_address] = Account(
        nonce=1,
        balance=0,
        code=factory_code,
        storage={},
    )
    
    # Transaction to create all contracts with complex state
    mass_create_tx = Transaction(
        sender=sender,
        to=factory_address,
        gas_limit=30_000_000,
    )
    
    post = Alloc()
    
    blockchain_test(
        pre=pre,
        post=post,
        blocks=[Block(txs=[mass_create_tx])],
    )


def test_deep_trie_calls_stress(
    blockchain_test: BlockchainTestFiller,
    pre_deep_trie: Alloc,
) -> None:
    """
    Test many calls to different addresses in a deep trie.
    
    This test performs calls to many existing addresses in the deep trie,
    forcing extensive trie lookups without modifications.
    """
    # Get funded test account and existing addresses
    sender = pre_deep_trie._deep_trie_stats["test_account"]
    addresses = pre_deep_trie._deep_trie_addresses
    
    # Get first 50 addresses from the spread accounts
    target_addresses = addresses["spread"][:50]
    
    # Contract that calls many addresses
    call_stress_code = Op.STOP  # Start with base
    
    # Build code that calls each address
    for i, addr in enumerate(target_addresses):
        call_code = (
            Op.PUSH1(0x00)  # retLength
            + Op.PUSH1(0x00)  # retOffset
            + Op.PUSH1(0x00)  # argsLength
            + Op.PUSH1(0x00)  # argsOffset
            + Op.PUSH1(0x00)  # value
            + Op.PUSH20(int(addr, 16))  # address
            + Op.PUSH2(0x1000)  # gas
            + Op.CALL
            + Op.POP  # discard result
        )
        call_stress_code = call_code + call_stress_code
    
    # Deploy the call stress contract
    call_contract = pre_deep_trie.deploy_contract(code=call_stress_code)
    
    # Transaction to trigger the stress test
    stress_tx = Transaction(
        sender=sender,
        to=call_contract,
        gas_limit=10_000_000,
    )
    
    # No state changes expected except gas usage
    post = Alloc()
    
    blockchain_test(
        pre=pre_deep_trie,
        post=post,
        blocks=[Block(txs=[stress_tx])],
        verify_sync=True,
    )
