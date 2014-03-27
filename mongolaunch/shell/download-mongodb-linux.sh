#!/bin/sh
# download mongodb on linux
mkdir -p /opt/mongolaunch
curl http://fastdl.mongodb.org/linux/mongodb-linux-x86_64-{{ version }}.tgz | tar xzv -C /opt/mongolaunch
