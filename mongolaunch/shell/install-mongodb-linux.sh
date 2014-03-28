#!/bin/sh
# download mongodb on linux
mkdir -p /opt/mongolaunch
if [ ! -d /opt/mongolaunch/mongodb-linux-x86_64-{{ version }} ]; then
    curl http://fastdl.mongodb.org/linux/mongodb-linux-x86_64-{{ version }}.tgz | tar xzv -C /opt/mongolaunch
fi
mkdir -p {{ dbpath }}
mkdir -p $(dirname {{ logpath }})
echo "installing with options {{ options }}"
if [ "{{ bin }}" = "mongos" ]; then
    /opt/mongolaunch/mongodb-linux-x86_64-{{ version }}/bin/{{ bin }} --logpath {{ logpath }} --configdb "{{ configdb }}" {{ options }}  --fork
else
    /opt/mongolaunch/mongodb-linux-x86_64-{{ version }}/bin/{{ bin }} --dbpath {{ dbpath }} --logpath {{ logpath }} {{ options }} --fork
fi
