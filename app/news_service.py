# Purpose: Provide a replaceable supplier news summary service with a safe placeholder implementation.
from __future__ import annotations

import os


class NewsService:
    """Small service wrapper that can later call a real provider."""

    def __init__(self, provider_name: str = "mock", api_key: str | None = None) -> None:
        self.provider_name = provider_name
        self.api_key = api_key

    def get_summary(self, supplier_name: str) -> str:
        """Return a short business-focused summary with at most seven sentences."""
        if self.provider_name != "mock" and self.api_key:
            # TODO: Add a real provider integration here without changing callers.
            return (
                f"Live news integration for {supplier_name} is not implemented yet. "
                "Version 1 still uses placeholder logic for business-relevant supplier news."
            )

        return (
            f"No live news provider is configured for {supplier_name}, so this section uses placeholder logic. "
            "Check for business-relevant items such as insolvency signals, layoffs, expansion, investments, or strategic shifts. "
            "When a real provider is connected, this section should summarize only material supplier-risk developments."
        )


def build_news_service_from_env() -> NewsService:
    """Create the service from environment variables so the provider can be swapped later."""
    return NewsService(
        provider_name=os.getenv("NEWS_PROVIDER", "mock"),
        api_key=os.getenv("NEWS_API_KEY"),
    )
