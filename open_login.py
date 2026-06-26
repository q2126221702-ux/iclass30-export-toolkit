"""打开 C30 SSO 登录页并跳转到学习平台."""
import sys

from playwright.sync_api import sync_playwright

from browser_util import PORTAL, SSO, launch_logged_in_context


def main():
    print("正在打开登录页…")
    print("登录后会进入 px 学习平台，再从「学习空间」进入课程。")

    with sync_playwright() as p:
        ctx = launch_logged_in_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(SSO, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        if "portalC30" not in page.url:
            page.goto(PORTAL, wait_until="domcontentloaded", timeout=60000)
        page.evaluate(
            """() => {
                document.documentElement.style.overflow = 'auto';
                document.body.style.overflow = 'auto';
                document.body.style.minWidth = '1200px';
            }"""
        )
        print("浏览器已打开。请完成登录。")
        try:
            input("完成后按 Enter 关闭浏览器...")
        except EOFError:
            try:
                page.wait_for_timeout(3_600_000)
            except Exception:
                pass
        try:
            ctx.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
