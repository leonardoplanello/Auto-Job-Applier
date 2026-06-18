import os
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext, Page
from backend.database import DATA_DIR

class BrowserSession:
    def __init__(self):
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def start(self, headless: bool = False) -> Page:
        """
        Launches Playwright using a persistent browser context in e:\1CODE\Auto_job_applier_linkedIn\data\chrome_profile.
        This ensures cookies, local storage, and active LinkedIn sessions persist.
        """
        if self.page:
            return self.page
            
        self.playwright = await async_playwright().start()
        
        profile_dir = os.path.join(DATA_DIR, "chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        
        # Launch persistent context to look human and persist authentication
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            channel="chrome",
            viewport=None,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        
        if not headless:
            self._focus_chrome_window()
            
        # Configure moderate network timeout
        self.context.set_default_timeout(30000)
        
        # Use existing page or open a new one
        pages = self.context.pages
        if pages:
            self.page = pages[0]
            # Close all other restored pages to avoid multi-tab confusion
            for p in pages[1:]:
                try:
                    await p.close()
                except Exception:
                    pass
        else:
            self.page = await self.context.new_page()
            
        # Avoid webdriver detection
        await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return self.page
        
    def _focus_chrome_window(self):
        import sys
        if sys.platform != "win32":
            return
        import ctypes
        import threading
        import time

        def run_focus():
            # Try a few times over 5 seconds since Chrome window might take a moment to appear
            for _ in range(10):
                time.sleep(0.5)
                try:
                    EnumWindows = ctypes.windll.user32.EnumWindows
                    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                    GetWindowText = ctypes.windll.user32.GetWindowTextW
                    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
                    IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                    SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
                    ShowWindow = ctypes.windll.user32.ShowWindow
                    
                    hwnd_to_focus = None
                    
                    def foreach_window(hwnd, lParam):
                        nonlocal hwnd_to_focus
                        if IsWindowVisible(hwnd):
                            GetClassName = ctypes.windll.user32.GetClassNameW
                            class_buff = ctypes.create_unicode_buffer(256)
                            GetClassName(hwnd, class_buff, 256)
                            class_name = class_buff.value.lower()
                            
                            if "chrome_widgetwin" in class_name:
                                length = GetWindowTextLength(hwnd)
                                buff = ctypes.create_unicode_buffer(length + 1)
                                GetWindowText(hwnd, buff, length + 1)
                                title = buff.value.lower()
                                # Match windows that contain "linkedin" or "chrome" or "chromium"
                                if "linkedin" in title or "chrome" in title or "chromium" in title:
                                    hwnd_to_focus = hwnd
                                    return False
                        return True

                    EnumWindows(EnumWindowsProc(foreach_window), 0)
                    
                    if hwnd_to_focus:
                        ShowWindow(hwnd_to_focus, 9) # SW_RESTORE
                        SetForegroundWindow(hwnd_to_focus)
                        break
                except Exception:
                    pass

        threading.Thread(target=run_focus, daemon=True).start()

    async def close(self):
        """
        Gracefully terminates context and stops playwright engine.
        """
        try:
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        finally:
            self.context = None
            self.playwright = None
            self.page = None
