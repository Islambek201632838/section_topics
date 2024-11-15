from django.core.cache import cache
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError
from subjects.models import Subject, Section, Quarter
from users.models import CustomUser
from training_test.payloads import *

TYPE_CHOICES = (
        ('single_choice', 'Одиночный выбор'),
        ('multiple_choice', 'Множественный выбор'),
        ('open', 'Открытый'),
        ('matching', 'Сопоставление'),
        ('value_for_keys', 'Значение для ключей'),
        ('essay', 'Эссе'),
        ('sentence_creation', 'Создание предложения'),
        ('blank', 'Заполнение пропусков'),
        ('text_analysis', 'Анализ текста'),
        ('order', 'Упорядочивание'),
        ('dialog', 'Диалог'),
        ('audio', 'Аудио'),
        ('video', 'Видео'),
    )


class Difficulty(models.Model):
    DIFFICULTY_CHOICES = (
        ('base', _('Легкий')),
        ('medium', _('Средний')),
        ('advanced', _('Продвинутый')),
        ('c_level', _('С-уровень')),
    )
    name = models.CharField(_('Сложность'), max_length=20, choices=DIFFICULTY_CHOICES, unique=True)

    class Meta:
        verbose_name = _('Сложность')
        verbose_name_plural = _('Сложности')

    def __str__(self):
        return self.get_name_display()


class SubjectLevel(models.Model):
    student = models.ForeignKey(CustomUser, verbose_name=_('Ученик'), blank=False,
                                related_name='subject_level',
                                limit_choices_to={'role': 'student'}, on_delete=models.CASCADE, db_index=True)

    subject = models.ForeignKey(Subject, verbose_name=_('Предмет'), blank=False, related_name='subject_level',
                                on_delete=models.CASCADE, db_index=True)
    quarter = models.ForeignKey(Quarter, verbose_name=_('Четверть'), blank=False, related_name='subject_level',
                                on_delete=models.CASCADE, db_index=True)

    level = models.ForeignKey(
        Difficulty,
        verbose_name='Уровень',
        related_name='subject_difficulty',
        on_delete=models.CASCADE,
        db_index=True,
        blank=False,
        default=None,
        null=True
    )


    class Meta:
        indexes = [
            models.Index(fields=['subject', 'quarter', 'student']),
        ]
        verbose_name = _('Ученик и Сложность Предмета')
        verbose_name_plural = _('Ученики и Сложности Предметов')

    def __str__(self):
        return f'{self.subject}_{self.quarter}_{self.level}_{self.student.first_name}_{self.student.last_name}'


class Topic(models.Model):
    name = models.CharField(verbose_name=_('Наименование'), max_length=300, blank=False, db_index=True)
    section = models.ForeignKey(Section, verbose_name=_('Раздел'), blank=False, related_name='topic',
                                on_delete=models.CASCADE, db_index=True)
    levels = models.ManyToManyField(Difficulty, verbose_name=_('Сложности'), related_name='topic')

    class Meta:
        indexes = [
            models.Index(fields=['section']),
        ]
        verbose_name = _('Тема')
        verbose_name_plural = _('Темы')

    def __str__(self):
        return self.name


class TopicHandbook(models.Model):
    topic = models.ForeignKey(Topic, verbose_name=_('Тема'), blank=False, related_name='topic_handbook',
                              on_delete=models.CASCADE, db_index=True)
    text = models.CharField(verbose_name=_('Текст'), max_length=255, blank=False, db_index=True)
    goals = models.JSONField(verbose_name=_('Цели'), null=True, blank=False, default=None)

    class Meta:
        verbose_name = _('Справочник Темы')
        verbose_name_plural = _('Справочники Тем')

    def __str__(self):
        return self.topic.name


