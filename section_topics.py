from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from handbook.utils.current_quarter import get_current_quarter
from schoolproj import settings
from subjects.models import Section
from training_test.models import Question, Test, Topic, TopicTrainingStat, ETestStatus, SubjectLevel
from training_test.views.utils.subject_sections import format_response

CACHE_TIMEOUT = settings.CACHE_TIMEOUT

now = timezone.now()


def get_topic_responses(section_id, student_id):
    quarter = get_current_quarter()
    if not quarter:
        return Response({"detail": "Нет текущей четверти или каникулы"}, status=status.HTTP_404_NOT_FOUND)

    try:
        subject = Section.objects.get(id=section_id).subject
    except Section.DoesNotExist:
        return Response({"detail": "Раздел не найден"}, status=status.HTTP_404_NOT_FOUND)
    except ObjectDoesNotExist:
        return Response({"detail": "Предмет не найден"}, status=status.HTTP_404_NOT_FOUND)

    subject_level = SubjectLevel.objects.filter(student_id=student_id, quarter=quarter, subject=subject)

    if subject_level.exists():
        level = subject_level.first().level
    else:
        level = None

    if level:
        question_prefetch = Prefetch(
            'question',
            queryset=Question.objects.filter(test_levels=level),
            to_attr='prefetched_questions'
        )

    else:
        question_prefetch = Prefetch(
            'question',
            queryset=Question.objects.all(),
            to_attr='prefetched_questions'
        )

    test_prefetch = Prefetch(
        'training_test',
        queryset=Test.objects.all().prefetch_related(question_prefetch).order_by('id'),
        to_attr='prefetched_tests'
    )

    topic_prefetch = Prefetch(
        'topic',
        queryset=Topic.objects.filter(levels=level).prefetch_related(test_prefetch).order_by('id'),
        to_attr='prefetched_topics'
    )

    try:
        section_instance = Section.objects.prefetch_related(topic_prefetch).get(id=section_id)
    except Section.DoesNotExist:
        return Response({"detail": "Заголовок не найден."}, status=status.HTTP_404_NOT_FOUND)

    topics = section_instance.prefetched_topics

    if not topics:
        return Response({"detail": "Темы не найдены."}, status=status.HTTP_404_NOT_FOUND)

    # Fetch the student's TopicTrainingStat for all topics in this section
    topic_ids = [topic.id for topic in topics]
    topic_stats = TopicTrainingStat.objects.filter(student_id=student_id, topic_id__in=topic_ids, level=level)

    # Create a lookup dictionary for fast access to topic stats
    topic_stats_dict = {stat.topic_id: stat for stat in topic_stats}

    responses = []
    for topic in topics:
        topic_name = topic.name

        # Get the prefetched tests
        tests = topic.prefetched_tests

        # Get the topic status from TopicTrainingStat or default to 'not_available'
        if topic.id in topic_stats_dict:
            topic_stat = topic_stats_dict[topic.id]
            tests_finished = topic_stat.get_finished_tests_count()
            tests_count = topic_stat.get_tests_count()
            topic_status = topic_stat.get_status()

            if topic_status == ETestStatus.NOT_AVAILABLE:
                topic_status = ETestStatus.IN_PROGRESS

            current_test = tests[tests_finished] if tests and tests_count > tests_finished else None
            current_test_id = current_test.id if current_test else None
            questions_count = len(current_test.prefetched_questions) if current_test else 0

            if (questions_count != 0 and current_test_id is not None) or topic_status == ETestStatus.FINISHED:
                response = {
                    "id": topic.id,
                    "name": topic_name,
                    "status": topic_status,
                    "tests_count": tests_count,
                    'tests_finished': tests_finished,
                    "current_test_id": current_test_id,
                    "questions_count": questions_count,
                }

                responses.append(response)

        else:
            # topic_status = ETestStatus.NOT_AVAILABLE
            topic_stat = TopicTrainingStat.objects.create(student_id=student_id, topic_id=topic.id, level=level,
                                                          finished_tests_count=0, tests_count=0)
            tests_count = topic_stat.get_tests_count()
            topic_status = ETestStatus.IN_PROGRESS
            tests_finished = topic_stat.get_finished_tests_count()
            current_test_id = None
            if topics.index(topic) == 0:
                topic_status = ETestStatus.IN_PROGRESS

            current_test_id = tests[0].id if tests else None
            questions_count = len(tests[0].prefetched_questions) if tests and tests[0] else 0

            if questions_count != 0 and current_test_id is not None:
                response = {
                    "id": topic.id,
                    "name": topic_name,
                    "status": topic_status,
                    "tests_count": tests_count,
                    "tests_finished": tests_finished,
                    "current_test_id": current_test_id,
                    "questions_count": questions_count,
                }
                responses.append(response)
    return responses

def get_section_topics(section_id, student_id):
    cache_key = f'topics_section_{section_id}_student_{student_id}'
    cached_data = cache.get(cache_key)
    # if cached_data:
    #     return Response(cached_data, status=status.HTTP_200_OK)

    response = get_topic_responses(section_id, student_id)

    formatted_response = format_response(response)
    if isinstance(formatted_response, list):
        cache.set(cache_key, response, timeout=60 * 5)
        return Response(response, status.HTTP_200_OK)
    return formatted_response
