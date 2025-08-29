"""
abstract: Tests that benchmarks EVMs to estimate the costs of  stateful opcodes.
    Tests that benchmarks EVMs to estimate the costs of stateful opcodes..
"""

import pytest

from ethereum_test_base_types import HashInt
from ethereum_test_forks import Fork
from ethereum_test_tools import (
    Account,
    Alloc,
    Block,
    BlockchainTestFiller,
    Environment,
    Storage,
    Transaction,
)
from ethereum_test_tools.vm.opcode import Opcodes as Op


@pytest.mark.valid_from("Osaka")
def test_bloatnet_sstore_cold(
    blockchain_test: BlockchainTestFiller, pre: Alloc, fork: Fork, gas_benchmark_value: int
):
    """
    Benchmark test that maximizes cold SSTORE operations (0 -> 1) by filling
    a block with multiple transactions, with each one containing a contract
    that performs a set of cold SSTOREs.

    The test iteratively creates new transactions until the cumulative gas used
    reaches the block's gas benchmark value. Each transaction deploys a contract
    that performs as many SSTOREs as possible within the transaction's gas limit.
    """
    gas_costs = fork.gas_costs()
    intrinsic_gas_calc = fork.transaction_intrinsic_cost_calculator()

    # TODO: We should maybe not use `None` for tx limit cap as this leads to typing
    #  issues. Maybe some really high value or the block gas limit?
    tx_gas_cap = fork.transaction_gas_limit_cap() or gas_benchmark_value

    storage_value = 1
    calldata = storage_value.to_bytes(32, "big")

    total_sstores = 0
    total_block_gas_used = 0
    all_txs = []

    expected_storage_state = {}

    while total_block_gas_used < gas_benchmark_value:
        remaining_block_gas = gas_benchmark_value - total_block_gas_used
        tx_gas_limit = min(remaining_block_gas, tx_gas_cap)

        intrinsic_gas = intrinsic_gas_calc(calldata=calldata)
        if tx_gas_limit <= intrinsic_gas:
            break

        opcode_gas_budget = tx_gas_limit - intrinsic_gas

        tx_contract_code = Op.PUSH0 + Op.CALLDATALOAD
        tx_opcode_gas = (
            gas_costs.G_BASE  # PUSH0
            + gas_costs.G_VERY_LOW  # CALLDATALOAD
        )
        tx_sstores_count = 0

        current_slot = total_sstores

        pop_gas = gas_costs.G_BASE

        while True:
            sstore_per_op_cost = (
                gas_costs.G_VERY_LOW * 2  # PUSH + DUP1
                + gas_costs.G_COLD_SLOAD
                + gas_costs.G_STORAGE_SET  # SSTORE
            )

            if tx_opcode_gas + sstore_per_op_cost + pop_gas > opcode_gas_budget:
                break

            tx_opcode_gas += sstore_per_op_cost
            tx_contract_code += Op.SSTORE(current_slot, Op.DUP1)
            tx_sstores_count += 1
            current_slot += 1

        # If no SSTOREs could be added, we've filled the block
        if tx_sstores_count == 0:
            break

        # Add a POP to clean up the stack at the end
        tx_contract_code += Op.POP
        tx_opcode_gas += pop_gas

        contract_address = pre.deploy_contract(code=tx_contract_code)
        tx = Transaction(
            to=contract_address,
            gas_limit=tx_gas_limit,
            data=calldata,
            sender=pre.fund_eoa(),
        )
        all_txs.append(tx)

        actual_intrinsic_consumed = intrinsic_gas_calc(
            calldata=calldata,
            # The actual gas consumed uses the standard intrinsic cost
            # (prior execution), not the floor cost used for validation
            return_cost_deducted_prior_execution=True,
        )

        tx_gas_used = actual_intrinsic_consumed + tx_opcode_gas
        total_block_gas_used += tx_gas_used

        total_sstores += tx_sstores_count

        # update expected storage state for each contract
        expected_storage_state[contract_address] = Account(
            storage=Storage(
                {
                    HashInt(slot): HashInt(storage_value)
                    for slot in range(current_slot - tx_sstores_count, current_slot)
                }
            )
        )

    blockchain_test(
        pre=pre,
        blocks=[Block(txs=all_txs)],
        post=expected_storage_state,
        expected_benchmark_gas_used=total_block_gas_used,
    )


