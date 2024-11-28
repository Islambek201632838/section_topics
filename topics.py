from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from schoolproj import settings
from subjects.models import Section
from training_test.models import Question, Test, Topic, TopicTrainingStat, ETestStatus, \
    get_student_level_by_section_id
from training_test.views.section.subject_sections import format_response

CACHE_TIMEOUT = settings.CACHE_TIMEOUT

now = timezone.now()


def get_topic_responses(section_id : int, student_id : int):
    level = get_student_level_by_section_id(section_id, student_id)

    if not level:
        return Response({"detail": "Уровень ученика на предмет и четверть не найден"}, status=status.HTTP_404_NOT_FOUND)

    question_prefetch = Prefetch(
        'question',
        queryset=Question.objects.filter(test_levels=level).order_by('id').distinct(),
        to_attr='prefetched_questions'
    )

    test_prefetch = Prefetch(
        'training_test',
        queryset=Test.objects.filter(question__isnull=False, question__test_levels=level).prefetch_related(question_prefetch).order_by('id').distinct(),
        to_attr='prefetched_tests'
    )

    topic_prefetch = Prefetch(
        'topic',
        queryset=Topic.objects.filter(
            levels=level,
            training_test__question__isnull=False,
            training_test__question__test_levels=level
        ).prefetch_related(test_prefetch).order_by('id').distinct(),
        to_attr='prefetched_topics'
    )

    try:
        section_instance = Section.objects.prefetch_related(topic_prefetch).get(id=section_id)
    except Section.DoesNotExist:
        return Response({"detail": "Заголовок не найден"}, status=status.HTTP_404_NOT_FOUND)

    topics = section_instance.prefetched_topics

    if not topics:
        return Response({"detail": "Темы не найдены"}, status=status.HTTP_404_NOT_FOUND)

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
            #tests_count = topic_stat.get_tests_count()
            tests_count = len(tests)
            tests_finished = topic_stat.get_finished_tests_count()
            topic_status = topic_stat.get_status(tests_count=tests_count, finished_tests_count=tests_finished)

            if topic_status == ETestStatus.NOT_AVAILABLE:
                topic_status = ETestStatus.IN_PROGRESS

            if tests_finished == tests_count:
                test_index = tests_finished - 1
            else:
                test_index = tests_finished
            current_test = tests[test_index] if tests and tests_count > test_index else None
            current_test_id = current_test.id if current_test else None


            prefetched_questions = current_test.prefetched_questions if current_test else []
            questions_count = len(prefetched_questions) if prefetched_questions else 0

            if questions_count != 0 and current_test_id is not None:
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
            #tests_count = topic_stat.get_tests_count()
            tests_count = len(tests)
            topic_status = ETestStatus.IN_PROGRESS
            tests_finished = topic_stat.get_finished_tests_count()
            if topics.index(topic) == 0:
                topic_status = ETestStatus.IN_PROGRESS

            current_test = tests[0] if len(tests) > 0 else None
            current_test_id = current_test.id if tests else None
            prefetched_questions = current_test.prefetched_questions if current_test else []
            questions_count = len(prefetched_questions) if prefetched_questions else 0

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

    if not responses:
        return Response({"detail": "Темы не найдены"}, status=status.HTTP_404_NOT_FOUND)
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
