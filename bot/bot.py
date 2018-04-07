def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)

import pika, argparse, psycopg2

parser = argparse.ArgumentParser(description='Бот')
parser.add_argument('password', action='store', metavar='{пароль от пользователя bot}')
parser.add_argument('--messenger', action='store', metavar='название мессенджера', default='telegram')
parser.add_argument('host', action='store', metavar='хост')
args = parser.parse_args()

conn = psycopg2.connect('dbname=imaginarium user=bot password=%s port=5432 host=%s' % (args.password, args.host))

credentials = pika.PlainCredentials('bot', args.password)
connection = pika.BlockingConnection(pika.ConnectionParameters(args.host, credentials=credentials))
channel = connection.channel()
arguments = dict()
arguments['x-dead-letter-exchange'] = args.messenger + '_deadletter'
arguments['x-dead-letter-routing-key'] = args.messenger + '_remote'
channel.basic_consume(callback, queue=args.messenger + '_remote', no_ack=True)
print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()