@pytest.mark.valid_from("Osaka")
def test_bloatnet_sstore_warm(
    blockchain_test: BlockchainTestFiller, pre: Alloc, fork: Fork, gas_benchmark_value: int
):
    """
    Benchmark test that maximizes warm SSTORE operations (1 -> 2).

    This test pre-fills storage slots with value=1, then overwrites them with value=2.
    This represents the case of changing a non-zero value to a different non-zero value,
    which is cheaper than cold SSTORE but still significant.
    """
    gas_costs = fork.gas_costs()
    intrinsic_gas_calc = fork.transaction_intrinsic_cost_calculator()
    tx_gas_cap = fork.transaction_gas_limit_cap() or gas_benchmark_value

    initial_value = 1
    new_value = 2
    calldata = new_value.to_bytes(32, "big")

    total_sstores = 0
    total_block_gas_used = 0
    all_txs = []
    expected_storage_state = {}

    while total_block_gas_used < gas_benchmark_value:
        remaining_block_gas = gas_benchmark_value - total_block_gas_used
        tx_gas_limit = min(remaining_block_gas, tx_gas_cap)

        intrinsic_gas = intrinsic_gas_calc(calldata=calldata)
        if tx_gas_limit <= intrinsic_gas:
            break

        opcode_gas_budget = tx_gas_limit - intrinsic_gas

        tx_contract_code = Op.PUSH0 + Op.CALLDATALOAD
        tx_opcode_gas = (
            gas_costs.G_BASE  # PUSH0
            + gas_costs.G_VERY_LOW  # CALLDATALOAD
        )
        tx_sstores_count = 0

        current_slot = total_sstores
        pop_gas = gas_costs.G_BASE

        warm_sstore_cost = gas_costs.G_COLD_SLOAD + gas_costs.G_STORAGE_RESET
        while True:
            sstore_per_op_cost = (
                gas_costs.G_VERY_LOW * 2  # PUSH + DUP1
                + warm_sstore_cost  # SSTORE
            )

            if tx_opcode_gas + sstore_per_op_cost + pop_gas > opcode_gas_budget:
                break

            tx_opcode_gas += sstore_per_op_cost
            tx_contract_code += Op.SSTORE(current_slot, Op.DUP1)
            tx_sstores_count += 1
            current_slot += 1

        if tx_sstores_count == 0:
            break

        tx_contract_code += Op.POP
        tx_opcode_gas += pop_gas

        # Pre-fill storage with initial values
        initial_storage = {
            slot: initial_value for slot in range(total_sstores, total_sstores + tx_sstores_count)
        }

        contract_address = pre.deploy_contract(
            code=tx_contract_code,
            storage=initial_storage,  # type: ignore
        )
        tx = Transaction(
            to=contract_address,
            gas_limit=tx_gas_limit,
            data=calldata,
            sender=pre.fund_eoa(),
        )
        all_txs.append(tx)

        actual_intrinsic_consumed = intrinsic_gas_calc(
            calldata=calldata, return_cost_deducted_prior_execution=True
        )

        tx_gas_used = actual_intrinsic_consumed + tx_opcode_gas
        total_block_gas_used += tx_gas_used
        total_sstores += tx_sstores_count

        expected_storage_state[contract_address] = Account(
            storage=Storage(
                {
                    HashInt(slot): HashInt(new_value)
                    for slot in range(current_slot - tx_sstores_count, current_slot)
                }
            )
        )

    blockchain_test(
        pre=pre,
        blocks=[Block(txs=all_txs)],
        post=expected_storage_state,
        expected_benchmark_gas_used=total_block_gas_used,
    )


# Warm reads are very cheap, which means you can really fill a block
# with them. Only fill the block by a factor of SPEEDUP.
SPEEDUP: int = 100


@pytest.mark.valid_from("Prague")
def test_bloatnet_sload_warm(blockchain_test: BlockchainTestFiller, pre: Alloc, fork: Fork):
    """Test that loads warm storage locations many times."""
    gas_costs = fork.gas_costs()

    # Pre-fill storage with values
    num_slots = 100  # Number of storage slots to warm up
    storage = Storage({HashInt(i): HashInt(0xDEADBEEF + i) for i in range(num_slots)})

    # Calculate gas costs
    totalgas = fork.transaction_intrinsic_cost_calculator()(calldata=b"")

    # First pass - warm up all slots (cold access)
    warmup_gas = num_slots * (gas_costs.G_COLD_SLOAD + gas_costs.G_BASE)
    totalgas += warmup_gas

    # Calculate how many warm loads we can fit
    gas_increment = gas_costs.G_WARM_SLOAD + gas_costs.G_BASE  # Warm SLOAD + POP
    remaining_gas = Environment().gas_limit - totalgas
    num_warm_loads = remaining_gas // (SPEEDUP * gas_increment)

    # Build the complete code: warmup + repeated warm loads
    sload_code = Op.SLOAD(0) + Op.POP if num_slots > 0 else Op.STOP
    for i in range(1, num_slots):
        sload_code = sload_code + Op.SLOAD(i) + Op.POP
    for i in range(num_warm_loads):
        sload_code = sload_code + Op.SLOAD(i % num_slots) + Op.POP

    sender = pre.fund_eoa()
    contract_address = pre.deploy_contract(
        code=sload_code,
        storage=storage,
    )

    tx = Transaction(
        to=contract_address,
        gas_limit=Environment().gas_limit,
        data=b"",
        value=0,
        sender=sender,
    )

    post = {contract_address: Account(storage=storage)}
    blockchain_test(pre=pre, blocks=[Block(txs=[tx])], post=post)


@pytest.mark.valid_from("Prague")
def test_bloatnet_sload_cold(blockchain_test: BlockchainTestFiller, pre: Alloc, fork: Fork):
    """Test that loads many different cold storage locations."""
    gas_costs = fork.gas_costs()

    # Calculate gas costs and max slots
    totalgas = fork.transaction_intrinsic_cost_calculator()(calldata=b"")
    # PUSH + Cold SLOAD + POP
    gas_increment = gas_costs.G_VERY_LOW + gas_costs.G_COLD_SLOAD + gas_costs.G_BASE
    max_slots = (Environment().gas_limit - totalgas) // gas_increment

    # Build storage and code for all slots
    storage = Storage({HashInt(i): HashInt(0xC0FFEE + i) for i in range(max_slots)})
    sload_code = Op.SLOAD(0) + Op.POP if max_slots > 0 else Op.STOP
    for i in range(1, max_slots):
        sload_code = sload_code + Op.SLOAD(i) + Op.POP

    sender = pre.fund_eoa()
    contract_address = pre.deploy_contract(
        code=sload_code,
        storage=storage,
    )

    tx = Transaction(
        to=contract_address,
        gas_limit=Environment().gas_limit,
        data=b"",
        value=0,
        sender=sender,
    )

    post = {contract_address: Account(storage=storage)}
    blockchain_test(pre=pre, blocks=[Block(txs=[tx])], post=post)
