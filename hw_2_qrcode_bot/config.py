import os

from utils.config_base import ConfigBase, EnvStringValue, EnvIntValue


class Config(ConfigBase):
    # rabbitmq
    RABBIT_HOST = EnvStringValue(default_value="localhost")
    RABBIT_PORT = EnvIntValue(default_value=5672)

    # queues names
    GENERATE_TASKS_QUEUE_NAME = EnvStringValue(default_value="generate_tasks_queue")
    COUPON_GENERATOR_QUEUE_NAME = EnvStringValue(default_value="coupon_generator_queue")
    RENDERED_IMAGES_QUEUE_NAME = EnvStringValue(default_value="rendered_images_queue")
    UPLOADED_IMAGES_DATA_QUEUE_NAME = EnvStringValue(
        default_value="uploaded_images_data_queue"
    )

    @property
    def queues(self):
        return [
            self.GENERATE_TASKS_QUEUE_NAME,
            self.COUPON_GENERATOR_QUEUE_NAME,
            self.RENDERED_IMAGES_QUEUE_NAME,
            self.UPLOADED_IMAGES_DATA_QUEUE_NAME,
        ]

    # coupons generator conf
    BUFFER_SIZE = EnvIntValue(default_value=3)

    # img generator conf
    html_template_file_name = "qr_code_img_template.html"
    PATH_TO_TEMPLATE = EnvStringValue(
        os.path.join(os.path.dirname(__file__), html_template_file_name)
    )
    IMG_HEIGHT = EnvIntValue(default_value=600)
    IMG_WIDTH = EnvIntValue(default_value=600)

    # img uploader conf
    DELAY_BETWEEN_UPLOADS = EnvIntValue(default_value=1)  # sec

    # vk api key
    VK_API_TOKEN = EnvStringValue(default_value=None)


c = Config()