class Test(models.Model):
    topic = models.ForeignKey(Topic, verbose_name=_('Тема'), blank=False, null=True, related_name='training_test',
                              on_delete=models.CASCADE, db_index=True)
    order = models.IntegerField(blank=False, db_index=True, default=1, verbose_name=_('Порядок Тренажера'))

    class Meta:
        indexes = [
            models.Index(fields=['topic']),
        ]
        verbose_name = _('Тренивочный Тест')
        verbose_name_plural = _('Тренивочный Тесты')

    def __str__(self):
        return f'{self.topic.name} ({self.order})'


class Question(models.Model):
    test = models.ForeignKey(
        Test,
        verbose_name='Тренировочный Тест',
        related_name='question',
        on_delete=models.CASCADE,
        db_index=True,
        blank=False
    )
    test_levels = models.ManyToManyField(Difficulty, verbose_name=_('Сложности Тестов'), related_name='question_test')
    difficulty = models.ForeignKey(
        Difficulty,
        verbose_name='Сложность Вопроса',
        related_name='question',
        on_delete=models.CASCADE,
        db_index=True,
        blank=False,
        default=None,
        null=True
    )
    text = models.TextField('Текст', blank=False, db_index=True)
    context = models.TextField('Контекст', blank=True, null=True)
    question_type = models.CharField(
        'Тип Вопроса',
        max_length=20,
        choices=TYPE_CHOICES,
        blank=False,
        db_index=True
    )

    payload = models.OneToOneField(
        Payload,
        on_delete=models.CASCADE,
        related_name='question',
        null=True,
        blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=['test', 'text', 'question_type']),
        ]
        verbose_name = _('Вопрос')
        verbose_name_plural = _('Вопросы')

    def __str__(self):
        return f"{self.text} ({self.get_question_type_display()})"

    def get_full_name(self):
        pass

    def clean(self):
        expected_payload_model = {
            'single_choice': SingleChoicePayload,
            'multiple_choice': MultipleChoicePayload,
            'open': OpenPayload,
            'matching': MatchingPayload,
            'value_for_keys': ValueForKeysPayload,
            'essay': EssayPayload,
            'sentence_creation': SentenceCreationPayload,
            'blank': BlankPayload,
            'text_analysis': TextAnalysisPayload,
            'order': OrderPayload,
            'dialog': DialogPayload,
            'audio': AudioPayload,
            'video': VideoPayload,
        }.get(self.question_type)

        if expected_payload_model is None:
            raise ValidationError('Неверный тип вопроса: %s' % self.question_type)

        if not isinstance(self.payload, expected_payload_model):
            raise ValidationError(
                'Payload должен быть типа %s для вопроса типа %s.' % (
                    expected_payload_model.__name__, self.question_type)
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        DIFFICULTY_ORDER = ['base', 'medium', 'advanced', 'c_level']
        try:
            question_difficulty_index = DIFFICULTY_ORDER.index(self.difficulty.name)
        except ValueError:
            raise ValueError('Invalid difficulty level: {}'.format(self.difficulty.name))

        levels_to_assign = DIFFICULTY_ORDER[question_difficulty_index:]
        difficulties = Difficulty.objects.filter(name__in=levels_to_assign)

        self.test_levels.set(difficulties)


class QuestionClone(models.Model):

    question = models.ForeignKey(Question, verbose_name=_('Генерирован от вопроса'), blank=False,
                                 related_name='question_clone',
                                 on_delete=models.CASCADE, db_index=True)

    text = models.TextField('Текст', blank=False, db_index=True)
    context = models.TextField('Контекст', blank=True, null=True)
    question_type = models.CharField(
        'Тип Вопроса',
        max_length=20,
        choices=TYPE_CHOICES,
        blank=False,
        db_index=True
    )
    difficulty = models.ForeignKey(
        Difficulty,
        verbose_name='Сложность Вопроса',
        related_name='question_clone',
        on_delete=models.CASCADE,
        db_index=True,
        blank=False,
        default=None,
        null=True
    )
    payload = models.OneToOneField(
        Payload,
        on_delete=models.CASCADE,
        related_name='question_clone',
        null=True,
        blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=['question', 'text', 'question_type']),
        ]
        verbose_name = _('Копия Вопроса')
        verbose_name_plural = _('Копии Вопросов')

    def __str__(self):
        return f"{self.text} ({self.get_question_type_display()})"

    def clean(self):
        expected_payload_model = {
            'single_choice': SingleChoicePayload,
            'multiple_choice': MultipleChoicePayload,
            'open': OpenPayload,
            'matching': MatchingPayload,
            'value_for_keys': ValueForKeysPayload,
            'essay': EssayPayload,
            'sentence_creation': SentenceCreationPayload,
            'blank': BlankPayload,
            'text_analysis': TextAnalysisPayload,
            'order': OrderPayload,
            'dialog': DialogPayload,
        }.get(self.question_type)

        if expected_payload_model is None:
            raise ValidationError('Неверный тип вопроса: %s' % self.question_type)

        if not isinstance(self.payload, expected_payload_model):
            raise ValidationError(
                'Payload должен быть типа %s для вопроса типа %s.' % (
                expected_payload_model.__name__, self.question_type)
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)



