import uuid
import numpy as np
import random
import pandas as pd

players_count=2

status_start = 'start_message'
status_wait_start_phrase = 'wait_start_phrase'
status_wait_images = 'wait_images'
status_wait_answers = 'wait_answers'
status_end_game = 'end_game'

users = pd.DataFrame(columns=['id', 'login', 'active', 'active_game']).set_index('id')
rounds = pd.DataFrame(columns=['id', 'game_id', 'active_user', 'messages', 'images', 'guess_phrase', 'active', 'status']).set_index('id')
games = pd.DataFrame(columns=['id', 'users', 'score', 'active_round']).set_index('id')
images = pd.DataFrame(columns=['id', 'guess_num', 'link', 'user_id', 'round_id']).set_index('id')


def create_user(userId, login):
    user = {
        'login': login,
        'active': False,
        'active_game': None
    }
    users.loc[userId] = user
    
    return [{'user_id': userId, 'message':'Добро пожаловать в игру, %s! Сейчас мы дождемся других участников и начнем. Пока напомню правила: \r\n1) Ведущий предлагает фразу\r\n2) Каждый игрок предлагает картинку, которая наиболее сильно ассоциируется с фразой\r\n3) Каждый игрок получает столько очков, сколько других игроков проголосовало за его картинку' % login}]

def start_round(game_id):
    round_uid = uuid.uuid4().hex
    game = games.loc[game_id]
    active_user_idx = random.randrange(0, len(game.users))
    rounds.loc[round_uid] = {
        'game_id': game_id,
        'active_user': game['users'][active_user_idx],
        'messages': {},
        'images': {},
        'guess_phrase': None,
        'active': True,
        'status': status_start
    }
    games.at[game_id, 'active_round'] = round_uid
    return round_uid

def try_start_game():
    game_users = users[users.active == False]
    if game_users.shape[0] < players_count:
        return None
    
    game_uid = uuid.uuid4().hex
    game_users = game_users[0:players_count].index
    
    games.loc[game_uid] = {
        'users': np.array(game_users),
        'score': {},
        'active_round': None
    }
    for i in game_users:
        users.at[i, 'active'] = True
        users.at[i, 'active_game'] = game_uid
    return game_uid


def send_start_messages(round_id):
    round_item = rounds.loc[round_id]
    if round_item.status != status_start:
        raise Exception("wrong status")
    game = games.loc[round_item.game_id]
    answer = []
    answer.append({'user_id': round_item.active_user, 'message':'Загадай фразу!'})
    for user in game.users:
        if user == round_item.active_user:
            continue
        answer.append({'user_id': user, 'message':'Игра началась! Ждем ведущего.'})
    rounds.at[round_id, 'status'] = status_wait_start_phrase
    return answer

def set_start_phrase(round_id, user_id, guess_phrase):
    round_item = rounds.loc[round_id]
    if round_item.status != status_wait_start_phrase:
        raise Exception("wrong status")
    game = games.loc[round_item.game_id]
    if user_id != round_item.active_user:
        return []
    round_item['guess_phrase'] = guess_phrase
    answer = []
    for user in game.users:
        answer.append({'user_id': user, 'message':'Итак, загаданная фраза: %s. Предложи картинку' % guess_phrase})
    rounds.at[round_id, 'status'] = status_wait_images
    return answer 

import psycopg2


image_queries = {}

args = {
    'password':'zNEBY4aM7Xy8EzYw',
    'host':'7cf28479313d429eb436a02fd0b45632',
    'messenger':'telegram'
}

conn_str = "dbname=imaginarium user=bot port=5432 host='%s' password='%s'"% (args['host'], args['password'])

def insert_image(user_id, round_id):
    query = image_queries[user_id]
    image_queries.pop(user_id, None)
    
    mimetype = query.get('mime_type')
    data = query.get('data')
    
    if data == None or mimetype == None:
        return None
    
    guid = uuid.uuid4()
    hex = get_hex(data)
    
    conn = psycopg2.connect(conn_str)
    cursor = conn.cursor()
    data = cursor.execute("INSERT INTO images(id,mimetype,image_content, link) VALUES ('%s', '%s', decode('%s', 'hex'), '');" % (guid, mimetype, hex))
    conn.commit()
    cursor.close()
    conn.close()
    
    images.loc[guid] = {'link' : 'http://images.ravop.ru/%s' % guid, 'guess_num':-1,'user_id': user_id, 'round_id':round_id}
    
    return guid

