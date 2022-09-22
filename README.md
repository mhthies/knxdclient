# KNXDclient

A pure Python async client for KNXD's (EIBD's) native Layer 4 KNX protocol.

EIBD is a *NIX daemon for routing EIB/KNX telegrams through various interfaces and programmatically accessing the EIB/KNX bus.
It's part of the no-longer maintained [BCUSDK](https://www.auto.tuwien.ac.at/~mkoegler/index.php/bcusdk).
However, there's a fork called [KNXD](https://github.com/knxd/knxd), which is still actively maintained. 

This package reimplements small parts of the EIBD client (see [BCUSDK documentation](https://web.archive.org/web/20160418110523/https://www.auto.tuwien.ac.at/~mkoegler/eib/sdkdoc-0.0.5.pdf), section 7.7)
in pure Python 3, based on asynchronous coroutines (asyncio).
Currently, it allows to open a Group Socket for sending and receiving KNX telegrams to/for any group address via KNXD.
Additionally, this package includes helper methods `encode_value()` and `decode_value()` to convert the send/received data from/to native Python types according to a known KNX Datapoint Type (DPT).


## Usage example

```python
import asyncio
from knxdclient import encoding, client


def handler(packet: client.ReceivedGroupAPDU) -> None:
    print("Received group telegram: {}".format(packet))

async def main() -> None:
    connection = client.KNXDConnection()
    connection.set_group_apdu_handler(handler)
    await connection.connect()
    # Connection was successful. Start receive loop:
    run_task = asyncio.create_task(connection.run())
    # Now that the receive loop is running, we can open the KNXd Group Socket:
    await connection.open_group_socket()

    # Startup completed. Now our `handler()` will receive incoming telegrams and we can send some:
    await connection.group_write(client.GroupAddress(1,3,2),
                                 client.KNXDAPDUType.WRITE,
                                 encoding.encode_value(True, encoding.KNXDPT.BOOLEAN))
    
    await asyncio.sleep(5)
    # Let's stop the connection and wait for graceful termination of the receive loop:
    await connection.stop()
    await run_task


asyncio.run_until_complete(main())
```

## License

This package is published under the terms of the Apache License 2.0.
