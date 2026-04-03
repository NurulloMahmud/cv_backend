"""
Plain DRF serializers for the cv app.
Mirrors the mongoengine EmbeddedDocument structure.
"""

from rest_framework import serializers

from .documents import CV, Certificate, Education, Experience, Language, PersonalInfo, Skill


# ---------------------------------------------------------------------------
# Embedded document serializers
# ---------------------------------------------------------------------------

class PersonalInfoSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    email = serializers.EmailField(required=False, default='', allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, default='', allow_blank=True)
    address = serializers.CharField(max_length=500, required=False, default='', allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    linkedin = serializers.URLField(required=False, default='', allow_blank=True)
    github = serializers.URLField(required=False, default='', allow_blank=True)
    website = serializers.URLField(required=False, default='', allow_blank=True)
    summary = serializers.CharField(required=False, default='', allow_blank=True)


class ExperienceSerializer(serializers.Serializer):
    company = serializers.CharField(max_length=255)
    position = serializers.CharField(max_length=255)
    location = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    start_date = serializers.CharField(max_length=10, required=False, allow_blank=True)
    end_date = serializers.CharField(max_length=10, required=False, default='', allow_blank=True)
    is_current = serializers.BooleanField(required=False, default=False)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    order = serializers.IntegerField(required=False, default=0)


class EducationSerializer(serializers.Serializer):
    institution = serializers.CharField(max_length=255)
    degree = serializers.CharField(max_length=255)
    field_of_study = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    location = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    start_date = serializers.CharField(max_length=10, required=False, allow_blank=True)
    end_date = serializers.CharField(max_length=10, required=False, default='', allow_blank=True)
    is_current = serializers.BooleanField(required=False, default=False)
    gpa = serializers.CharField(max_length=10, required=False, default='', allow_blank=True)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    order = serializers.IntegerField(required=False, default=0)


class SkillSerializer(serializers.Serializer):
    LEVEL_CHOICES = ['beginner', 'intermediate', 'advanced', 'expert']

    name = serializers.CharField(max_length=100)
    level = serializers.ChoiceField(choices=LEVEL_CHOICES, default='intermediate')
    category = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    order = serializers.IntegerField(required=False, default=0)


class LanguageSerializer(serializers.Serializer):
    PROFICIENCY_CHOICES = ['basic', 'conversational', 'fluent', 'native']

    name = serializers.CharField(max_length=100)
    proficiency = serializers.ChoiceField(choices=PROFICIENCY_CHOICES, default='conversational')


class CertificateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    issuer = serializers.CharField(max_length=255)
    issue_date = serializers.CharField(max_length=10, required=False, allow_blank=True)
    expiry_date = serializers.CharField(max_length=10, required=False, default='', allow_blank=True)
    credential_url = serializers.URLField(required=False, default='', allow_blank=True)
    description = serializers.CharField(required=False, default='', allow_blank=True)


# ---------------------------------------------------------------------------
# Full CV serializer
# ---------------------------------------------------------------------------

class CVSerializer(serializers.Serializer):
    """Full CV serializer — used for detail GET and PUT responses."""

    id = serializers.SerializerMethodField()
    title = serializers.CharField(max_length=255, required=False, default='My CV')
    template_choice = serializers.IntegerField(
        min_value=1, max_value=3, required=False, default=1
    )
    user_id = serializers.CharField(read_only=True)
    session_key = serializers.CharField(read_only=True)
    is_public = serializers.BooleanField(required=False, default=False)

    personal_info = PersonalInfoSerializer(required=False)
    experiences = ExperienceSerializer(many=True, required=False, default=list)
    education = EducationSerializer(many=True, required=False, default=list)
    skills = SkillSerializer(many=True, required=False, default=list)
    languages = LanguageSerializer(many=True, required=False, default=list)
    certificates = CertificateSerializer(many=True, required=False, default=list)

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_id(self, obj) -> str:
        return str(obj.id)

    def _build_embedded(self, cls, data: dict):
        """Instantiate a mongoengine EmbeddedDocument from a dict."""
        return cls(**data) if data else cls()

    def _build_embedded_list(self, cls, data_list: list) -> list:
        return [cls(**item) for item in data_list]

    def create(self, validated_data: dict) -> CV:
        personal_info_data = validated_data.pop('personal_info', {})
        experiences_data = validated_data.pop('experiences', [])
        education_data = validated_data.pop('education', [])
        skills_data = validated_data.pop('skills', [])
        languages_data = validated_data.pop('languages', [])
        certificates_data = validated_data.pop('certificates', [])

        cv = CV(
            **validated_data,
            personal_info=self._build_embedded(PersonalInfo, personal_info_data),
            experiences=self._build_embedded_list(Experience, experiences_data),
            education=self._build_embedded_list(Education, education_data),
            skills=self._build_embedded_list(Skill, skills_data),
            languages=self._build_embedded_list(Language, languages_data),
            certificates=self._build_embedded_list(Certificate, certificates_data),
        )
        cv.save()
        return cv

    def update(self, instance: CV, validated_data: dict) -> CV:
        from datetime import datetime

        personal_info_data = validated_data.pop('personal_info', None)
        experiences_data = validated_data.pop('experiences', None)
        education_data = validated_data.pop('education', None)
        skills_data = validated_data.pop('skills', None)
        languages_data = validated_data.pop('languages', None)
        certificates_data = validated_data.pop('certificates', None)

        # Update top-level fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update embedded documents if provided
        if personal_info_data is not None:
            instance.personal_info = self._build_embedded(PersonalInfo, personal_info_data)
        if experiences_data is not None:
            instance.experiences = self._build_embedded_list(Experience, experiences_data)
        if education_data is not None:
            instance.education = self._build_embedded_list(Education, education_data)
        if skills_data is not None:
            instance.skills = self._build_embedded_list(Skill, skills_data)
        if languages_data is not None:
            instance.languages = self._build_embedded_list(Language, languages_data)
        if certificates_data is not None:
            instance.certificates = self._build_embedded_list(Certificate, certificates_data)

        instance.updated_at = datetime.utcnow()
        instance.save()
        return instance


# ---------------------------------------------------------------------------
# Lightweight list serializer
# ---------------------------------------------------------------------------

class CVListSerializer(serializers.Serializer):
    """Lightweight serializer for the CV list endpoint — no embedded detail."""

    id = serializers.SerializerMethodField()
    title = serializers.CharField()
    template_choice = serializers.IntegerField()
    is_public = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    # Expose the person's name for quick display
    full_name = serializers.SerializerMethodField()

    def get_id(self, obj) -> str:
        return str(obj.id)

    def get_full_name(self, obj) -> str:
        if obj.personal_info:
            return obj.personal_info.full_name or ''
        return ''
