import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from backend.config.spider import GLOBAL_SPIDER_EL_WAIT_TIME
from backend.logger.logger import get_logger

logger = get_logger(__name__)


class LiepinResumeNoteSpider:
    HOME_URL = "https://h.liepin.com/"
    CHAT_URL = "https://h.liepin.com/im/showmsgnewpage"
    RESUME_DETAIL_URL = "https://h.liepin.com/resume/showresumedetail/?res_id_encode={encode_res_id}&encryptResId="
    LOGIN_MARKERS = ("登录", "扫码登录", "手机登录", "账号登录", "验证码登录")
    LAUNCH_TIMEOUT_MS = 30000
    PROFILE_ENV_BROWSER = "LIEPIN_NOTE_BROWSER"
    PROFILE_ENV_USER_DATA_DIR = "LIEPIN_NOTE_USER_DATA_DIR"
    PROFILE_ENV_DIRECTORY = "LIEPIN_NOTE_PROFILE_DIRECTORY"
    CDP_ENABLED_ENV = "LIEPIN_NOTE_USE_CDP"
    CDP_URL_ENV = "LIEPIN_NOTE_CDP_URL"
    CDP_BROWSER_PATH_ENV = "LIEPIN_NOTE_BROWSER_PATH"
    CDP_USER_DATA_DIR_ENV = "LIEPIN_NOTE_CDP_USER_DATA_DIR"
    DEFAULT_CDP_URL = "http://127.0.0.1:9222"
    CDP_STARTUP_TIMEOUT_SECONDS = 15

    def __init__(self, cookies):
        self.cookies = cookies
        self.playwright = sync_playwright().start()
        self.browser = None
        self.context = None
        self.page = None
        self.driver_context = None
        self.context, self.page, self.driver_context = self._create_context()

    @staticmethod
    def _existing_paths(paths):
        return [path for path in paths if path and os.path.exists(path)]

    @classmethod
    def _get_browser_diagnostics(cls):
        chrome_user_data_paths = cls._existing_paths([
            os.path.expandvars(r'%LocalAppData%\Google\Chrome\User Data'),
        ])
        edge_user_data_paths = cls._existing_paths([
            os.path.expandvars(r'%LocalAppData%\Microsoft\Edge\User Data'),
        ])
        return {
            'chrome_user_data_paths': chrome_user_data_paths,
            'edge_user_data_paths': edge_user_data_paths,
        }

    @classmethod
    def _browser_channel(cls, browser_name):
        return 'msedge' if browser_name == 'edge' else 'chrome'

    @classmethod
    def _get_profile_candidates(cls, user_data_dir):
        env_profile = os.environ.get(cls.PROFILE_ENV_DIRECTORY)
        if env_profile:
            return [env_profile]

        candidates = []
        for name in ("Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4"):
            if os.path.isdir(os.path.join(user_data_dir, name)):
                candidates.append(name)
        return candidates or ["Default"]

    @classmethod
    def _common_launch_args(cls, profile_directory=None):
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if profile_directory:
            args.append(f"--profile-directory={profile_directory}")
        return args

    @classmethod
    def _build_profile_context(cls, browser_name, user_data_dir, profile_directory):
        return {
            'browser': browser_name,
            'strategy': 'local_profile',
            'user_data_dir': user_data_dir,
            'profile_directory': profile_directory,
        }

    @classmethod
    def _build_cookie_context(cls, browser_name):
        return {
            'browser': browser_name,
            'strategy': 'cookie_only',
            'user_data_dir': None,
            'profile_directory': None,
        }

    @classmethod
    def _build_cdp_context(cls, browser_name, cdp_url, user_data_dir, launched):
        return {
            'browser': browser_name,
            'strategy': 'cdp',
            'cdp_url': cdp_url,
            'user_data_dir': user_data_dir,
            'launched_by_program': launched,
        }

    @staticmethod
    def _is_env_enabled(key, default=True):
        value = os.environ.get(key)
        if value is None:
            return default
        return value.strip().lower() not in {"0", "false", "no", "off"}

    def _get_browser_name(self):
        browser_name = (os.environ.get(self.PROFILE_ENV_BROWSER) or "").strip().lower()
        return 'edge' if browser_name == 'edge' else 'chrome'

    @classmethod
    def _default_cdp_user_data_dir(cls):
        return Path(__file__).resolve().parents[2] / 'save' / 'browser-profile' / 'liepin-note'

    @classmethod
    def _get_cdp_user_data_dir(cls):
        configured = os.environ.get(cls.CDP_USER_DATA_DIR_ENV)
        return Path(configured).expanduser() if configured else cls._default_cdp_user_data_dir()

    @classmethod
    def _get_cdp_url(cls):
        return os.environ.get(cls.CDP_URL_ENV, cls.DEFAULT_CDP_URL).strip() or cls.DEFAULT_CDP_URL

    @staticmethod
    def _get_cdp_port(cdp_url):
        parsed = urlparse(cdp_url)
        return parsed.port or 9222

    @classmethod
    def _find_browser_executable(cls, browser_name):
        configured = os.environ.get(cls.CDP_BROWSER_PATH_ENV)
        if configured and os.path.exists(configured):
            return configured

        if browser_name == 'edge':
            candidates = [
                shutil.which('msedge'),
                os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
                os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
            ]
        else:
            candidates = [
                shutil.which('chrome'),
                shutil.which('google-chrome'),
                os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
                os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
                os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
            ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    @classmethod
    def _is_cdp_available(cls, cdp_url):
        try:
            with urlopen(f"{cdp_url.rstrip('/')}/json/version", timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def _ensure_cdp_browser(self, browser_name, cdp_url, user_data_dir):
        if self._is_cdp_available(cdp_url):
            logger.info(f"检测到已启动的猎聘备注 Chrome 调试端口，cdp_url={cdp_url}")
            return False

        browser_path = self._find_browser_executable(browser_name)
        if not browser_path:
            raise RuntimeError(f"未找到可用浏览器程序，browser={browser_name}")

        user_data_dir.mkdir(parents=True, exist_ok=True)
        port = self._get_cdp_port(cdp_url)
        command = [
            browser_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={str(user_data_dir)}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        logger.info(
            f"自动启动猎聘备注专用浏览器，browser={browser_name}，cdp_url={cdp_url}，"
            f"user_data_dir={user_data_dir}"
        )
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )

        deadline = time.time() + self.CDP_STARTUP_TIMEOUT_SECONDS
        while time.time() < deadline:
            if self._is_cdp_available(cdp_url):
                logger.info(f"猎聘备注专用浏览器启动成功，cdp_url={cdp_url}")
                return True
            time.sleep(0.5)

        raise RuntimeError(f"猎聘备注专用浏览器启动超时，cdp_url={cdp_url}")

    def _connect_cdp_context(self, browser_name):
        cdp_url = self._get_cdp_url()
        user_data_dir = self._get_cdp_user_data_dir()
        launched = self._ensure_cdp_browser(browser_name, cdp_url, user_data_dir)
        logger.info(f"尝试连接猎聘备注 Chrome 调试端口，cdp_url={cdp_url}")
        self.browser = self.playwright.chromium.connect_over_cdp(cdp_url)
        self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        self.page = self._ensure_page()
        logger.info(f"连接猎聘备注 Chrome 调试端口成功，cdp_url={cdp_url}")
        return self.context, self.page, self._build_cdp_context(
            browser_name,
            cdp_url,
            str(user_data_dir),
            launched,
        )

    def _ensure_page(self):
        if self.context.pages:
            self.page = self.context.pages[-1]
        else:
            self.page = self.context.new_page()
        return self.page

    def _launch_persistent_context(self, browser_name, user_data_dir, profile_directory):
        channel = self._browser_channel(browser_name)
        logger.info(
            f"尝试初始化 Playwright 备注浏览器，browser={browser_name}，channel={channel}，"
            f"user_data_dir={user_data_dir}，profile_directory={profile_directory}"
        )
        context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel=channel,
            headless=False,
            timeout=self.LAUNCH_TIMEOUT_MS,
            args=self._common_launch_args(profile_directory=profile_directory),
        )
        self.context = context
        page = self._ensure_page()
        return context, page

    def _launch_cookie_context(self, browser_name):
        channel = self._browser_channel(browser_name)
        logger.info(f"尝试初始化 Playwright 备注浏览器，browser={browser_name}，channel={channel}，cookie_only=True")
        self.browser = self.playwright.chromium.launch(
            channel=channel,
            headless=False,
            timeout=self.LAUNCH_TIMEOUT_MS,
            args=self._common_launch_args(),
        )
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        return self.context, self.page

    def _create_context(self):
        diagnostics = self._get_browser_diagnostics()
        browser_name = self._get_browser_name()
        errors = []

        if self._is_env_enabled(self.CDP_ENABLED_ENV, default=True):
            try:
                return self._connect_cdp_context(browser_name)
            except Exception as e:
                errors.append(f"{browser_name}_cdp={e}")
                logger.warning(f"连接或启动猎聘备注专用浏览器失败，回退原初始化逻辑: {e}")

        user_data_dir = os.environ.get(self.PROFILE_ENV_USER_DATA_DIR)
        if not user_data_dir:
            key = 'edge_user_data_paths' if browser_name == 'edge' else 'chrome_user_data_paths'
            user_data_dir = diagnostics[key][0] if diagnostics[key] else None

        if user_data_dir:
            for profile_directory in self._get_profile_candidates(user_data_dir):
                try:
                    context, page = self._launch_persistent_context(browser_name, user_data_dir, profile_directory)
                    return context, page, self._build_profile_context(browser_name, user_data_dir, profile_directory)
                except Exception as e:
                    errors.append(f"{browser_name}_profile[{profile_directory}]={e}")
                    if "non-default data directory" in str(e):
                        logger.warning(
                            "Playwright 不支持直接复用浏览器默认 User Data 根目录，"
                            "请改用独立的自动化目录并手动登录一次后再复用。"
                        )
                    logger.warning(f"初始化 Playwright 本地 profile 备注浏览器失败: {e}")

        try:
            context, page = self._launch_cookie_context(browser_name)
            return context, page, self._build_cookie_context(browser_name)
        except Exception as e:
            errors.append(f"{browser_name}_cookie_only={e}")
            raise RuntimeError(
                f"无法初始化 Playwright 备注浏览器: browser={browser_name}, "
                f"user_data_dir={user_data_dir}, errors={errors}"
            ) from e

    @staticmethod
    def _clean_cookie(cookie):
        clean_cookie = {
            k: v for k, v in cookie.items()
            if k in {"name", "value", "domain", "path", "expiry", "secure", "httpOnly", "sameSite"}
        }

        expiry = clean_cookie.pop("expiry", None)
        if expiry is not None:
            try:
                expiry = float(expiry)
            except Exception:
                expiry = None
        if expiry and expiry > time.time():
            clean_cookie["expires"] = expiry

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
                if mapped == "None" and not clean_cookie.get("secure"):
                    clean_cookie.pop("sameSite", None)
                else:
                    clean_cookie["sameSite"] = mapped

        clean_cookie["path"] = clean_cookie.get("path") or "/"
        return clean_cookie

    @staticmethod
    def _cookie_domain(cookie):
        domain = (cookie or {}).get("domain")
        if not domain:
            return ""
        return str(domain).strip().lower()

    @staticmethod
    def _cookie_host(cookie):
        return LiepinResumeNoteSpider._cookie_domain(cookie).lstrip('.')

    def _cookie_matches_host(self, cookie, host):
        cookie_host = self._cookie_host(cookie)
        if not cookie_host:
            return host == "h.liepin.com"
        return host == cookie_host or host.endswith("." + cookie_host) or cookie_host == "liepin.com"

    def _domain_visit_url(self, host):
        if host == "h.liepin.com":
            return self.HOME_URL
        if host == "www.liepin.com":
            return "https://www.liepin.com/"
        if host == "passport.liepin.com":
            return "https://passport.liepin.com/"
        return f"https://{host}/"

    def _apply_cookies_for_host(self, host):
        cookies_to_add = []
        skipped_expired = 0
        failed = []
        for raw_cookie in self.cookies:
            if not self._cookie_matches_host(raw_cookie, host):
                continue
            clean_cookie = self._clean_cookie(raw_cookie)
            if "expires" not in clean_cookie and raw_cookie.get("expiry"):
                skipped_expired += 1
                continue
            try:
                cookies_to_add.append(clean_cookie)
            except Exception as e:
                failed.append(f"{raw_cookie.get('name')}={type(e).__name__}:{e}")

        if cookies_to_add:
            self.context.add_cookies(cookies_to_add)

        logger.info(
            f"猎聘 cookie 注入完成，host={host}，added={len(cookies_to_add)}，"
            f"failed={len(failed)}，skipped_expired={skipped_expired}"
        )
        if failed:
            logger.warning(f"猎聘 cookie 注入失败详情，host={host}，samples={failed[:5]}")

        return len(cookies_to_add), failed

    def _get_cookie_hosts(self):
        cookie_hosts = []
        for raw_cookie in self.cookies:
            host = self._cookie_host(raw_cookie)
            if host:
                cookie_hosts.append(host)

        ordered_hosts = []
        for host in ["www.liepin.com", "passport.liepin.com", "h.liepin.com"]:
            if host not in ordered_hosts:
                ordered_hosts.append(host)
        for host in cookie_hosts:
            if host not in ordered_hosts:
                ordered_hosts.append(host)
        return ordered_hosts

    def _wait_page_ready(self, page=None):
        target_page = page or self.page
        try:
            target_page.wait_for_load_state("domcontentloaded", timeout=GLOBAL_SPIDER_EL_WAIT_TIME * 1000)
        except PlaywrightTimeoutError:
            pass
        try:
            target_page.wait_for_load_state("networkidle", timeout=GLOBAL_SPIDER_EL_WAIT_TIME * 1000)
        except PlaywrightTimeoutError:
            pass

    def _is_logged_in(self):
        current_url = (self.page.url or "").lower()
        if any(marker in current_url for marker in ("login", "passport", "signin")):
            return False

        try:
            body_text = (self.page.locator("body").inner_text(timeout=3000) or "")[:2000]
        except Exception:
            body_text = ""

        if any(marker in body_text for marker in self.LOGIN_MARKERS):
            positive_markers = ("诚猎通", "职位", "聊天", "候选人", "简历")
            if not any(marker in body_text for marker in positive_markers):
                return False
        return True

    def login(self):
        logger.info(f"猎聘备注浏览器登录开始，driver_context={self.driver_context}")
        self.page.goto(self.CHAT_URL)
        self._wait_page_ready()

        if self._is_logged_in():
            logger.info(
                f"猎聘备注浏览器复用本地登录态成功，current_url={self.page.url}，"
                f"driver_context={self.driver_context}"
            )
            return

        logger.info(
            f"本地浏览器 profile 未直接带出登录态，开始回退 cookie 注入，"
            f"driver_context={self.driver_context}"
        )
        self.context.clear_cookies()
        host_results = {}
        for host in self._get_cookie_hosts():
            host_results[host] = self._apply_cookies_for_host(host)

        self.page.goto(self.CHAT_URL)
        self._wait_page_ready()

        if not self._is_logged_in():
            self._dump_debug_snapshot('login_failed')
            raise RuntimeError(
                f"猎聘备注浏览器未进入登录态，current_url={self.page.url}，host_results={host_results}"
            )

        logger.info(f"猎聘备注浏览器登录态校验成功，current_url={self.page.url}")

    @staticmethod
    def _sanitize_filename(value):
        safe = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in (value or 'unknown'))
        return safe[:60] or 'unknown'

    def _dump_debug_snapshot(self, stage, encode_res_id=None, candidate_name=None, opposite_im_id=None):
        try:
            debug_dir = Path(__file__).resolve().parents[2] / 'save' / 'cookies' / 'debug'
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            file_stub = (
                f"liepin_note_{stage}_"
                f"{self._sanitize_filename(candidate_name)}_"
                f"{self._sanitize_filename(encode_res_id)}_"
                f"{timestamp}"
            )
            html_path = debug_dir / f"{file_stub}.html"
            png_path = debug_dir / f"{file_stub}.png"
            info_path = debug_dir / f"{file_stub}.txt"

            html_path.write_text(self.page.content(), encoding='utf-8')
            try:
                self.page.screenshot(path=str(png_path), full_page=True)
            except Exception:
                pass

            info_path.write_text(
                "\n".join([
                    f"stage={stage}",
                    f"candidate_name={candidate_name or ''}",
                    f"encode_res_id={encode_res_id or ''}",
                    f"opposite_im_id={opposite_im_id or ''}",
                    f"url={self.page.url}",
                    f"title={self.page.title()}",
                ]),
                encoding='utf-8'
            )
            logger.warning(f"已写入猎聘备注调试快照: {html_path}")
        except Exception as e:
            logger.warning(f"写入猎聘备注调试快照失败: {e}")

    def open_resume_detail(self, encode_res_id):
        self.page.goto(self.RESUME_DETAIL_URL.format(encode_res_id=encode_res_id))
        self._wait_page_ready()

    def open_chat_page(self):
        self.page.goto(self.CHAT_URL)
        self._wait_page_ready()

    def _switch_to_detail_after_click(self, previous_pages):
        try:
            self.context.wait_for_event(
                "page",
                timeout=GLOBAL_SPIDER_EL_WAIT_TIME * 1000,
            )
        except PlaywrightTimeoutError:
            pass

        for page in reversed(self.context.pages):
            if page not in previous_pages:
                self.page = page
                self._wait_page_ready()
                return "showresumedetail" in (self.page.url or "")

        self._wait_page_ready()
        return "showresumedetail" in (self.page.url or "")

    def _click_chat_entry_to_detail(self, candidate_name):
        selector_builders = [
            lambda: self.page.locator('[data-tlg-elem-id="h_pc_im_photo_name_btn"]'),
            lambda: self.page.locator('.im-ui-pro-chat-header-name'),
            lambda: self.page.locator('.im-ui-pro-chat-header-work-compname'),
            lambda: self.page.locator('.im-ui-pro-chat-header-work-title'),
            lambda: self.page.locator('[class*="im-ui-pro-chat-header"]').filter(has_text=candidate_name),
        ]

        for builder in selector_builders:
            locator = builder()
            count = locator.count()
            for index in range(min(count, 5)):
                candidate = locator.nth(index)
                try:
                    if not candidate.is_visible(timeout=1000):
                        continue
                except Exception:
                    continue

                previous_pages = set(self.context.pages)
                candidate.click(force=True)
                if self._switch_to_detail_after_click(previous_pages):
                    logger.info(f"已从职聊跳转候选人详情页，候选人={candidate_name}")
                    return
                time.sleep(0.5)

        raise RuntimeError("未找到职聊页候选人详情入口")

    def _open_resume_detail_via_chat(self, candidate_name, encode_res_id=None, opposite_im_id=None):
        if not candidate_name:
            raise RuntimeError("缺少 candidate_name，无法从职聊页跳转详情")

        logger.info(
            f"尝试从职聊页跳转候选人详情，候选人={candidate_name}，"
            f"encode_res_id={encode_res_id}，opposite_im_id={opposite_im_id}"
        )
        self.open_chat_page()
        self._click_chat_entry_to_detail(candidate_name)
        if "showresumedetail" not in (self.page.url or ""):
            raise RuntimeError(f"职聊跳转后未进入详情页，current_url={self.page.url}")

    def _open_note_drawer_if_needed(self, encode_res_id=None, candidate_name=None, opposite_im_id=None):
        textarea = self.page.locator("#add-resume-note_rcContext")
        if textarea.count() and textarea.first.is_visible():
            return

        selectors = [
            '[data-tlg-elem-id="h_pc_res_detail_renark_btn"]',
            'button.c-add-btn',
            'button:has-text("添加备注")',
            'button:has-text("备注")',
        ]

        for selector in selectors:
            locator = self.page.locator(selector)
            count = locator.count()
            for index in range(min(count, 5)):
                button = locator.nth(index)
                try:
                    if not button.is_visible(timeout=1000):
                        continue
                    button.click(force=True)
                    self.page.wait_for_selector("#add-resume-note_rcContext", state="visible",
                                                timeout=GLOBAL_SPIDER_EL_WAIT_TIME * 1000)
                    return
                except Exception:
                    continue

        self._dump_debug_snapshot(
            'note_button_not_found',
            encode_res_id=encode_res_id,
            candidate_name=candidate_name,
            opposite_im_id=opposite_im_id
        )
        raise RuntimeError("未找到添加备注按钮")

    @staticmethod
    def _normalize_text(text):
        return ''.join((text or '').split())

    def _note_already_exists(self, note_text):
        normalized_note = self._normalize_text(note_text)
        if not normalized_note:
            return False

        selectors = ['.resume-node-drawer-list', '.resume-node-box']
        for selector in selectors:
            locator = self.page.locator(selector)
            for index in range(locator.count()):
                try:
                    container_text = self._normalize_text(locator.nth(index).inner_text(timeout=1000))
                except Exception:
                    continue
                if normalized_note in container_text:
                    return True
        return False

    def add_resume_note(self, encode_res_id, note_text, candidate_name=None, opposite_im_id=None):
        if not encode_res_id or not note_text:
            return "skipped"

        chat_flow_error = None
        if candidate_name:
            try:
                self._open_resume_detail_via_chat(candidate_name, encode_res_id, opposite_im_id)
            except Exception as e:
                chat_flow_error = e
                logger.warning(
                    f"职聊跳转详情失败，候选人={candidate_name}，encode_res_id={encode_res_id}，"
                    f"opposite_im_id={opposite_im_id}，error={e}"
                )

        if "showresumedetail" not in (self.page.url or ""):
            logger.info(f"开始兜底直达候选人详情页，候选人={candidate_name}，encode_res_id={encode_res_id}")
            self.open_resume_detail(encode_res_id)

        self._open_note_drawer_if_needed(
            encode_res_id=encode_res_id,
            candidate_name=candidate_name,
            opposite_im_id=opposite_im_id
        )

        if self._note_already_exists(note_text):
            logger.info(f"猎聘备注已存在，跳过保存，encode_res_id={encode_res_id}")
            return "duplicate"

        textarea = self.page.locator("#add-resume-note_rcContext")
        try:
            textarea.wait_for(state="visible", timeout=GLOBAL_SPIDER_EL_WAIT_TIME * 1000)
        except PlaywrightTimeoutError:
            self._dump_debug_snapshot(
                'note_textarea_not_found',
                encode_res_id=encode_res_id,
                candidate_name=candidate_name,
                opposite_im_id=opposite_im_id
            )
            if chat_flow_error:
                raise RuntimeError(f"未找到备注输入框，且职聊跳转详情失败: {chat_flow_error}")
            raise

        textarea.fill(note_text)

        save_button = self.page.locator('form#add-resume-note button[type="submit"]')
        try:
            save_button.wait_for(state="visible", timeout=GLOBAL_SPIDER_EL_WAIT_TIME * 1000)
            save_button.click(force=True)
        except PlaywrightTimeoutError:
            self._dump_debug_snapshot(
                'note_save_button_not_found',
                encode_res_id=encode_res_id,
                candidate_name=candidate_name,
                opposite_im_id=opposite_im_id
            )
            raise

        time.sleep(1)
        return "saved"

    def quit(self):
        is_cdp_context = (self.driver_context or {}).get('strategy') == 'cdp'
        try:
            if self.context and not is_cdp_context:
                self.context.close()
        finally:
            if self.browser and not is_cdp_context:
                self.browser.close()
            self.playwright.stop()
