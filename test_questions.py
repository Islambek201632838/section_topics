import random
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from rest_framework import status
from rest_framework.response import Response
from handbook.utils.current_quarter import get_current_quarter
from training_test.models import QuestionAndStudentRecord, Test, Question, QuestionClone, SubjectLevel, Difficulty
from training_test.serializers import StudentQuestionPayloadGetSerializer
from training_test.tasks.generate_clones import process_questions_in_background, task_generate_gpt_extra_questions
from training_test.views.question_clone.gpt_question import generate_gpt_question
from utils.translate import translate_text


def get_empty_student_response(next_question_type):
    if next_question_type in ['single_choice', 'open', 'essay', 'sentence_creation', 'text_analysis', 'dialog']:
        student_response = ''
    elif next_question_type in ['matching', 'value_for_keys']:
        student_response = {}
    elif next_question_type in ['multiple_choice', 'blank', 'order']:
        student_response = []
    else:
        return Response({'detail': f'неверный тип вопроса {next_question_type}'}, status=status.HTTP_400_BAD_REQUEST)
    return student_response


def get_student_level_by_test_id(test_id : int, student_id : int) -> Difficulty | Response | None:
    quarter = get_current_quarter()
    if not quarter:
        return Response({"detail": "Нет текущей четверти или каникулы"}, status=status.HTTP_404_NOT_FOUND)

    try:
        test_instance = Test.objects.select_related('topic__section__subject').get(id=test_id)
        subject = test_instance.topic.section.subject
    except (ObjectDoesNotExist, MultipleObjectsReturned, Exception) as e:
        return Response({'detail': translate_text(str(e))}, status=status.HTTP_404_NOT_FOUND)

    subject_level = SubjectLevel.objects.filter(student_id=student_id, quarter=quarter, subject=subject)
    if subject_level.exists():
        level = subject_level.first().level
    else:
        level = None

    return level

def test_questions(test_id : int, student_id : int) -> Response:

    cache_key = f'student_{student_id}_test_{test_id}_current_question'

    cached_data = cache.get(cache_key)
    # if cached_data:
    #     return Response(cached_data, status=status.HTTP_200_OK)

    level = get_student_level_by_test_id(test_id, student_id)
    if not level:
        return Response({"detail": "Уровень ученика на предмет и четверть не найден"}, status=status.HTTP_404_NOT_FOUND)

    questions_queryset = Question.objects.filter(test_id=test_id, test_levels=level).order_by('id')

    test_instance_questions = list(questions_queryset)
    recorded_questions_queryset = QuestionAndStudentRecord.objects.filter(question__in=questions_queryset, student_id=student_id)
    recorded_questions = list(recorded_questions_queryset)

    if not QuestionClone.objects.filter(question__test__id=test_id, question__test_levels=level).exists():
        print('process_questions_in_background')
        process_questions_in_background.delay(test_id)

    recorded_questions_list = [recorded_question.question for recorded_question in recorded_questions]
    distinct_questions_count = len(set(recorded_questions_list))
    last_question_record = recorded_questions[-1] if recorded_questions else None

    if last_question_record:
        last_id = last_question_record.question_id
        allowed_to_proceed = last_question_record.allowed_to_proceed
    else:
        # If no questions have been attempted, start with the first question
        first_question = test_instance_questions[0] if test_instance_questions else []
        last_id = first_question.id if first_question else None
        allowed_to_proceed = True

    if allowed_to_proceed:
        is_clone = False
        next_question = None
        # Proceed to the next random question if the last one was answered correctly
        remaining_questions = [q for q in test_instance_questions if
                               q.id not in [rq.question_id for rq in recorded_questions]]

        if remaining_questions:
            order = distinct_questions_count + 1
            next_question = random.choice(remaining_questions)
            student_response = get_empty_student_response(next_question.question_type)
            if isinstance(student_response, Response):
                return student_response

        else:
            order = distinct_questions_count
            questions_count = len(test_instance_questions)
            if order >= questions_count and last_question_record:
                last_question = last_question_record.question_clone
                if not last_question:
                    last_question = last_question_record.question
                student_response = last_question_record.student_response
                if student_response and last_question:
                    next_question = last_question
            else:
                return Response({"detail": "Нет вопросов для этого теста."}, status=status.HTTP_404_NOT_FOUND)

        if is_clone is True:
            serializer = StudentQuestionPayloadGetSerializer(next_question)
        else:
            serializer = StudentQuestionPayloadGetSerializer(next_question)
        response = serializer.data.copy()
        response['order'] = order
        response['is_clone'] = is_clone
        response['student_response'] = student_response


        cache.set(cache_key, response, timeout=None)

        return Response(response)

    else:
        is_clone = True
        order = distinct_questions_count
        # If not allowed to proceed, get or generate a clone question
        if last_id:
            clone_questions = QuestionClone.objects.filter(question_id=last_id).exclude(
                id__in=[rq.question_clone_id for rq in recorded_questions if rq.question_clone_id]
            )
        else:
            clone_questions = QuestionClone.objects.none()

        if clone_questions.exists():
            next_question = random.choice(clone_questions)
            if clone_questions.count() == 1 and last_id:
                task_generate_gpt_extra_questions.delay(last_id, 3)
        else:
            # If no clone exists, generate one using GPT
            print('clones didnt exist')
            if last_id:
                task_generate_gpt_extra_questions.delay(last_id, 3)
            next_question = generate_gpt_question(last_id) if last_id else None

            if isinstance(next_question, Response):
                return next_question

        if next_question:
            if is_clone is True:
                serializer = StudentQuestionPayloadGetSerializer(next_question)
            else:
                serializer = StudentQuestionPayloadGetSerializer(next_question)
            response = serializer.data.copy()
            response['order'] = order
            response['is_clone'] = is_clone

            student_response = get_empty_student_response(next_question.question_type)
            if isinstance(student_response, Response):
                return student_response


            response['student_response'] = student_response

            cache.set(cache_key, response, timeout=None)

            return Response(response, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Не удалось сгенерировать вопрос."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
