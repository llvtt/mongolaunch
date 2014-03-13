#!/usr/bin/env python

import argparse
import datetime
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
    CONFIG_BOOTSTRAP
)
from mongolaunch.shellscript import (build_context,
                                     script_from_config)
import mongolaunch.models

# Configurables defined as globals up here for now
CIDR_ADDRESS = "0.0.0.0/0"


def main():
    parser = argparse.ArgumentParser(
        description="Launch EC2 MongoDB configurations")
    parser.add_argument(type=str, dest="key_name", help="key pair name")
    parser.add_argument("--config", type=str, dest="config_filename",
                        default="config.json", help="JSON configuration file")
    parser.add_argument("--expiration-days", type=int, dest="days",
                        default=7, help="Number of days to set "
                        "in expire-on tag")
    parser.add_argument("--security-group", type=str, dest="sec_group", help=
                        "security group name", default="mongolaunch")
    parser.add_argument("--region", type=str, dest="region", help="AWS region",
                        default="us-west-1")
    parser.add_argument("--instance-type", type=str, dest="instance_type",
                        default="t1.micro", help="EC2 instance type. Defaults "
                        "to t1.micro")
    parser.add_argument("--secret-key", type=str, dest="secret", help=
                        "AWS secret key. This can be omitted if AWS_SECRET_KEY "
                        "is defined in your environment", default=None)
    parser.add_argument("--access-key", type=str, dest="access", help=
                        "AWS access key. This can be omitted if AWS_ACCESS_KEY "
                        "is defined in your environment", default=None)

    args = parser.parse_args()
    region = args.region
    days = args.days
    sec_group = args.sec_group
    key_name = args.key_name
    secret = args.secret or os.environ.get("AWS_SECRET_KEY")
    access = args.access or os.environ.get("AWS_ACCESS_KEY")
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

    if not key_name in (kp.name for kp in conn.get_all_key_pairs()):
        print("keypair %s does not yet exist. Creating it..." % key_name)
        keypair = conn.create_key_pair(key_name)
        keypair.save(ML_PATH)

    #
    # Get or create security group
    #

    if not sec_group in (g.name for g in conn.get_all_security_groups()):
        print("security group %s does not yet exist. Creating it..."
              % sec_group)
        rules = [
            ('tcp', 22, 22, CIDR_ADDRESS),            # SSH
            ('tcp', 3389, 3389, CIDR_ADDRESS),        # RDP
            ('tcp', 27017, 27017, CIDR_ADDRESS),      # MongoDB
            ('tcp', 27018, 27018, CIDR_ADDRESS),      # MongoDB
            ('tcp', 27019, 27019, CIDR_ADDRESS)       # MongoDB
        ]
        g = conn.create_security_group(sec_group, "mongolaunch security group")
        for rule in rules:
            g.authorize(*rule)

    #
    # Launch EC2 instances
    #

    def _launch_instance(**kwargs):
        reservation = conn.run_instances(**kwargs)
        inst = reservation.instances[0]
        inst.add_tag('expire-on',
                     (datetime.datetime.now() +
                      datetime.timedelta(days=days)).strftime("%Y-%m-%d"))
        inst.add_tag('source', 'mongolaunch')
        return inst

    instances = []
    for to_start in config['instances']:
        ami = to_start['ami']
        try:

            is_mongos = (to_start['mongo']['bin'] == 'mongos')
            # Start additional instance for config server if using mongos
            if is_mongos:
                print("starting config server instance...")
                inst = _launch_instance(
                    image_id=CONFIG_AMI,
                    key_name=key_name,
                    security_groups=[sec_group],
                    instance_type=instance_type,
                    user_data=CONFIG_BOOTSTRAP
                )
                configdb = mongolaunch.models.Mongod(
                    None, inst.id, conn, port=27019)
                instances.append(configdb)
                # We have to wait for the config server to get a DNS name
                # so we can plug it into the mongos bootstrap script
                configdb.wait_for_running()

                # configdb needs to have mongod already available, or else
                # mongos won't start
                configdb.wait_for_available()

            # Start main mongod/mongos instance
            print("starting instance %s..." % to_start['_id'])

            # Build bootstrap script based on AMI and config file
            img = conn.get_image(ami)
            if is_mongos:
                to_start['configdb'] = configdb.hostname()
            context = build_context(config, to_start)
            script_contents = script_from_config(
                context,
                windows=(img.platform == 'windows')
            )

            # Use install script as user data
            inst = _launch_instance(
                image_id=ami,
                key_name=key_name,
                security_groups=[sec_group],
                instance_type=instance_type,
                user_data=script_contents
            )
            if is_mongos:
                instances.append(mongolaunch.models.Mongos(
                    to_start,
                    inst.id,
                    configdb,
                    conn
                ))
            else:
                # Check if we're a shard
                instances.append(mongolaunch.models.Mongod(
                    to_start,
                    inst.id,
                    conn
                ))

        except BotoServerError:
            print("A problem ocurred while starting your instance.")
            # TODO: cleanup instances that did manage to start
            raise

    #
    # Save instances launched to .mongolaunchrc
    #

    with open(os.path.join(ML_PATH, ".mongolaunchrc"), "w") as fd:
        pickle.dump([inst.id for inst in instances], fd)

    #
    # Wait for instances to be 'running'
    #

    for inst in instances:
        inst.wait_for_running()

    #
    # Configure clusters
    #

    clusters = config.get("clusters") or []
    replicas = (c for c in clusters if c['type'].lower() == 'replicaset')
    sharded = (c for c in clusters if c['type'].lower() == 'shardedcluster')
    for rs in replicas:
        # EC2 Instances that will be in the replica set
        rs_instances = [i for i in instances if i.config_id() in rs['members']]

        # DNS names for those instances
        hosts = [inst.hostname() for inst in rs_instances]

        # try to connect to the hosts
        for inst in rs_instances:
            inst.wait_for_available()

        # initialize the replica set
        print("Initializing replica set...")
        # connect to 1 host
        client = pymongo.MongoClient(rs_instances[0].hostname())
        member_list = [{"_id": i, "host": h} for i, h in enumerate(hosts)]
        client.admin.command("replSetInitiate", {
            "_id": rs["name"],
            "members": member_list
        })
        client.close()

    for sh in sharded:
        # members is list of standalone ids/replica set ids
        members = sh['members']
        # Mapping of json config _ids to instances
        config_ids = dict((inst.config_id(), inst) for inst in instances)
        # Shards that are standalones (i.e., single EC2 Instances)
        cluster_instances = []
        # Shards that are replica sets (and consist of multiple Instances)
        cluster_repls = []
        for m in members:
            if m in config_ids:
                cluster_instances.append(config_ids[m])
            else:
                cluster_repls.append(m)

        hosts = [inst.hostname() for inst in cluster_instances]

        # Find host of the mongos
        mongos_id = sh["mongos"]
        mongos = config_ids[mongos_id]

        print("Initializing sharded cluster...")
        print("Waiting for mongos")
        mongos.wait_for_available()
        client = pymongo.MongoClient(mongos.hostname())
        print("adding shards")

        # Add standalone mongods as shards
        for inst in cluster_instances:
            # TODO: allow additional configurations here
            # http://docs.mongodb.org/manual/reference/command/addShard/#dbcmd.addShard
            # Shards may not be available yet
            inst.wait_for_available()
            print("adding shard %s..." % inst.hostname())
            client.admin.command({"addShard": inst.hostname()})

        # Add replica sets as shards
        for rsid in cluster_repls:
            for c in clusters:
                # Is this the config for the rs we're looking for?
                rs_members = []
                rs_instances = []
                if c.get("_id") == rsid:
                    # Get the members
                    rs_members = c.get("members")
                # Find the individual configs for these rs members
                rs_instances = [
                    i for i in instances if i.config_id() in rs_members
                ]
                if len(rs_instances) > 0:
                    shard_string = "%s/%s" % (
                        c.get("name"),
                        ",".join(i.hostname() for i in rs_instances)
                    )
                    print("adding shard %s..." % shard_string)
                    client.admin.command({"addShard": shard_string})
        client.close()

    #
    # Make sure all instances are available
    #

    for inst in instances:
        inst.wait_for_available()

    print("")
    print("Done. Setup took %f seconds" % (time.time() - start_time))
    print("Started the following instances:")
    for inst in instances:
        print("%s\t%s" % (inst.config_id() or "<configdb>", inst.hostname()))

if __name__ == '__main__':
    main()
