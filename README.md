# cborlite

CBOR (RFC 8949) encode and decode with no dependencies and strict errors.

```
python __init__.py --help
```

## files

- `cborlite/__init__.py` - cborlite - encode and decode CBOR without dependencies.
- `cborlite/codec.py` - A small CBOR implementation (RFC 8949) for the types JSON can express.
- `tests/test_codec.py` - tests for the module next to it

## running

Runs on 3.11 and newer.

```
git clone https://github.com/CodingWithFardin/cborlite.git
cd cborlite
```

Tests: `tests/test_codec.py`. The suite is the specification; start there if the code is unclear.

MIT, 2026.
