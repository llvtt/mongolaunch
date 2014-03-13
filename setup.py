# Copyright 2013-2014 MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

classifiers = """\
Development Status :: 4 - Beta
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Programming Language :: Python
Topic :: Database
Topic :: Software Development :: Libraries :: Python Modules
"""

from setuptools import setup

setup(name='mongolaunch',
      version="0.1",
      author="Luke Lovett",
      author_email='luke.lovett@mongodb.com',
      description=('mongolaunch is a set of tools for starting '
                   'MongoDB clusters on AWS.'),
      keywords='mongodb aws ec2 replicaset sharding',
      url='https://github.com/lovett89/mongolaunch',
      license="http://www.apache.org/licenses/LICENSE-2.0.html",
      platforms=["any"],
      classifiers=filter(None, classifiers.split("\n")),
      install_requires=['pymongo', 'boto>=2.27.0', 'argparse'],
      packages=["mongolaunch"],
      package_data={
          'mongolaunch': ['shell/*'],
      },
      entry_points={
          'console_scripts': [
              'mongolaunch = mongolaunch.launch:main',
              'mongoterm = mongolaunch.terminate:main'
          ],
      }
)