class QuestionAndStudentRecord(models.Model):
    question = models.ForeignKey(Question, verbose_name=_('Вопрос'), blank=False, on_delete=models.CASCADE,
                                 db_index=True, related_name='training_question_student_answer')
    question_clone = models.ForeignKey(QuestionClone, verbose_name=_('Клон Вопрос'), blank=True,
                                       on_delete=models.CASCADE, default=None, null=True,
                                       db_index=True, related_name='training_question_student_answer')
    student = models.ForeignKey(CustomUser, verbose_name=_('Студент'), blank=False,
                                related_name='training_question_student_answer', limit_choices_to={'role': 'student'},
                                on_delete=models.CASCADE, db_index=True)
    student_response = models.JSONField(_('Ответ Студента'), blank=False, null=False, default=dict)

    points = models.PositiveSmallIntegerField(default=0, blank=True, verbose_name="Засчитанный Балл")
    max_points = models.PositiveSmallIntegerField(default=1, blank=True, verbose_name="Максимальный балл")

    is_correct = models.BooleanField(
        verbose_name="Засчитан верным",
        blank=False,
        default=None,
        null=True
    )

    allowed_to_proceed = models.BooleanField(
        verbose_name="Разрешено продолжить",
        blank=False,
        default=None,
        null=True
    )

    ai_response = models.CharField(verbose_name='Ответ ИИ', max_length=1000, blank=True, default='')
    non_relevant = models.BooleanField(
        verbose_name="Неуместный ответ",
        blank=False,
        default=None,
        null=True
    )
    teacher_remarks = models.CharField(verbose_name='Заметка от Учителя', max_length=1000, blank=True, default='')
    date = models.DateTimeField(verbose_name=_('Дата Ответа'), null=True, default=None, blank=False)

    class Meta:
        indexes = [
            models.Index(fields=['question', 'student']),
        ]
        verbose_name = _('Ответ Студента на Вопрос')
        verbose_name_plural = _('Ответы Студентов на Вопросы')

    def __str__(self):
        return self.question.text

    def clean(self):
        super().clean()
        if self.question.test:
            cache_key = f'student_{self.student.id}_test_{self.question.test.id}_current_question'
            cache.delete(cache_key)

            question_type = self.question.question_type
            response = self.student_response

            if question_type in ['single_choice', 'open', 'essay', 'sentence_creation', 'text_analysis', 'dialog']:
                if not isinstance(response, str):
                    raise ValidationError({
                        'detail': _(f'Для типа  "{question_type}" ответ студента должен быть строкой.')
                    })
            elif question_type in ['multiple_choice', 'blank', 'order']:
                if not isinstance(response, list):
                    raise ValidationError({
                        'detail': _(f'Для типа "{question_type}" ответ студента должен быть списком.')
                    })
            elif question_type in ['matching', 'value_for_keys']:
                if not isinstance(response, dict):
                    raise ValidationError({
                        'detail': _(f'Для типа  "{question_type}" ответ студента должен быть объектом (словарем).')
                    })


    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.test:
            cache_key = f'student_{self.student.id}_test_{self.test.id}_current_question'
            cache.delete(cache_key)
        # Delete the object
        super().delete(*args, **kwargs)


