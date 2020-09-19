# Copyright 2020 Michael Thies <mail@mhthies.de>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.

"""
A pure Python async client for KNXd's (EIBd's) native Layer 4 KNX protocol.

This module reimplements small parts of the EIBd client (see BCUSDK documentation
`archive link <https://web.archive.org/web/20160418110523/https://www.auto.tuwien.ac.at/~mkoegler/eib/sdkdoc-0.0.5.pdf>`_)
based on Python asynchronous coroutines (asyncio). Currently, it allows to open a GroupSocket for sending and receiving
KNX telegrams to/for any group address via KNXd. Additionally, there are helper methods :func:`encode_value` and
:func:`decode_value` to convert the values from/to native Python types according to a known KNX Datapoint Type
(DPT).

This module's base class is :class:`KNXDConnection`. See its docstring for further reference.
"""

import asyncio
import datetime
import enum
import logging
import struct
from typing import NamedTuple, Awaitable, Callable, List, Any, Union, Optional

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


EncodedData = Union[int, bytes]


class KNXTime(NamedTuple):
    """ Python representation of a KNX 'time of day' packet. In addition to the actual time, it contains a weekday
    number (from 0-6)."""
    time: datetime.time
    weekday: Optional[int]

    @classmethod
    def from_datetime(cls, value: datetime.datetime):
        return cls(value.time(), value.weekday())


def encode_value(value: Any, t: KNXDPT) -> EncodedData:
    """
    Encode a python value for sending in a KNX telegram according to a known KNX Datapoint type (from KNX specification,
    section 3.7.2).

    :param value: The value to encode
    :param t: The target KNX datapoint main type from `KNXDPT`
    :return: the encoded value as an integer (for 1-6 bit values, which are encoded in byte 2 of the APDU) or a bytes
        string.
    """
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
        # KNX's DPT 9 (16bit float) is defined in the KNX Standard, section 3.7.2.3.10.
        # It is not compatible with the IEEE 754-2008 standard.
        # According to the standard, it uses a 4bit exponent (0-15), a 12bit two's complement mantissa and a prescaler
        # of 0,01. The calculation formula is defined by V = (0.01 * M) * 2^E. The 16 bits are used in the following
        # pattern: MEEE EMMM | MMMM MMMM. (First bit of the mantissa, which denotes the sign, is split apart from the
        # rest of the mantissa).
        # The highest resolution is 0,01 (with E = 0), so round the value to that resolution and increase E (lower
        # resolution) until the value fits the 12 bit mantissa
        m = round(value * 100)
        e = 0
        while m > 2047 or m < -2048:
            e += 1
            m = m >> 1  # FIXME: We are not rounding correctly here
            if e > 15:
                raise ValueError("Value {} is out of representable range for KNX DPT 9".format(value))
        return bytes([(m & 0x0800) >> 4 | e << 3 | (m & 0x0700) >> 8, m & 0xff])
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
    """
    Decode an encoded value from a KNX telegram according to a known KNX Datapoint type (from KNX specification,
    section 3.7.2).

    :param value: The encoded value, as a single int for 1-6 bit values or a bytes string for multibyte values
    :param t: The value's KNX datapoint main type from `KNXDPT`
    :return: the decoded value
    """
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
        # For a description of the KNX DPT 9 16-bit floating point format see comment in `encode_value()` above.
        # In two's complement notation, the MSB has a negative value (-2^(n-1)):
        msb = - (value[0] & 0x80) << 4
        e = (value[0] & 0x78) >> 3
        m = (value[0] & 0x07) << 8 | value[1]
        return (m + msb) * 0.01 * 2**e
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
    """
    A packet in TCP/socket communcation with the KNXd/EIBd daemon.
    """
    type: "KNXDPacketTypes"
    data: bytes

    def encode(self) -> bytes:
        """Encode a packet for sending it to the KNXd/EIBd."""
        return self.type.value.to_bytes(2, byteorder='big') + self.data

    @classmethod
    def decode(cls, data: bytes) -> "KNXDPacket":
        """Construct a packet tuple from the binary data received from the KNXd/EIBd."""
        return cls(KNXDPacketTypes(int.from_bytes(data[0:2], byteorder='big')), data[2:])

    def __repr__(self) -> str:
        return "{}({}, data={})".format(self.__class__.__name__, self.type.name, self.data.hex(' '))


