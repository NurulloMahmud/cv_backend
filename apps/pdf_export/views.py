"""
PDF Export views for TezCV.uz.
Generates PDFs programmatically using reportlab (no system dependencies).
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
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cv_for_export(request, cv_id: str):
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


def _safe_str(value, default='') -> str:
    return str(value) if value else default


def _build_pdf(cv) -> bytes:
    """Generate a clean A4 CV PDF using reportlab Platypus."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    # ── Styles ──────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()

    name_style = ParagraphStyle(
        'Name', parent=base['Normal'],
        fontSize=22, leading=26, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a1a2e'), alignment=TA_LEFT,
    )
    title_style = ParagraphStyle(
        'JobTitle', parent=base['Normal'],
        fontSize=12, leading=16, fontName='Helvetica',
        textColor=colors.HexColor('#555555'), alignment=TA_LEFT,
    )
    contact_style = ParagraphStyle(
        'Contact', parent=base['Normal'],
        fontSize=9, leading=13, fontName='Helvetica',
        textColor=colors.HexColor('#444444'),
    )
    section_heading = ParagraphStyle(
        'SectionHeading', parent=base['Normal'],
        fontSize=11, leading=14, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a1a2e'),
        spaceAfter=2,
    )
    item_title = ParagraphStyle(
        'ItemTitle', parent=base['Normal'],
        fontSize=10, leading=13, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#222222'),
    )
    item_sub = ParagraphStyle(
        'ItemSub', parent=base['Normal'],
        fontSize=9, leading=12, fontName='Helvetica-Oblique',
        textColor=colors.HexColor('#666666'),
    )
    body_style = ParagraphStyle(
        'Body', parent=base['Normal'],
        fontSize=9, leading=13, fontName='Helvetica',
        textColor=colors.HexColor('#333333'),
    )
    bullet_style = ParagraphStyle(
        'Bullet', parent=body_style,
        leftIndent=8, bulletIndent=0,
    )

    HR = lambda: HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=4)
    SP = lambda h=4: Spacer(1, h * mm)

    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    pi = cv.personal_info
    full_name = _safe_str(getattr(pi, 'full_name', '')) or cv.title or 'CV'
    story.append(Paragraph(full_name, name_style))

    job_title = _safe_str(getattr(pi, 'job_title', ''))
    if job_title:
        story.append(Paragraph(job_title, title_style))

    story.append(SP(2))

    # Contact line
    contact_parts = []
    for attr, label in [('email', None), ('phone', None), ('location', None),
                        ('linkedin', 'LinkedIn'), ('github', 'GitHub'), ('website', None)]:
        val = _safe_str(getattr(pi, attr, ''))
        if val:
            contact_parts.append(f'{label}: {val}' if label else val)
    if contact_parts:
        story.append(Paragraph('  ·  '.join(contact_parts), contact_style))

    story.append(SP(3))
    story.append(HR())

    # ── Summary ──────────────────────────────────────────────────────────────
    summary = _safe_str(getattr(pi, 'summary', ''))
    if summary:
        story.append(SP(2))
        story.append(Paragraph('PROFILE', section_heading))
        story.append(HR())
        story.append(Paragraph(summary, body_style))
        story.append(SP(3))

    # ── Experience ───────────────────────────────────────────────────────────
    experiences = sorted(cv.experiences, key=lambda e: (e.order, e.start_date or ''))
    if experiences:
        story.append(Paragraph('EXPERIENCE', section_heading))
        story.append(HR())
        for exp in experiences:
            company = _safe_str(getattr(exp, 'company', ''))
            position = _safe_str(getattr(exp, 'position', ''))
            start = _safe_str(getattr(exp, 'start_date', ''))
            end = _safe_str(getattr(exp, 'end_date', '')) or ('Present' if getattr(exp, 'is_current', False) else '')
            location = _safe_str(getattr(exp, 'location', ''))

            date_range = f'{start} – {end}' if start or end else ''
            right_text = '  ·  '.join(filter(None, [date_range, location]))

            # Title row: position left, date right
            title_data = [[
                Paragraph(position or company, item_title),
                Paragraph(right_text, ParagraphStyle('Right', parent=item_sub, alignment=2)),
            ]]
            title_table = Table(title_data, colWidths=['70%', '30%'])
            title_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            story.append(title_table)

            if position and company:
                story.append(Paragraph(company, item_sub))

            desc = _safe_str(getattr(exp, 'description', ''))
            if desc:
                for line in desc.split('\n'):
                    line = line.strip()
                    if line:
                        story.append(Paragraph(f'• {line}', bullet_style))
            story.append(SP(3))

    # ── Education ────────────────────────────────────────────────────────────
    education = sorted(cv.education, key=lambda e: (e.order, e.start_date or ''))
    if education:
        story.append(Paragraph('EDUCATION', section_heading))
        story.append(HR())
        for edu in education:
            institution = _safe_str(getattr(edu, 'institution', ''))
            degree = _safe_str(getattr(edu, 'degree', ''))
            field = _safe_str(getattr(edu, 'field_of_study', ''))
            start = _safe_str(getattr(edu, 'start_date', ''))
            end = _safe_str(getattr(edu, 'end_date', '')) or ('Present' if getattr(edu, 'is_current', False) else '')
            date_range = f'{start} – {end}' if start or end else ''

            degree_field = ', '.join(filter(None, [degree, field]))
            title_data = [[
                Paragraph(degree_field or institution, item_title),
                Paragraph(date_range, ParagraphStyle('Right', parent=item_sub, alignment=2)),
            ]]
            title_table = Table(title_data, colWidths=['70%', '30%'])
            title_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            story.append(title_table)
            if degree_field and institution:
                story.append(Paragraph(institution, item_sub))

            desc = _safe_str(getattr(edu, 'description', ''))
            if desc:
                story.append(Paragraph(desc, body_style))
            story.append(SP(3))

    # ── Skills ───────────────────────────────────────────────────────────────
    skills = sorted(cv.skills, key=lambda s: (s.order, s.category or '', s.name))
    if skills:
        story.append(Paragraph('SKILLS', section_heading))
        story.append(HR())

        # Group by category
        categories: dict = {}
        for skill in skills:
            cat = _safe_str(getattr(skill, 'category', '')) or 'General'
            categories.setdefault(cat, []).append(_safe_str(skill.name))

        for cat, names in categories.items():
            if cat != 'General':
                line = f'<b>{cat}:</b>  {", ".join(names)}'
            else:
                line = ', '.join(names)
            story.append(Paragraph(line, body_style))
        story.append(SP(3))

    # ── Languages ────────────────────────────────────────────────────────────
    languages = sorted(cv.languages, key=lambda la: la.name)
    if languages:
        story.append(Paragraph('LANGUAGES', section_heading))
        story.append(HR())
        lang_parts = []
        for lang in languages:
            name = _safe_str(lang.name)
            level = _safe_str(getattr(lang, 'proficiency', ''))
            lang_parts.append(f'{name} ({level})' if level else name)
        story.append(Paragraph(', '.join(lang_parts), body_style))
        story.append(SP(3))

    # ── Certificates ─────────────────────────────────────────────────────────
    certificates = sorted(cv.certificates, key=lambda c: c.issue_date or '', reverse=True)
    if certificates:
        story.append(Paragraph('CERTIFICATES', section_heading))
        story.append(HR())
        for cert in certificates:
            name = _safe_str(getattr(cert, 'name', ''))
            issuer = _safe_str(getattr(cert, 'issuer', ''))
            date = _safe_str(getattr(cert, 'issue_date', ''))
            right = '  ·  '.join(filter(None, [issuer, date]))
            title_data = [[
                Paragraph(name, item_title),
                Paragraph(right, ParagraphStyle('Right', parent=item_sub, alignment=2)),
            ]]
            title_table = Table(title_data, colWidths=['70%', '30%'])
            title_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            story.append(title_table)
            story.append(SP(2))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


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
        cv, error = _get_cv_for_export(request, pk)
        if error:
            return error

        if not PDF_AVAILABLE:
            return Response(
                {
                    'detail': 'PDF generation is not available. reportlab is not installed.',
                    'hint': 'Run: pip install reportlab',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            pdf_bytes = _build_pdf(cv)
        except Exception as exc:
            return Response(
                {'detail': f'Failed to generate PDF: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        pi = cv.personal_info
        name_part = ''
        full_name = _safe_str(getattr(pi, 'full_name', ''))
        if full_name:
            name_part = f'_{slugify(full_name)}'
        filename = f'tezcv{name_part}_cv_{pk}.pdf'

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
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

        from django.template.loader import render_to_string

        TEMPLATE_MAP = {
            1: 'cv_template_1.html',
            2: 'cv_template_2.html',
            3: 'cv_template_1.html',
        }

        pi = cv.personal_info
        experiences = sorted(cv.experiences, key=lambda e: (e.order, e.start_date or ''))
        education = sorted(cv.education, key=lambda e: (e.order, e.start_date or ''))
        skills = sorted(cv.skills, key=lambda s: (s.order, s.category or '', s.name))
        languages = sorted(cv.languages, key=lambda la: la.name)
        certificates = sorted(cv.certificates, key=lambda c: c.issue_date or '', reverse=True)

        skill_categories: dict = {}
        for skill in skills:
            cat = skill.category or 'General'
            skill_categories.setdefault(cat, []).append(skill)

        context = {
            'cv': cv,
            'personal_info': pi,
            'experiences': experiences,
            'education': education,
            'skills': skills,
            'skill_categories': skill_categories,
            'languages': languages,
            'certificates': certificates,
        }

        template_name = TEMPLATE_MAP.get(cv.template_choice, 'cv_template_1.html')
        html_string = render_to_string(template_name, context, request=request)
        return HttpResponse(html_string, content_type='text/html')
