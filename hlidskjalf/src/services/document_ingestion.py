"""
Document Ingestion Service - Web crawling to semantic memory

Integrates Firecrawl for LLM-friendly document extraction,
with httpx fallback for basic HTML scraping when Firecrawl is unavailable.
Stores crawled content as semantic memories in Muninn.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    """
    Crawl websites and ingest documents into Muninn semantic memory.
    
    Features:
    - Single page scraping
    - Multi-page site crawling
    - Automatic chunking for large documents
    - Metadata extraction (title, description, links)
    - Deduplication
    """
    
    def __init__(
        self,
        firecrawl_url: str = "http://firecrawl:3002",
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
    ):
        self.firecrawl_url = firecrawl_url
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    async def _call_firecrawl(
        self,
        endpoint: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Make request to Firecrawl API."""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.firecrawl_url}/{endpoint}"
                resp = await client.post(url, json=data)
                
                if resp.status_code == 200:
                    return resp.json()
                else:
                    logger.error(f"Firecrawl API error: {resp.status_code} - {resp.text[:200]}")
                    return None
        except httpx.ConnectError:
            logger.warning(f"Firecrawl not available at {self.firecrawl_url}, using httpx fallback")
            return None
        except Exception as e:
            logger.error(f"Failed to call Firecrawl: {e}")
            return None
    
    async def _httpx_fallback_scrape(self, url: str) -> dict[str, Any] | None:
        """
        Fallback scraper using httpx when Firecrawl is unavailable.
        
        Uses basic HTML parsing to extract content.
        """
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; Norns/1.0; +https://ravenhelm.test)",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    }
                )
                
                if resp.status_code != 200:
                    logger.error(f"HTTP {resp.status_code} fetching {url}")
                    return None
                
                html = resp.text
                
                # Extract title
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else url
                
                # Extract meta description
                desc_match = re.search(
                    r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
                    html, re.IGNORECASE
                )
                description = desc_match.group(1).strip() if desc_match else ""
                
                # Convert HTML to markdown-like text
                markdown = self._html_to_markdown(html)
                
                return {
                    "success": True,
                    "data": {
                        "markdown": markdown,
                        "title": title,
                        "description": description,
                        "source_url": str(resp.url),
                    },
                }
                
        except Exception as e:
            logger.error(f"Httpx fallback failed for {url}: {e}")
            return None
    
    def _html_to_markdown(self, html: str) -> str:
        """
        Simple HTML to Markdown conversion.
        
        Extracts main content, removes scripts/styles, converts basic formatting.
        """
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # Try to extract main content (common selectors)
        main_match = re.search(
            r'<(main|article|div[^>]*class=["\'][^"\']*content[^"\']*["\'])[^>]*>(.*?)</\1>',
            html, re.DOTALL | re.IGNORECASE
        )
        if main_match:
            html = main_match.group(2)
        else:
            # Fall back to body
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html, flags=re.DOTALL | re.IGNORECASE)
            if body_match:
                html = body_match.group(1)
        
        # Convert headings
        for i in range(1, 7):
            html = re.sub(rf'<h{i}[^>]*>(.*?)</h{i}>', rf'\n\n{"#" * i} \1\n\n', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert paragraphs
        html = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\n\1\n', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert lists
        html = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert links to markdown format
        html = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'[\2](\1)', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert bold/strong
        html = re.sub(r'<(b|strong)[^>]*>(.*?)</\1>', r'**\2**', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert italic/em
        html = re.sub(r'<(i|em)[^>]*>(.*?)</\1>', r'*\2*', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert code
        html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove remaining tags
        html = re.sub(r'<[^>]+>', ' ', html)
        
        # Clean up whitespace
        html = re.sub(r'&nbsp;', ' ', html)
        html = re.sub(r'&amp;', '&', html)
        html = re.sub(r'&lt;', '<', html)
        html = re.sub(r'&gt;', '>', html)
        html = re.sub(r'&quot;', '"', html)
        html = re.sub(r'&#\d+;', '', html)
        html = re.sub(r'\s+', ' ', html)
        html = re.sub(r'\n\s*\n\s*\n+', '\n\n', html)
        
        return html.strip()
    
    def _chunk_text(self, text: str) -> list[str]:
        """
        Split large text into overlapping chunks.
        
        Uses simple sentence-boundary chunking for now.
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                sentence_ends = ['.', '!', '?', '\n\n']
                best_break = end
                
                for i in range(end, max(start + self.chunk_size - 200, start), -1):
                    if text[i] in sentence_ends:
                        best_break = i + 1
                        break
                
                end = best_break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start with overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    async def crawl_page(
        self,
        url: str,
        domain: str = "external",
        metadata: dict[str, Any] | None = None,
        muninn=None,
    ) -> list[str]:
        """
        Crawl a single page and store in Muninn.
        
        Args:
            url: Page URL to crawl
            domain: Domain classification for memory organization
            metadata: Additional metadata to store
            muninn: Optional existing Muninn instance to use
            
        Returns:
            List of memory IDs created
        """
        from src.memory.muninn.store import MuninnStore, MemoryFragment, MemoryType
        from src.core.config import get_settings
        
        if muninn is None:
            settings = get_settings()
            db_url = str(settings.DATABASE_URL) if settings.DATABASE_URL else None
            muninn = MuninnStore(database_url=db_url)
        
        # Try Firecrawl first
        result = await self._call_firecrawl(
            endpoint="v0/scrape",
            data={
                "url": url,
                "formats": ["markdown", "html"],
                "onlyMainContent": True,
            },
        )
        
        # Fallback to httpx if Firecrawl unavailable
        if not result:
            logger.info(f"Using httpx fallback for {url}")
            result = await self._httpx_fallback_scrape(url)
        
        if not result or not result.get("success"):
            logger.error(f"Failed to crawl {url} (both Firecrawl and httpx failed)")
            return []
        
        data = result.get("data", {})
        content = data.get("markdown", data.get("html", ""))
        
        if not content:
            logger.warning(f"No content extracted from {url}")
            return []
        
        # Extract metadata
        title = data.get("title", url)
        description = data.get("description", "")
        
        # Chunk content
        chunks = self._chunk_text(content)
        memory_ids = []
        
        for i, chunk in enumerate(chunks):
            # Create semantic memory fragment
            fragment = MemoryFragment(
                type=MemoryType.SEMANTIC,
                content=chunk,
                domain=domain,
                topic="document",
                summary=description if i == 0 else f"{title} (part {i+1})",
                weight=0.5,
                features={
                    "source_url": url,
                    "title": title,
                    "description": description,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "crawled_at": datetime.now(timezone.utc).isoformat(),
                    **(metadata or {}),
                },
            )
            
            memory_id = await muninn.remember(fragment)
            memory_ids.append(memory_id)
        
        logger.info(f"Ingested {len(chunks)} chunks from {url}")
        return memory_ids
    
    async def crawl_site(
        self,
        url: str,
        domain: str = "external",
        max_depth: int = 2,
        max_pages: int = 50,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Crawl an entire website and store pages in Muninn.
        
        Args:
            url: Root URL to start crawling
            domain: Domain classification
            max_depth: Maximum link depth to follow
            max_pages: Maximum pages to crawl
            include_patterns: URL patterns to include (regex)
            exclude_patterns: URL patterns to exclude (regex)
            
        Returns:
            Dict with crawl statistics
        """
        # Call Firecrawl crawl API
        result = await self._call_firecrawl(
            endpoint="v0/crawl",
            data={
                "url": url,
                "crawlerOptions": {
                    "maxDepth": max_depth,
                    "limit": max_pages,
                    "includes": include_patterns or [],
                    "excludes": exclude_patterns or [],
                },
                "pageOptions": {
                    "onlyMainContent": True,
                    "formats": ["markdown"],
                },
            },
        )
        
        if not result or not result.get("success"):
            logger.error(f"Failed to start crawl of {url}")
            return {"success": False, "pages": 0}
        
        # Firecrawl returns a job ID for async crawling
        job_id = result.get("jobId")
        if not job_id:
            # Synchronous response with data
            pages = result.get("data", [])
        else:
            # Wait for job completion (polling)
            pages = await self._poll_crawl_job(job_id)
        
        # Ingest each page
        total_memories = 0
        ingested_urls = []
        
        for page_data in pages:
            page_url = page_data.get("url", "")
            content = page_data.get("markdown", "")
            
            if not content:
                continue
            
            # Store page
            memory_ids = await self.crawl_page(
                url=page_url,
                domain=domain,
                metadata={
                    "crawl_root": url,
                    "depth": page_data.get("depth", 0),
                },
            )
            
            total_memories += len(memory_ids)
            ingested_urls.append(page_url)
        
        logger.info(f"Site crawl complete: {len(ingested_urls)} pages, {total_memories} memories")
        
        return {
            "success": True,
            "pages": len(ingested_urls),
            "memories": total_memories,
            "urls": ingested_urls,
        }
    
    async def _poll_crawl_job(
        self,
        job_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Poll Firecrawl for async crawl job completion.
        
        Args:
            job_id: Firecrawl job ID
            timeout: Max wait time in seconds
            poll_interval: Seconds between polls
            
        Returns:
            List of crawled page data
        """
        import asyncio
        import httpx
        
        elapsed = 0
        
        while elapsed < timeout:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    url = f"{self.firecrawl_url}/v0/crawl/status/{job_id}"
                    resp = await client.get(url)
                    
                    if resp.status_code != 200:
                        logger.error(f"Failed to check job status: {resp.status_code}")
                        return []
                    
                    result = resp.json()
                    status = result.get("status")
                    
                    if status == "completed":
                        return result.get("data", [])
                    elif status == "failed":
                        logger.error(f"Crawl job failed: {result.get('error')}")
                        return []
                    
                    # Still in progress
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval
                        
            except Exception as e:
                logger.error(f"Error polling job: {e}")
                return []
        
        logger.warning(f"Crawl job {job_id} timed out after {timeout}s")
        return []
    
    async def search_documents(
        self,
        query: str,
        domain: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search ingested documents in Muninn.
        
        Args:
            query: Search query
            domain: Filter by domain
            limit: Max results
            
        Returns:
            List of matching documents with metadata
        """
        from src.memory.muninn.store import MuninnStore, MemoryType
        from src.core.config import get_settings
        
        settings = get_settings()
        muninn = MuninnStore(database_url=str(settings.DATABASE_URL))
        
        memories = await muninn.recall(
            query=query,
            k=limit,
            memory_type=MemoryType.SEMANTIC,
            domain=domain,
        )
        
        # Format results
        results = []
        for mem in memories:
            results.append({
                "id": mem.id,
                "content": mem.content[:500] + "..." if len(mem.content) > 500 else mem.content,
                "source_url": mem.features.get("source_url", ""),
                "title": mem.features.get("title", ""),
                "weight": mem.weight,
                "references": mem.references,
                "crawled_at": mem.features.get("crawled_at", ""),
            })
        
        return results
    
    async def get_crawl_stats(self, domain: str | None = None) -> dict[str, Any]:
        """Get statistics about ingested documents."""
        from src.memory.muninn.store import MuninnStore, MemoryType
        from src.core.config import get_settings
        
        settings = get_settings()
        muninn = MuninnStore(database_url=str(settings.DATABASE_URL))
        
        # Count semantic memories
        all_docs = [
            m for m in muninn._memory_index.values()
            if m.type == MemoryType.SEMANTIC
            and m.topic == "document"
            and (domain is None or m.domain == domain)
        ]
        
        # Extract unique URLs
        unique_urls = set(
            m.features.get("source_url")
            for m in all_docs
            if m.features.get("source_url")
        )
        
        # Calculate total size
        total_chars = sum(len(m.content) for m in all_docs)
        
        return {
            "total_documents": len(all_docs),
            "unique_urls": len(unique_urls),
            "total_chars": total_chars,
            "avg_weight": sum(m.weight for m in all_docs) / len(all_docs) if all_docs else 0,
        }

