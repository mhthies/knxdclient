import asyncio
import os
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
import time
from contextlib import suppress

import knxdclient
from ._helper import async_test


@unittest.skipIf(shutil.which("knxd") is None, "knxd is not available in PATH")
@unittest.skipIf(shutil.which("knxtool") is None, "knxtool is not available in PATH")
class MQTTClientTest(unittest.TestCase):
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

    # TODO test exception on connection failure
    # TODO test iterate_group_telegrams()
    # TODO test reconnect
