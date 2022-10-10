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

from .packets import GroupAddress, KNXDAPDUType, ReceivedGroupAPDU
from .client import KNXDConnection
from .encoding import encode_value, decode_value, KNXDPT, KNXTime, EncodedData
