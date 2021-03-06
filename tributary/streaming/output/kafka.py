import json as JSON
from aiokafka import AIOKafkaProducer
from .output import _OUTPUT_GRAPHVIZSHAPE
from ..node import Node


def Kafka(node, servers='', topic='', json=False, wrap=False, **producer_kwargs):
    '''Connect to kafka server and send data

    Args:
        node (Node): input tributary
        servers (list): kafka bootstrap servers
        topic (str): kafka topic to connect to
        json (bool): load input data as json
        wrap (bool): wrap result in a list
        interval (int): kafka poll interval
    '''

    async def _send(data, topic=topic, json=json, wrap=wrap):
        if ret._producer is None:
            ret._producer = AIOKafkaProducer(
                bootstrap_servers=servers,
                **producer_kwargs)

            # Get cluster layout and initial topic/partition leadership information
            await ret._producer.start()

        if wrap:
            data = [data]

        if json:
            data = JSON.dumps(data)

        # Produce message
        await ret._producer.send_and_wait(topic, data.encode('utf-8'))
        return data

    # # Wait for all pending messages to be delivered or expire.
    # await producer.stop()

    ret = Node(foo=_send, name='Kafka', inputs=1, graphvizshape=_OUTPUT_GRAPHVIZSHAPE)
    node >> ret

    ret.set('_producer', None)
    return ret
