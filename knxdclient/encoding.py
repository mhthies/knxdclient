# Copyright 2020-2022 Michael Thies <mail@mhthies.de>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.

import datetime
import enum
import logging
import struct
from typing import NamedTuple, Any, Union, Optional, cast, Type, Dict, Tuple

from .packets import EncodedData

logger = logging.getLogger(__name__)


class KNXDPT(enum.Enum):
    """
    Enum of supported KNX Datapoint Types (DPTs). Used by :func:`encode_value` and :func:`decode_value` to specify how
    the value should be interpreted. Each entries int `value` corresponds to the KNX Datatype Main number (according to
    KNX specification section 3.7.2).
    """
    BOOLEAN = 1
    TWO_BOOLEAN = 2
    BOOLEAN_UINT3 = 3
    CHAR = 4
    UINT8 = 5
    INT8 = 6
    UINT16 = 7
    INT16 = 8
    FLOAT16 = 9
    TIME = 10
    DATE = 11
    UINT32 = 12
    INT32 = 13
    FLOAT32 = 14
    ACCESS_CONTROL = 15
    STRING = 16
    SCENE_NUMBER = 17
    SCENE_CONTROL = 18
    DATE_TIME = 19
    ENUM8 = 20
    VARSTRING = 24
    COLOUR_RGB = 232


class KNXTime(NamedTuple):
    """ Python representation of a KNX 'time of day' packet. In addition to the actual time, it contains a weekday
    number (from 0-6)."""
    time: datetime.time
    weekday: Optional[int]

    @classmethod
    def from_datetime(cls, value: datetime.datetime):
        return cls(value.time(), value.weekday())


DPT_ENCODING: Dict[KNXDPT, Type[EncodedData]] = {
    KNXDPT.BOOLEAN: int,
    KNXDPT.TWO_BOOLEAN: int,
    KNXDPT.BOOLEAN_UINT3: int,
    KNXDPT.CHAR: bytes,
    KNXDPT.UINT8: bytes,
    KNXDPT.INT8: bytes,
    KNXDPT.UINT16: bytes,
    KNXDPT.INT16: bytes,
    KNXDPT.FLOAT16: bytes,
    KNXDPT.TIME: bytes,
    KNXDPT.DATE: bytes,
    KNXDPT.UINT32: bytes,
    KNXDPT.INT32: bytes,
    KNXDPT.FLOAT32: bytes,
    KNXDPT.STRING: bytes,
    KNXDPT.SCENE_NUMBER: bytes,
    KNXDPT.SCENE_CONTROL: bytes,
    KNXDPT.DATE_TIME: bytes,
    KNXDPT.ENUM8: bytes,
    KNXDPT.VARSTRING: bytes,
    KNXDPT.COLOUR_RGB: bytes,
}

DPT_PYTHON_REPRESENTATION: Dict[KNXDPT, Union[type, Tuple[type, ...]]] = {
    KNXDPT.BOOLEAN: object,  # any object can be interpreted as bool
    KNXDPT.TWO_BOOLEAN: tuple,
    KNXDPT.BOOLEAN_UINT3: tuple,
    KNXDPT.CHAR: str,
    KNXDPT.UINT8: int,
    KNXDPT.INT8: int,
    KNXDPT.UINT16: int,
    KNXDPT.INT16: int,
    KNXDPT.FLOAT16: float,
    KNXDPT.TIME: KNXTime,
    KNXDPT.DATE: datetime.date,
    KNXDPT.UINT32: int,
    KNXDPT.INT32: int,
    KNXDPT.FLOAT32: float,
    KNXDPT.STRING: str,
    KNXDPT.SCENE_NUMBER: int,
    KNXDPT.SCENE_CONTROL: tuple,
    KNXDPT.DATE_TIME: (datetime.datetime, datetime.date, datetime.time),
    KNXDPT.ENUM8: (int, enum.Enum),
    KNXDPT.VARSTRING: str,
    KNXDPT.COLOUR_RGB: bytes,
}


