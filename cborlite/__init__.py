"""cborlite - encode and decode CBOR without dependencies."""

from .codec import DecodeError, dumps, loads

__all__ = ["DecodeError", "dumps", "loads"]
