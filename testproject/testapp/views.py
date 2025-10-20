"""Example views for blog app."""

from django.shortcuts import render
from example.blog.indexes import PostIndex, PostIndexLegacy


def search_posts(request):
    """Search blog posts using Manticore."""
    query = request.GET.get("q", "")
    results = []

    if query:
        # Initialize the index
        index = PostIndex()

        # Search the index
        search_results = index.search(
            query=query, match_fields=["title", "content"], enable_wildcard_search=True, infix_search=True
        )

        # Convert results to QuerySet
        results = index.search_result_to_queryset(search_results)

    return render(request, "blog/search.html", {"results": results, "query": query})


def search_posts_legacy(request):
    """Search blog posts using Manticore with legacy API style."""
    query = request.GET.get("q", "")
    results = []

    if query:
        # Using the original static method approach
        results = PostIndexLegacy.search(query)

    return render(request, "blog/search.html", {"results": results, "query": query})
