from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, Count, Q
from rest_framework import status
from rest_framework.response import Response
from handbook.utils.current_quarter import get_current_quarter
from subjects.models import Section
from training_test.models import SectionTrainingStat, SubjectLevel
from training_test.views.utils.subject_sections import get_sections_responses


def get_section_by_id(request, section_id):
    student_id = request.user.id

    try:
        cache_key = f'sections_id_{section_id}_student_{student_id}'

        try:
            subject = Section.objects.get(id=section_id).subject
        except Section.DoesNotExist:
            return Response({"detail": "Раздел не найден"}, status=status.HTTP_404_NOT_FOUND)
        except ObjectDoesNotExist:
            return Response({"detail": "Предмет не найден"}, status=status.HTTP_404_NOT_FOUND)

        response_list = get_sections_responses(subject.id, student_id)

        if isinstance(response_list, Response):
            return response_list

        response = next((item for item in response_list if item["id"] == section_id), None)

        if not response:
            return Response({'detail': 'Раздел не найден'}, status=status.HTTP_404_NOT_FOUND)

        elif response and isinstance(response, dict):
            cache.set(cache_key, response, timeout=60 * 5)
            return Response(response, status=status.HTTP_200_OK)

        else:
            return Response({"detail": f"Ошибка сервера. Тип ответа {type(response)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