class KNXDAPDUType(enum.Enum):
    """
    KNX Group value APDU types. The int value of each entry corresponds to the second byte of the TPDU packet (see KNX
    specification, section 3.3.7.2).
    """
    WRITE = 0b10000000
    READ = 0b00000000
    RESPONSE = 0b01000000


class KNXGroupAPDU(NamedTuple):
    """
    A KNX A_GroupValue_Read/Response/Write-PDU (Application Data Unit), splitted into type and binary encoded value
    """
    type: KNXDAPDUType
    value: EncodedData

    def encode(self) -> bytes:
        if isinstance(self.value, bytes):
            return bytes([0, self.type.value]) + self.value
        elif self.value > 0b00111111 or self.value < 0:
            raise ValueError("Invalid value {} for KNXGroupAPDU".format(self.value))
        else:
            return bytes([0, self.type.value | self.value])

    @classmethod
    def decode(cls, data: bytes) -> "KNXGroupAPDU":
        apdu_type = KNXDAPDUType(data[1] & 0b11000000)
        if len(data) > 2:
            return cls(apdu_type, data[2:])
        else:
            return cls(apdu_type, data[1] & 0b00111111)

    def __repr__(self) -> str:
        return "{}({}, value={})".format(self.__class__.__name__, self.type.name,
                                         self.value.hex(' ') if isinstance(self.value, bytes) else "{:02X}".format(self.value))


class GroupAddress(NamedTuple):
    """
    A KNX group address in the three-layer (main/middle/sub) notation
    """
    main: int
    middle: int
    sub: int

    def encode(self) -> bytes:
        """Encode the KNX Group address into the two-octet transfer encoding"""
        return bytes([(self.main << 3) | self.middle, self.sub])

    @classmethod
    def decode(cls, data: bytes) -> "GroupAddress":
        """Decode a KNX Group address from the two-octet transfer encoding"""
        return cls(((data[0] >> 3) & 0x1f), data[0] & 0x07, data[1])

    def __repr__(self):
        return "{}/{}/{}".format(*self)


class IndividualAddress(NamedTuple):
    """
    A KNX device's Individual Address in the area.line.device notation
    """
    area: int
    line: int
    device: int

    def encode(self) -> bytes:
        """Encode the KNX Individual Address into the two-octet transfer encoding"""
        return bytes([(self.area << 4) | self.line, self.device])

    @classmethod
    def decode(cls, data: bytes) -> "IndividualAddress":
        """Decode a KNX Individual Address from the two-octet transfer encoding"""
        return cls(((data[0] >> 4) & 0x0f), data[0] & 0x0f, data[1])

    def __repr__(self):
        return "{}.{}.{}".format(*self)


class ReceivedGroupAPDU(NamedTuple):
    """
    A KNX Group Value Application Protocol, as received from KNXd in a EIB_GROUP_PACKET type packet. In addition to the
    APDU itself, the sender's individual address and the destination group address are included.
    """
    src: IndividualAddress
    dst: GroupAddress
    payload: KNXGroupAPDU

    @classmethod
    def decode(cls, data: bytes) -> "ReceivedGroupAPDU":
        """Decode all information (source Individual Gddress, destination Group Address and APDU) from the payload of
        an EIB_GROUP_PACKET-type KNXd packet."""
        return cls(IndividualAddress.decode(data[0:2]),
                   GroupAddress.decode(data[2:4]),
                   KNXGroupAPDU.decode(data[4:]))


