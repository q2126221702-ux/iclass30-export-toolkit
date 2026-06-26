"""共用：稳定启动浏览器（避免空白页）."""
import os
import shutil
from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright

ROOT = Path(__file__).parent
OLD_SESSION = ROOT / ".browser_session"
# 独立会话目录，避免与旧项目或其他副本共用登录态/缓存
TEMP_SESSION = Path(os.environ.get("TEMP", "C:/Temp")) / "iclass30_export_toolkit_session"

PORTAL = "https://px.iclass30.com/portalC30/home"
SSO = (
    "https://sso.iclass30.com/login"
    "?redirect_uri=https%3A%2F%2Fpx.iclass30.com%2FportalC30%2Fhome"
)


def pick_session_dir() -> Path:
    """优先用项目内会话（含登录态），失败时再用 TEMP."""
    if (OLD_SESSION / "Default").exists():
        return OLD_SESSION
    TEMP_SESSION.mkdir(parents=True, exist_ok=True)
    cookie = TEMP_SESSION / "Default" / "Network" / "Cookies"
    if OLD_SESSION.exists() and not cookie.exists():
        try:
            shutil.copytree(OLD_SESSION, TEMP_SESSION, dirs_exist_ok=True)
        except Exception:
            pass
    return TEMP_SESSION


def launch_logged_in_context(p: Playwright) -> BrowserContext:
    session = pick_session_dir()
    last_err = None
    for user_data in (session, TEMP_SESSION):
        try:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data),
                headless=False,
                viewport={"width": 1400, "height": 900},
                locale="zh-CN",
            )
            return ctx
        except Exception as e:
            last_err = e
    raise RuntimeError(f"无法启动浏览器: {last_err}")


def open_portal_page(ctx: BrowserContext):
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.bring_to_front()
    except Exception:
        pass
    page.goto(PORTAL, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(2000)
    body_len = page.evaluate("() => (document.body && document.body.innerText || '').length")
    if body_len < 20:
        page.goto(SSO, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(2000)
    return page
