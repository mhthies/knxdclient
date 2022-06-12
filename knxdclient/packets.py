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

import enum
from typing import NamedTuple, Union


EncodedData = Union[int, bytes]


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
        data_hex = self.data.hex()
        return "{}({}, data={})".format(self.__class__.__name__, self.type.name,
                                        ' '.join(data_hex[i:i+2] for i in range(0, len(data_hex), 2)))


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
        if isinstance(self.value, bytes):
            value_hex = self.value.hex()
            value_repr = ' '.join(value_hex[i:i + 2] for i in range(0, len(value_hex), 2))
        else:
            value_repr = "{:02X}".format(self.value)
        return "{}({}, value={})".format(self.__class__.__name__, self.type.name, value_repr)


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
