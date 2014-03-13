import time

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from mongolaunch import errors, settings


class Instance(object):

    def __init__(self, config, id, conn):
        '''Wrap a boto.Instance in a mongolaunch.models.Instance.

        id      the id of the boto instance
        config  this instance's portion of the json config file
        conn    the EC2Connection

        '''
        self._config = config
        self.id = id
        self._conn = conn

    def boto_instance(self):
        '''Return the boto.Instance object associated with this
        mongolaunch.models.Instance

        '''
        for reservation in self._conn.get_all_instances():
            for inst in reservation.instances:
                if inst.id == self.id:
                    return inst
        return None

    def hostname(self):
        '''Returns the external DNS name of this Instance.
        This could be the empty string while the Instance is still starting.

        '''
        return self.boto_instance().dns_name

    def config_id(self):
        return self._config.get("_id") if self._config else None

    def running(self):
        '''Returns True when this Instance is running and has a DNS name'''
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
            str(self.boto_instance().id),
            'running' if self.running() else 'not running',
            self.hostname()
        )

    def __repr__(self):
        return str(self)


class Mongod(Instance):

    def __init__(self, config, my_id, conn, port=27017):
        self.port = port
        Instance.__init__(self, config, my_id, conn)

    def available(self):
        '''Returns True when this mongo process can accept connections'''
        if not self.running():
            return False
        try:
            MongoClient(self.hostname(), port=self.port)
            return True
        except ConnectionFailure:
            return False

    def wait_for_available(self):
        counter = 0
        while not self.available():
            print("waiting for MongoDB to become "
                  "available on instance %s... %d" % (
                      str(self), counter
                  ))
            counter += 1
            time.sleep(1)
        if counter > settings.MAX_MONGO_TRIES:
            raise errors.MLConnectionError(
                "MongoDB  did not become available in a reasonable "
                "amount of time. Abandoning setup.")
        return True


class Mongos(Mongod):

    def __init__(self, config, my_id, configdb, conn):
        self.configdb = configdb
        Mongod.__init__(self, config, my_id, conn)
