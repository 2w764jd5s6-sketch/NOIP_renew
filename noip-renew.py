import argparse
import logging
import re
import time
from sys import stdout

import pyotp
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        ElementNotInteractableException,
                                        TimeoutException)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager   # 新增

from constants import HOST_URL, LOGIN_URL, SCREENSHOTS_PATH, USER_AGENT, OTP_LENGTH

# Set up logging
logger = logging.getLogger(__name__)

logFormatter = logging.Formatter(
    "%(name)-12s %(asctime)s %(levelname)-8s %(filename)s:%(funcName)s %(message)s"
)
consoleHandler = logging.StreamHandler(stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)


class NoIPUpdater:
    def __init__(
        self,
        username: str,
        password: str,
        totp_secret: str,
        https_proxy: str = None,
    ):
        self.username = username
        self.password = password
        self.totp_secret = totp_secret
        self.https_proxy = https_proxy
        self.browser = self._init_browser()

    def _init_browser(self, page_load_timeout: int = 90):
        logger.debug("Initializing browser...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")                 # 无头模式，适合服务器
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("window-size=1200x800")
        options.add_argument(f"user-agent={USER_AGENT}")
        if self.https_proxy:
            options.add_argument("proxy-server=" + self.https_proxy)

        # 使用 webdriver_manager 自动下载匹配的 ChromeDriver
        service = Service(ChromeDriverManager().install())
        browser = webdriver.Chrome(service=service, options=options)

        logger.debug(f"Setting page load timeout to: {page_load_timeout}")
        browser.set_page_load_timeout(page_load_timeout)
        return browser

    def _fill_credentials(self):
        logger.info("Filling username and password...")
        ele_usr = self.browser.find_element("name", "username")
        ele_pwd = self.browser.find_element("name", "password")
        try:
            ele_usr.send_keys(self.username)
            ele_pwd.send_keys(self.password)
        except (NoSuchElementException, ElementNotInteractableException) as e:
            logger.error(
                f"Error filling credentials: {e}, element: {ele_usr or ele_pwd}")
            raise Exception(f"Failed while inserting credentials: {e}")

    def _solve_captcha(self):
        logger.info("Solving captcha...")
        try:
            if logger.level == logging.DEBUG:
                self.browser.save_screenshot(
                    f"{SCREENSHOTS_PATH}/captcha_screen.png")
            try:
                close_buttons = self.browser.find_elements(By.XPATH,
                    "//button[contains(@class, 'close') or contains(@aria-label, 'Close') or contains(@class, 'modal-close')]")
                for btn in close_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        time.sleep(0.5)
                        logger.info("Closed a popup/ad")
            except Exception:
                pass

            login_button = self.browser.find_element(By.ID, "clogs-captcha-button")
            self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_button)
            time.sleep(0.5)
            self.browser.execute_script("arguments[0].click();", login_button)
            logger.info("Login button clicked via JavaScript")
        except (NoSuchElementException, ElementNotInteractableException) as e:
            logger.error(f"Error clicking captcha button: {e}")
            try:
                login_button = self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']")
                self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_button)
                time.sleep(0.5)
                self.browser.execute_script("arguments[0].click();", login_button)
                logger.info("Fallback login button clicked via JavaScript")
            except Exception as e2:
                logger.error(f"Fallback click also failed: {e2}")
                raise Exception(f"Failed to click login button: {e}")

    def _fill_otp(self):
        logger.info("Filling OTP...")
        if logger.level == logging.DEBUG:
            self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/otp_screen.png")
        otp = pyotp.TOTP(self.totp_secret).now()
        try:
            wait = WebDriverWait(self.browser, 30)
            otp_inputs = wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "#totp-input input[type='tel'], #totp-input input")
            ))
            if len(otp_inputs) >= OTP_LENGTH:
                for i in range(OTP_LENGTH):
                    otp_inputs[i].send_keys(otp[i])
            else:
                for pos in range(OTP_LENGTH):
                    otp_elem = self.browser.find_element(
                        By.XPATH, f'//*[@id="totp-input"]/input[{pos+1}]'
                    )
                    otp_elem.send_keys(otp[pos])
            try:
                trust_checkbox = self.browser.find_element(By.XPATH, "//input[@type='checkbox']")
                if not trust_checkbox.is_selected():
                    trust_checkbox.click()
                    logger.info("Checked 'Trust this device for 30 days'")
            except NoSuchElementException:
                logger.info("No trust checkbox found, skipping.")
            verify_btn = None
            try:
                verify_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@value='Verify']")))
            except TimeoutException:
                try:
                    verify_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
                except TimeoutException:
                    verify_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Verify')]")))
            if verify_btn:
                self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", verify_btn)
                time.sleep(0.5)
                self.browser.execute_script("arguments[0].click();", verify_btn)
                logger.info("Verify button clicked")
            wait.until(EC.url_contains("my.noip.com"))
            logger.info("Login successful after OTP verification")
        except Exception as e:
            logger.error(f"Error during OTP filling: {e}")
            self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/otp_error.png")
            raise Exception(f"OTP filling failed: {e}")

    def login(self):
        logger.info(f"Opening {LOGIN_URL} ...")
        max_retries = 2
        for attempt in range(max_retries):
            try:
                self.browser.get(LOGIN_URL)
                break
            except TimeoutException:
                logger.warning(f"Page load timeout, attempt {attempt+1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise
                self.browser.execute_script("window.stop();")
                time.sleep(3)

        if logger.level == logging.DEBUG:
            self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/debug1.png")

        logger.info("Logging in...")
        self._fill_credentials()
        self._solve_captcha()

        time.sleep(3)
        if logger.level == logging.DEBUG:
            self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/after_login.png")

        try:
            self.browser.find_element(By.ID, "totp-input")
            logger.info("TOTP input detected, filling OTP...")
            self._fill_otp()
        except NoSuchElementException:
            logger.info("No TOTP input, maybe already logged in.")

        if logger.level == logging.DEBUG:
            time.sleep(1)
            self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/debug2.png")

    def open_hosts_page(self):
        records_url = "https://my.noip.com/dns/records"
        logger.info(f"Opening {records_url} ...")
        try:
            self.browser.get(records_url)
        except TimeoutException as e:
            logger.error(f"The process has timed out: {e}")
            self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/timeout.png")

    def update_hosts(self):
        self.open_hosts_page()
        time.sleep(5)

        banners = self.browser.find_elements(By.CSS_SELECTOR, "div[id^='expiration-banner-hostname-']")
        if not banners:
            logger.info("No expiration banners found. All hosts are up to date or page structure changed.")
            return

        for banner in banners:
            try:
                banner_id = banner.get_attribute("id")
                host_name = banner_id.replace("expiration-banner-hostname-", "")
                logger.info(f"Processing host: {host_name}")

                confirm_btn = banner.find_element(By.XPATH, ".//button[contains(text(), 'Confirm')]")
                if confirm_btn and confirm_btn.is_displayed() and confirm_btn.is_enabled():
                    logger.info(f"Clicking Confirm for {host_name}")
                    self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_btn)
                    time.sleep(0.5)
                    self.browser.execute_script("arguments[0].click();", confirm_btn)
                    logger.info(f"Confirmed {host_name}")
                    self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/{host_name}-confirmed.png")
                    time.sleep(2)
                else:
                    logger.info(f"No clickable Confirm button for {host_name}, skipping.")
            except Exception as e:
                logger.error(f"Error processing banner for host: {e}")
                continue

    # 以下旧方法保留（未使用）
    def get_host_expiration_days(self, host):
        return 0

    def get_host_link(self, host):
        try:
            name_div = host.find_element(By.CSS_SELECTOR, "div.record-name")
            host_name = name_div.text.strip()
            if '\n' in host_name:
                host_name = host_name.split('\n')[0]
            return type('obj', (object,), {'text': host_name})()
        except NoSuchElementException:
            pass
        try:
            return host.find_element(By.XPATH, ".//a[contains(@class, 'link-info') and contains(@class, 'cursor-pointer')]")
        except NoSuchElementException:
            pass
        raise Exception("Unable to extract host name from host element.")

    def get_host_button(self, host):
        try:
            button = host.find_element(By.XPATH, ".//button[contains(text(), 'Confirm') or contains(text(), 'Renew')]")
            if button.is_displayed() and button.is_enabled():
                return button
        except NoSuchElementException:
            pass
        try:
            button = host.find_element(By.XPATH, ".//button[contains(@class, 'btn-success')]")
            if button.is_displayed() and button.is_enabled():
                return button
        except NoSuchElementException:
            pass
        return None

    def get_hosts(self) -> list:
        host_records = self.browser.find_elements(By.CSS_SELECTOR, "div.zone-record")
        if host_records:
            return host_records
        host_tds = self.browser.find_elements(By.XPATH, '//td[@data-title="Host"]')
        if host_tds:
            return host_tds
        logger.warning("No hosts found. The account may have no hosts or the page structure changed.")
        with open(f"{SCREENSHOTS_PATH}/page.html", "w", encoding="utf-8") as f:
            f.write(self.browser.page_source)
        return []

    def run(self) -> int:
        return_code = 0
        try:
            self.login()
            self.update_hosts()
        except Exception as e:
            logger.error(f"An error has ocurred while Robot was running: {e}")
            self.browser.save_screenshot(f"{SCREENSHOTS_PATH}/exception.png")
            return_code = 1
        finally:
            self.browser.quit()
        return return_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="noip DDNS auto renewer",
        description="Renews each of the no-ip DDNS hosts that are below 7 days to expire period",
    )
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-p", "--password", required=True)
    parser.add_argument("-s", "--totp-secret", required=True)
    parser.add_argument("-t", "--https-proxy", required=False)
    parser.add_argument("-d", "--debug", action="store_true", default=False,
                        help="Enable debug logging")
    args = vars(parser.parse_args())

    logger.setLevel(logging.DEBUG if args["debug"] else logging.INFO)

    NoIPUpdater(
        args["username"],
        args["password"],
        args["totp_secret"],
        args["https_proxy"],
    ).run()