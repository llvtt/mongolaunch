import argparse
import os
from os.path import join
import pickle

import boto.ec2 as ec2

from mongolaunch.settings import ML_PATH


def main():
    parser = argparse.ArgumentParser(description="terminate EC2 instances")
    parser.add_argument("--region", type=str, dest="region", help="AWS region",
                        default="us-west-1")
    parser.add_argument("--secret-key", type=str, dest="secret", help=
                        "AWS secret key. This can be omitted if AWS_SECRET_KEY "
                        "is defined in your environment", default=None)
    parser.add_argument("--access-key", type=str, dest="access", help=
                        "AWS access key. This can be omitted if AWS_ACCESS_KEY "
                        "is defined in your environment", default=None)

    args = parser.parse_args()
    region = args.region
    secret = args.secret or os.environ.get("AWS_SECRET_KEY")
    access = args.access or os.environ.get("AWS_ACCESS_KEY")

    instances = None
    try:
        with open(join(ML_PATH, ".mongolaunchrc"), "rb") as fd:
            instances = pickle.load(fd)
    except IOError:
        print("Could not find .mongolaunchrc in %s! "
              "Perhaps you didn't `launch` anything? Exiting..." % ML_PATH)
        exit(1)

    conn = ec2.connect_to_region(region,
                                 aws_access_key_id=access,
                                 aws_secret_access_key=secret)
    print("terminating instances: %s" % ",".join(instances))
    conn.terminate_instances(instances)

if __name__ == '__main__':
    main()
