"""General transaction structure of ethereum/tests fillers."""

from typing import Any, List

from pydantic import BaseModel, Field, field_validator, model_validator

from ethereum_test_base_types import Address, CamelModel, Hash
from ethereum_test_exceptions import TransactionExceptionInstanceOrList
from ethereum_test_types import Transaction

from .common import (
    AccessListInFiller,
    AddressOrTagInFiller,
    CodeInFiller,
    HashOrTagInFiller,
    ValueInFiller,
)
from .common.tags import Tag, TagDict


class DataWithAccessList(CamelModel):
    """Class that represents data with access list."""

    data: CodeInFiller
    access_list: List[AccessListInFiller] | None = None

    @field_validator("access_list", mode="before")
    def convert_keys_to_hash(cls, access_list):  # noqa: N805
        """Fix keys."""
        if access_list is None:
            return None
        for entry in access_list:
            if "storageKeys" in entry:
                entry["storageKeys"] = [
                    Hash(key, left_padding=True) for key in entry["storageKeys"]
                ]
        return access_list

    @model_validator(mode="wrap")
    @classmethod
    def wrap_data_only(cls, data: Any, handler) -> "DataWithAccessList":
        """Wrap data only if it is not a dictionary."""
        if not isinstance(data, dict) and not isinstance(data, DataWithAccessList):
            data = {"data": data}
        return handler(data)


class GeneralTransactionInFiller(BaseModel):
    """Class that represents general transaction in filler."""

    data: List[DataWithAccessList]
    gas_limit: List[ValueInFiller] = Field(..., alias="gasLimit")
    gas_price: ValueInFiller | None = Field(None, alias="gasPrice")
    nonce: ValueInFiller | None
    to: AddressOrTagInFiller | None
    value: List[ValueInFiller]
    secret_key: HashOrTagInFiller = Field(..., alias="secretKey")

    max_fee_per_gas: ValueInFiller | None = Field(None, alias="maxFeePerGas")
    max_priority_fee_per_gas: ValueInFiller | None = Field(None, alias="maxPriorityFeePerGas")

    max_fee_per_blob_gas: ValueInFiller | None = Field(None, alias="maxFeePerBlobGas")
    blob_versioned_hashes: List[Hash] | None = Field(None, alias="blobVersionedHashes")

    class Config:
        """Model Config."""

        extra = "forbid"

    @field_validator("to", mode="before")
    def check_single_key(cls, to):  # noqa: N805
        """Creation transaction."""
        if to == "":
            to = None
        return to

    @model_validator(mode="after")
    def check_fields(self) -> "GeneralTransactionInFiller":
        """Validate all fields are set."""
        if self.gas_price is None:
            if self.max_fee_per_gas is None or self.max_priority_fee_per_gas is None:
                raise ValueError(
                    "If `gasPrice` is not set,"
                    " `maxFeePerGas` and `maxPriorityFeePerGas` must be set!"
                )
        return self

    def get_transaction(
        self,
        tags: TagDict,
        d: int,
        g: int,
        v: int,
        exception: TransactionExceptionInstanceOrList | None,
    ) -> Transaction:
        """Get the transaction."""
        data_box = self.data[d]
        kwargs = {}
        if self.to is None:
            kwargs["to"] = None
        elif isinstance(self.to, Tag):
            kwargs["to"] = self.to.resolve(tags)
        else:
            kwargs["to"] = Address(self.to)

        kwargs["data"] = data_box.data.compiled(tags)
        if data_box.access_list is not None:
            kwargs["access_list"] = [entry.resolve(tags) for entry in data_box.access_list]

        kwargs["gas_limit"] = self.gas_limit[g]

        if isinstance(self.secret_key, Tag):
            kwargs["sender"] = self.secret_key.resolve(tags)
        else:
            kwargs["secret_key"] = self.secret_key

        if self.value[v] > 0:
            kwargs["value"] = self.value[v]
        if self.gas_price is not None:
            kwargs["gas_price"] = self.gas_price
        if self.nonce is not None:
            kwargs["nonce"] = self.nonce
        if self.max_fee_per_gas is not None:
            kwargs["max_fee_per_gas"] = self.max_fee_per_gas
        if self.max_priority_fee_per_gas is not None:
            kwargs["max_priority_fee_per_gas"] = self.max_priority_fee_per_gas
        if self.max_fee_per_blob_gas is not None:
            kwargs["max_fee_per_blob_gas"] = self.max_fee_per_blob_gas
        if self.blob_versioned_hashes is not None:
            kwargs["blob_versioned_hashes"] = self.blob_versioned_hashes

        if exception is not None:
            kwargs["error"] = exception

        return Transaction(**kwargs)
