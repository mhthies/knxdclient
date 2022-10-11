
import unittest

import knxdclient


class MQTTClientTest(unittest.TestCase):
    def test_type_error(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            knxdclient.encode_value(5.3, knxdclient.KNXDPT.INT8)
        self.assertIn("not a <class 'int'>", ctx.exception.args[0])

        with self.assertRaises(TypeError) as ctx:
            knxdclient.decode_value(bytes([255, 7]), knxdclient.KNXDPT.BOOLEAN)
        self.assertIn("Expected a <class 'int'>", ctx.exception.args[0])

    def test_dtp1_conversion(self) -> None:
        self.assertEqual(0x01,
                         knxdclient.encode_value(True, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(0x00,
                         knxdclient.encode_value(False, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(True,
                         knxdclient.decode_value(0x01, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(False,
                         knxdclient.encode_value(0x00, knxdclient.KNXDPT.BOOLEAN))

        # Special handling for bool: We accept any object type and cast it to bool:
        self.assertEqual(0x01,
                         knxdclient.encode_value(57, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(0x00,
                         knxdclient.encode_value(0.0, knxdclient.KNXDPT.BOOLEAN))
