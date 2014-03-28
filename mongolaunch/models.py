import datetime
import getpass
import os
import socket
import time

from fabric.api import env, run
from fabric.tasks import execute
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from mongolaunch import errors, settings
from mongolaunch.shellscript import get_script


# Raise an Exception on connection failures,
# instead of printing stuff everywhere and exiting
env.skip_bad_hosts = True


class Host(object):
    '''Base class representing anything a Mongod or Mongos is capable of
    running on. This includes EC2 instances and physical machines.

    '''

    def __init__(self, id):
        self.id = id
        # This is the plural of 'mongo'
        self.mongoes = []

    def add_mongo(self, mongo):
        '''Add a Mongod or Mongos to be run on this Host'''
        mongo.set_host(self)    # FIXME: reference cycle
        self.mongoes.append(mongo)

    def initialize(self):
        '''Initializes this host:

        1. Download relevant versions of MongoDB
        2. Unarchive binaries
        3. Mount volumes
        4. Start mongo processes
        '''
        raise NotImplementedError

    def reboot(self):
        '''Reboots the host'''
        raise NotImplementedError

    def start(self):
        '''Starts MongoDB:

        1. Mount volumes
        2. Start mongo processes
        '''
        raise NotImplementedError

    def hostname(self):
        raise NotImplementedError

    def running(self):
        raise NotImplementedError

    def wait_for_running(self):
        raise NotImplementedError


class OwnMachine(Host):
    '''Class for machines not in EC2'''

    def __init__(self, id, hostname, passwd):
        self._hostname = hostname
        self._passwd = passwd
        Host.__init__(self, id)

    def initialize(self):
        # do nothing
        pass

    def hostname(self):
        return self._hostname

    def running(self):
        def try_connect():
            run("touch .hello")
        try:
            execute(try_connect, hosts=[self.hostname()])
            return True
        except:
            return False

    def wait_for_running(self):
        counter = 0
        while not self.running():
            print(
                "waiting for machine %s to be running... %d" % (
                    str(self), counter
                ))
            counter += 1
            time.sleep(1)
        if counter > settings.MAX_MONGO_TRIES:
            raise errors.MLConnectionError(
                "machine did not come online in a reasonable "
                "amount of time. Abandoning setup.")
        return True

    def __str__(self):
        return "<OwnMachine %s %s>" % (str(self.id), self.hostname())

    def __repr__(self):
        return str(self)


class Instance(Host):

    def __init__(self, id, conn, ami, keypair, group, instance_type):
        '''Wrap a boto.Instance in a mongolaunch.models.Instance.

        id              the id given in the JSON config file
        conn            the EC2Connection

        '''
        self._conn = conn
        self._ami = ami
        self._is_windows = self._conn.get_image(self._ami).platform == 'windows'
        self._keypair = keypair
        self._group = group
        self._initialized = False
        self._type = instance_type
        self._instance_id = None
        Host.__init__(self, id)

    def _get_bootstrap_script(self):
        '''Helper method that provides the bootstrap script for the Instance'''
        script = []

        ############ TODO: Clean this up
        # If mongoS + any other part of the sharded cluster is on this instance,
        # they all should use "localhost" as their hostname.
        #
        #TODO: Something similar probably needs to happen for replica sets?
        mongoD = []
        mongoS = []
        for mongo in self.mongoes:
            if isinstance(mongo, Mongos):
                mongoS.append(mongo)
            elif isinstance(mongo, Mongod):
                mongoD.append(mongo)

        for m in mongoS:
            use_localhost = False
            for cdb in m.configdbs:
                if cdb.host == m.host:
                    use_localhost = True
                    break
            if use_localhost:
                # Adjust --configdb on Mongos
                m.config['configdb'] = ",".join("localhost:%d" % cdb.port
                                                for cdb in m.configdbs)

        # Scripts for mongod first, then mongos
        for mongo in mongoD + mongoS:
            bootstrap = get_script("install-mongodb",
                                   mongo.config,
                                   windows=self._is_windows)
            script.append(bootstrap)

        if self._is_windows:
            script_text = ("<powershell>\r\n%s\r\n</powershell>"
                           % "\r\n".join(script))
        else:
            script_text = "\n".join(script)
        # DEBUG
        print(script_text)
        return script_text

    def initialize(self):
        if not self._initialized:
            reservation = self._conn.run_instances(
                image_id=self._ami,
                key_name=self._keypair,
                security_groups=[self._group],
                instance_type=self._type,
                user_data=self._get_bootstrap_script()
            )
            inst = reservation.instances[0]
            inst.add_tag('expire-on',
                         (datetime.datetime.now() +
                          datetime.timedelta(days=7)).strftime("%Y-%m-%d"))
            inst.add_tag('owner', '%s@%s' % (getpass.getuser(),
                                             socket.gethostname()))
            inst.add_tag('source', 'mongolaunch')
            self._instance_id = inst.id
            self._initialized = True
            return inst

    def boto_instance(self):
        '''Return the boto.Instance object associated with this
        mongolaunch.models.Instance

        '''
        if self._initialized:
            # boto doesn't update Instances in-place, so need to request new one
            # each time
            for reservation in self._conn.get_all_instances():
                for inst in reservation.instances:
                    if inst.id == self._instance_id:
                        return inst
        return None

    def hostname(self):
        '''Returns the external DNS name of this Instance.
        This could be the empty string while the Instance is still starting.

        '''
        if self._initialized:
            return self.boto_instance().dns_name
        return None

    def running(self):
        '''Returns True when this Instance is running and has a DNS name'''
        if not self._initialized:
            return None
        return self.boto_instance().state == 'running' and bool(self.hostname())

    def wait_for_running(self):
        counter = 0
        while not self.running():
            print(
                "waiting for instance %s to be running... %d" % (
                    str(self), counter
                ))
            counter += 1
            time.sleep(1)
        if counter > settings.MAX_MONGO_TRIES:
            raise errors.MLConnectionError(
                "instance did not come online in a reasonable "
                "amount of time. Abandoning setup.")
        return True

    def __str__(self):
        return '<Instance %s (%s) %s>' % (
            self._instance_id,
            str(self.id),
            self.hostname()
        )

    def __repr__(self):
        return str(self)


