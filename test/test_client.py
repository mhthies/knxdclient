import asyncio
import os
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
import time
from contextlib import suppress
import sys

import knxdclient
from ._helper import async_test


@unittest.skipIf(shutil.which("knxd") is None, "knxd is not available in PATH")
@unittest.skipIf(shutil.which("knxtool") is None, "knxtool is not available in PATH")
class KNXDClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.knxd_socket = tempfile.mktemp(suffix=".sock", prefix="knxdclient-test-knxd-")
        self.knxd_process = subprocess.Popen(["knxd", f"--listen-local={self.knxd_socket}", "-e", "0.5.1", "-E",
                                              "0.5.2:10", "dummy"])
        time.sleep(0.25)

    def tearDown(self) -> None:
        self.knxd_process.terminate()
        self.knxd_process.wait()

    @async_test
    async def test_receive(self) -> None:
        handler = unittest.mock.Mock()

        # Setup connection and receive loop task
        connection = knxdclient.KNXDConnection()
        connection.set_group_apdu_handler(handler)
        await connection.connect(sock=self.knxd_socket)
        run_task = asyncio.create_task(connection.run())

        try:
            # Open Group socket
            await connection.open_group_socket()

            proc = await asyncio.create_subprocess_exec('knxtool', 'on', f'local://{self.knxd_socket}', '1/2/3',
                                                        env=dict(PATH=os.environ['PATH']))
            await proc.communicate()
            if proc.returncode:
                raise RuntimeError(f"knxtool failed with exit code {proc.returncode}")
            proc = await asyncio.create_subprocess_exec('knxtool', 'groupwrite', f'local://{self.knxd_socket}',
                                                        '17/5/127', 'de', 'ad', 'c0', 'ff', 'ee',
                                                        env=dict(PATH=os.environ['PATH']))
            await proc.communicate()
            if proc.returncode:
                raise RuntimeError(f"knxtool failed with exit code {proc.returncode}")

            await asyncio.sleep(0.05)
            self.assertEqual(2, handler.call_count)
            value1 = handler.call_args_list[0][0][0]
            self.assertIsInstance(value1, knxdclient.ReceivedGroupAPDU)
            self.assertEqual(knxdclient.GroupAddress(1, 2, 3), value1.dst)
            self.assertEqual(0, value1.src.area)
            self.assertEqual(5, value1.src.line)
            self.assertEqual(knxdclient.KNXGroupAPDU(knxdclient.KNXDAPDUType.WRITE, 0x1),
                             value1.payload)
            value2 = handler.call_args_list[1][0][0]
            self.assertIsInstance(value2, knxdclient.ReceivedGroupAPDU)
            self.assertEqual(knxdclient.GroupAddress(17, 5, 127), value2.dst)
            self.assertEqual(0, value2.src.area)
            self.assertEqual(5, value2.src.line)
            self.assertEqual(knxdclient.KNXGroupAPDU(knxdclient.KNXDAPDUType.WRITE,
                                                     bytes([0xde, 0xad, 0xc0, 0xff, 0xee])),
                             value2.payload)

        finally:
            await connection.stop()
            with suppress(asyncio.CancelledError):
                await run_task

    @async_test
    async def test_send(self) -> None:
        # Setup connection and receive loop task
        connection = knxdclient.KNXDConnection()
        await connection.connect(sock=self.knxd_socket)
        run_task = asyncio.create_task(connection.run())
        try:
            proc = await asyncio.create_subprocess_exec(
                'knxtool',
                'vbusmonitor1',
                f'local://{self.knxd_socket}',
                stdout=asyncio.subprocess.PIPE,
                env=dict(PATH=os.environ['PATH'])
            )
            await asyncio.sleep(0.1)

            # Open Group socket
            await connection.open_group_socket()

            # Send value
            await connection.group_write(knxdclient.GroupAddress(4, 5, 6), knxdclient.KNXDAPDUType.RESPONSE, 0x2a)
            await connection.group_write(knxdclient.GroupAddress(24, 3, 55), knxdclient.KNXDAPDUType.WRITE,
                                         bytes([0xc0, 0x1d, 0xc0, 0xff, 0xee]))

            # Stop busmonitor and gather output
            await asyncio.sleep(0.1)
            proc.terminate()
            stdout, _stderr = await proc.communicate()
            if proc.returncode != -15:
                raise RuntimeError(f"knxtool vbusmonitor1 failed with unexpected exit code {proc.returncode}")

            # Analyze output
            lines = stdout.strip().split(b'\n')
            # self.assertEqual(2, len(lines))  # exactly two line of Busmonitor output (=2 telegrams) are expected
            self.assertRegex(lines[0], rb"L_Data low from 0\.5\.\d+ to 4/5/6 hops: \d+ (T_Data_Group|T_DATA_XXX_REQ) "
                                       rb"A_GroupValue_Response \(small\) 2A")
            self.assertRegex(lines[1], rb"L_Data low from 0\.5\.\d+ to 24/3/55 hops: \d+ (T_Data_Group|T_DATA_XXX_REQ) "
                                       rb"A_GroupValue_Write C0 1D C0 FF EE")

        finally:
            await connection.stop()
            with suppress(asyncio.CancelledError):
                await run_task

    @async_test
    async def test_connection_failure(self) -> None:
        # Setup connection and receive loop task
        connection = knxdclient.KNXDConnection()
        await connection.connect(sock=self.knxd_socket)
        run_task = asyncio.create_task(connection.run())

        # Open Group socket
        await connection.open_group_socket()

        # Now, let's stop KNXD
        self.knxd_process.terminate()
        self.knxd_process.wait()  # This is thread-blocking, which should not be a problem here

        # This should raise an exception in the run_task (receive loop)
        with self.assertRaises(ConnectionAbortedError):
            await run_task

        # Let's restart KNXD
        self.knxd_process = subprocess.Popen(["knxd", f"--listen-local={self.knxd_socket}", "-e", "0.5.1", "-E",
                                              "0.5.2:10", "dummy"])
        time.sleep(0.25)  # This is thread-blocking, which should not be a problem here

        # Now, we should be able to reconnect the client and open the group socket
        await connection.connect(sock=self.knxd_socket)
        run_task = asyncio.create_task(connection.run())
        try:
            await connection.open_group_socket()
        finally:
            await connection.stop()
            with suppress(asyncio.CancelledError):
                await run_task

    @async_test
    async def test_receive_iterator(self) -> None:
        # Setup connection and receive loop task
        connection = knxdclient.KNXDConnection()
        await connection.connect(sock=self.knxd_socket)
        run_task = asyncio.create_task(connection.run())

        try:
            handler = unittest.mock.Mock()

            async def iter_packets():
                async for packet in connection.iterate_group_telegrams():
                    handler(packet)
            iterator_task = asyncio.create_task(iter_packets())
            # let task start
            await asyncio.sleep(0.05)

            try:
                # A second iterator should not be allowed
                with self.assertRaises(RuntimeError):
                    _telegram_iterator2 = await connection.iterate_group_telegrams().__aiter__().__anext__()

                # Open Group socket
                await connection.open_group_socket()
                await asyncio.sleep(0.05)

                proc = await asyncio.create_subprocess_exec('knxtool', 'on', f'local://{self.knxd_socket}', '1/2/3',
                                                            env=dict(PATH=os.environ['PATH']))
                await proc.communicate()
                if proc.returncode:
                    raise RuntimeError(f"knxtool failed with exit code {proc.returncode}")
                handler.assert_called_once()
                value1 = handler.call_args[0][0]

                proc = await asyncio.create_subprocess_exec('knxtool', 'groupwrite', f'local://{self.knxd_socket}',
                                                            '17/5/127', 'de', 'ad', 'c0', 'ff', 'ee',
                                                            env=dict(PATH=os.environ['PATH']))
                await proc.communicate()
                if proc.returncode:
                    raise RuntimeError(f"knxtool failed with exit code {proc.returncode}")

                self.assertEqual(2, handler.call_count)
                value2 = handler.call_args[0][0]

            except Exception:
                iterator_task.cancel()
                await iterator_task
                raise

            # Trigger a CancelledError in the iterator to ensure correct handling
            iterator_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await iterator_task
            # This should allow us to create a new iterator
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(connection.iterate_group_telegrams().__aiter__().__anext__(), timeout=0.05)

            # Check received values
            self.assertIsInstance(value1, knxdclient.ReceivedGroupAPDU)
            self.assertEqual(knxdclient.GroupAddress(1, 2, 3), value1.dst)
            self.assertEqual(0, value1.src.area)
            self.assertEqual(5, value1.src.line)
            self.assertEqual(knxdclient.KNXGroupAPDU(knxdclient.KNXDAPDUType.WRITE, 0x1),
                             value1.payload)
            self.assertIsInstance(value2, knxdclient.ReceivedGroupAPDU)
            self.assertEqual(knxdclient.GroupAddress(17, 5, 127), value2.dst)
            self.assertEqual(0, value2.src.area)
            self.assertEqual(5, value2.src.line)
            self.assertEqual(knxdclient.KNXGroupAPDU(knxdclient.KNXDAPDUType.WRITE,
                                                     bytes([0xde, 0xad, 0xc0, 0xff, 0xee])),
                             value2.payload)

        finally:
            await connection.stop()
            with suppress(asyncio.CancelledError):
                await run_task