class QuestionAppeal(models.Model):
    STATUS_CHOICES = {
        ('new', _('Новая')),
        ('on_review', _('На рассмотрении')),
        ('satisfied', _('Удовлетворенна')),
        ('not-satisfied', _('Не удовлетворена'))
    }
    description = models.CharField(_("Описание Аппеляции"), max_length=2000)

    question = models.ForeignKey(Question, verbose_name=_('Вопрос'), blank=True, default=None, null=True,
                                 on_delete=models.CASCADE,
                                 db_index=True, related_name='question_appeal')
    question_clone = models.ForeignKey(QuestionClone, verbose_name=_('Клон Вопрос'), blank=True,
                                       on_delete=models.CASCADE, default=None, null=True,
                                       db_index=True, related_name='question_appeal')
    student = models.ForeignKey(CustomUser, verbose_name=_('Студент'), blank=False,
                                related_name='question_appeal', limit_choices_to={'role': 'student'},
                                on_delete=models.CASCADE, db_index=True)
    status = models.CharField(_("статус"), max_length=50, choices=STATUS_CHOICES, blank=False, db_index=True)
    created_at = models.DateTimeField(
        verbose_name=_('Дата создания'),
        auto_now_add=True,
        blank=False,
        null=True
    )
    updated_at = models.DateTimeField(
        verbose_name=_('Дата обновления'),
        auto_now=True,
        blank=False,
        null=True
    )

    class Meta:
        indexes = [
            models.Index(fields=['student', 'question', 'question_clone']),
        ]
        verbose_name = _('Аппеляция')
        verbose_name_plural = _('Аппеляция')

    def __str__(self):
        return f'Аппеляция_{self.question_clone.text}_{self.student.last_name}' if self.question_clone else \
            f'Аппеляция_{self.question.text}_{self.student.last_name}'


class SubjectTrainingStat(models.Model):
    DIFFICULTY_CHOICES = (
        ('base', _('Легкий')),
        ('medium', _('Средний')),
        ('advanced', _('Продвинутый')),
        ('c-level', _('С-уровень'))
    )
    student = models.ForeignKey(CustomUser, verbose_name=_('Студент'), blank=False,
                                related_name='subject_training_stat', limit_choices_to={'role': 'student'},
                                on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, verbose_name=_('Предмет'), blank=False,
                                related_name='subject_training_stat',
                                on_delete=models.CASCADE)
    level = models.ForeignKey(
        Difficulty,
        verbose_name='Уровень',
        related_name='subject_training_stat',
        on_delete=models.CASCADE,
        db_index=True,
        blank=False,
        default=None,
        null=True

    )
    tests_count = models.IntegerField(default=0, verbose_name=_('Колличество Теcтов'))
    finished_tests_count = models.IntegerField(default=0, verbose_name=_('Колличество Завершенных Теcтов'))
    performance = models.IntegerField(verbose_name=_('Успеваемость'))

    class Meta:
        verbose_name = _('Статистика на Предмет')
        verbose_name_plural = _('Статистика на Предметы')
        indexes = [
            models.Index(fields=['student', 'subject']),
        ]

    def __str__(self):
        return f'{self.subject.__str__()}_{self.student.get_full_name()}'


class ETestStatus(models.TextChoices):
    FINISHED = 'finished', 'Finished'
    IN_PROGRESS = 'in_progress', 'In Progress'
    NOT_AVAILABLE = 'not_available', 'Not Available'