def encode_value(value: Any, t: KNXDPT) -> EncodedData:
    """
    Encode a python value for sending in a KNX telegram according to a known KNX Datapoint type (from KNX specification,
    section 3.7.2).

    :param value: The value to encode
    :param t: The target KNX datapoint main type from `KNXDPT`
    :return: the encoded value as an integer (for 1-6 bit values, which are encoded in byte 2 of the APDU) or a bytes
        string.
    """
    if not isinstance(value, DPT_PYTHON_REPRESENTATION[t]):
        raise TypeError(f"Cannot use {repr(value)} as a KNX {t.name}, since it is not a {DPT_PYTHON_REPRESENTATION[t]}")
    val = cast(Any, value)
    # TODO add tuple entry type checks and range checks
    if t is KNXDPT.BOOLEAN:
        return 1 if val else 0
    elif t is KNXDPT.TWO_BOOLEAN:
        return (1 if val[0] else 0) << 1 | (1 if val[1] else 0)
    elif t is KNXDPT.BOOLEAN_UINT3:
        return (1 if val[0] else 0) << 3 | (val[1] & 0x07)
    elif t is KNXDPT.CHAR:
        return bytes([val.encode('iso-8859-1')[0]])
    elif t is KNXDPT.UINT8:
        return bytes([val & 0xff])
    elif t is KNXDPT.INT8:
        return struct.pack('b', val)
    elif t is KNXDPT.UINT16:
        return struct.pack('>H', val)
    elif t is KNXDPT.INT16:
        return struct.pack('>h', val)
    elif t is KNXDPT.FLOAT16:
        # KNX's DPT 9 (16bit float) is defined in the KNX Standard, section 3.7.2.3.10.
        # It is not compatible with the IEEE 754-2008 standard.
        # According to the standard, it uses a 4bit exponent (0-15), a 12bit two's complement mantissa and a prescaler
        # of 0,01. The calculation formula is defined by V = (0.01 * M) * 2^E. The 16 bits are used in the following
        # pattern: MEEE EMMM | MMMM MMMM. (First bit of the mantissa, which denotes the sign, is split apart from the
        # rest of the mantissa).
        # The highest resolution is 0,01 (with E = 0), so round the val to that resolution and increase E (lower
        # resolution) until the val fits the 12 bit mantissa
        m = round(val * 100)
        e = 0
        while m > 2047 or m < -2048:
            e += 1
            m = m >> 1  # FIXME: We are not rounding correctly here
            if e > 15:
                raise ValueError("Value {} is out of representable range for KNX DPT 9".format(val))
        return bytes([(m & 0x0800) >> 4 | e << 3 | (m & 0x0700) >> 8, m & 0xff])
    elif t is KNXDPT.TIME:
        return bytes([((val.weekday+1) << 5 if val.weekday is not None else 0) | val.time.hour,
                      val.time.minute,
                      val.time.second])
    elif t is KNXDPT.DATE:
        if not 1990 <= val.year < 2090:
            raise ValueError("Only dates between year 1990 and 2089 can be represend via KNX DPT 11.001")
        return bytes([val.day, val.month, val.year - 2000 if val.year >= 2000 else val.year - 1900])
    elif t is KNXDPT.UINT32:
        return struct.pack('>I', val)
    elif t is KNXDPT.INT32:
        return struct.pack('>i', val)
    elif t is KNXDPT.FLOAT32:
        return struct.pack('>f', val)
    elif t is KNXDPT.STRING:
        enc = val.encode('iso-8859-1')
        return enc + bytes([0] * (14 - len(enc)))
    elif t is KNXDPT.SCENE_NUMBER:
        return bytes([val])
    elif t is KNXDPT.SCENE_CONTROL:
        return bytes([(0x80 if val[0] else 0) | val[1] & 0x3f])
    elif t is KNXDPT.DATE_TIME:
        month = day = hour = minute = second = weekday = 0
        year = 1900
        date_invalid = time_invalid = 1
        dst = 0
        if isinstance(val, (datetime.date, datetime.datetime)):
            year = val.year
            month = val.month
            day = val.day
            date_invalid = 0
            weekday = val.weekday()
        if isinstance(val, (datetime.time, datetime.datetime)):
            if isinstance(val, datetime.datetime):
                val = val.astimezone()
            hour = val.hour
            minute = val.minute
            second = val.second
            time_invalid = 0
            if isinstance(val, datetime.datetime):
                dst = int(bool(val.tzinfo.dst(val)))  # type: ignore
        return bytes([year-1900, month, day, ((weekday+1) << 5 if not date_invalid else 0) | hour,
                      minute, second,
                      (0x20 | (date_invalid * 0x1c) | (time_invalid * 0x02) | (dst * 0x01)),
                      0])
    elif t is KNXDPT.ENUM8:
        # Support raw int vals or Python enum with val type int
        if isinstance(val, int):
            return bytes([val])
        val = val.value
        if not isinstance(val, int):
            raise TypeError(f"Enum entry value for ENUM8 must be an int")
        return bytes([val])
    elif t is KNXDPT.VARSTRING:
        return val.encode('iso-8859-1') + b'\0'
    elif t is KNXDPT.COLOUR_RGB:
        return bytes([val[0] , val[1] , val[2]])
    else:
        raise NotImplementedError()


