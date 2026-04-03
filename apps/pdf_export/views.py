"""
PDF Export views for TezCV.uz.
Fetches CV documents from MongoDB, renders HTML templates, returns PDF via WeasyPrint.
"""

import io

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cv.documents import CV

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False
    HTML = None


TEMPLATE_MAP = {
    1: 'cv_template_1.html',
    2: 'cv_template_2.html',
    3: 'cv_template_1.html',  # fallback for template choice 3
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cv_for_export(request, cv_id: str):
    """
    Retrieve a CV and check that the requester has permission to export it.
    Returns (cv, error_response). One of the two will be None.
    """
    try:
        cv = CV.objects.get(id=cv_id)
    except (CV.DoesNotExist, Exception):
        return None, Response({'detail': 'CV not found.'}, status=status.HTTP_404_NOT_FOUND)

    user = getattr(request, 'user', None)
    is_authed = user and getattr(user, 'is_authenticated', False)

    if is_authed:
        if cv.user_id != str(user.id) and not cv.is_public:
            return None, Response(
                {'detail': 'You do not have permission to export this CV.'},
                status=status.HTTP_403_FORBIDDEN,
            )
    else:
        if not cv.is_public:
            session_key = request.META.get('HTTP_X_SESSION_KEY', '')
            if cv.session_key != session_key:
                return None, Response(
                    {'detail': 'You do not have permission to export this CV.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

    return cv, None


def _build_cv_context(cv: CV) -> dict:
    """Build the template context dict from a CV mongoengine document."""
    personal_info = cv.personal_info

    # Sort embedded lists for consistent PDF output
    experiences = sorted(cv.experiences, key=lambda e: (e.order, e.start_date or ''))
    education = sorted(cv.education, key=lambda e: (e.order, e.start_date or ''))
    skills = sorted(cv.skills, key=lambda s: (s.order, s.category or '', s.name))
    languages = sorted(cv.languages, key=lambda la: la.name)
    certificates = sorted(cv.certificates, key=lambda c: c.issue_date or '', reverse=True)

    # Group skills by category (used by template 2)
    skill_categories: dict = {}
    for skill in skills:
        cat = skill.category or 'General'
        skill_categories.setdefault(cat, []).append(skill)

    return {
        'cv': cv,
        'personal_info': personal_info,
        'experiences': experiences,
        'education': education,
        'skills': skills,
        'skill_categories': skill_categories,
        'languages': languages,
        'certificates': certificates,
    }


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class CVExportPDFView(APIView):
    """
    GET /api/pdf/<id>/export-pdf/
    Generate and download a PDF version of a CV.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        # Check CV existence and permissions first (so 404/403 are returned correctly
        # even when WeasyPrint is not available on the current machine).
        cv, error = _get_cv_for_export(request, pk)
        if error:
            return error

        if not WEASYPRINT_AVAILABLE:
            return Response(
                {
                    'detail': 'PDF generation is not available. WeasyPrint is not installed.',
                    'hint': 'Run: pip install WeasyPrint',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        template_name = TEMPLATE_MAP.get(cv.template_choice, 'cv_template_1.html')
        context = _build_cv_context(cv)

        html_string = render_to_string(template_name, context, request=request)

        pdf_file = io.BytesIO()
        HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(pdf_file)
        pdf_file.seek(0)

        # Build a clean filename
        personal_info = context.get('personal_info')
        name_part = ''
        if personal_info and getattr(personal_info, 'full_name', ''):
            name_part = f'_{slugify(personal_info.full_name)}'
        filename = f'tezcv{name_part}_cv_{pk}.pdf'

        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-CV-ID'] = str(pk)
        response['X-CV-Title'] = cv.title
        return response


class CVPreviewHTMLView(APIView):
    """
    GET /api/pdf/<id>/preview/
    Return the rendered HTML of a CV (useful for debugging templates).
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        cv, error = _get_cv_for_export(request, pk)
        if error:
            return error

        template_name = TEMPLATE_MAP.get(cv.template_choice, 'cv_template_1.html')
        context = _build_cv_context(cv)
        html_string = render_to_string(template_name, context, request=request)
        return HttpResponse(html_string, content_type='text/html')
