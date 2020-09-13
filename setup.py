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

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="knxdclient",
    version="0.2.0",
    author="Michael Thies",
    author_email="mail@mhthies.de",
    url="https://github.com/mhthies/knxdclient",
    description="A pure Python async client for KNXD's (EIBD's) native Layer 4 KNX protocol.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["knxdclient"],
    package_data={"knxdclient": ["py.typed"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
    ],
    python_requires='>=3.7',
)
