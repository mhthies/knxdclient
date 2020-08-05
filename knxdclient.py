import asyncio
import datetime
import enum
import logging
import struct
from typing import NamedTuple, Awaitable, Callable, List, Any, Union, Optional

logger = logging.getLogger(__name__)


class KNXDPacketTypes(enum.Enum):
    EIB_INVALID_REQUEST             = 0x0000
    EIB_CONNECTION_INUSE            = 0x0001
    EIB_PROCESSING_ERROR            = 0x0002
    EIB_CLOSED                      = 0x0003
    EIB_RESET_CONNECTION            = 0x0004
    EIB_OPEN_BUSMONITOR             = 0x0010
    EIB_OPEN_BUSMONITOR_TEXT        = 0x0011
    EIB_OPEN_VBUSMONITOR            = 0x0012
    EIB_OPEN_VBUSMONITOR_TEXT       = 0x0013
    EIB_BUSMONITOR_PACKET           = 0x0014
    EIB_OPEN_T_CONNECTION           = 0x0020
    EIB_OPEN_T_INDIVIDUAL           = 0x0021
    EIB_OPEN_T_GROUP                = 0x0022
    EIB_OPEN_T_BROADCAST            = 0x0023
    EIB_OPEN_T_TPDU                 = 0x0024
    EIB_APDU_PACKET                 = 0x0025
    EIB_OPEN_GROUPCON               = 0x0026
    EIB_GROUP_PACKET                = 0x0027
    EIB_PROG_MODE                   = 0x0030
    EIB_MASK_VERSION                = 0x0031
    EIB_M_INDIVIDUAL_ADDRESS_READ   = 0x0032
    EIB_M_INDIVIDUAL_ADDRESS_WRITE  = 0x0040
    EIB_ERROR_ADDR_EXISTS           = 0x0041
    EIB_ERROR_MORE_DEVICE           = 0x0042
    EIB_ERROR_TIMEOUT               = 0x0043
    EIB_ERROR_VERIFY                = 0x0044
    EIB_MC_INDIVIDUAL               = 0x0049
    EIB_MC_CONNECTION               = 0x0050
    EIB_MC_READ                     = 0x0051
    EIB_MC_WRITE                    = 0x0052
    EIB_MC_PROP_READ                = 0x0053
    EIB_MC_PROP_WRITE               = 0x0054
    EIB_MC_PEI_TYPE                 = 0x0055
    EIB_MC_ADC_READ                 = 0x0056
    EIB_MC_AUTHORIZE                = 0x0057
    EIB_MC_KEY_WRITE                = 0x0058
    EIB_MC_MASK_VERSION             = 0x0059
    EIB_MC_RESTART                  = 0x005a
    EIB_MC_WRITE_NOVERIFY           = 0x005b
    EIB_MC_PROG_MODE                = 0x0060
    EIB_MC_PROP_DESC                = 0x0061
    EIB_MC_PROP_SCAN                = 0x0062
    EIB_LOAD_IMAGE                  = 0x0063
    EIB_CACHE_ENABLE                = 0x0070
    EIB_CACHE_DISABLE               = 0x0071
    EIB_CACHE_CLEAR                 = 0x0072
    EIB_CACHE_REMOVE                = 0x0073
    EIB_CACHE_READ                  = 0x0074
    EIB_CACHE_READ_NOWAIT           = 0x0075
    EIB_CACHE_LAST_UPDATES          = 0x0076


class KNXDPT(enum.Enum):
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


EncodedData = Union[int, bytes]


class KNXTime(NamedTuple):
    time: datetime.time
    weekday: Optional[int]