def add_image(user_id, round_id, message):
    guid = uuid.uuid4()
    images.loc[guid] = {'link':message, 'guess_num':-1,'user_id': user_id, 'round_id':round_id}
    return guid

import re
http_re = re.compile('^https?://\S+')

def set_image(round_id, user_id, message):
    round_item = rounds.loc[round_id]
    if round_item.status != status_wait_images:
        raise Exception("wrong status")
    game = games.loc[round_item.game_id]
    if not user_id in game.users:
        return
    if not user_id in image_queries and (message == None or not http_re.match(message)):
        return
    if user_id in image_queries:
        image_id = insert_image(user_id, round_id)
    else:
        image_id = add_image(user_id, round_id, http_re.match(message)[0])
    if image_id == None:
        return
    round_item.images[user_id] = image_id 
    
    if len(round_item.images) < len(game.users):
        return [{'user_id': user_id, 'message':'Картинка добавлена, ждем варианты других игроков'}]
    
    image_ids = list(round_item.images.values())
    random.shuffle(image_ids)
    
    for i, image_id in enumerate(image_ids):
        images.at[image_id, 'guess_num'] = i
    
    answer = []
    for user in game.users:
        answer.append({'user_id': user, 'message':'Итак, варианты ответов:'})
        for i, image_id in enumerate(image_ids):
            answer.append({'user_id': user, 'message':'%d) %s' % (i, images.loc[image_id].link)})
    rounds.at[round_id, 'status'] = status_wait_answers
    return answer


numre = re.compile('\d')

def sklon(count, oneWord, twoWords, tenWords):
    lastDigit = count % 10;
    last2Digit = count % 100;
    if last2Digit >= 10 and last2Digit <= 20:
        return tenWords
    if lastDigit == 1:
        return oneWord
    if lastDigit > 1 and lastDigit < 5:
        return twoWords
    return tenWords;

def set_answer(round_id, user_id, answer):
    round_item = rounds.loc[round_id]
    if round_item.status != status_wait_answers:
        raise Exception("wrong status")
    game = games.loc[round_item.game_id]
    if not user_id in game.users or user_id == round_item.active_user:
        return []
    
    match = numre.search(answer)
    if match == None:
        return [{'user_id': user_id, 'message':"Мне срочно нужен номер картинки"}]
    num = int(match[0])
    if num >= len(game.users):
        return [{'user_id': user_id, 'message':"Мне срочно нужен номер картинки от 0 до %d" % len(game.users)}]
    
    interesting_images = images[images.round_id == round_id]
    users_answers = interesting_images[images.user_id.isin(game.users)][['guess_num','user_id']].set_index('user_id')
    if num == users_answers.loc[user_id].guess_num:
        return [{'user_id': user_id, 'message':"Мне срочно нужен номер картинки, отличной от той, что вы загадали"}]
    
    answer = []
    
    round_item.messages[user_id] = num 
    answer.append({'user_id': user_id, 'message':'Ответ %d принят!' % num})
    
    if len(round_item.messages) < len(game.users) - 1:
        return answer
    
    interesting_images = images[images.round_id == round_id]
    
    right_answer = interesting_images[images.user_id == round_item.active_user].iloc[0].guess_num
    users_answers = interesting_images[images.user_id.isin(game.users)][['guess_num','user_id']].set_index('guess_num')
    
    scores = np.zeros(len(game.users))
    
    for message in round_item.messages.values():
        scores[message] = scores[message] + 1
                                          
    total_result = "Результаты:"
    for i, score in enumerate(scores):
        if right_answer == i:
            total_result += "\r\n" + 'Картинка №%d (Правильный ответ) набрала %d %s' % (i, score, sklon(score, 'голос', 'голоса', 'голосов'))
        else:
            total_result += "\r\n" + 'Картинка №%d набрала %d %s' % (i, score, sklon(score, 'голос', 'голоса', 'голосов'))
             
    for i, score in enumerate(scores):
        user = users_answers.loc[i].user_id
        game.score[user] = game.score.get(user, 0) + score
        
    #for user in game.users:
    total_result += '\r\n\r\nСчёт по всем играм:'
    for user_id in game.score:
        name = users.loc[user_id].login
        total_result += '\r\n%s: %d %ы' % (name, game.score.get(user_id, 0), sklon(score, 'очко', 'очка', 'очков'))
    total_result += '\r\nПродолжаем...'
    
    for user in game.users:
        answer.append({'user_id':user,'message':total_result})
            
    rounds.at[round_id, 'status'] = status_end_game
    
    return answer


