import math
import struct
import unittest

from cborlite.codec import DecodeError, dumps, loads


class IntegerTest(unittest.TestCase):
    def test_shortest_encoding(self):
        self.assertEqual(dumps(0), bytes([0]))
        self.assertEqual(dumps(23), bytes([23]))
        self.assertEqual(dumps(24), bytes([24, 24]))
        self.assertEqual(dumps(255), bytes([24, 255]))
        self.assertEqual(dumps(256), bytes([25, 1, 0]))

    def test_negative_values(self):
        self.assertEqual(dumps(-1), bytes([0x20]))
        self.assertEqual(dumps(-500), bytes([0x39, 0x01, 0xF3]))

    def test_round_trip(self):
        for value in (0, 1, 23, 24, 2 ** 8, 2 ** 16, 2 ** 32 - 1, 2 ** 63):
            self.assertEqual(loads(dumps(value)), value)

    def test_negative_round_trip(self):
        for value in (-1, -24, -25, -2 ** 40):
            self.assertEqual(loads(dumps(value)), value)

    def test_overflow_rejected(self):
        with self.assertRaises(ValueError):
            dumps(2 ** 64)


class StringTest(unittest.TestCase):
    def test_text_and_bytes(self):
        self.assertEqual(dumps("a"), bytes([0x61]) + b"a")
        self.assertEqual(loads(dumps("a")), "a")
        payload = bytes([1, 2])
        self.assertEqual(loads(dumps(payload)), payload)

    def test_unicode(self):
        value = "salam دنیا"
        self.assertEqual(loads(dumps(value)), value)

    def test_indefinite_text_is_joined(self):
        blob = bytes([0x7F, 0x61]) + b"a" + bytes([0x61]) + b"b" + bytes([0xFF])
        self.assertEqual(loads(blob), "ab")

    def test_indefinite_bytes_is_joined(self):
        blob = bytes([0x5F, 0x41, 0x01, 0x41, 0x02, 0xFF])
        self.assertEqual(loads(blob), bytes([1, 2]))


class ContainerTest(unittest.TestCase):
    def test_array(self):
        self.assertEqual(dumps([1, 2]), bytes([0x82, 0x01, 0x02]))
        self.assertEqual(loads(dumps([1, 2])), [1, 2])

    def test_map_round_trip(self):
        value = {"a": 1, "b": [True, None]}
        self.assertEqual(loads(dumps(value)), value)

    def test_nested(self):
        value = {"x": {"y": [{"z": -3}]}}
        self.assertEqual(loads(dumps(value)), value)

    def test_indefinite_array(self):
        self.assertEqual(loads(bytes([0x9F, 1, 2, 0xFF])), [1, 2])

    def test_indefinite_map(self):
        self.assertEqual(loads(bytes([0xBF, 0x61]) + b"a" + bytes([1, 0xFF])), {"a": 1})


class SimpleTest(unittest.TestCase):
    def test_booleans_and_null(self):
        self.assertEqual(dumps(False), bytes([0xF4]))
        self.assertEqual(dumps(True), bytes([0xF5]))
        self.assertEqual(dumps(None), bytes([0xF6]))
        self.assertIsNone(loads(dumps(None)))
        self.assertIs(loads(dumps(True)), True)

    def test_float64(self):
        blob = dumps(1.5)
        self.assertEqual(blob[0], 0xFB)
        self.assertEqual(loads(blob), 1.5)

    def test_float32_and_float16_decode(self):
        self.assertEqual(loads(bytes([0xFA]) + struct.pack("!f", 0.5)), 0.5)
        self.assertEqual(loads(bytes([0xF9, 0x3C, 0x00])), 1.0)

    def test_half_precision_infinity(self):
        self.assertTrue(math.isinf(loads(bytes([0xF9, 0x7C, 0x00]))))


class ErrorTest(unittest.TestCase):
    def test_trailing_bytes(self):
        with self.assertRaises(DecodeError):
            loads(bytes([1, 1]))

    def test_truncated_string(self):
        with self.assertRaises(DecodeError):
            loads(bytes([0x62]) + b"a")

    def test_tagged_value_refused(self):
        with self.assertRaises(DecodeError):
            loads(bytes([0xC1, 0x01]))

    def test_unsupported_type_rejected(self):
        with self.assertRaises(TypeError):
            dumps(object())

    def test_unterminated_indefinite(self):
        with self.assertRaises(DecodeError):
            loads(bytes([0x9F, 0x01]))


if __name__ == "__main__":
    unittest.main()
