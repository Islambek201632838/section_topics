from django.core.cache import cache
from django.db.models import Count, Q, Exists
from rest_framework import status
from rest_framework.response import Response

from handbook.utils.current_quarter import get_current_quarter
from schoolproj import settings
from subjects.models import Section
from training_test.models import SectionTrainingStat, ETestStatus, SubjectLevel
from training_test.views.utils.test_questions import test_questions
from users.models import CustomUser

CACHE_TIMEOUT = settings.CACHE_TIMEOUT


def format_response(response):
    if isinstance(response, Response):
        return response

    elif isinstance(response, list):
        return response

    else:
        return Response({"detail": f"Ошибка сервера. Тип ответа {type(response)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_sections_responses(subject_id, student_id):
    quarter = get_current_quarter()

    if not quarter:
        return Response({"detail": "Нет текущей четверти или каникулы"}, status=status.HTTP_404_NOT_FOUND)

    subject_level = SubjectLevel.objects.filter(student_id=student_id, quarter=quarter, subject_id=subject_id).first()

    level = subject_level.level if subject_level else None

    if not level:
        return Response({"detail": "Уровень не указан"}, status=status.HTTP_404_NOT_FOUND)

    sections = Section.objects.filter(subject_id=subject_id).annotate(
        topics_count=Count(
            'topic',
            filter=Q(
                topic__levels=level,
                topic__training_test__question__isnull=False
            ),
            distinct=True
        )
    ).filter(topics_count__gt=0).order_by('id')

    student = CustomUser.objects.get(id=student_id, role='student')
    section_records = SectionTrainingStat.objects.filter(student=student).order_by('id')
    last_section_stat = section_records.last()
    last_section_id = last_section_stat.section_id if last_section_stat else None

    responses = []
    if sections:
        sections = list(sections)
        for section in sections:
            if last_section_id:
                if section.id < last_section_id:
                    section_status = ETestStatus.FINISHED
                elif section.id == last_section_id:
                    section_status = last_section_stat.get_status()
                else:
                    # section_status = ETestStatus.NOT_AVAILABLE
                    section_status = ETestStatus.IN_PROGRESS
            else:
                if sections.index(section) == 0:
                    section_status = ETestStatus.IN_PROGRESS
                else:
                    # section_status = ETestStatus.NOT_AVAILABLE
                    section_status = ETestStatus.IN_PROGRESS

            topics_count = section.topics_count
            if topics_count > 0:
                response = {
                    "id": section.id,
                    "name": section.name,
                    "topics_count": topics_count,
                    "status": section_status,
                }
                responses.append(response)

        return responses

    return Response({"detail": "Нет разделов на этот предмет"}, status=status.HTTP_404_NOT_FOUND)


def get_subject_sections(subject_id, student_id):
    cache_key = f'sections_subject_{subject_id}_student_{student_id}'

    cached_data = cache.get(cache_key)
    # if cached_data:
    #     return Response(cached_data, status=status.HTTP_200_OK)

    response = get_sections_responses(subject_id, student_id)
    formatted_response = format_response(response)
    if isinstance(formatted_response, list):
        cache.set(cache_key, response, timeout=60 * 5)
        return Response(response, status.HTTP_200_OK)
    return formatted_response


