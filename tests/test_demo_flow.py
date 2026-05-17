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
    
    # Pre-seed DB to guarantee stock for the test
    from pymongo import MongoClient
    from dotenv import load_dotenv
    load_dotenv()
    try:
        client = MongoClient(os.environ.get("MONGO_URI"))
        db = client.get_database("demandsync_db")
        db.local_inventory.update_many({}, {"$set": {"stock_count": 5}})
    except Exception as e:
        print(f"Seed error: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Open Dashboard
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser error: {err}"))
        page.goto(app_server)
        assert "DemandSync" in page.title()

        # 2. Trigger Event
        page.select_option("#event-select", "Local American Tennis Player wins US Open upset")
        page.click("#trigger-btn")

        # 3. Wait for price to surge and image to render
        campaign_card = page.locator("#campaign-card")
        campaign_card.wait_for(state="visible", timeout=90000)
        
        # Verify Price container is visible
        price_container = page.locator("#price-container")
        price_container.wait_for(state="visible", timeout=15000)
        
        # Verify Multi-channel tabs exist
        assert page.locator("button:has-text('Instagram')").is_visible()
        assert page.locator("button:has-text('Twitter')").is_visible()
        assert page.locator("button:has-text('Facebook')").is_visible()
        
        # 4. Click Simulate Viral Sales
        viral_btn = page.locator("#viral-btn")
        viral_btn.wait_for(state="visible")
        viral_btn.click()

        # 5. Capture screenshot exact moment PO is transmitted
        po_receipt = page.locator("#po-receipt")
        po_receipt.wait_for(state="visible", timeout=30000)
        
        page.screenshot(path="assets/e2e_supply_chain.png", full_page=True)
        page.screenshot(path="assets/e2e_god_mode.png", full_page=True)

        browser.close()