class KNXDConnection:
    """
    A connector for the KNXd native protocol. It wraps an asyncio TCP or UNIX socket server and provides highlevel
    (async) methods to interact with KNXd.

    The main control flow for the connector is split into three methods:

    * :meth:`connect` trys to open the TCP/unix socket to connect to KNXd. It returns upon successful estalishment of
        the connection or raises an exception.
    * :meth:`run` runs the main receive loop for incoming messages (like Group Addres telegrams). It spins in an await
        loop until the connector has been stopped gracefully. In case of a read error, an exception is raised.
    * :meth:`stop` initiates a graceful shutdown and termination of the connection.

    To send and receive Group Address packets, a Group Socket must be opened in KNXD. This is initiated by the
    :meth:`open_group_socket` method. However, this method requires the receive loop (i.e. the :meth:`run` method)
    to be already running in an second asyncio task.

    After opening the Group Socket, incoming Group Address telegrams are registered and passed on to all handler
    functions, registered via :meth:`register_telegram_handler`. To send a Group Address telegram, :meth:`group_write`
    can be used.

    In summary, a typical invocation of this connector looks like this::

        async def handler(packet: knxdclient.ReceivedGroupAPDU) -> None:
            print("Received group telegram: {}".format(packet))

        connection = KNXDConnection()
        connection.register_telegram_handler(handler)
        await connection.connect()
        # Connection was successful. Start receive loop:
        run_task = asyncio.create_task(connection.run())
        # Now that the receive loop is running, we can open the KNXd Group Socket:
        await connection.open_group_socket()

        # Startup completed. Now our `handler()` will receive incoming telegrams and we can send some:
        await connection.group_write(GroupAddress(1,3,2), KNXDAPDUType.WRITE, encode_value(True, KNXDPT.BOOLEAN))

        # Let's stop the connection and wait for graceful termination of the receive loop:
        await connection.stop()
        await run_task
    """
    def __init__(self):
        self._handlers: List[Callable[[ReceivedGroupAPDU], Awaitable[Any]]] = []
        self.closing = False
        self._current_response: Optional[KNXDPacket] = None
        # A lock to ensure, that only one synchronous action is performed on the KNXD connection at once. Synchronous
        # actions are for example EIB_OPEN_GROUPCON. The lock should be acquired before sending the synchronous request
        # packet to KNXD and only released after receiving the response packet from KNXD.
        # Sending and receiving group telegrams via an opened Group Socket is asynchronous and thus does not require the
        # lock.
        self._lock = asyncio.Lock()
        # An (asyncio) event to await the receipt of a synchronous response packet from KNXD. Before sending a
        # synchronous request packet to KNXD, a coroutine method should ``clear()`` this event; and afterwards
        # ``wait()`` on it. As soon as a response is received by the :meth:`run` coroutine, it will store the response
        # in ``_current_response` and inform the waiting method by setting the event.
        self._response_ready = asyncio.Event()

    async def connect(self, host: str = 'localhost', port: int = 6720, sock: Optional[str] = None):
        """
        Coroutine to connect to KNXd/EIBd via TCP port or UNIX socket

        Awaits until connection has been established or raises one of Python's built in Exceptions on connection errors.

        :param host: KNXd host for TCP connection. Defaults to 'localhost'. Ignored, if `sock` is present.
        :param port: Port for KNXd TCP connection. Defaults to 6720, which is KNXd's default port. Ignored, if `sock` is
            present.
        :param sock: Path of the KNXd UNIX socket. If given, `host` and `port` are ignored.
        """
        if sock:
            logger.info("Connecting to KNXd via UNIX domain socket at %s ...", sock)
            # TODO close previous connection if any
            self._reader, self._writer = await asyncio.open_unix_connection(sock)
        else:
            logger.info("Connecting to KNXd at %s:%s ...", host, port)
            self._reader, self._writer = await asyncio.open_connection(host=host, port=port)
        logger.info("Connecting to KNXd successful")

    async def run(self):
        """
        Coroutine for running the receive loop for incoming packets from EIBD/KNXD.

        This method awaits incoming packets in a loop and only returns upon successful shutdown via :meth:`stop`. In
        case of an ``ConnectionError`` or an unexpected connection termination, an exception is raised. Other
        exceptions occuring within the loop are caught and logged.

        The connection with KNXD must be opened using :meth:`connect`, before starting this coroutine.

        Incoming packets are separated by their type:
        * for each packet of type *EIB_GROUP_PACKET* (asynchronous message from KNXD), all registered telegram handlers
          are called with the payload decoded as :class:`ReceivedGroupAPDU`
        * for every other (synchronous response) EIBD packet type, the packet is stored in an internal buffer and
          waiting synchronous KNXD request functions (like :meth:`open_group_socket`) are informed.

        :raises ConnectionAbortedError: in case of an unexpected EOF (connection closed without ``stop()`` being called)
        :raises ConnectionError: in case such an error occurs while reading
        """
        logger.info("Entering KNXd client receive loop ...")

        async def call_handler(handler: Callable[[ReceivedGroupAPDU], Awaitable[Any]], apdu: ReceivedGroupAPDU):
            try:
                await handler(apdu)
            except Exception as e:
                logger.error("Error while calling handler %s for incoming KNX APDU %s:", handler, apdu, exc_info=e)

        # TODO check if _reader is existing
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
            except asyncio.IncompleteReadError as e:
                if self.closing:
                    logger.info("KNXd connection reached EOF. KNXd client is stopped.")
                    return
                else:
                    raise ConnectionAbortedError("KNXd connection was closed with EOF unexpectedly.") from e
            except ConnectionError:
                # A connection error typically means we cannot proceed further with this connection. Thus  we abort the
                # receive loop execution with the exception.
                raise
            except Exception as e:
                logger.error("Error while receiving KNX packets:", exc_info=e)

    async def stop(self):
        """
        Coroutine to initiate a graceful shutdown of the KNXD connection.

        This coroutine awaits the successful shutdown of the connection.
        """
        logger.info("Stopping KNXd client ...")
        self.closing = True
        self._writer.close()
        await self._writer.wait_closed()

    def register_telegram_handler(self, handler: Callable[[ReceivedGroupAPDU], Awaitable[Any]]) -> None:
        """
        Register a coroutine as callback handler for incoming group read/response/write telegrams.

        The :meth:`run` coroutine will run each registered handler function in a separate :class:`asyncio.Task` for
        every incoming group telegram (asynchronous message from KNXD). To enable receiving of group telegrams, a
        Group Socket has to be opened in KNXD.

        :param handler: The handler coroutine. It must be awaitable and take a single argument of type
            :class:`ReceivedGroupAPDU`.
        """
        self._handlers.append(handler)

    async def open_group_socket(self, write_only=False) -> None:
        """
        Coroutine to request KNXD to open a Group Socket for sending and receiving group telegrams to/from any Group
        Address.

        This is a synchronous KNXD function, i.e. it will send a request packet to KNXD and await the receipt of a
        response packet from KNXD.
        Attention: This coroutine requires :meth:`run` to be running in a separate task of the **same** asyncio event
        loop!

        :param write_only: If True, KNXD is requested to open the Group Socket in write-only mode, i.e. no incoming
            group telegrams will be received.
        :raises RuntimeError: when KNXD responds with an error message or an unexpected response packet.
        """
        logger.info("Opening KNX group socket for sending to group addresses ...")
        async with self._lock:
            self._response_ready.clear()
            await self._send_eibd_packet(KNXDPacket(KNXDPacketTypes.EIB_OPEN_GROUPCON,
                                                    bytes([0, 0xff if write_only else 0, 0])))
            await self._response_ready.wait()  # TODO add timeout and Exception on timeout
            response = self._current_response
        assert(response is not None)
        if response.type is not KNXDPacketTypes.EIB_OPEN_GROUPCON:
            raise RuntimeError("Could not open KNX group socket. Response: {}".format(response))
        else:
            logger.info("Opening KNX group socket successful")

    async def group_write(self, addr: GroupAddress, write_type: KNXDAPDUType, encoded_data: EncodedData) -> None:
        """
        Send a Group Read/Response/Write telegram to the KNX bus via a KNXD Group Socket.

        This requires an open connection to KNXD and a KNXD Group Socket being opened on this connection. See
        :meth:`connect` and :meth:`open_group_socket`.

        This coroutine awaits the sending (including flushing the write buffer) of the packet to KNXD.

        :param addr: The KNX group address as :class:`GroupAddress`
        :param write_type: The telegram type (read/response/write) as :class:`KNXDAPDUType`
        :param encoded_data: The payload data, binary encoded for KNX transmission, as returned by :func:`encode_data`
            when called with the correct KNX Datapoint type for the relevant Group Address.
        """
        logger.debug("%s to KNX group address %s: %s", write_type.name, addr, encoded_data)
        await self._send_eibd_packet(KNXDPacket(KNXDPacketTypes.EIB_GROUP_PACKET,
                                                addr.encode() + KNXGroupAPDU(write_type, encoded_data).encode()))

    async def _send_eibd_packet(self, packet: KNXDPacket) -> None:
        """
        Send a packet to KNXD via its simple TCP/UNIX protocol.

        Requires an open connection to KNXD.
        This coroutine awaits the sending (including flushing the write buffer) of the packet to KNXD.

        :param packet: The packet to send, as a :class:`KNXDPacket`
        """
        # TODO check if _writer is existing
        logger.debug("Sending packet to KNXd: %s", packet)
        data = packet.encode()
        if len(data) < 2 or len(data) > 0xffff:
            raise ValueError('Invalid packet length: {}'.format(repr(data)))
        data = len(data).to_bytes(2, byteorder='big') + data
        self._writer.write(data)
        await self._writer.drain()


class KNXDPacketTypes(enum.Enum):
    # From BCUSDK 0.0.5 sources (https://web.archive.org/web/20150801154025/https://www.auto.tuwien.ac.at/~mkoegler/eib/bcusdk_0.0.5.tar.gz)
    # /eibd/include/eibtypes.h
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
