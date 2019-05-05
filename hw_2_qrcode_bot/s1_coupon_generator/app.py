import os
import random
import string
from typing import Callable

from hw_2_qrcode_bot.utils.rabbitmq_app import RabbitMQApp
from hw_2_qrcode_bot.config import c


class CouponGen(RabbitMQApp):
    """ Generates coupons strings """

    def __init__(self, coupon_gen: Callable):
        super().__init__()
        self.coupon_gen = coupon_gen

    def init_consumers(self):
        self.channel.basic_qos(
            prefetch_count=1
        )  # just to guarantee ack of all incoming tasks
        self.channel.basic_consume(
            queue=c.GENERATE_TASKS_QUEUE_NAME,
            on_message_callback=self.process_generate_task,
        )

    @staticmethod
    def validate_generate_task(data):
        if isinstance(data, bytes):
            data = data.decode()
        if not isinstance(data, str):
            raise AssertionError(f"str or bytes was expected, got {data!r}")

        try:
            amount_to_generate = int(data)
        except ValueError:
            raise AssertionError(
                f"Incorrect coupon generate task, expected digit, got {data!r}"
            )
        return amount_to_generate

    def process_generate_task(self, ch, method, _, body):
        self.logger.debug("Got task to generate some coupons %s", body)
        amount_to_generate = self.validate_generate_task(body)
        self.logger.debug("Will generate %s", amount_to_generate)
        for _ in range(amount_to_generate):
            self.generate_coupon_and_put_in_queue()

        self.logger.debug("Coupon generated, will ack task")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def check_buffer(self):
        """
        At start will check buffer of images
        and if it is less that conf value - will plan some work
        """
        self.logger.info("Checking buffer")
        final_queue_size = self.get_len_of_queue(c.UPLOADED_IMAGES_DATA_QUEUE_NAME)

        if final_queue_size < c.BUFFER_SIZE:
            delta = c.BUFFER_SIZE - final_queue_size
            self.logger.info("Need to generate %s more coupons for buffer", delta)
            for _ in range(delta):
                self.generate_coupon_and_put_in_queue()
        else:
            self.logger.info("Buffer is OK, %s", final_queue_size)

    def generate_coupon_and_put_in_queue(self):
        coupon = self.coupon_gen()
        if coupon:
            self.put_data_to_queue(c.COUPON_GENERATOR_QUEUE_NAME, coupon)


class UnlimitedCouponsGenerator:
    """ Just an implementation of coupons generator """

    def __init__(self, coupon_prefix: str):
        self.coupon_prefix = coupon_prefix

    def generate_coupon(self):
        coupon_postfix = random.choices(string.ascii_letters + string.digits, k=6)
        coupon_postfix = "".join(coupon_postfix)
        coupon = f"{self.coupon_prefix}_{coupon_postfix}"
        return coupon

    def __call__(self):
        return self.generate_coupon()


class LimitedCouponsGenerator(UnlimitedCouponsGenerator):
    """ Coupons generator with limited quantity """

    def __init__(self, coupon_prefix: str, limit=5, counter_file_path=None):
        super().__init__(coupon_prefix)

        self._coupons_left = limit

        if not counter_file_path:
            counter_file_path = f"{coupon_prefix}_limited_coupons_counter"
        self.counter_file_path = counter_file_path

        if os.path.exists(self.counter_file_path):
            with open(self.counter_file_path) as counter_file:
                # overloading left amount with stored
                self._coupons_left = int(counter_file.read())

    @property
    def coupons_left(self):
        return self._coupons_left

    @coupons_left.setter
    def coupons_left(self, new_value):
        self._coupons_left = new_value
        with open(self.counter_file_path, "w") as counter_file:
            counter_file.write(str(new_value))

    def __call__(self):
        if self.coupons_left <= 0:
            return None
        else:
            coupon = self.generate_coupon()
            self.coupons_left -= 1
            return coupon


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)-50s %(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S %z]",
    )
    logging.getLogger("pika").setLevel(logging.INFO)

    coupon_generator = UnlimitedCouponsGenerator("COOL_COUPON")
    app = CouponGen(coupon_generator)
    app.check_buffer()
    app.run()
