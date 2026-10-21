import inspect
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from backend.config.spider import *

class FSSpider:
    def __init__(self, cookies):
        self.wd = webdriver.Chrome()
        self.wait = WebDriverWait(self.wd, GLOBAL_SPIDER_EL_WAIT_TIME)
        self.cookies = cookies

    @staticmethod
    def get_missing_required_params(func, **kwargs):
        missing_params = []
        signature = inspect.signature(func)
        for name, parameter in signature.parameters.items():
            if name == 'self' or parameter.default is not inspect.Signature.empty:
                continue
            value = kwargs.get(name)
            if value is None:
                missing_params.append(name)
                continue
            if isinstance(value, str) and not value.strip():
                missing_params.append(name)
        return missing_params

    def login(self):
        self.wd.get("https://hire.feishu.cn/hunter/position")

        for cookie in self.cookies:
            try:
                # 只保留常用字段
                clean_cookie = {
                    k: v for k, v in cookie.items()
                    if k in {"name", "value", "domain", "path", "expiry", "secure", "httpOnly", "sameSite"}
                }

                # 修正 expiry
                if "expiry" in clean_cookie and clean_cookie["expiry"] is not None:
                    try:
                        clean_cookie["expiry"] = int(clean_cookie["expiry"])
                    except Exception:
                        clean_cookie.pop("expiry", None)

                # 修正 sameSite
                if "sameSite" in clean_cookie:
                    val = str(clean_cookie["sameSite"]).strip()

                    mapping = {
                        "strict": "Strict",
                        "lax": "Lax",
                        "none": "None",
                        "no_restriction": "None",
                        "unspecified": None,
                        "": None,
                    }

                    mapped = mapping.get(val.lower(), None)

                    if mapped is None:
                        clean_cookie.pop("sameSite", None)
                    else:
                        clean_cookie["sameSite"] = mapped

                self.wd.add_cookie(clean_cookie)
                print(f"添加成功: {clean_cookie.get('name')}")

            except Exception as e:
                print(f"添加 cookie 失败: {cookie.get('name')} -> {type(e).__name__}: {repr(e)}")

        # 刷新让 cookie 生效
        self.wd.get("https://hire.feishu.cn/hunter/position")

    def go_to_recommend_page(self, name):
        while True:
            try:
                job_tr = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, f"//tr[contains(.,'{name}')]"))
                )

                job_tr.click()

                recommend_button = self.wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "atsx-btn-primary"))
                )
                recommend_button.click()
                return True

            except Exception:
                next_page_li = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "atsx-pagination-next"))
                )

                if next_page_li.get_attribute("aria-disabled") == "true":
                    return False

                next_page_li.click()

    def recommend_candidate(self, resume_name, resume_phone, resume_school,
                            resume_edu_level='博士', edu_start_year="2020", edu_start_month="09",
                            edu_end_year="2024", edu_end_month="06", resume_email="candidate@example.com",
                            is_duplicate_with_fs=True):

        name_input = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-cy="nameInput"]'))
        )

        name_input.send_keys(str(resume_name))

        phone_input = self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'atsx-phone-input'))
        )

        phone_input.send_keys(str(resume_phone))

        email_input = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-cy="emailInput"]'))
        )

        email_input.send_keys(resume_email)

        school_input = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-cy="education[0].schoolInput"]'))
        )

        school_input.send_keys(str(resume_school))

        self.wd.execute_script(
            'document.getElementsByClassName("resumeEditForm-item resumeEditForm-education")[0].getElementsByClassName("atsx-select-arrow-icon")[0].click()')

        time.sleep(1)

        self.wd.execute_script("""
    const target = arguments[0];

    Array.from(document.getElementsByClassName("atsx-select-dropdown-menu-item"))
      .find(a => a.textContent.trim() === target)
      ?.click();
    """, edu_level_map[resume_edu_level])

        work_exp_check_box = self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'atsx-checkbox-input'))
        )

        work_exp_check_box.click()

        self.wd.execute_script("""
    document.getElementsByClassName("atsx-date-picker-period-month-label-year")[0].click()
    """)
        time.sleep(1)
        self.wd.execute_script("""
    const target = arguments[0];
    const el = document.querySelector(`[data-cy="${target}"]`);
    if (el) el.click();
    else throw new Error(`没找到 data-cy=${target} 的元素`);
    """, edu_start_year)
        self.wd.execute_script("""
    document.getElementsByClassName("atsx-date-picker-period-month-label-month")[0].click()
    """)
        time.sleep(1)
        self.wd.execute_script("""
    const target = arguments[0];
    const el = document.querySelector(`[data-cy="${target}"]`);
    if (el) el.click();
    else throw new Error(`没找到 data-cy=${target} 的元素`);
    """, edu_start_month)

        self.wd.execute_script("""
    document.getElementsByClassName("atsx-date-picker-period-month-label-year")[1].click()
    """)
        time.sleep(1)
        self.wd.execute_script("""
    const target = arguments[0];
    const el = document.querySelector(`[data-cy="${target}"]`);
    if (el) el.click();
    else throw new Error(`没找到 data-cy=${target} 的元素`);
    """, edu_end_year)
        self.wd.execute_script("""
    document.getElementsByClassName("atsx-date-picker-period-month-label-month")[1].click()
    """)
        time.sleep(1)
        self.wd.execute_script("""
    const target = arguments[0];
    const el = document.querySelector(`[data-cy="${target}"]`);
    if (el) el.click();
    else throw new Error(`没找到 data-cy=${target} 的元素`);
    """, edu_end_month)

        submit_button = self.wait.until(
            EC.presence_of_element_located((By.XPATH, f"//button[contains(.,'简历查重')]"))
        )
        submit_button.click()

        pop_span = self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "atsx-modal-confirm-title"))
        )

        if "未发现重复简历" in pop_span.text:
            is_duplicate_with_fs = False

        know_button = self.wait.until(
            EC.presence_of_element_located((By.XPATH, f"//button[contains(.,'我知道了')]"))
        )
        know_button.click()
        return is_duplicate_with_fs

    def quit(self):
        self.wd.quit()

# Manual demo removed from repository import; use synthetic fixtures for local testing.
