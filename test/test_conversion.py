import datetime
import enum
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

    def test_dpt1_conversion(self) -> None:
        self.assertEqual(0x01,
                         knxdclient.encode_value(True, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(0x00,
                         knxdclient.encode_value(False, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(True,
                         knxdclient.decode_value(0x01, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(False,
                         knxdclient.decode_value(0x00, knxdclient.KNXDPT.BOOLEAN))

        # Special handling for bool: We accept any object type and cast it to bool:
        self.assertEqual(0x01,
                         knxdclient.encode_value(57, knxdclient.KNXDPT.BOOLEAN))
        self.assertEqual(0x00,
                         knxdclient.encode_value(0.0, knxdclient.KNXDPT.BOOLEAN))

    def test_dpt2_conversion(self) -> None:
        self.assertEqual(0x01,
                         knxdclient.encode_value((False, True), knxdclient.KNXDPT.TWO_BOOLEAN))
        self.assertEqual(0x02,
                         knxdclient.encode_value((True, False), knxdclient.KNXDPT.TWO_BOOLEAN))
        self.assertEqual((False, True),
                         knxdclient.decode_value(0x01, knxdclient.KNXDPT.TWO_BOOLEAN))
        self.assertEqual((True, False),
                         knxdclient.decode_value(0x02, knxdclient.KNXDPT.TWO_BOOLEAN))

    def test_dpt3_conversion(self) -> None:
        self.assertEqual(0b0101,
                         knxdclient.encode_value((False, 5), knxdclient.KNXDPT.BOOLEAN_UINT3))
        self.assertEqual(0b1001,
                         knxdclient.encode_value((True, 1), knxdclient.KNXDPT.BOOLEAN_UINT3))
        self.assertEqual((False, 5),
                         knxdclient.decode_value(0b0101, knxdclient.KNXDPT.BOOLEAN_UINT3))
        self.assertEqual((True, 1),
                         knxdclient.decode_value(0b1001, knxdclient.KNXDPT.BOOLEAN_UINT3))

    def test_dpt4_conversion(self) -> None:
        self.assertEqual(bytes([0x4D]),
                         knxdclient.encode_value('M', knxdclient.KNXDPT.CHAR))
        self.assertEqual(bytes([0xC4]),
                         knxdclient.encode_value('Ä', knxdclient.KNXDPT.CHAR))
        self.assertEqual('M',
                         knxdclient.decode_value(bytes([0x4D]), knxdclient.KNXDPT.CHAR))
        self.assertEqual('Ä',
                         knxdclient.decode_value(bytes([0xC4]), knxdclient.KNXDPT.CHAR))

    def test_dpt5_conversion(self) -> None:
        self.assertEqual(bytes([255]),
                         knxdclient.encode_value(255, knxdclient.KNXDPT.UINT8))
        self.assertEqual(bytes([42]),
                         knxdclient.encode_value(42, knxdclient.KNXDPT.UINT8))
        self.assertEqual(255,
                         knxdclient.decode_value(bytes([255]), knxdclient.KNXDPT.UINT8))
        self.assertEqual(42,
                         knxdclient.decode_value(bytes([42]), knxdclient.KNXDPT.UINT8))

    def test_dpt6_conversion(self) -> None:
        self.assertEqual(bytes([0xff]),
                         knxdclient.encode_value(-1, knxdclient.KNXDPT.INT8))
        self.assertEqual(bytes([42]),
                         knxdclient.encode_value(42, knxdclient.KNXDPT.INT8))
        self.assertEqual(-1,
                         knxdclient.decode_value(bytes([0xff]), knxdclient.KNXDPT.INT8))
        self.assertEqual(42,
                         knxdclient.decode_value(bytes([42]), knxdclient.KNXDPT.INT8))

    def test_dpt7_conversion(self) -> None:
        self.assertEqual(bytes([0xff, 0x42]),
                         knxdclient.encode_value(0xff42, knxdclient.KNXDPT.UINT16))
        self.assertEqual(bytes([0x00, 0x05]),
                         knxdclient.encode_value(0x0005, knxdclient.KNXDPT.UINT16))
        self.assertEqual(0xff42,
                         knxdclient.decode_value(bytes([0xff, 0x42]), knxdclient.KNXDPT.UINT16))
        self.assertEqual(0x0005,
                         knxdclient.decode_value(bytes([0x00, 0x05]), knxdclient.KNXDPT.UINT16))

    def test_dpt8_conversion(self) -> None:
        self.assertEqual(bytes([0xff, 0xfe]),
                         knxdclient.encode_value(-2, knxdclient.KNXDPT.INT16))
        self.assertEqual(bytes([0x00, 0xfe]),
                         knxdclient.encode_value(254, knxdclient.KNXDPT.INT16))
        self.assertEqual(-2,
                         knxdclient.decode_value(bytes([0xff, 0xfe]), knxdclient.KNXDPT.INT16))
        self.assertEqual(254,
                         knxdclient.decode_value(bytes([0x00, 0xfe]), knxdclient.KNXDPT.INT16))

    def test_dpt9_conversion(self) -> None:
        # bits: MEEEEMMM MMMMMMMMM
        # value = m * 2^e * 0,01; mantissa in two's complement
        self.assertAlmostEqual(-0.42,
                               knxdclient.decode_value(bytes([0b10000111, 0b11010110]), knxdclient.KNXDPT.FLOAT16))
        self.assertAlmostEqual(41.28,
                               knxdclient.decode_value(bytes([0b00101000, 0b10000001]), knxdclient.KNXDPT.FLOAT16))
        self.assertEqual(bytes([0b10000111, 0b11010110]),
                         knxdclient.encode_value(-0.42, knxdclient.KNXDPT.FLOAT16))
        # Slightly different value should be rounded
        self.assertEqual(-0.42,
                         knxdclient.decode_value(knxdclient.encode_value(-0.420001, knxdclient.KNXDPT.FLOAT16),
                                                 knxdclient.KNXDPT.FLOAT16))
        self.assertEqual(-0.42,
                         knxdclient.decode_value(knxdclient.encode_value(-0.419999, knxdclient.KNXDPT.FLOAT16),
                                                 knxdclient.KNXDPT.FLOAT16))
        self.assertEqual(41.28,
                         knxdclient.decode_value(knxdclient.encode_value(41.28, knxdclient.KNXDPT.FLOAT16),
                                                 knxdclient.KNXDPT.FLOAT16))

    def test_dpt10_conversion(self) -> None:
        # bits: WWWHHHHH 00MMMMMM 00SSSSSS
        self.assertEqual(bytes([0b00010101, 42, 17]),
                         knxdclient.encode_value(knxdclient.encoding.KNXTime(datetime.time(21, 42, 17), None),
                                                 knxdclient.KNXDPT.TIME))
        self.assertEqual(bytes([0b11000110, 0, 11]),
                         knxdclient.encode_value(knxdclient.encoding.KNXTime(datetime.time(6, 0, 11), 5),
                                                 knxdclient.KNXDPT.TIME))
        self.assertEqual(knxdclient.encoding.KNXTime(datetime.time(6, 0, 11), 5),
                         knxdclient.decode_value(bytes([0b11000110, 0, 11]), knxdclient.KNXDPT.TIME))
        self.assertEqual(knxdclient.encoding.KNXTime(datetime.time(21, 42, 17), None),
                         knxdclient.decode_value(bytes([0b00010101, 42, 17]), knxdclient.KNXDPT.TIME))

    def test_dpt10_from_datetime(self) -> None:
        self.assertEqual(knxdclient.encoding.KNXTime(datetime.time(6, 0, 11), 2),  # wednesday
                         knxdclient.encoding.KNXTime.from_datetime(datetime.datetime(2022, 10, 12, 6, 00, 11)))
        self.assertEqual(knxdclient.encoding.KNXTime(datetime.time(0, 0, 10), 3),  # thursday
                         knxdclient.encoding.KNXTime.from_datetime(datetime.datetime(1970, 1, 1, 0, 0, 10)))

    def test_dpt11_conversion(self) -> None:
        # bits: 000DDDDD 0000MMMMM 0YYYYYYY
        self.assertEqual(bytes([12, 10, 22]),
                         knxdclient.encode_value(datetime.date(2022, 10, 12), knxdclient.KNXDPT.DATE))
        self.assertEqual(bytes([1, 1, 91]),
                         knxdclient.encode_value(datetime.date(1991, 1, 1), knxdclient.KNXDPT.DATE))
        self.assertEqual(datetime.date(2022, 10, 12),
                         knxdclient.decode_value(bytes([12, 10, 22]), knxdclient.KNXDPT.DATE))
        self.assertEqual(datetime.date(1991, 1, 1),
                         knxdclient.decode_value(bytes([1, 1, 91]), knxdclient.KNXDPT.DATE))

    def test_dpt12_conversion(self) -> None:
        self.assertEqual(bytes([0xff, 0x42, 0xbe, 0xef]),
                         knxdclient.encode_value(0xff42beef, knxdclient.KNXDPT.UINT32))
        self.assertEqual(bytes([0x00, 0x05, 0xbe, 0xef]),
                         knxdclient.encode_value(0x0005beef, knxdclient.KNXDPT.UINT32))
        self.assertEqual(0xff42beef,
                         knxdclient.decode_value(bytes([0xff, 0x42, 0xbe, 0xef]), knxdclient.KNXDPT.UINT32))
        self.assertEqual(0x0005beef,
                         knxdclient.decode_value(bytes([0x00, 0x05, 0xbe, 0xef]), knxdclient.KNXDPT.UINT32))

    def test_dpt13_conversion(self) -> None:
        self.assertEqual(bytes([0xff, 0xff, 0xff, 0xfe]),
                         knxdclient.encode_value(-2, knxdclient.KNXDPT.INT32))
        self.assertEqual(bytes([0x05, 0x00, 0xbe, 0xef]),
                         knxdclient.encode_value(0x0500beef, knxdclient.KNXDPT.INT32))
        self.assertEqual(-2,
                         knxdclient.decode_value(bytes([0xff, 0xff, 0xff, 0xfe]), knxdclient.KNXDPT.INT32))
        self.assertEqual(0x0500beef,
                         knxdclient.decode_value(bytes([0x05, 0x00, 0xbe, 0xef]), knxdclient.KNXDPT.INT32))

    def test_dpt14_conversion(self) -> None:
        # Example from https://de.wikipedia.org/wiki/IEEE_754#Berechnung_Dezimalzahl_%E2%86%92_IEEE754-Gleitkommazahl
        self.assertEqual(bytes([0b11000001, 0b10010011, 0b00110011, 0b00110011]),
                         knxdclient.encode_value(-18.4, knxdclient.KNXDPT.FLOAT32))
        self.assertAlmostEqual(-18.4,
                               knxdclient.decode_value(bytes([0b11000001, 0b10010011, 0b00110011, 0b00110011]),
                                                       knxdclient.KNXDPT.FLOAT32),
                               places=5)

    def test_dpt16_conversion(self) -> None:
        # Example from the KNX standard
        self.assertEqual(bytes.fromhex("4B 4E 58 20 69 73 20 4F 4B 00 00 00 00 00"),
                         knxdclient.encode_value("KNX is OK", knxdclient.KNXDPT.STRING))
        self.assertEqual("KNX is OK",
                         knxdclient.decode_value(bytes.fromhex("4B 4E 58 20 69 73 20 4F 4B 00 00 00 00 00"),
                                                 knxdclient.KNXDPT.STRING))

        self.assertEqual(b"German has \xc4\xd6\xdc",
                         knxdclient.encode_value("German has ÄÖÜ", knxdclient.KNXDPT.STRING))
        self.assertEqual("German has ÄÖÜ",
                         knxdclient.decode_value(b"German has \xc4\xd6\xdc",
                                                 knxdclient.KNXDPT.STRING))

    def test_dpt24_conversion(self) -> None:
        # Example from the KNX standard
        self.assertEqual(bytes.fromhex("4B 4E 58 20 69 73 20 4F 4B 00"),
                         knxdclient.encode_value("KNX is OK", knxdclient.KNXDPT.VARSTRING))
        self.assertEqual("KNX is OK",
                         knxdclient.decode_value(bytes.fromhex("4B 4E 58 20 69 73 20 4F 4B 00"),
                                                 knxdclient.KNXDPT.VARSTRING))
        encoded = bytes.fromhex('54 68 69 73 20 66 6F 72 6D 61 74 20 61 6C 6C 6F 77 73 20 74 72 61 6E 73 6D 69 73 73 69'
                                '6F 6E 20 6F 66 20 76 65 72 79 20 6C 6F 6E 67 20 73 74 72 69 6E 67 73 21 00')
        decoded = "This format allows transmission of very long strings!"
        self.assertEqual(encoded, knxdclient.encode_value(decoded, knxdclient.KNXDPT.VARSTRING))
        self.assertEqual(decoded, knxdclient.decode_value(encoded, knxdclient.KNXDPT.VARSTRING))

        self.assertEqual(b"German has \xc4\xd6\xdc\x00",
                         knxdclient.encode_value("German has ÄÖÜ", knxdclient.KNXDPT.VARSTRING))
        self.assertEqual("German has ÄÖÜ",
                         knxdclient.decode_value(b"German has \xc4\xd6\xdc\x00",
                                                 knxdclient.KNXDPT.VARSTRING))

    def test_dpt17_conversion(self) -> None:
        self.assertEqual(bytes([63]),
                         knxdclient.encode_value(63, knxdclient.KNXDPT.SCENE_NUMBER))
        self.assertEqual(bytes([42]),
                         knxdclient.encode_value(42, knxdclient.KNXDPT.SCENE_NUMBER))
        self.assertEqual(63,
                         knxdclient.decode_value(bytes([63]), knxdclient.KNXDPT.SCENE_NUMBER))
        self.assertEqual(42,
                         knxdclient.decode_value(bytes([42]), knxdclient.KNXDPT.SCENE_NUMBER))

    def test_dpt18_conversion(self) -> None:
        self.assertEqual(bytes([63 | 0x80]),
                         knxdclient.encode_value((True, 63), knxdclient.KNXDPT.SCENE_CONTROL))
        self.assertEqual(bytes([42]),
                         knxdclient.encode_value((False, 42), knxdclient.KNXDPT.SCENE_CONTROL))
        self.assertEqual((True, 63),
                         knxdclient.decode_value(bytes([63 | 0x80]), knxdclient.KNXDPT.SCENE_CONTROL))
        self.assertEqual((False, 42),
                         knxdclient.decode_value(bytes([42]), knxdclient.KNXDPT.SCENE_CONTROL))

    def test_dpt19_conversion(self) -> None:
        # bits: YYYYYYYY 0000MMMM 000DDDDD WWWHHHHH 00MMMMM 00SSSSS XXXXXXXX X0000000
        # where the Xs are:
        # - Fault
        # - Working Day
        # - Working Day invalid
        # - Year invalid
        # - Month and Day invalid
        # - Weekday invalid
        # - Time invalid
        # - Daylight Saving Time / SUTI
        # - Clock has external sync signal
        self.assertEqual(bytes([122, 10, 12, (3 << 5) | 21, 42, 17, 0b00100000, 0]),
                         knxdclient.encode_value(datetime.datetime(2022, 10, 12, 21, 42, 17),
                                                 knxdclient.KNXDPT.DATE_TIME))
        self.assertEqual(datetime.datetime(2022, 10, 12, 21, 42, 17),
                         knxdclient.decode_value(bytes([122, 10, 12, (3 << 5) | 21, 42, 17, 0b00100000, 0]),
                                                 knxdclient.KNXDPT.DATE_TIME))

        self.assertEqual(bytes([91, 1, 1, (2 << 5), 0, 0, 0b00100010, 0]),
                         knxdclient.encode_value(datetime.date(1991, 1, 1),
                                                 knxdclient.KNXDPT.DATE_TIME))
        self.assertEqual(bytes([0, 0, 0, 6, 0, 11, 0b00111100, 0]),
                         knxdclient.encode_value(datetime.time(6, 0, 11),
                                                 knxdclient.KNXDPT.DATE_TIME))

    def test_dpt20_conversion(self) -> None:
        class HAVCMode(enum.Enum):
            Auto = 0
            Comfort = 1
            Standby = 2
            Economy = 3
            Building_Protection = 4

        self.assertEqual(bytes([2]), knxdclient.encode_value(HAVCMode.Standby, knxdclient.KNXDPT.ENUM8))
        self.assertEqual(bytes([2]), knxdclient.encode_value(2, knxdclient.KNXDPT.ENUM8))
        self.assertEqual(2, knxdclient.decode_value(bytes([2]), knxdclient.KNXDPT.ENUM8))

    def test_dpt26_conversion(self) -> None:
        self.assertEqual(bytes([63 | 0x80]),
                         knxdclient.encode_value((True, 63), knxdclient.KNXDPT.SCENE_INFO))
        self.assertEqual(bytes([42]),
                         knxdclient.encode_value((False, 42), knxdclient.KNXDPT.SCENE_INFO))
        self.assertEqual((True, 63),
                         knxdclient.decode_value(bytes([63 | 0x40]), knxdclient.KNXDPT.SCENE_INFO))
        self.assertEqual((False, 42),
                         knxdclient.decode_value(bytes([42]), knxdclient.KNXDPT.SCENE_INFO))
    
    def test_dpt29_conversion(self) -> None:
        self.assertEqual(bytes([0xff, 0xff, 0xff, 0xff, 0xf8, 0xa4, 0x32, 0xeb]),
                         knxdclient.encode_value(-123456789, knxdclient.KNXDPT.INT64))
        self.assertEqual(bytes([0x00, 0x00, 0x00, 0x0b, 0xad, 0xc0, 0xff, 0xee]),
                         knxdclient.encode_value(0xbadc0ffee, knxdclient.KNXDPT.INT64))
        self.assertEqual(-123456789,
                         knxdclient.decode_value(bytes([0xff, 0xff, 0xff, 0xff, 0xf8, 0xa4, 0x32, 0xeb]),
                                                 knxdclient.KNXDPT.INT64))
        self.assertEqual(0xbadc0ffee,
                         knxdclient.decode_value(bytes([0x00, 0x00, 0x00, 0x0b, 0xad, 0xc0, 0xff, 0xee]),
                                                 knxdclient.KNXDPT.INT64))

    def test_dpt232_conversion(self) -> None:
        self.assertEqual((0x12, 0x34, 0x56),
                         knxdclient.decode_value(
                             knxdclient.encode_value((0x12, 0x34, 0x56), knxdclient.KNXDPT.COLOUR_RGB),
                             knxdclient.KNXDPT.COLOUR_RGB))
        self.assertEqual(bytes([0x7f, 0x00, 0x20]),
                         knxdclient.encode_value((0x7f, 0x00, 0x20), knxdclient.KNXDPT.COLOUR_RGB))
        self.assertEqual((0x10, 0xcc, 0x0a),
                         knxdclient.decode_value(bytes([0x10, 0xcc, 0x0a]), knxdclient.KNXDPT.COLOUR_RGB))