def decode_value(value: EncodedData, t: KNXDPT) -> Any:
    """
    Decode an encoded value from a KNX telegram according to a known KNX Datapoint type (from KNX specification,
    section 3.7.2).

    :param value: The encoded value, as a single int for 1-6 bit values or a bytes string for multibyte values
    :param t: The value's KNX datapoint main type from `KNXDPT`
    :return: the decoded value
    """
    if not isinstance(value, DPT_ENCODING[t]):
        raise TypeError(f"Expected a {DPT_ENCODING[t]} for KNX {t.name}, not {repr(value)}")
    val = cast(Any, value)
    if t is KNXDPT.BOOLEAN:
        return bool(val)
    elif t is KNXDPT.TWO_BOOLEAN:
        return bool(val >> 1 & 0x01), bool(val & 0x01)
    elif t is KNXDPT.BOOLEAN_UINT3:
        return bool(val >> 3 & 0x01), val & 0x07
    elif t is KNXDPT.CHAR:
        return val.decode('iso-8859-1')
    elif t is KNXDPT.UINT8:
        return val[0]
    elif t is KNXDPT.INT8:
        return struct.unpack('b', val)[0]
    elif t is KNXDPT.UINT16:
        return struct.unpack('>H', val)[0]
    elif t is KNXDPT.INT16:
        return struct.unpack('>h', val)[0]
    elif t is KNXDPT.FLOAT16:
        # For a description of the KNX DPT 9 16-bit floating point format see comment in `encode_val()` above.
        # In two's complement notation, the MSB has a negative val (-2^(n-1)):
        msb = - (val[0] & 0x80) << 4
        e = (val[0] & 0x78) >> 3
        m = (val[0] & 0x07) << 8 | val[1]
        return (m + msb) * 0.01 * 2**e
    elif t is KNXDPT.TIME:
        weekday_val = val[0] >> 5 & 0x07
        return KNXTime(
            datetime.time(val[0] & 0x1f, val[1], val[2]),
            weekday_val-1 if weekday_val else None)
    elif t is KNXDPT.DATE:
        return datetime.date(val[2]+2000 if val[2] < 90 else val[2] + 1900, val[1], val[0])
    elif t is KNXDPT.UINT32:
        return struct.unpack('>I', val)[0]
    elif t is KNXDPT.INT32:
        return struct.unpack('>i', val)[0]
    elif t is KNXDPT.FLOAT32:
        return struct.unpack('>f', val)[0]
    elif t in (KNXDPT.STRING, KNXDPT.VARSTRING):
        return val.decode('iso-8859-1').split('\0')[0]
    elif t is KNXDPT.SCENE_NUMBER:
        return val[0]
    elif t is KNXDPT.SCENE_CONTROL:
        return bool(val[0] & 0x80), val[0] & 0x3f
    elif t is KNXDPT.DATE_TIME:
        return datetime.datetime(year=val[0]+1900, month=val[1], day=val[2], hour=val[3] & 0x1f,
                                 minute=val[4], second=val[5])
    elif t is KNXDPT.ENUM8:
        # The raw int val is returned. The User code must construct the correct Enum type if required.
        return val[0]
    elif t is KNXDPT.COLOUR_RGB:
        return f'{(val[2] + (val[1] << 8) + (val[0] << 16)):X}'
    else:
        raise NotImplementedError()
