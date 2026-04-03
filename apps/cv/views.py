"""
CV views for TezCV.uz.

All endpoints use APIView.
Ownership is determined by user_id (authenticated) or session_key (anonymous).
The X-Session-Key request header is used for anonymous session identification.
"""

import uuid

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .documents import CV
from .serializers import CVListSerializer, CVSerializer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session_key(request) -> str:
    """
    Return the session key from the X-Session-Key header.
    If absent, generate a new UUID and note it should be returned to the client.
    """
    return request.META.get('HTTP_X_SESSION_KEY', '') or str(uuid.uuid4())


def _build_query(request):
    """
    Return (queryset_filter_kwargs, session_key).
    Authenticated users filter by user_id; anonymous by session_key.
    """
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        return {'user_id': str(user.id)}, None

    session_key = _get_session_key(request)
    return {'session_key': session_key}, session_key


def _get_cv_or_404(cv_id: str, request):
    """
    Fetch a CV by id and verify ownership.
    Returns (cv, error_response) — one of the two will be None.
    """
    try:
        cv = CV.objects.get(id=cv_id)
    except (CV.DoesNotExist, Exception):
        return None, Response({'detail': 'CV not found.'}, status=status.HTTP_404_NOT_FOUND)

    user = getattr(request, 'user', None)
    is_authed = user and getattr(user, 'is_authenticated', False)

    if is_authed:
        if cv.user_id != str(user.id):
            # Allow viewing public CVs; deny modification (checked in view)
            if not cv.is_public:
                return None, Response(
                    {'detail': 'You do not have permission to access this CV.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
    else:
        if not cv.is_public:
            session_key = request.META.get('HTTP_X_SESSION_KEY', '')
            if cv.session_key != session_key:
                return None, Response(
                    {'detail': 'You do not have permission to access this CV.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

    return cv, None


def _owns_cv(cv: CV, request) -> bool:
    """Return True only if the requester is the owner (not just a viewer of a public CV)."""
    user = getattr(request, 'user', None)
    is_authed = user and getattr(user, 'is_authenticated', False)
    if is_authed:
        return cv.user_id == str(user.id)
    session_key = request.META.get('HTTP_X_SESSION_KEY', '')
    return cv.session_key == session_key


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class CVListCreateView(APIView):
    """
    GET  /api/cv/  — List all CVs belonging to the current user or session.
    POST /api/cv/  — Create a new CV.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        filter_kwargs, session_key = _build_query(request)
        cvs = CV.objects(**filter_kwargs).order_by('-updated_at')
        serializer = CVListSerializer(cvs, many=True)
        response = Response(serializer.data)
        if session_key:
            response['X-Session-Key'] = session_key
        return response

    def post(self, request):
        serializer = CVSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = getattr(request, 'user', None)
        is_authed = user and getattr(user, 'is_authenticated', False)

        # Inject ownership before saving
        validated = serializer.validated_data
        session_key = None
        if is_authed:
            validated['user_id'] = str(user.id)
            validated.pop('session_key', None)
        else:
            session_key = _get_session_key(request)
            validated['session_key'] = session_key
            validated.pop('user_id', None)

        cv = serializer.save()
        response = Response(CVSerializer(cv).data, status=status.HTTP_201_CREATED)
        if session_key:
            response['X-Session-Key'] = session_key
        return response


class CVDetailView(APIView):
    """
    GET    /api/cv/<id>/  — Retrieve a CV (full nested).
    PUT    /api/cv/<id>/  — Replace/update a CV.
    PATCH  /api/cv/<id>/  — Partially update a CV.
    DELETE /api/cv/<id>/  — Delete a CV.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        cv, error = _get_cv_or_404(pk, request)
        if error:
            return error
        return Response(CVSerializer(cv).data)

    def put(self, request, pk):
        cv, error = _get_cv_or_404(pk, request)
        if error:
            return error
        if not _owns_cv(cv, request):
            return Response(
                {'detail': 'You do not have permission to update this CV.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CVSerializer(cv, data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_cv = serializer.save()
        return Response(CVSerializer(updated_cv).data)

    def patch(self, request, pk):
        cv, error = _get_cv_or_404(pk, request)
        if error:
            return error
        if not _owns_cv(cv, request):
            return Response(
                {'detail': 'You do not have permission to update this CV.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CVSerializer(cv, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_cv = serializer.save()
        return Response(CVSerializer(updated_cv).data)

    def delete(self, request, pk):
        cv, error = _get_cv_or_404(pk, request)
        if error:
            return error
        if not _owns_cv(cv, request):
            return Response(
                {'detail': 'You do not have permission to delete this CV.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        cv.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
