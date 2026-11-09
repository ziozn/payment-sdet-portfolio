from xml.etree import ElementTree

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class PaymentPage:
    AMOUNT_INPUT = (AppiumBy.ID, "com.example.paymentsim:id/et_payment_amount")
    SUBMIT = (AppiumBy.ID, "com.example.paymentsim:id/btn_submit_payment")
    STATUS = (AppiumBy.ID, "com.example.paymentsim:id/tv_payment_status")
    AMOUNT_RESULT = (AppiumBy.ID, "com.example.paymentsim:id/tv_payment_amount_result")
    TRANSACTION_ID = (AppiumBy.ID, "com.example.paymentsim:id/tv_transaction_id")
    BACK_HOME = (AppiumBy.ID, "com.example.paymentsim:id/btn_back_home")

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)

    def wait_until_loaded(self):
        self.wait.until(EC.visibility_of_element_located(self.AMOUNT_INPUT))
        self.wait.until(EC.element_to_be_clickable(self.SUBMIT))

    def enter_amount(self, value):
        field = self.wait.until(EC.visibility_of_element_located(self.AMOUNT_INPUT))
        field.clear()
        if value:
            field.send_keys(value)
        if self.driver.is_keyboard_shown():
            self.driver.hide_keyboard()

    def input_text(self):
        self.wait.until(EC.visibility_of_element_located(self.AMOUNT_INPUT))
        # Empty EditText exposes its hint as text. This driver includes the
        # showing-hint flag in XML but rejects get_attribute for that flag.
        root = ElementTree.fromstring(self.driver.page_source)
        for node in root.iter():
            if node.get("resource-id") == self.AMOUNT_INPUT[1]:
                return "" if node.get("showing-hint") == "true" else node.attrib["text"]
        raise RuntimeError("Amount field missing from the current page XML")

    def submit(self):
        self.wait.until(EC.element_to_be_clickable(self.SUBMIT)).click()

    def wait_for_status(self, expected_text):
        # The test supplies the expectation; this method only waits for the UI.
        self.wait.until(EC.text_to_be_present_in_element(self.STATUS, expected_text))

    def status_text(self):
        return self.wait.until(EC.visibility_of_element_located(self.STATUS)).text

    def amount_text(self):
        return self.wait.until(EC.visibility_of_element_located(self.AMOUNT_RESULT)).text

    def transaction_id_text(self):
        return self.wait.until(EC.visibility_of_element_located(self.TRANSACTION_ID)).text

    def back_home(self):
        self.wait.until(EC.element_to_be_clickable(self.BACK_HOME)).click()