def encode_value(value: Any, t: KNXDPT) -> EncodedData:
    # TODO add type and range checks
    if t is KNXDPT.BOOLEAN:
        return 1 if value else 0
    elif t is KNXDPT.TWO_BOOLEAN:
        return (1 if value[0] else 0) << 1 | (1 if value[1] else 0)
    elif t is KNXDPT.BOOLEAN_UINT3:
        return (1 if value[0] else 0) << 3 | (value[1] & 0x07)
    elif t is KNXDPT.CHAR:
        return bytes([value.encode('iso-8859-1')[0]])
    elif t is KNXDPT.UINT8:
        return bytes([value & 0xff])
    elif t is KNXDPT.INT8:
        return struct.pack('b', value)
    elif t is KNXDPT.UINT16:
        return struct.pack('>H', value)
    elif t is KNXDPT.INT16:
        return struct.pack('>h', value)
    elif t is KNXDPT.FLOAT16:
        # Source: https://github.com/mknx/smarthome/blob/15ebd847eac142557ab1b8d7ff92dafe965ea7b2/plugins/knx/dpts.py#L143
        s = 0
        e = 0
        if value < 0:
            s = 0x8000
        m = int(value * 100)
        while (m > 2047) or (m < -2048):
            e = e + 1
            m = m >> 1
        num = s | (e << 11) | (int(m) & 0x07ff)
        return struct.pack('>H', num)
    elif t is KNXDPT.TIME:
        return bytes([((value.weekday+1) << 5 if value.weekday is not None else 0) | value.time.hour,
                      value.time.minute,
                      value.time.second])
    elif t is KNXDPT.DATE:
        return bytes([value.day, value.month, value.year - 2000])
    elif t is KNXDPT.UINT32:
        return struct.pack('>I', value)
    elif t is KNXDPT.INT32:
        return struct.pack('>i', value)
    elif t is KNXDPT.FLOAT32:
        return struct.pack('>f', value)
    elif t is KNXDPT.STRING:
        enc = value.encode('iso-8859-1')
        return enc + bytes([0] * (14 - len(enc)))
    elif t is KNXDPT.SCENE_NUMBER:
        return bytes([value])
    elif t is KNXDPT.SCENE_CONTROL:
        return bytes([(0x80 if value[0] else 0) | value[1] & 0x3f])
    elif t is KNXDPT.DATE_TIME:
        year = month = day = hour = minute = second = weekday = 0
        date_invalid = time_invalid = 1
        dst = 0
        if isinstance(value, (datetime.date, datetime.datetime)):
            year = value.year
            month = value.month
            day = value.day
            date_invalid = 0
        if isinstance(value, (datetime.time, datetime.datetime)):
            value = value.astimezone()
            hour = value.hour
            minute = value.minute
            second = value.second
            time_invalid = 0
            if isinstance(value, datetime.datetime):
                dst = int(bool(value.tzinfo.dst(value)))
        else:
            year = month = day = 0
        return bytes([year-2000, month, day, ((weekday+1) << 5 if not date_invalid else 0) | hour,
                      minute, second,
                      (0x20 | (date_invalid * 0x1c) | (time_invalid * 0x02) | (dst * 0x01)),
                      0])
    elif t is KNXDPT.ENUM8:
        # Support raw int values or Python enum with value type int
        if isinstance(value, int):
            return bytes([value])
        return bytes([value.value])
    elif t is KNXDPT.VARSTRING:
        return value.encode('iso-8859-1') + b'\0'
    else:
        raise NotImplementedError()


