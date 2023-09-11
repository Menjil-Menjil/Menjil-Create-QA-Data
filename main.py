import csv
import re
from pymongo import MongoClient
import openai
from datetime import datetime, timedelta
import boto3  # The AWS SDK for Python

import config

# Declare a constant variable
TARGET_LANGUAGE_CODE = 'en'
SOURCE_LANGUAGE_CODE = 'ko'


def read_csv(file_name):
    data_list = []
    with open(file_name, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)

        for row in reader:
            # Assuming the columns are named 'question' and 'answer'
            question = re.sub('\n+', '\n', row['question'])
            answer = re.sub('\n+', '\n', row['answer'])
            data_dict = {
                'mentee_nickname': '',
                'mentor_nickname': '',
                'question_origin': question,
                'question_summary': '',
                'question_summary_en': '',
                'question_time': datetime.now() - timedelta(days=1),
                'answer': answer,
                'answer_time': datetime.now() - timedelta(days=1)
            }
            data_list.append(data_dict)

    return data_list


def get_mongo_client():
    username = config.MONGODB_USERNAME
    password = config.MONGODB_PASSWORD
    host = config.MONGODB_HOST
    port = config.MONGODB_PORT

    # Create a MongoDB connection URI
    mongo_uri = f'mongodb://{username}:{password}@{host}:{port}/'

    # Create the MongoDB client and return it
    return MongoClient(mongo_uri)


if __name__ == '__main__':
    """1. csv의 데이터를 읽어 온다."""
    question_and_answer_list = read_csv('q_and_a.csv')

    """2. ChatGPT API를 사용하여 세 줄 요약을 한다"""
    openai.api_key = config.OPENAI_SECRET_KEY
    for i in question_and_answer_list:
        prompt = '제 질문은 \"' + i.get('question_origin') + '\" 입니다. 이 질문을 세 줄 요약해주세요.'

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        i['question_summary'] = response['choices'][0]['message']['content']

    """3. AWS Translate API를 사용한 영어 번역을 한다"""
    # Configure AWS Translate client
    translate = boto3.client(service_name='translate',
                             aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
                             region_name=config.AWS_SEOUL_REGION)

    for i in question_and_answer_list:
        translation_response = translate.translate_text(Text=i.get('question_summary'),
                                                        SourceLanguageCode=SOURCE_LANGUAGE_CODE,
                                                        TargetLanguageCode=TARGET_LANGUAGE_CODE)
        i['question_summary_en'] = translation_response['TranslatedText']

    """4. 그 외 정보들 생성 및 document 생성"""
    for i in range(len(question_and_answer_list)):
        question_and_answer_list[i]['mentee_nickname'] = '서울과기대21'
        question_and_answer_list[i]['mentor_nickname'] = 'mentor1'
        question_and_answer_list[i]['question_time'] = \
            question_and_answer_list[i]['answer_time'] - timedelta(minutes=i + 3)
        question_and_answer_list[i]['answer_time'] = \
            question_and_answer_list[i]['answer_time'] + timedelta(minutes=i)

    """5. Connect MongoDB and save documents """
    # Connect MongoDB
    mongo_client = get_mongo_client()
    menjil_db = mongo_client['menjil']
    qa_list_collection = menjil_db['qa_list']

    qa_list_collection.insert_many(question_and_answer_list)