import json
import requests

def add_messages(messages_list, add_messages):
    if add_messages != None:
        messages_list.extend(add_messages)
    
not_first_time_seen = set()

def get_messages(partner_id, message):
    messages = []
    if not partner_id in users.index:
        if not partner_id in not_first_time_seen:
            not_first_time_seen.add(partner_id)
            return [{
                'user_id': partner_id, 
                'message':'Привет! Мы здесь проводим игру в "Имаджинариум" и предлагаем тебе к ней присоединиться! Напиши свое имя:'}]
        add_messages(messages, create_user(partner_id, message))
        game_id = try_start_game()
        if game_id != None: 
            round_id = start_round(game_id)
            messages = send_start_messages(round_id)
        return messages
    
    game_id = users.loc[partner_id].active_game
    if game_id == None:
        return [{'user_id': partner_id,'message':"Подожди немного, мы ждем других участников."}]
    game = games.loc[game_id]
    round_id = game.active_round
    if round_id == None:
        return [{'user_id': partner_id,'message':"Подожди немного, мы ждем других участников."}]
    
    round_item = rounds.loc[round_id]
    
    if round_item.status == status_wait_start_phrase:
        return set_start_phrase(round_id, partner_id, message)
    if round_item.status == status_wait_images:
        return set_image(round_id, partner_id, message)
    if round_item.status == status_wait_answers:
        messages = set_answer(round_id, partner_id, message)
    if round_item.status == status_end_game:
        #for user in game.users:
        #    users.at[user, 'active'] = False
        #    users.at[user, 'active_game'] = None 
        round_id = start_round(game_id)
        add_messages(messages, send_start_messages(round_id))
    return messages

def get_hex(byte_line):
    return ''.join('{:02x}'.format(x) for x in byte_line)

def try_analyse_image(data):
    partner_id = data['payload'].get('partner_id')
    
    if not partner_id in users.index:
        return True
    game_id = users.loc[partner_id].active_game
    if game_id is None:
        return True
    round_id = games.loc[game_id].active_round
    if round_id is None or rounds.loc[round_id].status != status_wait_images:
        return True
    
    media = data['payload'].get('media')
    
    if media != None:
        media = media.get('mime_type')
        image_queries[partner_id] = {'mime_type':media}
        return False
    
    buffer_data = data['payload'].get('data')
    if buffer_data != None:
        buffer_data = buffer_data.get('data')
        image_queries[partner_id]['data'] = buffer_data
        
    return True

def callback(ch, method, properties, body):
    #print(str(body, "utf8") + "\r\n\r\n")
    data = json.loads(str(body, "utf8"))
    if not try_analyse_image(data):
        return
    message = data['payload'].get('message')
    partner_id = data['payload'].get('partner_id')
    is_incoming = data['payload'].get('direction') == "Incoming"
    if is_incoming or partner_id in image_queries:
        print (partner_id, message)
        messages = get_messages(partner_id, message)
        if messages == None:
            return
        for message in messages:
            print (message)
            requests.post("http://7cf28479313d429eb436a02fd0b45632/sendTelegram", data={"partner_id":message['user_id'],"message":message['message']})

import pika

credentials = pika.PlainCredentials('bot', args['password'])
connection = pika.BlockingConnection(pika.ConnectionParameters(args['host'], credentials=credentials))
channel = connection.channel()
arguments = dict()
arguments['x-dead-letter-exchange'] = args['messenger'] + '_deadletter'
arguments['x-dead-letter-routing-key'] = args['messenger'] + '_remote'
channel.basic_consume(callback, queue=args['messenger'] + '_remote', no_ack=True)
print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()