class Mongo(object):
    '''Base class for all models'''

    def start(self):
        '''Start a Mongo process'''
        raise NotImplementedError

    def stop(self):
        '''Stop a Mongo process'''
        raise NotImplementedError

    def __str__(self):
        return "<Mongo on %s>" % str(self.host)


class MongoProcess(Mongo):
    '''Base class for Mongo process models (i.e. Mongod and Mongos)'''

    def __init__(self):
        self.host = None

    def set_host(self, host):
        self.host = host


class Mongod(MongoProcess):

    def __init__(self, config=None, port=27017):
        self.port = port
        self.config = config
        # Adjust port in command-line options, if not present
        options = config.get("options", "")
        if not "--port" in options:
            options += " --port %d" % self.port
            config["options"] = options
        # Adjust logpath, dbpath
        if 'dbpath' not in self.config:
            self.config['dbpath'] = '/data/db'
        if 'logpath' not in self.config:
            self.config['logpath'] = '/var/log/mongod.log'
        Mongo.__init__(self)

    def available(self):
        '''Returns True when this mongo process can accept connections'''
        if not self.host.running():
            return False
        try:
            MongoClient(self.host.hostname(), port=self.port)
            return True
        except ConnectionFailure:
            return False

    def wait_for_available(self):
        counter = 0
        while not self.available():
            print("waiting for MongoDB to become "
                  "available on host %s:%d... %d" % (
                      str(self.host), self.port, counter
                  ))
            counter += 1
            time.sleep(1)
        if counter > settings.MAX_MONGO_TRIES:
            raise errors.MLConnectionError(
                "MongoDB did not become available in a reasonable "
                "amount of time. Abandoning setup.")
        return True

    def start(self):
        self.host.initialize()
        self.wait_for_available()


class Mongos(Mongod):

    def __init__(self, config, configdbs, port=27017):
        self.configdbs = configdbs
        Mongod.__init__(self, config, port=port)

    def available(self):
        return (all(conf.available() for conf in self.configdbs) and
                Mongod.available(self))

    def start(self):
        for configdb in self.configdbs:
            print("STARTING CONFIGDB ON PORT %d" % configdb.port)
            print(configdb.config)
            configdb.start()
        # Get --configdb string
        config_string = ",".join("%s:%d" % (c.host.hostname(),
                                            c.port) for c in self.configdbs)
        print("config_string: %s" % config_string)
        self.config['configdb'] = config_string
        Mongod.start(self)

    def __str__(self):
        return "<Mongos on %s with configdbs: %s>" % (
            str(self.host),
            ",".join(str(configdb) for configdb in self.configdbs)
        )


class Cluster(Mongo):
    '''Base class for MongoDB cluster models'''

    def __init__(self):
        self._initialized = False

    def available(self):
        return self._initialized

    def wait_for_available(self):
        if not self.available():
            return self.start()
        return True


class ReplicaSet(Cluster):

    def __init__(self, members, config):
        self.members = members
        self.config = config
        self.name = self.config['name']
        self._initialized = False

    def start(self):
        if not self._initialized:
            for memb in self.members:
                memb.start()

            # Use "localhost" as hostname if all members are on the same host
            use_localhost = False
            if all((m.host == memb.host) for m in self.members):
                use_localhost = True

            def host(m):
                if use_localhost:
                    return "localhost"
                else:
                    return m.host.hostname()
            client = MongoClient(memb.host.hostname(), port=memb.port)
            hosts = ["%s:%d" % (host(memb),
                                memb.port) for memb in self.members]
            member_list = [{"_id": i, "host": h} for i, h in enumerate(hosts)]
            client.admin.command("replSetInitiate", {
                "_id": self.name,
                "members": member_list
            })
            client.close()
            self._initialized = True
        return self._initialized

    def __str__(self):
        return "<ReplicaSet %s: %s>" % (
            self.name,
            ",".join(str(m) for m in self.members)
        )

    def __repr__(self):
        return str(self)


class ShardedCluster(Cluster):

    def __init__(self, mongos, shards):
        self.mongos = mongos
        self.shards = shards
        self._initialized = False

    def start(self):
        if not self._initialized:
            print("STARTING MONGOS!!!!")
            self.mongos.start()
            print("STARTING SHARDS!!!!")
            for sh in self.shards:
                sh.start()
            client = MongoClient(self.mongos.host.hostname(),
                                 port=self.mongos.port)
            for sh in self.shards:
                # Initialize shard
                sh.start()

                # Determine standalone v replica set
                def hostname(mongo):
                    if mongo.host == self.mongos.host:
                        return "localhost"
                    return mongo.host.hostname()

                if isinstance(sh, ReplicaSet):
                    sh_str = "%s/%s" % (
                        sh.name,
                        ",".join("%s:%d" % (hostname(m), m.port)
                                 for m in sh.members)
                    )
                elif isinstance(sh, Mongod):
                    sh_str = "%s:%d" % (hostname(sh), sh.port)
                client.admin.command({"addShard": sh_str})
            self._initialized = True
        return self._initialized

    def __str__(self):
        return "<ShardedCluster %s>" % (
            ",".join(str(sh) for sh in self.shards))

    def __repr__(self):
        return str(self)
