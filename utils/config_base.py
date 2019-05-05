import json
import os


class ConfigValue:
    """
    Base class for config values.
    Will get its .name during subclassing from ConfigBase
    """

    def __init__(self, default_value):
        self.default_value = default_value
        self.name = None


class EnvStringValue(ConfigValue):
    """ String environ config value """

    def __get__(self, instance, owner):
        return os.environ.get(self.name, self.default_value)


class EnvIntValue(EnvStringValue):
    """ Int environ config value """

    def __get__(self, instance, owner):
        return int(super().__get__(instance, owner))


class ConfigBase:
    """
    To use it you must inherit from ConfigBase like:
    >>> class Config(ConfigBase):
    ...     SOME_INT_ENV_VAR = EnvIntValue(420)
    ...     SOME_STR_ENV_VAR = EnvStringValue('smoke weed')
    >>> Config.SOME_INT_ENV_VAR
    420
    >>> Config.SOME_STR_ENV_VAR
    'smoke weed'
    >>> import os
    >>> os.environ['SOME_INT_ENV_VAR'] = '14'
    >>> os.environ['SOME_STR_ENV_VAR'] = '88'
    >>> Config.SOME_INT_ENV_VAR
    14
    >>> Config.SOME_STR_ENV_VAR
    '88'
    """

    def __init_subclass__(cls, **kwargs):
        for k, v in cls.__dict__.items():
            if isinstance(v, ConfigValue):
                v.name = k
