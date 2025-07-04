"""Ethereum General State Test filler static test spec parser."""

from typing import Callable, ClassVar, Dict, List, Tuple

import pytest
from _pytest.mark.structures import ParameterSet

from ethereum_test_base_types import Address
from ethereum_test_exceptions import TransactionExceptionInstanceOrList
from ethereum_test_forks import Fork
from ethereum_test_types import EOA, Alloc, Transaction
from ethereum_test_types import Alloc as BaseAlloc

from ..base_static import BaseStaticTest
from ..state import StateTestFiller
from .common.common import TagDict
from .expect_section import (
    ResultInFiller,
)
from .state_test_filler import (
    StateTestInFiller,
    StateTestVector,
)

CONTRACT_ADDRESS_INCREMENTS_DEFAULT = 0x100


class StateStaticTest(StateTestInFiller, BaseStaticTest):
    """General State Test static filler from ethereum/tests."""

    test_name: str = ""
    vectors: List[StateTestVector] | None = None
    format_name: ClassVar[str] = "state_test"

    _alloc_registry: Dict[str, BaseAlloc] = {}
    _tag_to_address_map: Dict[str, Dict[str, Address]] = {}
    _tag_to_eoa_map: Dict[str, Dict[str, EOA]] = {}
    _request: pytest.FixtureRequest | None = None

    def model_post_init(self, context):
        """Initialize StateStaticTest."""
        super().model_post_init(context)

    def fill_function(self) -> Callable:
        """Return a StateTest spec from a static file."""
        d_g_v_parameters: List[ParameterSet] = []
        for d in range(len(self.transaction.data)):
            for g in range(len(self.transaction.gas_limit)):
                for v in range(len(self.transaction.value)):
                    exception_test = False
                    for expect in self.expect:
                        if expect.has_index(d, g, v) and expect.expect_exception is not None:
                            exception_test = True
                    # TODO: This does not take into account exceptions that only happen on
                    #       specific forks, but this requires a covariant parametrize
                    marks = [pytest.mark.exception_test] if exception_test else []
                    d_g_v_parameters.append(
                        pytest.param(d, g, v, marks=marks, id=f"d{d}-g{g}-v{v}")
                    )

        @pytest.mark.valid_at(*self.get_valid_at_forks())
        @pytest.mark.parametrize("d,g,v", d_g_v_parameters)
        def test_state_vectors(
            state_test: StateTestFiller,
            pre: Alloc,
            fork: Fork,
            d: int,
            g: int,
            v: int,
            request: pytest.FixtureRequest,
        ):
            for expect in self.expect:
                if expect.has_index(d, g, v):
                    if fork.name() in expect.network:
                        test_id = request.node.nodeid
                        tags = self.pre.resolve(pre)
                        env = self.env.get_environment(tags)
                        # Now create the vector with populated caches
                        post, tx = self._make_vector(
                            tags,
                            d,
                            g,
                            v,
                            expect.result,
                            test_id,
                            fork,
                            exception=None
                            if expect.expect_exception is None
                            else expect.expect_exception[fork.name()],
                        )
                        return state_test(
                            env=env,
                            pre=pre,
                            post=post,
                            tx=tx,
                        )
            pytest.fail(f"Expectation not found for d={d}, g={g}, v={v}, fork={fork}")

        if self.info and self.info.pytest_marks:
            for mark in self.info.pytest_marks:
                apply_mark = getattr(pytest.mark, mark)
                test_state_vectors = apply_mark(test_state_vectors)

        return test_state_vectors

    def get_valid_at_forks(self) -> List[str]:
        """Return list of forks that are valid for this test."""
        fork_list: List[str] = []
        for expect in self.expect:
            for fork in expect.network:
                if fork not in fork_list:
                    fork_list.append(fork)
        return fork_list

    def _make_vector(
        self,
        tags: TagDict,
        d: int,
        g: int,
        v: int,
        expect_result: ResultInFiller,
        test_id: str,
        fork: Fork,
        exception: TransactionExceptionInstanceOrList | None,
    ) -> Tuple[Alloc, Transaction]:
        """Compose test vector from test data."""
        tx: Transaction = self.transaction.get_transaction(tags, d, g, v, exception)
        post = expect_result.resolve(tags)
        return post, tx
