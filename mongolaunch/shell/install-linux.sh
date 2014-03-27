mkdir -p {{ dbpath }}
mkdir -p $(dirname {{ logpath }})
echo "installing with options {{ options }}"
if [ "{{ bin }}" = "mongos" ]; then
    /opt/mongolaunch/mongodb-linux-x86_64-{{ version }}/bin/{{ bin }} --logpath {{ logpath }} --configdb "{{ configdb }}" {{ options }}  --fork
else
    /opt/mongolaunch/mongodb-linux-x86_64-{{ version }}/bin/{{ bin }} --dbpath {{ dbpath }} --logpath {{ logpath }} {{ options }} --fork
fi
