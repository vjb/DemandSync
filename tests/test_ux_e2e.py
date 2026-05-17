import pytest
import subprocess
import time
import os
import requests
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="module")
def app_server():
    # Start the FastAPI server
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    import sys
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        env=env
    )
    
    # Wait for the server to start
    for _ in range(30):
        try:
            response = requests.get("http://127.0.0.1:8000/")
            if response.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        process.terminate()
        pytest.fail("Server did not start in time")
        
    yield "http://127.0.0.1:8000"
    
    # Teardown
    process.terminate()
    process.wait()

def test_dashboard_e2e(app_server):
    # Make assets directory for screenshot
    os.makedirs("assets", exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 1. Navigate to dashboard
        page.goto(app_server)
        
        # 2. Assert dashboard loads correctly
        assert page.title() == "OmniCaster | Autonomous Micro-Ad Agent"
        assert page.locator("h1").inner_text().replace('\n', ' ') == "OmniCaster AGENT ACTIVE"
        
        # 3. Click the trigger button
        # There's a button with text "⛈️ Trigger Midtown Downpour"
        trigger_btn = page.locator("button", has_text="Trigger Midtown Downpour")
        assert trigger_btn.is_visible()
        trigger_btn.click()
        
        # 4. Wait for the SSE stream to populate
        # The campaign card should become active
        campaign_card = page.locator("#campaign-card")
        campaign_card.wait_for(state="visible", timeout=15000)
        
        # 5. Assert Ad Copy appears
        ad_copy_element = page.locator("#ad-copy-text")
        assert ad_copy_element.inner_text() != "Loading copy..."
        assert ad_copy_element.inner_text() != ""
        
        # Also check that target zip is populated
        zip_element = page.locator("#target-zip")
        assert zip_element.inner_text() != "---"
        
        # 6. Take a screenshot
        page.screenshot(path="assets/e2e_success.png")
        
        browser.close()
