import os

from utils.config_base import ConfigBase, EnvStringValue, EnvIntValue


class Config(ConfigBase):
    CRAWLER_MAX_WORKERS = EnvIntValue(default_value=3)
    CRAWLER_MAX_RPS_PER_DOMAIN = EnvIntValue(default_value=3)
    CRAWLER_MAX_RETRIES = EnvIntValue(default_value=3)
    CRAWLER_MAX_PARSING_WORKERS = EnvIntValue(default_value=os.cpu_count())

    CRAWLER_ELASTICSEARCH_HOST = EnvStringValue(default_value="localhost")
    CRAWLER_ELASTICSEARCH_PORT = EnvIntValue(default_value=9200)

    CRAWLER_ELASTICSEARCH_INDEX = EnvStringValue(default_value="crawler_index_v1")
    CRAWLER_ELASTICSEARCH_DOC_TYPE = EnvStringValue(default_value="sites_crawling_v1")


config = Config()