def decode_value(value: EncodedData, t: KNXDPT) -> Any:
    # TODO add type checks
    if t is KNXDPT.BOOLEAN:
        return bool(value)
    elif t is KNXDPT.TWO_BOOLEAN:
        return bool(value >> 1 & 0x01), bool(value & 0x01)
    elif t is KNXDPT.BOOLEAN_UINT3:
        return bool(value >> 3 & 0x01), value & 0x07
    elif t is KNXDPT.CHAR:
        return value[0].decode('iso-8859-1')
    elif t is KNXDPT.UINT8:
        return value[0]
    elif t is KNXDPT.INT8:
        return struct.unpack('b', value)[0]
    elif t is KNXDPT.UINT16:
        return struct.unpack('>H', value)[0]
    elif t is KNXDPT.INT16:
        return struct.unpack('>h', value)[0]
    elif t is KNXDPT.FLOAT16:
        # Source: https://github.com/mknx/smarthome/blob/15ebd847eac142557ab1b8d7ff92dafe965ea7b2/plugins/knx/dpts.py#L156
        i1 = value[0]
        i2 = value[1]
        s = (i1 & 0x80) >> 7
        e = (i1 & 0x78) >> 3
        m = (i1 & 0x07) << 8 | i2
        if s == 1:
            s = -1 << 11
        return (m | s) * 0.01 * pow(2, e)
    elif t is KNXDPT.TIME:
        weekday_value = value[0] >> 5 & 0x07
        return KNXTime(
            datetime.time(value[0] & 0x1f, value[1], value[2]),
            weekday_value-1 if weekday_value else None)
    elif t is KNXDPT.DATE:
        return datetime.date(value[0], value[1], value[2]+2000)
    elif t is KNXDPT.UINT32:
        return struct.unpack('>I', value)[0]
    elif t is KNXDPT.INT32:
        return struct.unpack('>i', value)[0]
    elif t is KNXDPT.FLOAT32:
        return struct.unpack('>f', value)[0]
    elif t in (KNXDPT.STRING, KNXDPT.VARSTRING):
        return value.decode('iso-8859-1').split('\0')[0]
    elif t is KNXDPT.SCENE_NUMBER:
        return value[0]
    elif t is KNXDPT.SCENE_CONTROL:
        return bool(value[0] & 0x80), value[0] & 0x3f
    elif t is KNXDPT.DATE_TIME:
        return datetime.datetime(year=value[0]+2000, month=value[1], day=value[2], hour=value[3] & 0x1f,
                                 minute=value[4], second=value[5])
    elif t is KNXDPT.ENUM8:
        # The raw int value is returned. The User code must construct the correct Enum type if required.
        return value[0]
    else:
        raise NotImplementedError()


class KNXDPacket(NamedTuple):
    type: KNXDPacketTypes
    data: bytes

    def encode(self) -> bytes:
        return self.type.value.to_bytes(2, byteorder='big') + self.data

    @classmethod
    def decode(cls, data: bytes) -> "KNXDPacket":
        return cls(KNXDPacketTypes(int.from_bytes(data[0:2], byteorder='big')), data[2:])

    def __repr__(self) -> str:
        return "{}({}, data={})".format(self.__class__.__name__, self.type.name, self.data.hex(' '))


class KNXDAPDUType(enum.Enum):
    WRITE = 0b10000000
    READ = 0b00000000
    RESPONSE = 0b01000000


class KNXDAPDU(NamedTuple):
    type: KNXDAPDUType
    value: EncodedData

    def encode(self) -> bytes:
        if isinstance(self.value, bytes):
            return bytes([0, self.type.value]) + self.value
        elif self.value > 0b00111111 or self.value < 0:
            raise ValueError("Invalid value {} for KNXDAPDU".format(self.value))
        else:
            return bytes([0, self.type.value | self.value])

    @classmethod
    def decode(cls, data: bytes) -> "KNXDAPDU":
        apdu_type = KNXDAPDUType(data[1] & 0b11000000)
        if len(data) > 2:
            return cls(apdu_type, data[2:])
        else:
            return cls(apdu_type, data[1] & 0b00111111)

    def __repr__(self) -> str:
        return "{}({}, value={})".format(self.__class__.__name__, self.type.name,
                                         self.value.hex(' ') if isinstance(self.value, bytes) else "{:02X}".format(self.value))


class GroupAddress(NamedTuple):
    main: int
    middle: int
    sub: int

    def encode(self) -> bytes:
        return bytes([(self.main << 3) | self.middle, self.sub])

    @classmethod
    def decode(cls, data: bytes) -> "GroupAddress":
        return cls(((data[0] >> 3) & 0x1f), data[0] & 0x07, data[1])

    def __repr__(self):
        return "{}/{}/{}".format(*self)


class IndividualAddress(NamedTuple):
    area: int
    line: int
    device: int

    def encode(self) -> bytes:
        return bytes([(self.area << 4) | self.line, self.device])

    @classmethod
    def decode(cls, data: bytes) -> "IndividualAddress":
        return cls(((data[0] >> 4) & 0x0f), data[0] & 0x0f, data[1])

    def __repr__(self):
        return "{}.{}.{}".format(*self)


