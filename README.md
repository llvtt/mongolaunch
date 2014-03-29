# mongolaunch

`mongolaunch` is a tool for starting MongoDB clusters on your own machines or on AWS. This is a Work In Progress, so things may not always work as expected. I've been running this on a Mac, targeting Linux and Windows, and everything has gone smoothly so far. If you think there are critical features that are missing, or you've found a heinous, nasty bug, please make a pull request or ask for push access!

## Goals

1. Provide an easy way to set up MongoDB in a more realistic way than running everything on localhost.
2. Make setup easily repeatable and scriptable.
3. Provide a way to customize setup through shell scripts and JSON config files.

## TODO

1. Clean up EC2 instances on error.
2. Validate json config files before running with them.
3. Be able to re-use EC2 instances to avoid overhead of provisioning new ones.
4. Be able to use more than 1 mongos in a sharded cluster.

## Installation

1. Clone this repository:

        git clone https://github.com/lovett89/mongolaunch.git

2. Install with `setup.py`:

        python setup.py install

## Usage

`mongolaunch` spins up MongoDB clusters from json configuration files. Each config file has a few basic sections:

    {
        "configuration_title": <give your configuration a title>,

        "instances": [ <descriptions of EC2 instances go here> ],

        "hosts": [ <put descriptions of machines you already own here> ],

        "mongo": [ <descriptions of individual mongo processes (i.e. mongod/s)> ],

        "replicas": [ <descriptions of replica sets> ],

        "clusters": [ <descriptions of sharded clusters> ]
    }

Some of these sections are optional. For example, you don't need to provide both a `instances` and `hosts` section, if you only plan on using EC2 or only your own machines. Likewise, you may not need the `replicas` or `clusters` sections, either, if you're only creating single mongod instances.

Now let's see an example document that might go in the `instances` section:

        "instances": [
                {
                        "_id": "shard0_inst",
                        "ami": "ami-12345678",
                        "type": "t1.micro"
                }
        ]

There are just a few fields you need to specify:
- `_id` gives the instance a name so you can refer to it in other places within the config file (more on this later)
- `ami` gives the Amazon Machine Image to use. Note that these are only available within certain regions.
- `type` is the instance type

Instead of provisioning new EC2 instances, you can also elect to run clusters on hardware you already have (or EC2 instances you already have). Here's what that looks like in the `hosts` section:

        "hosts": [
                {
                        "_id": "SuperBeefMachine",
                        "address": 1.2.3.4,
                        "windows": true,
                        "user": "mongolaunch",
                        "password": "zbatbynhapu"
                }
        ]

Let's go over what these fields mean:
- `_id` gives the host a name so you can refer to it in other places within the config file
- `address` is an IP address or external hostname that can be used to connect to the box
- `windows` tells us whether this machine is running windows
- `user` is the user to do the setup as. *This user must have sudo privileges without password*.
- `password` is the password for the user above.

At the heart of the setup, we want to start some `mongod` or `mongos` processes. That's what the `mongo` section of the config file is for:

        "mongo": [
                {
                        "_id": "s0_rs0",
                        "bin": "mongod",
                        "options": "--replSet rs0",
                        "dbpath": "/opt/mongodb/data",
                        "logpath": "/var/log/mongo0.log",
                        "version": "2.6.0-rc2",
                        "host": "SuperBeefMachine"
                },
                {
                        "_id": "mongos",
                        "bin": "mongos",
                        "logpath": "/var/log/mongos.log",
                        "version": "2.6.0-rc2",
                        "single_configdb": false,
                        "configdb_version": "2.6.0-rc2",
                        "instance": "shard0_inst"
                }
        ]

Here's what the fields are all about:
- `_id` is a name so you can refer to this mongo process elsewhere in the config file
- `bin` is either "mongod" or "mongos"
- `options` are additional options to pass to mongod or mongos
- `dbpath` is where to put the data files. Defaults to /data/db
- `logpath` is where to put the log file. Defaults to /var/log/mongod.log
- `version` is the version of MongoDB to use
- `host` or `instance` gives the `_id` of a host or instance document, respectively, where this mongo process is to run