class SectionTrainingStat(models.Model):
    DIFFICULTY_CHOICES = (
        ('base', _('Легкий')),
        ('medium', _('Средний')),
        ('advanced', _('Продвинутый')),
        ('c-level', _('С-уровень'))
    )
    student = models.ForeignKey(CustomUser, verbose_name=_('Студент'), blank=False,
                                related_name='section_training_stat', limit_choices_to={'role': 'student'},
                                on_delete=models.CASCADE)
    section = models.ForeignKey(Section, verbose_name=_('Раздел'), null=True, blank=False,
                                related_name='section_training_stat',
                                on_delete=models.CASCADE)

    topics_count = models.IntegerField(verbose_name=_('Колличество Тем'))
    finished_topics_count = models.IntegerField(verbose_name=_('Колличество Завершенных Тем'))

    class Meta:
        verbose_name = _('Статистика на Раздел')
        verbose_name_plural = _('Статистика на Разделы')
        indexes = [
            models.Index(fields=['student', 'section']),
        ]

    def get_status(self):
        if self.topics_count == self.finished_topics_count:
            return ETestStatus.FINISHED
        else:
            return ETestStatus.IN_PROGRESS

    def __str__(self):
        return f'{self.section.name}_{self.student.first_name}_{self.student.last_name}'


class TopicTrainingStat(models.Model):
    student = models.ForeignKey(CustomUser, verbose_name=_('Студент'), blank=False,
                                related_name='topic_training_stat', limit_choices_to={'role': 'student'},
                                on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, verbose_name=_('Тема'), blank=False, default=None, null=True,
                              related_name='topic_training_stat',
                              on_delete=models.CASCADE)
    tests_count = models.IntegerField(verbose_name=_('Колличество Тестов'))
    finished_tests_count = models.IntegerField(verbose_name=_('Колличество Завершенных  Тестов'))

    level = models.ForeignKey(
        Difficulty,
        verbose_name='Уровень',
        related_name='topic_training_stat',
        on_delete=models.CASCADE,
        db_index=True,
        blank=False,
        default=None,
        null=True

    )

    class Meta:
        verbose_name = _('Статистика на Тему')
        verbose_name_plural = _('Статистика на Темы')
        indexes = [
            models.Index(fields=['student', 'topic']),
        ]

    def get_finished_tests_count(self):
        if self.topic:
            finished_tests_count = TestTrainingStat.objects.filter(test__topic=self.topic, student=self.student).count()
        else:
            finished_tests_count = 0
        self.finished_tests_count = finished_tests_count
        return finished_tests_count

    def get_tests_count(self):
        if self.topic:
            test_queryset = Test.objects.filter(topic=self.topic)
            tests = list(test_queryset)
            tests_count = 0

            if not tests:
                for i in range(1, 4):
                    Test.objects.create(topic=self.topic, order=i)

            test_queryset = Test.objects.filter(topic=self.topic)
            tests = list(test_queryset)

            for test in tests:
                questions = Question.objects.filter(test=test, test_levels=self.level)
                if len(questions) > 0:
                    tests_count += 1

            self.tests_count = tests_count
            return tests_count
        else:
            return self.tests_count

    def get_status(self):
        if self.tests_count == self.finished_tests_count and self.tests_count != 0:
            return ETestStatus.FINISHED
        else:
            return ETestStatus.IN_PROGRESS

    def __str__(self):
        return f'{self.topic.name}_{self.student.first_name}_{self.student.last_name}'


class TestTrainingStat(models.Model):
    student = models.ForeignKey(CustomUser, verbose_name=_('Студент'), blank=False,
                                related_name='test_training_stat', limit_choices_to={'role': 'student'},
                                on_delete=models.CASCADE)
    test = models.ForeignKey(Test, verbose_name=_('Тренивочный Тест'), blank=False,
                             related_name='test_training_stat',
                             on_delete=models.CASCADE, db_index=True)

    class Meta:
        verbose_name = _('Статистика на Тест')
        verbose_name_plural = _('Статистика на Тесты')

    def __str__(self):
        return f'{self.test.topic.name}_{self.student.first_name}_{self.student.last_name}'


