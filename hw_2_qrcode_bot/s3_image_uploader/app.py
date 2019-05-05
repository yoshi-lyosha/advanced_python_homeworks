import imghdr
import io
import time

import vk_api

from hw_2_qrcode_bot.config import c
from hw_2_qrcode_bot.utils.rabbitmq_app import RabbitMQApp


class ImageUploaderApp:
    """ Uploads images to vk with rate limiting """

    def __init__(self, rabbit: RabbitMQApp):
        self.logger = logging.getLogger(f"hw_2.{type(self).__name__}")

        self.rabbit = rabbit

        self.vk_session = vk_api.VkApi(token=c.VK_API_TOKEN)
        self.vk_upload_api = vk_api.VkUpload(self.vk_session)

        self.last_upload_time = time.time()

    @staticmethod
    def validate_rendered_image(image):
        if not isinstance(image, bytes):
            raise RuntimeError(f"Incorrect image data type {type(image)!r}")
        img_type = imghdr.what(None, h=image)
        if img_type not in {"jpeg", "png", "gif"}:
            raise RuntimeError(f"Incorrect image type {img_type!r}")
        return image

    def run(self):
        try:
            self._run()
        except KeyboardInterrupt:
            pass

    def _run(self):
        while True:
            method, _, body = self.rabbit.get_data_from_queue(
                c.RENDERED_IMAGES_QUEUE_NAME
            )
            if not method:
                time.sleep(1)
                continue
            image = self.validate_rendered_image(body)
            self.logger.debug("Got new image to upload")

            # rate limit feature
            time_after_last_upload = time.time() - self.last_upload_time
            time_to_sleep = max(0, c.DELAY_BETWEEN_UPLOADS - time_after_last_upload)
            self.logger.debug(
                "(vk api rate limit) Will sleep for %s sec", time_to_sleep
            )
            time.sleep(time_to_sleep)

            # uploading to vk and passing to the next service through the queue
            uploaded_images_data = self.upload_messages_photos([image])
            self.put_images_ids_to_uploaded_images_queue(uploaded_images_data)
            self.logger.debug("Upload completed, will ack task")
            self.rabbit.channel.basic_ack(
                delivery_tag=method.delivery_tag
            )  # todo: encapsulate that

    def upload_messages_photos(self, images) -> list:
        # returns list of dicts with info about uploaded imgs
        # [{'id': 456239017,
        #   'album_id': -64,
        #   'owner_id': -181965583,
        #   'user_id': 100,
        #   'sizes': [...],
        #   'text': '',
        #   'date': 1557026988,
        #   'access_key': '905e55fa597fe85d61'},
        #  {...}, ...]
        images = [io.BytesIO(image) for image in images]
        upload_response = self.vk_upload_api.photo_messages(images)
        self.last_upload_time = time.time()
        return upload_response

    def put_images_ids_to_uploaded_images_queue(self, uploaded_photos: list):
        # we need to create smth like photo100172_166443618
        # <type><owner_id>_<media_id> where <type> is 'photo'
        for photo_info in uploaded_photos:
            owner_id = photo_info.get("owner_id")
            media_id = photo_info.get("id")
            attachment_id = f"photo{owner_id}_{media_id}"
            self.rabbit.put_data_to_queue(
                queue_name=c.UPLOADED_IMAGES_DATA_QUEUE_NAME, data=attachment_id
            )


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)-50s %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S %z]",
    )
    logging.getLogger("pika").setLevel(logging.INFO)

    rabbitmq_app = RabbitMQApp()
    app = ImageUploaderApp(rabbitmq_app)
    app.run()
