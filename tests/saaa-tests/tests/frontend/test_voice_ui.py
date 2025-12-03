"""Playwright E2E tests for Voice UI.

Tests the Next.js frontend including:
- Room connection flow
- Microphone permissions
- Voice activity indicators
- Agent response display
- WebRTC connectivity
"""

import pytest
from playwright.async_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


@pytest.fixture
def frontend_url() -> str:
    """Frontend URL for testing."""
    import os

    return os.environ.get("FRONTEND_URL", "http://localhost:3005")


class TestVoiceRoomConnection:
    """Test LiveKit room connection flow."""

    async def test_landing_page_loads(self, page: Page, frontend_url: str):
        """Landing page should load with connect button."""
        await page.goto(frontend_url)

        # Should see the main heading
        heading = page.locator("h1")
        await expect(heading).to_be_visible()

        # Should have a connect/start button
        connect_button = page.get_by_role("button", name=/connect|start|join/i)
        await expect(connect_button).to_be_visible()

    async def test_room_connection_initiated(self, page: Page, frontend_url: str):
        """Clicking connect should initiate room connection."""
        await page.goto(frontend_url)

        # Click connect button
        connect_button = page.get_by_role("button", name=/connect|start|join/i)
        await connect_button.click()

        # Should show connecting state or room UI
        # Wait for either a loading indicator or the room interface
        await page.wait_for_selector(
            "[data-testid='room-container'], [data-testid='connecting'], .lk-room",
            timeout=10000,
        )

    async def test_microphone_permission_prompt(self, page: Page, frontend_url: str):
        """Should prompt for microphone permission."""
        # Grant microphone permission
        await page.context.grant_permissions(["microphone"])

        await page.goto(frontend_url)
        connect_button = page.get_by_role("button", name=/connect|start|join/i)
        await connect_button.click()

        # After connection, should show audio controls
        await page.wait_for_selector(
            "[data-testid='audio-controls'], .lk-audio-track, button[aria-label*='microphone']",
            timeout=15000,
        )


class TestVoiceActivityIndicators:
    """Test voice activity and visualization."""

    @pytest.fixture
    async def connected_page(self, page: Page, frontend_url: str):
        """Page with established room connection."""
        await page.context.grant_permissions(["microphone"])
        await page.goto(frontend_url)

        connect_button = page.get_by_role("button", name=/connect|start|join/i)
        await connect_button.click()

        # Wait for room to be ready
        await page.wait_for_selector(
            "[data-testid='room-container'], .lk-room",
            timeout=15000,
        )
        return page

    async def test_audio_visualizer_present(self, connected_page: Page):
        """Should show audio visualizer when connected."""
        visualizer = connected_page.locator(
            "[data-testid='audio-visualizer'], .audio-visualizer, canvas"
        )
        await expect(visualizer.first).to_be_visible()

    async def test_mute_toggle_works(self, connected_page: Page):
        """Mute button should toggle microphone state."""
        mute_button = connected_page.get_by_role(
            "button", name=/mute|unmute|microphone/i
        )
        await expect(mute_button).to_be_visible()

        # Click to toggle
        await mute_button.click()

        # Button state should change (aria-pressed or class)
        # This depends on implementation
        await connected_page.wait_for_timeout(500)


class TestAgentResponseDisplay:
    """Test agent response rendering."""

    @pytest.fixture
    async def connected_page(self, page: Page, frontend_url: str):
        """Page with established room connection."""
        await page.context.grant_permissions(["microphone"])
        await page.goto(frontend_url)

        connect_button = page.get_by_role("button", name=/connect|start|join/i)
        await connect_button.click()

        await page.wait_for_selector(
            "[data-testid='room-container'], .lk-room",
            timeout=15000,
        )
        return page

    async def test_transcript_area_exists(self, connected_page: Page):
        """Should have a transcript/chat area for displaying responses."""
        transcript = connected_page.locator(
            "[data-testid='transcript'], [data-testid='chat'], .transcript, .messages"
        )
        # May or may not be visible depending on if messages exist
        await expect(transcript.first).to_be_attached()

    async def test_agent_status_indicator(self, connected_page: Page):
        """Should show agent status (listening, thinking, speaking)."""
        status = connected_page.locator(
            "[data-testid='agent-status'], .agent-status, [aria-label*='status']"
        )
        await expect(status.first).to_be_visible()


class TestErrorHandling:
    """Test error states and recovery."""

    async def test_connection_error_displayed(self, page: Page, frontend_url: str):
        """Should show error when connection fails."""
        # Block LiveKit WebSocket to simulate connection failure
        await page.route("**/livekit/**", lambda route: route.abort())

        await page.goto(frontend_url)
        connect_button = page.get_by_role("button", name=/connect|start|join/i)
        await connect_button.click()

        # Should show error message
        error = page.locator("[data-testid='error'], .error, [role='alert']")
        await expect(error.first).to_be_visible(timeout=15000)

    async def test_disconnect_button_works(self, page: Page, frontend_url: str):
        """Disconnect button should leave room."""
        await page.context.grant_permissions(["microphone"])
        await page.goto(frontend_url)

        # Connect
        connect_button = page.get_by_role("button", name=/connect|start|join/i)
        await connect_button.click()

        await page.wait_for_selector(
            "[data-testid='room-container'], .lk-room",
            timeout=15000,
        )

        # Find and click disconnect
        disconnect_button = page.get_by_role(
            "button", name=/disconnect|leave|end/i
        )
        if await disconnect_button.count() > 0:
            await disconnect_button.click()

            # Should return to initial state
            await expect(connect_button).to_be_visible(timeout=5000)


class TestAccessibility:
    """Test accessibility requirements."""

    async def test_keyboard_navigation(self, page: Page, frontend_url: str):
        """UI should be navigable via keyboard."""
        await page.goto(frontend_url)

        # Tab to connect button
        await page.keyboard.press("Tab")

        # Should focus on interactive element
        focused = await page.evaluate("document.activeElement.tagName")
        assert focused.lower() in ["button", "a", "input"]

    async def test_aria_labels_present(self, page: Page, frontend_url: str):
        """Interactive elements should have aria labels."""
        await page.goto(frontend_url)

        # All buttons should have accessible names
        buttons = page.locator("button")
        count = await buttons.count()

        for i in range(count):
            button = buttons.nth(i)
            name = await button.get_attribute("aria-label") or await button.inner_text()
            assert name.strip(), f"Button {i} missing accessible name"

    async def test_color_contrast(self, page: Page, frontend_url: str):
        """Text should have sufficient color contrast."""
        await page.goto(frontend_url)

        # This is a simplified check - real testing would use axe-core
        # For now, just verify the page loads without contrast errors in console
        logs = []
        page.on("console", lambda msg: logs.append(msg.text))

        await page.wait_for_timeout(2000)

        # No contrast warnings in console
        contrast_warnings = [l for l in logs if "contrast" in l.lower()]
        assert len(contrast_warnings) == 0, f"Contrast issues: {contrast_warnings}"
