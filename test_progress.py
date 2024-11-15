from rest_framework.response import Response
from training_test.models import QuestionAndStudentRecord, Question


def generate_test_progress(test_id, student_id):
    # Get all records for the given test and student

    records = QuestionAndStudentRecord.objects.filter(
        question__test_id=test_id,
        student_id=student_id
    ).select_related('question', 'question_clone').order_by('id')

    # Prepare a dictionary to hold questions and their associated clones
    question_status_dict = {}

    # Iterate over records and populate the dictionary
    order = 0
    for record in records:
        question_id = record.question.id

        if question_id not in question_status_dict:
            question_status_dict[question_id] = {
                'question_correct': None,
                'clones_correct': []
            }

        if record.question_clone:
            # If it's a clone, append to the clones_correct list
            question_status_dict[question_id]['clones_correct'].append(record.is_correct)
        else:
            # If it's the main question, set the question_correct field
            order += 1
            question_status_dict[question_id]['order'] = order if order != 0 else 1
            question_status_dict[question_id]['question_correct'] = record.is_correct

    # Convert dictionary to the required list of lists format
    questions = []
    for question_status in question_status_dict.values():
        questions.append(question_status)
    questions_count = Question.objects.filter(test_id=test_id).count()
    clones_correct = questions[-1]['clones_correct'] if len(questions) >= 1 else []
    if order < questions_count and (len(questions) == 0 or questions[-1]['question_correct'] == True or
                                    (len(clones_correct) >= 3 and all(clones_correct[-3:]))):
        order += 1
        questions.append(
            {
                'question_correct': None,
                'clones_correct': [],
                'order': order if order != 0 else 1
            }
        )
    return Response(questions)
