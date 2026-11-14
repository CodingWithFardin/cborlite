"""A small CBOR implementation (RFC 8949) for the types JSON can express.

Supported: unsigned and negative integers, byte strings, text strings, arrays,
maps, false/true/null, and float64 on encode (float16/32/64 on decode). Tags are
rejected rather than ignored, because silently dropping a tag changes meaning.

Indefinite-length items are accepted on decode: some encoders still emit them.
"""
import struct


class DecodeError(Exception):
    pass


MAJOR_UINT, MAJOR_NINT, MAJOR_BYTES, MAJOR_TEXT = 0, 1, 2, 3
MAJOR_ARRAY, MAJOR_MAP, MAJOR_TAG, MAJOR_SIMPLE = 4, 5, 6, 7

SIMPLE_FALSE, SIMPLE_TRUE, SIMPLE_NULL = 20, 21, 22
FLOAT16, FLOAT32, FLOAT64 = 25, 26, 27
BREAK = 0xFF


def _head(major, value):
    """Encode a major type and its argument using the shortest form."""
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 2 ** 8:
        return bytes([(major << 5) | 24, value])
    if value < 2 ** 16:
        return bytes([(major << 5) | 25]) + struct.pack("!H", value)
    if value < 2 ** 32:
        return bytes([(major << 5) | 26]) + struct.pack("!I", value)
    if value < 2 ** 64:
        return bytes([(major << 5) | 27]) + struct.pack("!Q", value)
    raise ValueError("integer %d does not fit in 64 bits" % value)


def dumps(value):
    if value is False:
        return bytes([(MAJOR_SIMPLE << 5) | SIMPLE_FALSE])
    if value is True:
        return bytes([(MAJOR_SIMPLE << 5) | SIMPLE_TRUE])
    if value is None:
        return bytes([(MAJOR_SIMPLE << 5) | SIMPLE_NULL])
    if isinstance(value, int):
        if value >= 0:
            return _head(MAJOR_UINT, value)
        return _head(MAJOR_NINT, -1 - value)
    if isinstance(value, float):
        return bytes([(MAJOR_SIMPLE << 5) | FLOAT64]) + struct.pack("!d", value)
    if isinstance(value, bytes):
        return _head(MAJOR_BYTES, len(value)) + value
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _head(MAJOR_TEXT, len(raw)) + raw
    if isinstance(value, (list, tuple)):
        body = b"".join(dumps(item) for item in value)
        return _head(MAJOR_ARRAY, len(value)) + body
    if isinstance(value, dict):
        body = b"".join(dumps(key) + dumps(value[key]) for key in value)
        return _head(MAJOR_MAP, len(value)) + body
    raise TypeError("cannot encode %s as CBOR" % type(value).__name__)


class _Reader:
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0

    def byte(self):
        if self.pos >= len(self.buf):
            raise DecodeError("unexpected end of input")
        value = self.buf[self.pos]
        self.pos += 1
        return value

    def peek(self):
        if self.pos >= len(self.buf):
            raise DecodeError("unexpected end of input")
        return self.buf[self.pos]

    def take(self, count):
        end = self.pos + count
        if end > len(self.buf):
            raise DecodeError("wanted %d bytes, %d remain" % (count, len(self.buf) - self.pos))
        chunk = bytes(self.buf[self.pos:end])
        self.pos = end
        return chunk

    def argument(self, info):
        if info < 24:
            return info
        if info == 24:
            return self.byte()
        if info == 25:
            return struct.unpack("!H", self.take(2))[0]
        if info == 26:
            return struct.unpack("!I", self.take(4))[0]
        if info == 27:
            return struct.unpack("!Q", self.take(8))[0]
        if info == 31:
            return None
        raise DecodeError("reserved additional information %d" % info)


def loads(data):
    reader = _Reader(memoryview(data))
    value = _item(reader)
    if reader.pos != len(reader.buf):
        raise DecodeError("%d trailing bytes" % (len(reader.buf) - reader.pos))
    return value


def _chunks(reader, expect):
    """Collect an indefinite-length run of items until the break byte."""
    parts = []
    while reader.peek() != BREAK:
        chunk = _item(reader)
        if not isinstance(chunk, expect):
            raise DecodeError("indefinite run holds an item of the wrong type")
        parts.append(chunk)
    reader.pos += 1
    return parts


def _item(reader):
    first = reader.byte()
    major, info = first >> 5, first & 0x1F
    # only the major types 0-6 carry an argument; simple values are the argument
    argument = reader.argument(info) if major != MAJOR_SIMPLE else info

    if major in (MAJOR_UINT, MAJOR_NINT):
        if argument is None:
            raise DecodeError("indefinite length on an integer")
        return argument if major == MAJOR_UINT else -1 - argument
    if major == MAJOR_BYTES:
        if argument is None:
            return b"".join(_chunks(reader, bytes))
        return bytes(reader.take(argument))
    if major == MAJOR_TEXT:
        if argument is None:
            return "".join(_chunks(reader, str))
        return bytes(reader.take(argument)).decode("utf-8")
    if major == MAJOR_ARRAY:
        if argument is None:
            items = []
            while reader.peek() != BREAK:
                items.append(_item(reader))
            reader.pos += 1
            return items
        return [_item(reader) for _ in range(argument)]
    if major == MAJOR_MAP:
        result = {}
        if argument is None:
            while reader.peek() != BREAK:
                key = _hashable(_item(reader))
                result[key] = _item(reader)
            reader.pos += 1
            return result
        for _ in range(argument):
            key = _hashable(_item(reader))
            result[key] = _item(reader)
        return result
    if major == MAJOR_TAG:
        raise DecodeError("CBOR tags are not supported (tag %s)" % argument)
    if info == SIMPLE_FALSE:
        return False
    if info == SIMPLE_TRUE:
        return True
    if info == SIMPLE_NULL:
        return None
    if info == FLOAT16:
        return _half(reader.take(2))
    if info == FLOAT32:
        return struct.unpack("!f", reader.take(4))[0]
    if info == FLOAT64:
        return struct.unpack("!d", reader.take(8))[0]
    raise DecodeError("unsupported simple value %d" % info)


def _hashable(value):
    if isinstance(value, list):
        return tuple(_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((_hashable(k), _hashable(v)) for k, v in value.items()))
    return value


def _half(raw):
    (bits,) = struct.unpack("!H", raw)
    sign = -1.0 if bits & 0x8000 else 1.0
    exponent = (bits >> 10) & 0x1F
    fraction = bits & 0x03FF
    if exponent == 0:
        return sign * 2.0 ** -14 * (fraction / 1024.0)
    if exponent == 31:
        return sign * (float("inf") if fraction == 0 else float("nan"))
    return sign * 2.0 ** (exponent - 15) * (1 + fraction / 1024.0)