@unittest.skipIf(shutil.which("knxd") is None, "knxd is not available in PATH")
class KNXDClientTCPTest(unittest.TestCase):
    def setUp(self) -> None:
        self.knxd_process = subprocess.Popen(["knxd", "--listen-tcp=16720", "-e", "0.5.1", "-E",
                                              "0.5.2:10", "dummy"])
        time.sleep(0.25)

    def tearDown(self) -> None:
        self.knxd_process.terminate()
        self.knxd_process.wait()

    @async_test
    async def test_connect_tcp(self) -> None:
        # Setup connection and receive loop task
        connection = knxdclient.KNXDConnection()
        await connection.connect(host="127.0.0.1", port=16720)
        run_task = asyncio.create_task(connection.run())

        try:
            # Open Group socket
            await connection.open_group_socket()

        finally:
            await connection.stop()
            with suppress(asyncio.CancelledError):
                await run_task


class KNXDClientTimeoutTest(unittest.TestCase):
    @async_test
    async def test_timeout(self) -> None:
        # Create TCP server
        async def client_handler(reader, writer):
            # We never respond anything, so the client should run into timeout
            await reader.read(-1)
            writer.close()
        server = await asyncio.start_server(client_handler, host="127.0.0.1", port=16720)

        try:
            # Setup connection and receive loop task
            connection = knxdclient.KNXDConnection(timeout=1)
            await connection.connect(host="127.0.0.1", port=16720)
            run_task = asyncio.create_task(connection.run())

            with self.assertRaises(ConnectionAbortedError):
                await connection.open_group_socket()

            with self.assertRaises(TimeoutError if sys.version_info >= (3, 11) else asyncio.TimeoutError):
                await run_task
            await connection.stop()
        finally:
            server.close()
            await server.wait_closed()
