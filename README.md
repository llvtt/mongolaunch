# mongolaunch

`mongolaunch` is a tool for starting MongoDB clusters on AWS. This is a Work In Progress, so things may not always work as expected. I've been running this on a Mac, targeting Linux and Windows, and everything has gone smoothly so far. If you think there are critical features that are missing, or you've found a heinous, nasty bug, please make a pull request or ask for push access!

## Goals

1. Provide an easy way to set up MongoDB in a more realistic way than running everything on localhost.
2. Make setup easily repeatable and scriptable.
3. Provide a way to customize setup.

## TODO

1. Clean up EC2 instances on error.
2. Validate json config files before running with them.
3. Be able to re-use EC2 instances to avoid overhead of provisioning new ones.
4. Be able to start up MongoDB on already-existing machines not on AWS.

## Installation

Coming soon!

## Usage

`mongolaunch` spins up MongoDB clusters from json configuration files. Configuration files consist of a list of _instances_, and a list of _clusters_. Each instance has the following format:

    {
        "_id": <Give your instance a name, like "i_am_a_mongos". Used to
                specify membership in a replica set or as a shard>,
        "ami": <EC2 AMI to use>,

        "mongo": {
            "bin": <either "mongod" or "mongos">,
            "options": <flags to pass to "bin" above. DO NOT specify --port, --logpath, --dbpath, or --configdb>,
            "version": <any mongodb version, as a string: "2.4.9", "2.6.0-rc1", etc.>
        }
    }

Cluster documents describe replica sets or sharded clusters. Here's an example of a replica set:

    {
        "_id": <must give an _id. This can be used to specify this replica set as a shard>,

        "type": "replicaSet",
        "members": <array of the _ids from 'instances' described previously>,
        "name": <replica sets must have a name>
    }

Here's how to set up a sharded cluster:

    {
        "_id": "shcluster",

        "type": "shardedCluster",
        "members": <array of _ids from 'instances' or 'clusters' (to use replica set shards)>,
        "mongos": <_id of the instance hosting the mongos>
    }

The `examples` directory already contains a few ready-made configurations for reference. To see a complete example of a sharded cluster involving a replica set, check out `examples/sharded_replset.json`.

### Starting them up

You can start mongo instances with `mongolaunch`. You can see all available command-line options by doing

        mongolaunch --help

### Tearing Down

You can tear down every instance in the most recent launch with `mongoterm`. The invocation is dead-simple:

        mongoterm

The most basic usage need not specify any options.

### Gotchas

- `mongolaunch` makes certain assumptions about the existence of certain directories and port numbers. You'll have to modify the bootrap scripts (see "Cusomizing Your Instances") if you specify any of the following in the `options` of an instance:
    - `--port`
    - `--shardsvr`
    - `--logpath`
    - `--dbpath`
- You don't need to specify `--configdb` to mongos. `mongolaunch` will automatically launch exactly one config server for each mongos and provide the appropriate `--configdb` to each.

### Customizing Your Instances

`mongolaunch` bootstraps EC2 instances with MongoDB by providing one of the shell scripts in the `mongolaunch/shell` directory to the instance, which executes the script on first boot. `install-windows.ps1` is executed in the Windows PowerShell, and `install-linux.sh` is run in the Bourne shell. You can customize exactly how MongoDB is installed and run by editing these scripts.

## Limitations

- The 'options' field for each instance is pretty much passed literally to the mongo binary. This means that you need to keep in mind what operating system MongoDB will be running on. For example, you wouldn't want to specify --logpath /var/log/mongodb.log to a Windows machine.
- In general, there is little error checking going on right now. Be sure to double-check your configuration files before launching. If a mongod/mongos fails to launch for some reason, `mongolaunch` will keep waiting for it to become available, and you'll be waiting a long time...
- Config servers are created automatically for mongos processes. There is **always** exactly 1 config server, and it **always** runs on Linux (ami-a43909e1, to be exact). If you need to, you can adjust this in the `settings` module inside the `monglaunch` package.
- Mongolaunch doesn't currently re-use any instances; new ones are created each time. Obviously, there's a significant overhead to launching new instances, so be patient when launching clusters, which may take up to 3 or 4 minutes to complete. When Windows is involved as a target for deployment, it could take a lot longer...
- This tool does not handle upgrade/downgrade, failures, fires, alien invasions, etc. You'll have to wait for another tool for that. ;) This tool is mainly meant for spawning MongoDB clusters on AWS in an automatic fashion.

## Related Work

[`mlaunch`](https://github.com/rueckstiess/mtools/wiki/mlaunch), part of [`mtools`](https://github.com/rueckstiess/mtools) by , provides an easy way to start MongoDB clusters all on one machine.

[`m`](https://github.com/aheckmann/m) is a version manager for MongoDB.
