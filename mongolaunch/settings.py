'''global settings that affect mongolaunch (not EC2 instances)'''


import os

# Base path for mongolaunch resources (e.g., scripts, keys, etc.)
ML_PATH = os.path.abspath(os.path.dirname(__file__))
# Number of tries to connect while waiting for MongoDB to become available
MAX_MONGO_TRIES = 240
# AMI to use for the config server (Amazon linux)
CONFIG_AMI = "ami-a43909e1"
# Bootstrap script for the config server. Obviously dependent on CONFIG_AMI
CONFIG_BOOTSTRAP = '''
#!/bin/sh

cd /home/ec2-user
curl http://fastdl.mongodb.org/linux/mongodb-linux-x86_64-latest.tgz | tar xzv
mkdir -p /data/db
mongodb-linux-x86_64-*/bin/mongod --configsvr \
        --logpath /var/log/mongodb-config.log \
        --dbpath /data/db --fork

'''
