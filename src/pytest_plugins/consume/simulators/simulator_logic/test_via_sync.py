"""
A hive based simulator that executes blocks against clients using the `engine_newPayloadVX` method
from the Engine API with sync testing. The simulator uses the `BlockchainEngineSyncFixtures` to 
test against clients with client synchronization.

This simulator:
1. Spins up two clients: one as the client under test and another as the sync client
2. Executes payloads on the client under test
3. Has the sync client synchronize from the client under test
4. Verifies that the sync was successful
"""

import time

from ethereum_test_exceptions import UndefinedException
from ethereum_test_fixtures import BlockchainEngineSyncFixture
from ethereum_test_rpc import EngineRPC, EthRPC
from ethereum_test_rpc.types import ForkchoiceState, JSONRPCError, PayloadStatusEnum

from ....logging import get_logger
from ..helpers.exceptions import GenesisBlockMismatchExceptionError
from ..helpers.timing import TimingData

logger = get_logger(__name__)


class LoggedError(Exception):
    """Exception that uses the logger to log the failure."""

    def __init__(self, *args: object) -> None:
        """Initialize the exception and log the failure."""
        super().__init__(*args)
        logger.fail(str(self))


def wait_for_sync(
    sync_eth_rpc: EthRPC,
    sync_engine_rpc: EngineRPC,
    expected_block_hash: str,
    timeout: int = 60,
    poll_interval: float = 1.0,
) -> bool:
    """Wait for the sync client to reach the expected block hash."""
    start_time = time.time()
    last_block_number = 0
    
    while time.time() - start_time < timeout:
        try:
            # First check if we have the expected block
            block = sync_eth_rpc.get_block_by_hash(expected_block_hash)
            if block is not None:
                logger.info(f"Sync complete! Client has block {expected_block_hash}")
                return True
                
            # Check current sync progress
            current_block = sync_eth_rpc.get_block_by_number("latest")
            if current_block:
                current_number = int(current_block.get("number", "0x0"), 16)
                if current_number > last_block_number:
                    logger.info(f"Sync progress: block {current_number}")
                    last_block_number = current_number
                    
        except Exception as e:
            logger.debug(f"Error checking sync status: {e}")
            
        time.sleep(poll_interval)
    
    # Log final state
    try:
        final_block = sync_eth_rpc.get_block_by_number("latest")
        if final_block:
            logger.warning(
                f"Sync timeout! Final block: {final_block.get('number', 'unknown')} "
                f"(hash: {final_block.get('hash', 'unknown')})"
            )
    except Exception:
        pass
        
    return False


