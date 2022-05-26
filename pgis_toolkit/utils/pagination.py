from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'

    def get_paginated_response(self, data):
        limit_value = int(self.request.query_params.get('limit', 10))
        current_page = int(self.request.query_params.get('page', 1))
        next_page_link = self.get_next_link()
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'counts': self.page.paginator.count,
            'results': data
        }, status=200)
