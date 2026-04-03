"""
Mongoengine documents for the cv app.
The entire CV is stored as a single MongoDB document for fast retrieval.
"""

import mongoengine as me
from datetime import datetime


class PersonalInfo(me.EmbeddedDocument):
    full_name = me.StringField(max_length=255, default='')
    # StringField instead of EmailField/URLField so empty strings are valid.
    # Validation of format is handled by the DRF serializer layer.
    email = me.StringField(max_length=254, default='')
    phone = me.StringField(max_length=30, default='')
    address = me.StringField(max_length=500, default='')
    city = me.StringField(max_length=100, default='')
    country = me.StringField(max_length=100, default='')
    linkedin = me.StringField(max_length=500, default='')
    github = me.StringField(max_length=500, default='')
    website = me.StringField(max_length=500, default='')
    summary = me.StringField(default='')


class Experience(me.EmbeddedDocument):
    company = me.StringField(max_length=255, required=True)
    position = me.StringField(max_length=255, required=True)
    location = me.StringField(max_length=255, default='')
    start_date = me.StringField(max_length=10)   # "YYYY-MM" or "YYYY-MM-DD"
    end_date = me.StringField(max_length=10, default='')
    is_current = me.BooleanField(default=False)
    description = me.StringField(default='')
    order = me.IntField(default=0)


class Education(me.EmbeddedDocument):
    institution = me.StringField(max_length=255, required=True)
    degree = me.StringField(max_length=255, required=True)
    field_of_study = me.StringField(max_length=255, default='')
    location = me.StringField(max_length=255, default='')
    start_date = me.StringField(max_length=10)
    end_date = me.StringField(max_length=10, default='')
    is_current = me.BooleanField(default=False)
    gpa = me.StringField(max_length=10, default='')
    description = me.StringField(default='')
    order = me.IntField(default=0)


class Skill(me.EmbeddedDocument):
    name = me.StringField(max_length=100, required=True)
    level = me.StringField(
        max_length=20,
        choices=['beginner', 'intermediate', 'advanced', 'expert'],
        default='intermediate',
    )
    category = me.StringField(max_length=100, default='')
    order = me.IntField(default=0)


class Language(me.EmbeddedDocument):
    name = me.StringField(max_length=100, required=True)
    proficiency = me.StringField(
        max_length=20,
        choices=['basic', 'conversational', 'fluent', 'native'],
        default='conversational',
    )


class Certificate(me.EmbeddedDocument):
    name = me.StringField(max_length=255, required=True)
    issuer = me.StringField(max_length=255, required=True)
    issue_date = me.StringField(max_length=10)
    expiry_date = me.StringField(max_length=10, default='')
    credential_url = me.StringField(max_length=500, default='')
    description = me.StringField(default='')


class CV(me.Document):
    title = me.StringField(max_length=255, default='My CV')
    template_choice = me.IntField(default=1, choices=[1, 2, 3])

    # Ownership — one of these two will be set
    user_id = me.StringField()       # str(user.id) for authenticated users
    session_key = me.StringField()   # for anonymous users

    is_public = me.BooleanField(default=False)

    personal_info = me.EmbeddedDocumentField(PersonalInfo, default=PersonalInfo)
    experiences = me.EmbeddedDocumentListField(Experience, default=list)
    education = me.EmbeddedDocumentListField(Education, default=list)
    skills = me.EmbeddedDocumentListField(Skill, default=list)
    languages = me.EmbeddedDocumentListField(Language, default=list)
    certificates = me.EmbeddedDocumentListField(Certificate, default=list)

    created_at = me.DateTimeField(default=datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'cvs',
        'indexes': ['user_id', 'session_key', '-updated_at'],
        'ordering': ['-updated_at'],
    }

    def touch(self) -> None:
        """Update the updated_at timestamp and save."""
        self.updated_at = datetime.utcnow()
        self.save()
