"""Defines Error sub-classes specific to the mongolaunch package"""


class MongoLaunchError (Exception):
    """Base class for all Exceptions raised by mongolaunch"""
    pass


class MLConfigurationError (MongoLaunchError):
    """Raised when there is a misconfiguration of mongolaunch or AWS"""
    pass


class MLConnectionError (MongoLaunchError):
    """Raised for network errors. It may be possible to fix the situation
    just by trying again.

    """
    pass
