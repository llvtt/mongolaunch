#!/usr/bin/env python

import argparse
import itertools
import json
import os
import os.path
import pickle
import time

import boto.ec2 as ec2
from boto.exception import BotoServerError
import pymongo
import pymongo.errors

from mongolaunch import errors
from mongolaunch.settings import (
    ML_PATH,
    CONFIG_AMI,
    MAX_MONGO_TRIES
)
import mongolaunch.models

# Configurables defined as globals up here for now
CIDR_ADDRESS = "0.0.0.0/0"


def main():
    parser = argparse.ArgumentParser(
        description="Launch EC2 MongoDB configurations")
    parser.add_argument("--key-name", type=str, dest="key_name", default=None,
                        help="key pair name")
    parser.add_argument("--config", type=str, dest="config_filename",
                        default="config.json", help="JSON configuration file")
    parser.add_argument("--start-port", type=int, dest="port", default=27017,
                        help="starting port for mongo processes")
    parser.add_argument("--security-group", type=str, dest="sec_group", help=
                        "security group name", default="mongolaunch")
    parser.add_argument("--region", type=str, dest="region", help="AWS region",
                        default="us-west-1")
    parser.add_argument("-z", "--availability-zone", dest='zone',
                        action='store', default=None, help="availability zone")
    parser.add_argument("--instance-type", type=str, dest="instance_type",
                        default="t1.micro", help="EC2 instance type. Defaults "
                        "to t1.micro")
    parser.add_argument("--secret-key", type=str, dest="secret", help=
                        "AWS secret key. This can be omitted if AWS_SECRET_KEY "
                        "is defined in your environment", default=None)
    parser.add_argument("-t", "--tag", type=str, dest="tags", action="append",
                        help="Add a tag with --tag key=value or --tag tagname",
                        default=[])
    parser.add_argument("--access-key", type=str, dest="access", help=
                        "AWS access key. This can be omitted if AWS_ACCESS_KEY "
                        "is defined in your environment", default=None)

    args = parser.parse_args()
    region = args.region
    sec_group = args.sec_group
    key_name = args.key_name
    secret = args.secret or os.environ.get("AWS_SECRET_KEY")
    access = args.access or os.environ.get("AWS_ACCESS_KEY")
    start_port = args.port
    if start_port < 0 or start_port > 65535:
        raise errors.MLConfigurationError(
            "--start-port out of range: %d" % start_port)
    tags = args.tags
    zone = args.zone
    instance_type = args.instance_type
    config_filename = args.config_filename

    # Record how long all setup takes
    start_time = time.time()

    # Open config file
    try:
        with open(config_filename, "r") as fd:
            try:
                config = json.load(fd)
            except ValueError:
                print("Invalid configuration file: %s" % config_filename)
                raise
    except IOError:
        print("Could not open configuration file %s. Is it readable?"
              % config_filename)
        exit(1)

    if not secret or not access:
        raise errors.MLConfigurationError(
            "You must have both AWS_ACCESS_KEY and AWS_SECRET_KEY "
            "defined in your shell environment")

    conn = ec2.connect_to_region(region,
                                 aws_access_key_id=access,
                                 aws_secret_access_key=secret)
    if conn is None:
        raise errors.MLConnectionError(
            "Could not connect to region %s!" % region)

    #
    # Get or create KeyPair
    #

    if key_name is not None:
        if not key_name in (kp.name for kp in conn.get_all_key_pairs()):
            print("keypair %s does not yet exist. Creating it..." % key_name)
            keypair = conn.create_key_pair(key_name)
            keypair.save(ML_PATH)

    #
    # Get or create security group
    #

    if sec_group is not None:
        if not sec_group in (g.name for g in conn.get_all_security_groups()):
            print("security group %s does not yet exist. Creating it..."
                  % sec_group)
            rules = [
                ('tcp', 22, 22, CIDR_ADDRESS),          # SSH
                ('tcp', 3389, 3389, CIDR_ADDRESS),      # RDP
                ('tcp', 10000, 50000, CIDR_ADDRESS),    # Some ports for MongoDB
            ]
            g = conn.create_security_group(sec_group,
                                           "mongolaunch security group")
            for rule in rules:
                g.authorize(*rule)

    #
    # Create Host models
    #

    # mapping of host _id to Host instance
    hosts = {}

    # EC2
    for to_start in config.get('instances', []):
        # TODO: isolate this kind of logic, and do all config file
        # validation at once
        if key_name is None:
            raise errors.MLConfigurationError(
                "Config file %s has EC2 instances, but no key was provided. "
                "Abandoning setup." % config_filename)
        model = mongolaunch.models.Instance(
            id=to_start['_id'],
            conn=conn,
            ami=to_start['ami'],
            keypair=key_name,
            group=sec_group,
            instance_type=to_start.get("type", instance_type)
        )
        hosts[to_start['_id']] = model

    # own machines
    for to_start in config.get('hosts', []):
        model = mongolaunch.models.OwnMachine(
            id=to_start['_id'],
            address=to_start['address'],
            user=to_start['user'],
            passwd=to_start['password'],
            windows=to_start.get("windows", False)
        )
        hosts[to_start['_id']] = model

    #
    # Create models of Mongo processes
    #

    # next available port #
    # this is somewhat dependent on security group rules
    available_port = itertools.count(start_port)

    mongoes = {}
    for mongo in config['mongo']:
        configdbs = []
        if mongo['bin'].lower() == 'mongos':
            # Create config server(s)
            for i in range(1 if mongo['single_configdb'] else 3):
                config_port = next(available_port)
                configdb = mongolaunch.models.Mongod(
                    port=config_port,
                    config={
                        "version": mongo['configdb_version'],
                        "options": "--configsvr ",
                        "bin": "mongod",
                        # TODO: don't hard-code --logpath and --dbpath
                        # on config servers. Using config_port as part
                        # of file name, to prevent 3 config servers on
                        # same host from clobbering each other
                        "dbpath": "/data/configdb-%d" % config_port,
                        "logpath": "/var/log/configdb-%d.log" % config_port,
                        "_id": "config%d" % config_port
                    })
                configdbs.append(configdb)

            model = mongolaunch.models.Mongos(
                config=mongo,
                configdbs=configdbs,
                port=mongo.get("port", next(available_port))
            )
            # N.B. 'configdbs' are not in this mapping, since there is
            # no config id
            mongoes[mongo['_id']] = model
        elif mongo['bin'].lower() == 'mongod':
            model = mongolaunch.models.Mongod(
                config=mongo,
                port=mongo.get("port", next(available_port))
            )
            mongoes[mongo['_id']] = model

        # Attach mongo process model to appropriate Host model
        host_id = mongo.get("instance") or mongo.get("host")
        host = hosts.get(host_id)
        if host is None:
            raise errors.MLConfigurationError(
                "no host %s found for %s!" % (host_id, mongo['_id']))
        host.add_mongo(model)

    #
    # Create models of replicas
    #

    replicas = {}
    for rs in config.get("replicas", []):
        member_ids = rs['members']
        model = mongolaunch.models.ReplicaSet(
            members=[mongoes[k] for k in member_ids],
            config=rs
        )
        replicas[rs['_id']] = model

    #
    # Create models of sharded clusters
    #

    sharded = {}
    for sh in config.get("clusters", []):
        shard_ids = sh['shards']
        mongos = mongoes.get(sh['mongos'])
        shards = [mongoes.get(k, replicas.get(k)) for k in shard_ids]
        model = mongolaunch.models.ShardedCluster(mongos=mongos, shards=shards)

        # Determine if the configdbs should run on the same Host as the Mongos,
        # or different. If any of the shards are not on the same Host as the
        # Mongos, then so must the config servers
        #
        #TODO: should same_host just check the .host property?
        def same_host(mongos, shard):
            host = lambda m: m.config.get("host", m.config.get("instance"))
            if hasattr(shard, 'members'):
                # ReplicaSet
                return all((host(m) == host(mongos)) for m in shard.members)
            # Standalone
            return host(mongos) == host(shard)

        # Assign Hosts to config server Mongods
        for i, configdb in enumerate(mongos.configdbs):
            if all(same_host(mongos, shard) for shard in shards):
                # Config servers must live on Mongos Host
                print("Putting configs on same host as mongoS!")
                mongos.host.add_mongo(configdb)
            else:
                print("Putting configs on separate host from mongoS!")
                # Config servers must live on other EC2 Instances
                new_instance = mongolaunch.models.Instance(
                    id="config%d_inst" % i,
                    conn=conn,
                    ami=CONFIG_AMI,
                    keypair=key_name,
                    group=sec_group,
                    instance_type=instance_type
                )
                new_instance.add_mongo(configdb)

        sharded[sh['_id']] = model

    #
    # Configure replica sets
    #

    for rsid, rs in replicas.items():
        print("Configuring replica set %s..." % rsid)
        rs.start()
        # Need to wait for replica set to come up
        member = rs.members[0]
        client = pymongo.MongoClient(member.host.hostname(), port=member.port)
        is_master = client.admin.command("isMaster")
        # Wait for primary to become available
        counter = 0
        while is_master.get("primary") is None and counter < MAX_MONGO_TRIES:
            print("Waiting for a primary to be elected for %s... %d" % (
                rsid, counter))
            counter += 1
            time.sleep(1)
            is_master = client.admin.command("isMaster")
        if is_master.get("primary") is None:
            raise errors.MLConnectionError("Replica set %s could not elect a "
                                           "primary in a reasonable amount of "
                                           "time. Abandoning setup.")
        client.close()

    #
    # Configure sharded clusters
    #

    for shclid, shcl in sharded.items():
        print("Configuring sharded cluster %s..." % shclid)
        shcl.start()
        # Don't need to wait for this to come up, but perhaps should
        # for consistency?

    #
    # Initialize standalone instances
    #

    for mongoid, mongo in mongoes.items():
        if not mongo.available():
            print("Initializing %s" % mongoid)
            mongo.start()

    #
    # Print out results
    #

    print("")
    print("Done. Setup took %f seconds" % (time.time() - start_time))
    print("Started the following mongo processes:")
    for mongoid, mongo in mongoes.items():
        print("%s\t%s:%d" % (mongoid, mongo.host.hostname(), mongo.port))
        if isinstance(mongo, mongolaunch.models.Mongos):
            for cdb in mongo.configdbs:
                print("%s\t%s:%d" % (cdb.host.id,
                                     cdb.host.hostname(),
                                     cdb.port))


if __name__ == '__main__':
    main()