def test_blockchain_via_sync(
    timing_data: TimingData,
    eth_rpc: EthRPC,
    engine_rpc: EngineRPC,
    sync_eth_rpc: EthRPC | None,
    sync_engine_rpc: EngineRPC | None,
    fixture: BlockchainEngineSyncFixture,
    strict_exception_matching: bool,
):
    """
    Test blockchain synchronization between two clients.
    
    1. Initialize the client under test with the genesis block
    2. Execute all payloads on the client under test
    3. Initialize the sync client with the genesis block
    4. Send the sync payload to the sync client to trigger synchronization
    5. Verify that the sync client successfully syncs to the same state
    """
    # Initialize client under test
    with timing_data.time("Initialize client under test"):
        logger.info("Initializing client under test with genesis block...")

        # Send initial forkchoice update to client under test
        delay = 0.5
        for attempt in range(3):
            forkchoice_response = engine_rpc.forkchoice_updated(
                forkchoice_state=ForkchoiceState(
                    head_block_hash=fixture.genesis.block_hash,
                ),
                payload_attributes=None,
                version=fixture.payloads[0].forkchoice_updated_version,
            )
            status = forkchoice_response.payload_status.status
            logger.info(f"Initial forkchoice update response attempt {attempt + 1}: {status}")
            if status != PayloadStatusEnum.SYNCING:
                break
            if attempt < 2:
                time.sleep(delay)
                delay *= 2

        if forkchoice_response.payload_status.status != PayloadStatusEnum.VALID:
            logger.error(
                f"Client under test failed to initialize properly after 3 attempts, "
                f"final status: {forkchoice_response.payload_status.status}"
            )
            raise LoggedError(
                f"unexpected status on forkchoice updated to genesis: {forkchoice_response}"
            )

    # Verify genesis block on client under test
    with timing_data.time("Verify genesis on client under test"):
        logger.info("Verifying genesis block on client under test...")
        genesis_block = eth_rpc.get_block_by_number(0)
        if genesis_block["hash"] != str(fixture.genesis.block_hash):
            expected = fixture.genesis.block_hash
            got = genesis_block["hash"]
            logger.fail(f"Genesis block hash mismatch. Expected: {expected}, Got: {got}")
            raise GenesisBlockMismatchExceptionError(
                expected_header=fixture.genesis,
                got_genesis_block=genesis_block,
            )

    # Execute all payloads on client under test
    last_valid_block_hash = fixture.genesis.block_hash
    with timing_data.time("Execute payloads on client under test") as total_payload_timing:
        logger.info(f"Starting execution of {len(fixture.payloads)} payloads...")
        for i, payload in enumerate(fixture.payloads):
            logger.info(f"Processing payload {i + 1}/{len(fixture.payloads)}...")
            with total_payload_timing.time(f"Payload {i + 1}") as payload_timing:
                with payload_timing.time(f"engine_newPayloadV{payload.new_payload_version}"):
                    logger.info(f"Sending engine_newPayloadV{payload.new_payload_version}...")
                    try:
                        payload_response = engine_rpc.new_payload(
                            *payload.params,
                            version=payload.new_payload_version,
                        )
                        logger.info(f"Payload response status: {payload_response.status}")
                        expected_validity = (
                            PayloadStatusEnum.VALID
                            if payload.valid()
                            else PayloadStatusEnum.INVALID
                        )
                        if payload_response.status != expected_validity:
                            raise LoggedError(
                                f"unexpected status: want {expected_validity},"
                                f" got {payload_response.status}"
                            )
                        if payload.error_code is not None:
                            raise LoggedError(
                                f"Client failed to raise expected Engine API error code: "
                                f"{payload.error_code}"
                            )
                        elif payload_response.status == PayloadStatusEnum.INVALID:
                            if payload_response.validation_error is None:
                                raise LoggedError(
                                    "Client returned INVALID but no validation error was provided."
                                )
                            if isinstance(payload_response.validation_error, UndefinedException):
                                message = (
                                    "Undefined exception message: "
                                    f'expected exception: "{payload.validation_error}", '
                                    f'returned exception: "{payload_response.validation_error}" '
                                    f'(mapper: "{payload_response.validation_error.mapper_name}")'
                                )
                                if strict_exception_matching:
                                    raise LoggedError(message)
                                else:
                                    logger.warning(message)
                            else:
                                if (
                                    payload.validation_error
                                    not in payload_response.validation_error
                                ):
                                    message = (
                                        "Client returned unexpected validation error: "
                                        f'got: "{payload_response.validation_error}" '
                                        f'expected: "{payload.validation_error}"'
                                    )
                                    if strict_exception_matching:
                                        raise LoggedError(message)
                                    else:
                                        logger.warning(message)

                    except JSONRPCError as e:
                        logger.info(f"JSONRPC error encountered: {e.code} - {e.message}")
                        if payload.error_code is None:
                            raise LoggedError(f"Unexpected error: {e.code} - {e.message}") from e
                        if e.code != payload.error_code:
                            raise LoggedError(
                                f"Unexpected error code: {e.code}, expected: {payload.error_code}"
                            ) from e

                if payload.valid():
                    with payload_timing.time(
                        f"engine_forkchoiceUpdatedV{payload.forkchoice_updated_version}"
                    ):
                        # Send a forkchoice update to the engine
                        version = payload.forkchoice_updated_version
                        logger.info(f"Sending engine_forkchoiceUpdatedV{version}...")
                        forkchoice_response = engine_rpc.forkchoice_updated(
                            forkchoice_state=ForkchoiceState(
                                head_block_hash=payload.params[0].block_hash,
                            ),
                            payload_attributes=None,
                            version=payload.forkchoice_updated_version,
                        )
                        status = forkchoice_response.payload_status.status
                        logger.info(f"Forkchoice update response: {status}")
                        if forkchoice_response.payload_status.status != PayloadStatusEnum.VALID:
                            raise LoggedError(
                                f"unexpected status: want {PayloadStatusEnum.VALID},"
                                f" got {forkchoice_response.payload_status.status}"
                            )
                        last_valid_block_hash = payload.params[0].block_hash

        logger.info("All payloads processed successfully on client under test.")

    # Initialize sync client
    with timing_data.time("Initialize sync client"):
        logger.info("Initializing sync client with genesis block...")

        # Send initial forkchoice update to sync client
        delay = 0.5
        for attempt in range(3):
            forkchoice_response = sync_engine_rpc.forkchoice_updated(
                forkchoice_state=ForkchoiceState(
                    head_block_hash=fixture.genesis.block_hash,
                ),
                payload_attributes=None,
                version=fixture.payloads[0].forkchoice_updated_version,
            )
            status = forkchoice_response.payload_status.status
            logger.info(f"Sync client forkchoice update response attempt {attempt + 1}: {status}")
            if status != PayloadStatusEnum.SYNCING:
                break
            if attempt < 2:
                time.sleep(delay)
                delay *= 2

        if forkchoice_response.payload_status.status != PayloadStatusEnum.VALID:
            logger.error(
                f"Sync client failed to initialize properly after 3 attempts, "
                f"final status: {forkchoice_response.payload_status.status}"
            )
            raise LoggedError(
                f"unexpected status on sync client forkchoice updated to genesis: "
                f"{forkchoice_response}"
            )

    # Give sync client time to connect to the client under test
    logger.info("Waiting for sync client to connect to client under test...")
    time.sleep(5)  # Give time for peer connection

    # Trigger sync process using forkchoice update to head
    with timing_data.time("Trigger sync process"):
        logger.info("Triggering sync process with forkchoice update to head...")
        try:
            # Send forkchoice update pointing to the head block
            # This should trigger the sync client to start syncing
            sync_forkchoice_response = sync_engine_rpc.forkchoice_updated(
                forkchoice_state=ForkchoiceState(
                    head_block_hash=last_valid_block_hash,
                    safe_block_hash=last_valid_block_hash,
                    finalized_block_hash=fixture.genesis.block_hash,
                ),
                payload_attributes=None,
                version=fixture.payloads[-1].forkchoice_updated_version if fixture.payloads else 1,
            )
            logger.info(f"Sync trigger response status: {sync_forkchoice_response.payload_status.status}")
            
            # If we have a sync payload, send it as well
            if fixture.sync_payload:
                logger.info("Sending sync payload...")
                try:
                    sync_response = sync_engine_rpc.new_payload(
                        *fixture.sync_payload.params,
                        version=fixture.sync_payload.new_payload_version,
                    )
                    logger.info(f"Sync payload response status: {sync_response.status}")
                except JSONRPCError as e:
                    logger.warning(f"Error sending sync payload: {e.code} - {e.message}")
        except JSONRPCError as e:
            logger.warning(f"Error triggering sync: {e.code} - {e.message}")

    # Wait for synchronization
    with timing_data.time("Wait for synchronization"):
        logger.info(f"Waiting for sync client to reach block {last_valid_block_hash}...")

        if wait_for_sync(sync_eth_rpc, sync_engine_rpc, last_valid_block_hash, timeout=120):
            logger.info("Sync client successfully synchronized!")

            # Verify the final state
            sync_block = sync_eth_rpc.get_block_by_hash(last_valid_block_hash)
            client_block = eth_rpc.get_block_by_hash(last_valid_block_hash)

            if sync_block["stateRoot"] != client_block["stateRoot"]:
                raise LoggedError(
                    f"State root mismatch after sync. "
                    f"Sync client: {sync_block['stateRoot']}, "
                    f"Client under test: {client_block['stateRoot']}"
                )

            # Verify post state if available
            if fixture.post_state_hash:
                if sync_block["stateRoot"] != str(fixture.post_state_hash):
                    raise LoggedError(
                        f"Final state root mismatch. "
                        f"Expected: {fixture.post_state_hash}, "
                        f"Got: {sync_block['stateRoot']}"
                    )
        else:
            raise LoggedError(
                f"Sync client failed to synchronize to block {last_valid_block_hash} "
                f"within timeout"
            )

    logger.info("Sync test completed successfully!")


