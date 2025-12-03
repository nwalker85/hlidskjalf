"""Locust Load Tests for SAAA Agent Mesh.

Tests concurrent load handling:
- Agent tool call throughput
- Streaming response under load
- Redis Streams / Reactive Blackboard concurrency
- Multi-agent delegation patterns

Run with:
    locust -f tests/load/locustfile.py --host http://localhost:8209
"""

import json
import os
import time
import uuid
from typing import Any

from locust import HttpUser, TaskSet, between, task
from locust.contrib.fasthttp import FastHttpUser


# =============================================================================
# Configuration
# =============================================================================

DEEP_AGENT_HOST = os.environ.get("DEEP_AGENT_URL", "http://localhost:8209")
RESEARCH_AGENT_HOST = os.environ.get("RESEARCH_AGENT_URL", "http://localhost:8210")
ANALYSIS_AGENT_HOST = os.environ.get("ANALYSIS_AGENT_URL", "http://localhost:8211")


def create_mcp_request(tool: str, arguments: dict[str, Any]) -> dict:
    """Create an MCP tool call request."""
    return {
        "tool": tool,
        "arguments": arguments,
        "request_id": str(uuid.uuid4()),
    }


# =============================================================================
# Deep Agent Load Tests
# =============================================================================


class DeepAgentTasks(TaskSet):
    """Task set for Deep Agent load testing."""

    @task(3)
    def health_check(self):
        """Health check endpoint (high frequency)."""
        self.client.get("/health", name="deep_agent_health")

    @task(2)
    def list_tools(self):
        """List available tools."""
        self.client.get("/mcp/tools/list", name="deep_agent_list_tools")

    @task(5)
    def simple_query(self):
        """Simple conversational query."""
        request = create_mcp_request(
            tool="deep/stream",
            arguments={
                "message": "Hello, how are you?",
                "session_id": f"load-test-{uuid.uuid4().hex[:8]}",
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="deep_agent_simple_query",
        )

    @task(3)
    def research_delegation(self):
        """Query that triggers research agent delegation."""
        request = create_mcp_request(
            tool="deep/stream",
            arguments={
                "message": "Research the latest news about AI regulations",
                "session_id": f"load-test-{uuid.uuid4().hex[:8]}",
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="deep_agent_research_delegation",
        )

    @task(2)
    def analysis_delegation(self):
        """Query that triggers analysis agent delegation."""
        request = create_mcp_request(
            tool="deep/stream",
            arguments={
                "message": "Analyze the sentiment of: The market is very bullish today",
                "session_id": f"load-test-{uuid.uuid4().hex[:8]}",
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="deep_agent_analysis_delegation",
        )


class DeepAgentUser(HttpUser):
    """Simulated user for Deep Agent."""

    tasks = [DeepAgentTasks]
    wait_time = between(0.5, 2.0)
    host = DEEP_AGENT_HOST


# =============================================================================
# Research Agent Load Tests
# =============================================================================


class ResearchAgentTasks(TaskSet):
    """Task set for Research Agent load testing."""

    @task(2)
    def health_check(self):
        """Health check."""
        self.client.get("/health", name="research_agent_health")

    @task(5)
    def web_search(self):
        """Web search tool."""
        queries = [
            "AI regulations",
            "climate technology",
            "quantum computing",
            "renewable energy",
            "machine learning",
        ]
        request = create_mcp_request(
            tool="research/search",
            arguments={
                "query": queries[int(time.time()) % len(queries)],
                "max_results": 3,
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="research_agent_search",
        )

    @task(3)
    def gather_sources(self):
        """Gather sources tool."""
        request = create_mcp_request(
            tool="research/gather",
            arguments={
                "topic": "artificial intelligence",
                "depth": "standard",
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="research_agent_gather",
        )

    @task(2)
    def extract_facts(self):
        """Extract facts tool."""
        request = create_mcp_request(
            tool="research/extract",
            arguments={
                "content": "AI adoption grew 40% in 2024. Enterprise spending on ML reached $50B.",
                "focus_areas": ["statistics", "trends"],
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="research_agent_extract",
        )


class ResearchAgentUser(HttpUser):
    """Simulated user for Research Agent."""

    tasks = [ResearchAgentTasks]
    wait_time = between(0.3, 1.5)
    host = RESEARCH_AGENT_HOST


# =============================================================================
# Analysis Agent Load Tests
# =============================================================================


class AnalysisAgentTasks(TaskSet):
    """Task set for Analysis Agent load testing."""

    @task(2)
    def health_check(self):
        """Health check."""
        self.client.get("/health", name="analysis_agent_health")

    @task(5)
    def sentiment_analysis(self):
        """Sentiment analysis tool."""
        texts = [
            "The company reported excellent quarterly earnings.",
            "The market experienced significant volatility today.",
            "Investors are concerned about rising interest rates.",
            "New product launch exceeded all expectations.",
            "Regulatory uncertainty is affecting investor confidence.",
        ]
        request = create_mcp_request(
            tool="analysis/sentiment",
            arguments={"content": texts[int(time.time()) % len(texts)]},
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="analysis_agent_sentiment",
        )

    @task(3)
    def summarize(self):
        """Summarization tool."""
        request = create_mcp_request(
            tool="analysis/summarize",
            arguments={
                "content": (
                    "The global technology sector continues to evolve rapidly. "
                    "Artificial intelligence has emerged as a key driver of innovation. "
                    "Companies are investing heavily in machine learning capabilities. "
                    "Cloud computing adoption remains strong across industries."
                ),
                "style": "brief",
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="analysis_agent_summarize",
        )

    @task(2)
    def extract_insights(self):
        """Extract insights tool."""
        request = create_mcp_request(
            tool="analysis/insights",
            arguments={
                "content": "Revenue grew 25% YoY. Customer acquisition cost decreased 15%. NPS score reached 72.",
                "focus": "business_metrics",
            },
        )
        self.client.post(
            "/mcp/tools/call",
            json=request,
            name="analysis_agent_insights",
        )


class AnalysisAgentUser(HttpUser):
    """Simulated user for Analysis Agent."""

    tasks = [AnalysisAgentTasks]
    wait_time = between(0.3, 1.5)
    host = ANALYSIS_AGENT_HOST


# =============================================================================
# Streaming Load Tests
# =============================================================================


class StreamingLoadTasks(TaskSet):
    """Task set for streaming endpoint load testing."""

    @task(1)
    def streaming_query(self):
        """Test streaming endpoint under load."""
        request = create_mcp_request(
            tool="deep/stream",
            arguments={
                "message": "Tell me about climate change impacts",
                "session_id": f"stream-load-{uuid.uuid4().hex[:8]}",
            },
        )

        with self.client.post(
            "/mcp/tools/call/stream",
            json=request,
            name="deep_agent_streaming",
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                # Read the stream to completion
                content_length = 0
                for chunk in response.iter_content(chunk_size=1024):
                    content_length += len(chunk)
                if content_length > 0:
                    response.success()
                else:
                    response.failure("Empty streaming response")
            else:
                response.failure(f"Status code: {response.status_code}")


class StreamingUser(HttpUser):
    """Simulated user for streaming load tests."""

    tasks = [StreamingLoadTasks]
    wait_time = between(1.0, 3.0)
    host = DEEP_AGENT_HOST


# =============================================================================
# Concurrent Multi-Agent Tests
# =============================================================================


class MultiAgentTasks(TaskSet):
    """Task set simulating concurrent multi-agent workflows."""

    @task(1)
    def full_workflow(self):
        """Simulate full research + analysis workflow."""
        session_id = f"workflow-{uuid.uuid4().hex[:8]}"

        # Step 1: Research
        research_request = create_mcp_request(
            tool="research/search",
            arguments={"query": "AI market trends", "max_results": 3},
        )
        research_response = self.client.post(
            "/mcp/tools/call",
            json=research_request,
            name="workflow_research",
        )

        if research_response.status_code != 200:
            return

        # Step 2: Analysis (using research results)
        analysis_request = create_mcp_request(
            tool="analysis/sentiment",
            arguments={"content": research_response.text[:500]},
        )
        self.client.post(
            "/mcp/tools/call",
            json=analysis_request,
            name="workflow_analysis",
        )


class MultiAgentUser(HttpUser):
    """Simulated user for multi-agent workflow tests."""

    tasks = [MultiAgentTasks]
    wait_time = between(2.0, 5.0)
    # Uses research agent for the workflow
    host = RESEARCH_AGENT_HOST


# =============================================================================
# High-Performance FastHTTP Users
# =============================================================================


class FastDeepAgentUser(FastHttpUser):
    """High-performance Deep Agent user using FastHTTP."""

    wait_time = between(0.1, 0.5)
    host = DEEP_AGENT_HOST

    @task
    def fast_health_check(self):
        """Fast health check."""
        self.client.get("/health")

    @task
    def fast_simple_query(self):
        """Fast simple query."""
        request = create_mcp_request(
            tool="deep/stream",
            arguments={
                "message": "Hello",
                "session_id": f"fast-{uuid.uuid4().hex[:8]}",
            },
        )
        self.client.post("/mcp/tools/call", json=request)
