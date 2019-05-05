import re

import vk_api.longpoll
import vk_api.utils

from hw_2_qrcode_bot.config import c
from hw_2_qrcode_bot.utils.rabbitmq_app import RabbitMQApp


class VkBotApp:
    """ Responds on users messages with qr-promo-codes """

    greet_msg = "Oh, hello there, i think that you want some coupons"
    try_later_msg = "Sorry, there is no coupons left, try later :c"
    coupon_msg = "Here comes dat boi"
    some_error_msg = "Oh, something goes wrong. Please stand by"

    def __init__(self, rabbit: RabbitMQApp):
        self.logger = logging.getLogger(f"hw_2.{type(self).__name__}")

        self.rabbit = rabbit

        self.vk_session = vk_api.VkApi(token=c.VK_API_TOKEN)
        self.vk_api = self.vk_session.get_api()
        self.long_poll = vk_api.longpoll.VkLongPoll(self.vk_session)

    @staticmethod
    def validate_uploaded_image(uploaded_image_id):
        # todo: re.match to the <type><owner_id>_<media_id> template
        if isinstance(uploaded_image_id, bytes):
            uploaded_image_id = uploaded_image_id.decode()
        if not isinstance(uploaded_image_id, str):
            raise RuntimeError(
                f"Incorrect type of uploaded_image_id {type(uploaded_image_id)!r}, need str/bytes"
            )
        if not re.match(r"photo-?\d+_\d+", uploaded_image_id):
            raise RuntimeError(
                f"Incorrect attachment id {uploaded_image_id!r}, must be like photo<owner_id>_<media_id>"
            )
        return uploaded_image_id

    def run(self):
        try:
            self._run()
        except KeyboardInterrupt:
            pass

    def _run(self):
        for event in self.long_poll.listen():
            self.logger.debug("Got new event (%s)", event.type)
            if event.type != vk_api.longpoll.VkEventType.MESSAGE_NEW:
                continue
            if not (event.to_me and event.text):
                continue
            self.process_new_message(event)

    def process_new_message(self, event):
        """
        Main part of bot

        1. Greets user
        2. and after that
            - if there is no codes - says sorry
            or
            - if there is some codes - sends one of them to user
        """
        self.logger.debug("It is event to_me with text %s", event.text)
        # greet at first
        self.send_message_to_user(event.user_id, self.greet_msg)

        # lookup for uploaded coupons
        method, _, body = self.rabbit.get_data_from_queue(
            queue_name=c.UPLOADED_IMAGES_DATA_QUEUE_NAME
        )
        if not method:  # there is no coupons in queue
            self.send_message_to_user(event.user_id, self.try_later_msg)
            self.logger.debug("There is no coupons left :c, just said sorry to client")
        else:
            image_attach_id = self.validate_uploaded_image(body)
            self.send_message_to_user(
                event.user_id, self.coupon_msg, attachment=image_attach_id
            )
            self.logger.debug("Sent new shiny coupon, will ack the task")
            self.rabbit.channel.basic_ack(delivery_tag=method.delivery_tag)
            self.logger.debug("Will put task to generate new coupon")
            self.rabbit.put_data_to_queue(
                c.GENERATE_TASKS_QUEUE_NAME, "1"  # how much to generate
            )

    def send_message_to_user(self, user_id, msg, **kwargs):
        return self.vk_api.messages.send(
            user_id=user_id,
            random_id=vk_api.utils.get_random_id(),
            message=msg,
            **kwargs,
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
    app = VkBotApp(rabbitmq_app)
    app.run()
