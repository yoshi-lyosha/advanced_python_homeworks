from hw_2_qrcode_bot.config import c
from hw_2_qrcode_bot.utils.rabbitmq_app import RabbitMQApp
from hw_2_qrcode_bot.s2_qrcode_img_generator.generator import QRCodeImgGenerator


class QRCodeImagesGenApp(RabbitMQApp):
    """ Generates images with qr-codes """

    task_coupon_field = "coupon"

    def __init__(self):
        super().__init__()
        self.qr_code_img_gen = QRCodeImgGenerator(
            c.PATH_TO_TEMPLATE, c.IMG_HEIGHT, c.IMG_WIDTH
        )

    def init_consumers(self):
        self.channel.basic_qos(
            prefetch_count=1
        )  # just to guarantee ack of all incoming tasks
        self.channel.basic_consume(
            queue=c.COUPON_GENERATOR_QUEUE_NAME,
            on_message_callback=self.process_qr_code_generation_task_cb,
        )

    @staticmethod
    def validate_coupon(data):
        if isinstance(data, bytes):
            data = data.decode()
        if not isinstance(data, str):
            raise AssertionError(f"str or bytes was expected, got {data!r}")
        return data

    def process_qr_code_generation_task_cb(self, ch, method, _, body):
        self.logger.debug("Generating coupon for task %s", body)
        coupon_data = self.validate_coupon(body)
        image_binary = self.qr_code_img_gen.generate_qr_code_img(coupon_data)
        self.put_data_to_queue(c.RENDERED_IMAGES_QUEUE_NAME, image_binary)
        self.logger.debug("Coupon image generated, will ack task")
        ch.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)-50s %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S %z]",
    )
    logging.getLogger("pika").setLevel(logging.INFO)

    app = QRCodeImagesGenApp()
    app.run()
