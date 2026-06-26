"""打开 C30 学习平台（仅打开浏览器，不自动点击）."""
import sys

from playwright.sync_api import sync_playwright

from browser_util import launch_logged_in_context, open_portal_page


def main():
    with sync_playwright() as p:
        ctx = launch_logged_in_context(p)
        page = open_portal_page(ctx)
        print("已打开:", page.url)
        print("路径: 头像 -> 学习空间 -> 你的课程 -> 作业考试 -> 测验/作业")
        try:
            input("按 Enter 关闭...")
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
