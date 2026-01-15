import os
import random
import time
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# Banner registration page (user will still need to log in manually)
REGISTER_URL = "https://registration.banner.gatech.edu/StudentRegistrationSsb/ssb/classRegistration/classRegistration"


def make_driver(profile_dir: str) -> webdriver.Chrome:
    opts = Options()
    # Dedicated local profile folder so session cookies can persist
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument("--start-maximized")
    return webdriver.Chrome(options=opts)


def wait_click(driver, xpath: str, timeout: int = 20):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )


def wait_present(driver, xpath: str, timeout: int = 20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )


def safe_click(driver, xpath: str, timeout: int = 20):
    el = wait_click(driver, xpath, timeout)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    el.click()
    return el


def click_enter_crns_tab_if_needed(driver):
    enter_crns_tab_xpath = "//a[normalize-space()='Enter CRNs']"
    try:
        safe_click(driver, enter_crns_tab_xpath, timeout=5)
    except TimeoutException:
        # already on it or not clickable due to layout state
        pass


def set_crn_and_add_to_summary(driver, crn: str):
    # CRN input next to label “CRN”
    crn_input_xpath = "//label[normalize-space()='CRN']/following::input[1]"
    crn_input = wait_present(driver, crn_input_xpath, timeout=20)
    crn_input.clear()
    crn_input.send_keys(crn)

    # Click Add to Summary
    add_to_summary_xpath = (
        "//button[normalize-space()='Add to Summary']"
        " | //input[@type='button' and @value='Add to Summary']"
        " | //input[@type='submit' and @value='Add to Summary']"
    )
    safe_click(driver, add_to_summary_xpath, timeout=20)


def click_submit(driver):
    submit_xpath = (
        "//button[normalize-space()='Submit']"
        " | //input[@type='button' and @value='Submit']"
        " | //input[@type='submit' and @value='Submit']"
    )
    safe_click(driver, submit_xpath, timeout=20)


def read_errors_and_status(driver) -> Dict:
    """
    Returns:
      {
        "closed": bool,
        "registered": bool,
        "messages": [str, ...]
      }
    """
    messages: List[str] = []

    # Banner often shows errors in an alert region or notification panel
    possible_message_xpaths = [
        "//*[@role='alert']",
        "//*[contains(@class,'alert')]",
        "//*[contains(@class,'notification')]",
        "//*[contains(@class,'messages')]",
    ]

    for xp in possible_message_xpaths:
        els = driver.find_elements(By.XPATH, xp)
        for e in els:
            txt = (e.text or "").strip()
            if txt and txt not in messages:
                messages.append(txt)

    joined = "\n".join(messages).lower()

    # Note: "or 'closed' in joined" is intentionally avoided because it can false-positive.
    closed = ("closed section" in joined) or ("section is closed" in joined)

    # Broad detection: any “registered” text on the page
    registered = False
    try:
        reg_el = driver.find_elements(
            By.XPATH,
            "//*[contains(translate(., 'REGISTERED', 'registered'),'registered')]"
        )
        registered = len(reg_el) > 0
    except StaleElementReferenceException:
        pass

    return {"closed": closed, "registered": registered, "messages": messages}


def try_register_once(driver, crns: List[str]) -> Dict:
    # Ensure you are on the right page
    if "classRegistration" not in driver.current_url:
        driver.get(REGISTER_URL)

    click_enter_crns_tab_if_needed(driver)

    # Add each CRN to Summary (in the current UI, you typically type one CRN at a time)
    for crn in crns:
        set_crn_and_add_to_summary(driver, crn)
        time.sleep(0.6)

    # Submit once (Banner processes summary actions)
    click_submit(driver)

    # Wait briefly for any alerts/messages to appear
    time.sleep(1.2)

    return read_errors_and_status(driver)


def camp_for_seat(
    driver,
    crns: List[str],
    min_delay_s: int = 45,
    max_delay_s: int = 90,
) -> Dict:
    attempt = 1
    print("\n⏳ Camping for seat. Press Ctrl+C to stop.\n")

    try:
        while True:
            result = try_register_once(driver, crns)

            print(f"[Attempt {attempt}] registered={result['registered']} closed={result['closed']}")

            if result["messages"]:
                print("Messages:")
                for m in result["messages"][:4]:
                    first_line = m.split("\n")[0][:200]
                    print(" -", first_line)

            # Success condition
            if result["registered"] and not result["closed"]:
                print("\nSUCCESS — registration detected!")
                return result

            delay = random.randint(min_delay_s, max_delay_s)
            print(f"Retrying in {delay}s...\n")
            time.sleep(delay)

            # Refresh to keep Banner state sane
            driver.refresh()
            time.sleep(2)

            attempt += 1

    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).")
        return {"registered": False, "closed": True, "messages": ["Stopped by user"]}


def parse_crns(user_input: str) -> List[str]:
    # Accept "29626" or "29626, 12345 67890"
    raw = user_input.replace(",", " ").split()
    crns = [x.strip() for x in raw if x.strip()]
    # Basic validation: numeric and length 5
    cleaned = []
    for c in crns:
        if c.isdigit() and len(c) == 5:
            cleaned.append(c)
        else:
            print(f"Skipping invalid CRN: {c!r} (expected 5 digits)")
    return cleaned


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "chrome_profile")  # portable for any user

    driver = make_driver(profile_dir=profile_dir)
    driver.get(REGISTER_URL)

    print("\n1) Chrome opened.")
    print("2) Log in manually (GT SSO/Duo) and navigate to:")
    print("   Register for Classes → Enter CRNs\n")
    input("Press Enter here once you're on the Enter CRNs screen...")

    crn_input = input("Enter CRN(s) (one or multiple, separated by spaces/commas): ").strip()
    crns = parse_crns(crn_input)
    if not crns:
        print("No valid CRNs provided. Exiting.")
        driver.quit()
        return
    
    mode = input("Type 'once' to try one time, or 'camp' to retry until it succeeds: ").strip().lower()
    if mode not in {"once", "camp"}:
        mode = "camp"

    if mode == "once":
        result = try_register_once(driver, crns)
        print("\nResult:", result)
    else:
        camp_for_seat(driver, crns)


    input("\nDone. Press Enter to quit...")
    driver.quit()


if __name__ == "__main__":
    main()
