"""Tests for protocol.py encoding/decoding functions.

Run: python test_protocol.py
"""

import struct
import unittest
from types import SimpleNamespace
from datetime import datetime
import protocol as prt


def _ev(val, q=0, ioa=1):
    return SimpleNamespace(val=val, q=q, ioa=ioa, ts=datetime.now())


class TestCP56Time(unittest.TestCase):
    """datetime_to_cp56 / datetime_from_cp56 roundtrip."""

    def test_roundtrip(self):
        dt = datetime(2025, 3, 21, 14, 30, 25, 123000)
        raw = prt.datetime_to_cp56(dt)
        self.assertEqual(len(raw), 7)
        restored, iv = prt.datetime_from_cp56(raw)
        self.assertEqual(restored, dt)
        self.assertFalse(iv)

    def test_iv_flag(self):
        dt = datetime(2025, 1, 1, 0, 0, 0)
        raw = prt.datetime_to_cp56(dt, iv=True)
        _, iv = prt.datetime_from_cp56(raw)
        self.assertTrue(iv)

    def test_too_short_raises(self):
        with self.assertRaises(ValueError):
            prt.datetime_from_cp56(b'\x00' * 6)


class TestEncDecRoundtrip(unittest.TestCase):
    """_enc_val -> _dec_val roundtrip for all supported types."""

    CASES = [
        (1, 1, 0),        # SIQ, val=ON
        (1, 0, 0x80),     # SIQ, val=OFF, quality=NT
        (3, 2, 0),        # DIQ
        (9, 1000, 0),     # NVA (normalized)
        (9, -100, 4),     # NVA negative, quality=BL
        (13, 3.14, 0),    # Float
        (15, 42, 0),      # BCR
        (100, 20, 0),     # C_IC_NA_1
    ]

    def test_encode_then_decode(self):
        for type_id, val, q in self.CASES:
            with self.subTest(type_id=type_id, val=val, q=q):
                encoded = prt._enc_val(type_id, _ev(val, q))
                self.assertIsNotNone(encoded)
                dec_val, dec_q = prt._dec_val(type_id, encoded)
                if type_id in (13, 36):
                    self.assertAlmostEqual(dec_val, val, places=5)
                else:
                    self.assertEqual(dec_val, val)
                if type_id != 100:
                    self.assertEqual(dec_q, q)

    def test_unknown_type(self):
        self.assertIsNone(prt._enc_val(999, _ev(0)))
        self.assertIsNone(prt._dec_val(999, b'\x00')[0])


class TestEncVal(unittest.TestCase):
    """Specific encoding checks."""

    def test_siq_value_and_quality_combined(self):
        result = prt._enc_val(1, _ev(val=1, q=0x80))
        self.assertEqual(result, bytes([0x81]))

    def test_diq_value_bits(self):
        result = prt._enc_val(3, _ev(val=2, q=0))
        self.assertEqual(result, bytes([0x02]))

    def test_float_encoding(self):
        result = prt._enc_val(13, _ev(val=0.0, q=0))
        self.assertEqual(result, struct.pack('<fB', 0.0, 0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
