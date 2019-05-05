import logging

import pika

from hw_2_qrcode_bot.config import c


class RabbitMQApp:
    """ Just a class to reduce boilerplate code """

    rabbit_params = pika.ConnectionParameters(host=c.RABBIT_HOST, port=c.RABBIT_PORT)

    def __init__(self):
        self.logger = logging.getLogger(f"hw_2.{type(self).__name__}")

        self.logger.info("Initializing app")
        self.connection = pika.BlockingConnection(self.rabbit_params)
        self.channel = self.connection.channel()
        self.init_queues()
        self.init_consumers()

    def init_consumers(self):
        # you can define this method in child class
        pass

    def init_queues(self):
        self.logger.info("Creating queues %s", c.queues)
        for queue_name in c.queues:  # will declare all queues
            self.channel.queue_declare(queue=queue_name, durable=True)

    def put_data_to_queue(self, queue_name: str, data, exchange="", **kwargs):
        return self.channel.basic_publish(
            exchange=exchange,
            routing_key=queue_name,
            body=data,
            properties=pika.BasicProperties(delivery_mode=2),  # make message persistent
            **kwargs,
        )

    def get_data_from_queue(self, queue_name: str, **kwargs):
        return self.channel.basic_get(queue=queue_name, **kwargs)

    def get_len_of_queue(self, queue_name: str):
        q = self.channel.queue_declare(
            queue=queue_name,
            durable=True,
            passive=True,  # if there is no such queue - will be exception
        )
        return q.method.message_count

    def run(self):
        self.logger.info("Starting app...")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.logger.info("Stopping\n\n")
