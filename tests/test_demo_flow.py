import subprocess
import time
import requests
import os
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="module")
def app_server():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    import sys
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        env=env
    )

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
    process.terminate()
    process.wait()

def test_demo_flow_e2e(app_server):
    os.makedirs("assets", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Open Dashboard
        page.goto(app_server)
        assert "DemandSync" in page.title()

        # 2. Trigger Blizzard Event
        page.select_option("#event-select", "Category 4 Blizzard hitting Central Park")
        page.click("#trigger-btn")

        # 3. Wait for price to surge and image to render
        campaign_card = page.locator("#campaign-card")
        campaign_card.wait_for(state="visible", timeout=90000)
        
        # Verify Price container is visible
        price_container = page.locator("#price-container")
        price_container.wait_for(state="visible", timeout=15000)
        
        # 4. Click Simulate Viral Sales
        viral_btn = page.locator("#viral-btn")
        viral_btn.wait_for(state="visible")
        viral_btn.click()

        # 5. Capture screenshot exact moment PO is transmitted
        po_receipt = page.locator("#po-receipt")
        po_receipt.wait_for(state="visible", timeout=30000)
        
        # Take screenshot of the ultimate win
        page.screenshot(path="assets/demo_god_mode_success.png", full_page=True)

        browser.close()
