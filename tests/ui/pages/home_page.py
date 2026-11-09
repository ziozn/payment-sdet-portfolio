from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class HomePage:
    TITLE = (AppiumBy.ID, "com.example.paymentsim:id/tv_app_title")
    USER_NAME = (AppiumBy.ID, "com.example.paymentsim:id/tv_demo_user_name")
    USER_STATUS = (AppiumBy.ID, "com.example.paymentsim:id/tv_demo_user_status")
    ENTER_PAYMENT = (AppiumBy.ID, "com.example.paymentsim:id/btn_enter_payment")

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)

    def is_displayed(self):
        title = self.wait.until(EC.visibility_of_element_located(self.TITLE))
        button = self.wait.until(EC.element_to_be_clickable(self.ENTER_PAYMENT))
        return title.is_displayed() and button.is_displayed()

    def title_text(self):
        return self.wait.until(EC.visibility_of_element_located(self.TITLE)).text

    def user_name_text(self):
        return self.wait.until(EC.visibility_of_element_located(self.USER_NAME)).text

    def user_status_text(self):
        return self.wait.until(EC.visibility_of_element_located(self.USER_STATUS)).text

    def open_payment(self):
        self.wait.until(EC.element_to_be_clickable(self.ENTER_PAYMENT)).click()
