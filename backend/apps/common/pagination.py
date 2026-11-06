from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """`?page=N&page_size=M` → {count, next, previous, results}."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class LargePagination(StandardPagination):
    """For dashboards that render a user's whole (small) collection, e.g. bookings."""

    page_size = 50
    max_page_size = 100


class SmallPagination(StandardPagination):
    page_size = 10
