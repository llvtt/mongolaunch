#!/bin/sh
#
# install-linux.sh
# Installs MongoDB on linux
#
# This script will run as root at the instance's first boot

cd /home/ec2-user
curl http://fastdl.mongodb.org/linux/mongodb-linux-x86_64-{{ version }}.tgz | tar xzv
mkdir -p /data/db
if [ "{{ bin }}" = "mongos" ]; then
    mongodb-linux-x86_64-{{ version }}/bin/{{ bin }} --configdb {{ configdb }} {{ options }} --logpath /var/log/mongos.log --fork
else
    mongodb-linux-x86_64-{{ version }}/bin/{{ bin }} {{ options }} --logpath /var/log/mongod.log --fork
fi
