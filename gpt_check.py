import json
import re
import openai
import requests
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from schoolproj import settings
from teacher_data.serializers.questions_get import QuestionClonePayloadGetSerializer, QuestionPayloadGetSerializer
from training_test.models import QuestionClone, Question, TopicHandbook
from training_test.views.question.gpt_message import get_function_and_messages

openai.api_key = settings.OPEN_AI_KEY
MAX_RESPONSE_LENGTH = 1000

def sanitize_input(student_response):
    sanitized_response = re.sub(r'[<>/{}[\]`~]', '', student_response)
    sanitized_response = sanitized_response.strip()
    return sanitized_response

def check_by_gpt(question_or_clone_id : int, is_clone, student_response) -> Response:
    #pdb.set_trace()
    if is_clone:
        try:
            question_clone_instance = QuestionClone.objects.select_related('question__test__topic__section__subject', 'payload').get(id=question_or_clone_id)
            test_instance = question_clone_instance.question.test
            difficulty_name = question_clone_instance.difficulty.name

            if question_clone_instance.question_type == 'open':
                question_serializer = QuestionClonePayloadGetSerializer(question_clone_instance)
                question_serializer_data = question_serializer.data
                if question_serializer_data and 'payload' in question_serializer_data and 'criteria' in question_serializer_data['payload']:
                    criteria = question_serializer_data['payload']['criteria']
                else:
                    criteria = ''
            else:
                criteria = ''

        except QuestionClone.DoesNotExist:
            return Response(
                {'detail': 'Вопрос не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ObjectDoesNotExist:
            return Response(
                {'detail': 'Тест не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = QuestionClonePayloadGetSerializer(question_clone_instance)
        question_details = serializer.data
    else:
        try:
            question_instance = Question.objects.select_related('test__topic__section__subject', 'payload').get(id=question_or_clone_id)
            if question_instance.question_type == 'open':
                question_serializer = QuestionPayloadGetSerializer(question_instance)
                question_serializer_data = question_serializer.data
                if question_serializer_data and 'payload' in question_serializer_data and 'criteria' in \
                        question_serializer_data['payload']:
                    criteria = question_serializer_data['payload']['criteria']
                else:
                    criteria = ''
            else:
                criteria = ''

            test_instance = question_instance.test
            difficulty_name = question_instance.difficulty.name

        except Question.DoesNotExist:
            return Response(
                {'detail': 'Вопрос не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        except ObjectDoesNotExist:
            return Response(
                {'detail': 'Тест не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = QuestionPayloadGetSerializer(question_instance)
        question_details = serializer.data

    sanitized_student_response = sanitize_input(student_response)

    try:
        topic_instance = test_instance.topic
        goals = TopicHandbook.objects.get(topic=topic_instance).goals
        student_goal = goals.get(difficulty_name)

        subject_name = topic_instance.section.subject.name

        if 'казах' in subject_name.lower() or 'қазақ' in subject_name.lower():
            gpt_model = 'gpt-4o'
        else:
            gpt_model = 'gpt-4o-mini'

        topic_name = topic_instance.name
    except ObjectDoesNotExist:
        return Response(
            {'detail': 'Предмет, тема или цель не найдены'},
            status=status.HTTP_404_NOT_FOUND
        )

    if len(sanitized_student_response) > MAX_RESPONSE_LENGTH:
        raise ValidationError('Ваш ответ слишком длинный')

    fn_mes_dict = get_function_and_messages(subject_name, topic_name, student_goal, question_details, sanitized_student_response, criteria)

    function = fn_mes_dict.get("function")
    messages = fn_mes_dict.get("messages")


    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {openai.api_key}',
        },
        json={
            'model': gpt_model,
            'messages': messages ,
            'functions': [function],
            'function_call': {'name': 'evaluate_answer'},
            'temperature': 0.2,
        }
    )

    #print(response.content)

    response.raise_for_status()
    response_data = response.json()

    if 'choices' not in response_data or not response_data['choices']:
        raise ValueError("Некорректный ответ от OpenAI API")

    message = response_data['choices'][0]['message']
    function_call = message.get('function_call')

    if function_call and function_call.get('arguments'):
        arguments = function_call['arguments']
        arguments = arguments.decode('utf-8') if isinstance(arguments, bytes) else arguments

        try:
            parsed_arguments = json.loads(arguments)
            if parsed_arguments.get('moderation_flag'):
                parsed_arguments['points'] = 0
            #print(f"Parsed Arguments: {parsed_arguments}")  # For debugging
            return parsed_arguments
        except json.JSONDecodeError:
            raise ValueError("Некорректный JSON в ответе от OpenAI API")
    else:
        raise ValueError("Получено пустое содержимое от OpenAI API")