class ReceivedGroupAPDU(NamedTuple):
    src: IndividualAddress
    dst: GroupAddress
    payload: KNXDAPDU

    @classmethod
    def decode(cls, data: bytes) -> "ReceivedGroupAPDU":
        return cls(IndividualAddress.decode(data[0:2]),
                   GroupAddress.decode(data[2:4]),
                   KNXDAPDU.decode(data[4:]))


class KNXDConnection:
    def __init__(self):
        self._handlers: List[Callable[[ReceivedGroupAPDU], Awaitable[Any]]] = []

    async def connect(self, host: str = 'localhost', port: int = 6720, sock: Optional[str] = None):
        self._lock = asyncio.Lock()
        self._current_response: Optional[KNXDPacket] = None
        self._response_ready = asyncio.Event()

        if sock:
            logger.info("Connecting to KNXd via UNIX domain socket at %s ...", sock)
            self._reader, self._writer = await asyncio.open_unix_connection(sock)
        else:
            logger.info("Connecting to KNXd at %s:%s ...", host, port)
            self._reader, self._writer = await asyncio.open_connection(host=host, port=port)
        logger.info("Connecting to KNXd successful")

    async def run(self):
        logger.info("Entering KNXd client receive loop ...")

        async def call_handler(handler: Callable[[ReceivedGroupAPDU], Awaitable[Any]], apdu: ReceivedGroupAPDU):
            try:
                await handler(apdu)
            except Exception as e:
                logger.error("Error while calling handler %s for incoming KNX APDU %s:", handler, apdu, exc_info=e)

        while True:
            try:
                length = int.from_bytes(await self._reader.readexactly(2), byteorder='big')
                data = await self._reader.readexactly(length)
                packet = KNXDPacket.decode(data)
                logger.debug("Received packet from KNXd: %s", packet)
                if packet.type is KNXDPacketTypes.EIB_GROUP_PACKET:
                    apdu = ReceivedGroupAPDU.decode(packet.data)
                    logger.debug("Received Group Address broadcast (APDU) from KNXd: %s", apdu)
                    for handler in self._handlers:
                        asyncio.create_task(call_handler(handler, apdu))
                else:
                    self._current_response = packet
                    self._response_ready.set()
            except asyncio.IncompleteReadError:
                logger.info("KNXd connection reached EOF. Shutting down KNXClient.")
                return
            except Exception as e:
                logger.error("Error while receiving KNX packets:", exc_info=e)

    async def stop(self):
        logger.info("Stopping KNXd client ...")
        self._writer.close()
        await self._writer.wait_closed()

    def register_telegram_handler(self, handler: Callable[[ReceivedGroupAPDU], Awaitable[Any]]) -> None:
        self._handlers.append(handler)

    async def open_group_socket(self, write_only=False) -> None:
        logger.info("Opening KNX group socket for sending to group addresses ...")
        async with self._lock:
            self._response_ready.clear()
            await self._send_eibd_packet(KNXDPacket(KNXDPacketTypes.EIB_OPEN_GROUPCON, bytes([0, 0xff if write_only else 0, 0])))
            await self._response_ready.wait()
            response = self._current_response
        assert(response is not None)
        if response.type is not KNXDPacketTypes.EIB_OPEN_GROUPCON:
            raise RuntimeError("Could not open KNX group socket. Response: {}".format(response))
        else:
            logger.info("Opening KNX group socket successful")

    async def group_write(self, addr: GroupAddress, write_type: KNXDAPDUType, encoded_data: EncodedData) -> None:
        logger.debug("%s to KNX group address %s: %s", write_type.name, addr, encoded_data)
        await self._send_eibd_packet(KNXDPacket(KNXDPacketTypes.EIB_GROUP_PACKET,
                                                addr.encode() + KNXDAPDU(write_type, encoded_data).encode()))

    async def _send_eibd_packet(self, packet: KNXDPacket):
        logger.debug("Sending packet to KNXd: %s", packet)
        data = packet.encode()
        if len(data) < 2 or len(data) > 0xffff:
            raise ValueError('Invalid packet length: {}'.format(repr(data)))
        data = len(data).to_bytes(2, byteorder='big') + data
        self._writer.write(data)
        await self._writer.drain()