There are a few more options to provide when `bin` is `mongos`:
- `configdb_version` is the version of MongoDB to use for the config servers
- `single_configdb` is whether to use 1 instead of all 3 config servers. Default is `true`.

Replica set configurations are provided in the `replicas` section:

        "replicas": [
                {
                        "_id": "rs0",
                        "members": ["s0_rs0", "s0_rs1"],
                        "name": "shard0"
                }
        ]

- `_id` provides a name so that this replica set can be referred to elsewhere in the configuration
- `members` is a list of `_id`s of `mongo` sub-documents within the configuration
- `name` is the name of the replica set (i.e., it has to match `--replSet`)

Sharded cluster configurations go in the `clusters` section:

        "clusters": [
                {
                        "_id": "chocolateCaramelCluster",
                        "shards": ["shard0", "standalone"],
                        "mongos": "mongos"
                }
        ]

- `_id` provides a name so that this cluster can be referred to elsewhere in the configuration
- `shards` is a list of `_id`s of either singleton `mongo` sub-documents or `replicas` sub-documents. These may be combined.
- `mongos` is the `_id` of the `mongos` sub-document to use.

The `examples` directory already contains a few ready-made configurations for reference. To see a complete example of a sharded cluster involving a replica set, check out `examples/repl_sharded_windows.json`. You may also want to check out `examples/repl_ownmachines.json` for an example of running a replica set on your own hardware.

### Starting them up

You can start mongo instances with `mongolaunch`. You can see all available command-line options by doing

        mongolaunch --help

### Tearing Down

Coming soon!

### Gotchas

Some parameters to mongod/s are filled in automatically by mongolaunch and should not be specified by the user. Please don't specify:

- `--logpath`
- `--dbpath`
- `--configdb`

in the `options` section of a `mongo` sub-document. You may specify the first two options in the `logpath` and `dbpath` fields, respectively.

### Customizing Your Instances

`mongolaunch` bootstraps EC2 instances with MongoDB by providing one of the shell scripts in the `mongolaunch/shell` directory to the instance, which executes the script on first boot. `install-mongodb-windows.ps1` is executed in the Windows PowerShell, and `install-mongodb-linux.sh` is run in the Bourne shell. You can customize exactly how MongoDB is installed and run by editing these scripts.

## Limitations

- The 'options' field for each instance is pretty much passed literally to the mongo binary. This means that you need to keep in mind what operating system MongoDB will be running on. For example, you wouldn't want to specify --logpath /var/log/mongodb.log to a Windows machine.
- In general, there is little error checking going on right now. Be sure to double-check your configuration files before launching. If a mongod/mongos fails to launch for some reason, `mongolaunch` will keep waiting for it to become available, and you'll be waiting a long time...
- Config servers are created automatically for mongos processes, and thus allow minimal configuration.
- Mongolaunch doesn't currently re-use any instances (although you may create a new confgiuration that references these as `hosts`); new ones are created each time. Obviously, there's a significant overhead to launching new instances, so be patient when launching clusters, which may take up to 3 or 4 minutes to complete. When Windows is involved as a target for deployment, it could take a lot longer...
- This tool does not handle upgrade/downgrade, failures, fires, alien invasions, etc. You'll have to wait for another tool for that. ;) This tool is mainly meant for spawning MongoDB clusters in an automatic fashion.

## Related Work

[`mlaunch`](https://github.com/rueckstiess/mtools/wiki/mlaunch), part of [`mtools`](https://github.com/rueckstiess/mtools) by @rueckstiess, provides an easy way to start MongoDB clusters all on one machine.

[`m`](https://github.com/aheckmann/m) by @aheckmann is a version manager for MongoDB.

[`chef-mongodb`](https://github.com/edelight/chef-mongodb) contains Chef recipes for MongoDB.

[`elastic-mongodb`](https://github.com/diegows/elastic-mongodb) contains Salt recipes for MongoDB.

[`MongoDB on OpsWorks`](http://blogs.aws.amazon.com/application-management/post/Tx1RB65XDMNVLUA/Deploying-MongoDB-with-OpsWorks) uses Chef to install and configure software on Amazon EC2 instances
