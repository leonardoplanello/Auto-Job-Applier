import asyncio
import time
import random
import urllib.parse
from typing import List, Optional
from playwright.async_api import Page
from sqlalchemy.orm import Session
from backend.models import Job, SearchCriteria
from backend.services.logger import log_event
from backend.bot.qa_resolver import BrowserClosedException, is_browser_closed_exception

def build_linkedin_search_url(keyword: str, location: str, remote_only: bool, date_filter: str, exp_levels: List[str]) -> str:
    """
    Constructs the target search URL containing filters for keywords, location, Easy Apply,
    experience levels, and date ranges.
    """
    base = "https://www.linkedin.com/jobs/search/?"
    params = {
        "keywords": keyword,
        "location": location,
        "f_AL": "true"  # Mandatory Easy Apply filter
    }
    
    # Workplace type (Remote Only = 2)
    if remote_only:
        params["f_WT"] = "2"
        
    # Date posted
    if date_filter == "past_day":
        params["f_TPR"] = "r86400"
    elif date_filter == "past_week":
        params["f_TPR"] = "r604800"
    elif date_filter == "past_month":
        params["f_TPR"] = "r2592000"
        
    # Experience Level mapping
    level_map = {
        "internship": "1",
        "entry_level": "2",
        "associate": "3",
        "mid_senior": "4",
        "director": "5",
        "executive": "6"
    }
    if exp_levels:
        mapped_levels = [level_map[l] for l in exp_levels if l in level_map]
        if mapped_levels:
            params["f_E"] = ",".join(mapped_levels)
            
    return base + urllib.parse.urlencode(params)

async def apply_company_filter_ui(page: Page, company_name: str, session_id: str) -> bool:
    """
    Attempts to apply the company filter via the LinkedIn web interface.
    Clicks the 'Company' filter button, types the company name, selects the matching
    suggestion from the popup dropdown, and clicks the apply/show results button.
    """
    log_event(session_id, "info", "search", f"Attempting to apply company filter for '{company_name}' via LinkedIn UI...")
    
    # 1. Find the Company filter button
    company_button = None
    button_selectors = [
        "button[aria-label*='Company' i]",
        "button[aria-label*='Empresa' i]",
        "button:has-text('Company')",
        "button:has-text('Empresa')",
    ]
    for sel in button_selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible():
                    company_button = el
                    break
            if company_button:
                break
        except Exception:
            continue
            
    if not company_button:
        log_event(session_id, "warning", "search", "Could not find 'Company' filter button directly. Trying 'All filters'...")
        # Try to click "All filters" or "Todos os filtros" as fallback
        all_filters_button = None
        all_filters_selectors = [
            "button[aria-label*='All filters' i]",
            "button[aria-label*='Todos os filtros' i]",
            "button:has-text('All filters')",
            "button:has-text('Todos os filtros')",
        ]
        for sel in all_filters_selectors:
            try:
                loc = page.locator(sel)
                if await loc.first.is_visible():
                    all_filters_button = loc.first
                    break
            except Exception:
                continue
                
        if all_filters_button:
            try:
                await all_filters_button.click()
                await page.wait_for_timeout(random.randint(1500, 2500))
            except Exception as e:
                log_event(session_id, "warning", "search", f"Failed to click 'All filters' button: {str(e)}")
                return False
        else:
            log_event(session_id, "warning", "search", "Could not find 'All filters' button either.")
            return False
            
    else:
        # Click the Company filter button
        try:
            await company_button.click()
            await page.wait_for_timeout(random.randint(1500, 2500))
        except Exception as e:
            log_event(session_id, "warning", "search", f"Failed to click 'Company' filter button: {str(e)}")
            return False
            
    # 2. Locate the "Add a company" input field
    company_input = None
    input_selectors = [
        "input[placeholder*='Add a company' i]",
        "input[placeholder*='Adicionar uma empresa' i]",
        "input[placeholder*='Adicionar empresa' i]",
        "input[placeholder*='company' i]",
        "input[placeholder*='empresa' i]",
    ]
    for sel in input_selectors:
        try:
            loc = page.locator(sel)
            if await loc.first.is_visible():
                company_input = loc.first
                break
        except Exception:
            continue
            
    if not company_input:
        log_event(session_id, "warning", "search", "Could not find 'Add a company' input field.")
        return False
        
    try:
        await company_input.click()
        await page.wait_for_timeout(random.randint(500, 1000))
        # Clear existing text if any, then type company name
        await company_input.fill("")
        await company_input.type(company_name, delay=random.randint(100, 200))
        await page.wait_for_timeout(random.randint(2500, 4000))  # Wait for suggestions to load
    except Exception as e:
        log_event(session_id, "warning", "search", f"Failed to type company name: {str(e)}")
        return False
        
    # 3. Select the company suggestion
    suggestion_clicked = False
    suggestion_selectors = [
        "ul[role='listbox'] li",
        "[role='listbox'] [role='option']",
        ".typeahead-suggestion",
        "div[role='option']",
        ".search-reusables__value-label",
    ]
    for sel in suggestion_selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            for i in range(count):
                item = loc.nth(i)
                if await item.is_visible():
                    text = await item.inner_text()
                    if company_name.lower() in text.lower():
                        await item.click()
                        suggestion_clicked = True
                        log_event(session_id, "info", "search", f"Clicked suggestion: '{text.strip()}'")
                        await page.wait_for_timeout(random.randint(1000, 1500))
                        break
            if suggestion_clicked:
                break
        except Exception:
            continue
            
    if not suggestion_clicked:
        log_event(session_id, "warning", "search", f"Could not find exact suggestion matching '{company_name}'. Attempting fallback press Enter...")
        try:
            await company_input.press("Enter")
            await page.wait_for_timeout(random.randint(1000, 1500))
        except Exception as e:
            log_event(session_id, "warning", "search", f"Failed to press Enter: {str(e)}")
            
    # 4. Click the "Show results" / "Apply" button
    apply_clicked = False
    apply_selectors = [
        "button:has-text('Show results')",
        "button:has-text('Exibir resultados')",
        "button:has-text('Mostrar resultados')",
        "button:has-text('Apply')",
        "button:has-text('Aplicar')",
        "button[data-control-name='filter_show_results']",
    ]
    for sel in apply_selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible():
                    await el.click()
                    apply_clicked = True
                    log_event(session_id, "info", "search", "Clicked 'Show results' / 'Apply' button.")
                    await page.wait_for_timeout(random.randint(3000, 5000))  # Wait for page to reload/filter results
                    break
            if apply_clicked:
                break
        except Exception:
            continue
            
    if not apply_clicked:
        log_event(session_id, "warning", "search", "Could not click the apply button.")
        return False
        
    return True

async def discover_jobs(
    page: Page,
    criteria: SearchCriteria,
    session_id: str,
    db: Session,
    session_limit: int = 10,
    pause_event: Optional[asyncio.Event] = None
) -> List[Job]:
    """
    Navigates to LinkedIn, loads the job listings, performs search pagination,
    checks titles/companies against user blacklists, and saves results in SQLite.
    """
    discovered_jobs = []
    
    # We choose one keyword and location from configuration
    keywords = criteria.keywords
    location = criteria.location or "Brazil"
    
    # If keywords are empty, log warning and exit
    if not keywords:
        log_event(session_id, "warning", "search", "No keywords configured for search.")
        return []
        
    keyword = random.choice(keywords)
    
    search_url = build_linkedin_search_url(
        keyword=keyword,
        location=location,
        remote_only=criteria.remote_only,
        date_filter=criteria.date_posted_filter,
        exp_levels=criteria.experience_levels or []
    )
    
    log_event(
        session_id, "info", "search", 
        f"Starting search with keyword: '{keyword}' and location: '{location}'",
        extra={"search_url": search_url}
    )
    
    blacklist_companies = [c.lower().strip() for c in (criteria.blacklist_companies or [])]
    blacklist_keywords = [k.lower().strip() for k in (criteria.blacklist_keywords or [])]
    
    jobs_count = 0
    page_num = 0
    max_pages = 5  # Safety boundary to prevent infinite loop crawling
    seen_ids = set()
    
    need_url_navigation = True
    
    while jobs_count < session_limit and page_num < max_pages:
        if pause_event:
            await pause_event.wait()
        if page.is_closed():
            raise BrowserClosedException("Browser was closed.")
            
        if need_url_navigation:
            # Construct search URL for pagination
            current_url = search_url
            if page_num > 0:
                current_url += f"&start={page_num * 25}"
                log_event(session_id, "info", "search", f"Navigating to page {page_num + 1} of search results...")
            else:
                log_event(session_id, "info", "search", "Navigating to initial search URL...")
                
            # Navigate to LinkedIn Search page
            try:
                await page.goto(current_url)
                await page.wait_for_timeout(random.randint(2500, 4000))
            except Exception as e:
                if is_browser_closed_exception(e):
                    raise BrowserClosedException("Browser was closed.") from e
                # Check if list container is already visible despite navigation timeout
                list_container_selector = "div.jobs-search-results-list, ul.scaffold-layout__list-container, div.scaffold-layout__list"
                try:
                    await page.wait_for_selector(list_container_selector, timeout=5000)
                    log_event(session_id, "warning", "search", f"Search page load timed out on page {page_num + 1}, but jobs container is present. Proceeding...")
                except Exception:
                    # If not present, re-raise original timeout error
                    raise e
            
            # Check if we were redirected to a login/auth page
            if "login" in page.url or "checkpoint" in page.url:
                log_event(session_id, "warning", "auth", "Redirect to login detected during job search.")
                break
                
            if page_num == 0 and getattr(criteria, 'company', None):
                filter_success = await apply_company_filter_ui(page, criteria.company, session_id)
                if filter_success:
                    # Update search_url with the new page URL containing company query params (e.g. f_C)
                    search_url = page.url
                    log_event(session_id, "info", "search", f"Updated base search URL after company filter application: {search_url}")
                else:
                    log_event(session_id, "warning", "search", f"Failed to apply company filter UI for '{criteria.company}'. Proceeding without filter.")
                
            need_url_navigation = False
            
        # Scroll down the listings list to trigger lazy loading
        list_container_selector = "div.jobs-search-results-list, ul.scaffold-layout__list-container, div.scaffold-layout__list"
        try:
            await page.wait_for_selector(list_container_selector, timeout=8000)
        except Exception:
            # No jobs found or container selector changed
            log_event(session_id, "info", "search", f"No list container found on page {page_num + 1}.")
            break
            
        log_event(session_id, "info", "search", f"Starting scroll search on page {page_num + 1}...")
        
        last_new_card_time = time.time()
        scroll_attempts = 0
        max_scroll_attempts = 30
        
        while jobs_count < session_limit:
            if pause_event:
                await pause_event.wait()
            if page.is_closed():
                raise BrowserClosedException("Browser was closed.")
                
            # Get scroll info before scrolling to check if scroll works
            scroll_info_before = await page.evaluate(
                """(selector) => {
                    const el = document.querySelector(selector);
                    if (el) {
                        return {
                            scrollTop: el.scrollTop,
                            scrollHeight: el.scrollHeight,
                            clientHeight: el.clientHeight
                        };
                    }
                    return null;
                }""",
                "div.jobs-search-results-list, div.scaffold-layout__list"
            )
            
            scroll_attempts += 1
            scroll_ratio = min(scroll_attempts / 10.0, 1.0)
            
            # Evaluate scroll to fetch cards
            await page.evaluate(
                f"(selector) => {{ const el = document.querySelector(selector); if (el) el.scrollTop = el.scrollHeight * {scroll_ratio}; }}", 
                "div.jobs-search-results-list, div.scaffold-layout__list"
            )
            await page.wait_for_timeout(random.randint(400, 800))
            
            # Get scroll info after scrolling
            scroll_info_after = await page.evaluate(
                """(selector) => {
                    const el = document.querySelector(selector);
                    if (el) {
                        return {
                            scrollTop: el.scrollTop,
                            scrollHeight: el.scrollHeight,
                            clientHeight: el.clientHeight
                        };
                    }
                    return null;
                }""",
                "div.jobs-search-results-list, div.scaffold-layout__list"
            )
            
            # Select all job card items visible inside the list container to avoid matching detail pane elements
            list_container = page.locator("div.jobs-search-results-list, ul.scaffold-layout__list-container, div.scaffold-layout__list").first
            card_elements = []
            if await list_container.count() > 0:
                card_elements = await list_container.locator("li[data-occludable-job-id], div[data-job-id]").all()
            else:
                card_elements = await page.locator("li[data-occludable-job-id], div[data-job-id]").all()
            
            new_cards_found = 0
            for card in card_elements:
                if jobs_count >= session_limit:
                    break
                    
                try:
                    if page.is_closed():
                        raise BrowserClosedException("Browser was closed.")
                    # Extract job ID
                    job_id_attr = await card.get_attribute("data-occludable-job-id") or await card.get_attribute("data-job-id")
                    if not job_id_attr:
                        continue
                        
                    if job_id_attr in seen_ids:
                        continue
                    seen_ids.add(job_id_attr)
                    new_cards_found += 1
                        
                    # Form clean job URL
                    job_url = f"https://www.linkedin.com/jobs/view/{job_id_attr}"
                    
                    # Check if job exists in DB
                    existing_job = db.query(Job).filter(Job.linkedin_id == job_id_attr).first()
                    if existing_job:
                        status_desc = existing_job.status
                        log_event(
                            session_id, "info", "search",
                            f"Job already {status_desc} — {existing_job.title} @ {existing_job.company} (ID: {existing_job.linkedin_id}). Not adding again.",
                            company=existing_job.company, job_title=existing_job.title, job_url=job_url, job_id=existing_job.id
                        )
                        continue
                        
                    # Scroll card into view to trigger lazy loading of title/company
                    await card.scroll_into_view_if_needed()
                    await page.wait_for_timeout(200)
                    
                    # Re-verify job ID after scroll to prevent virtual-scroll recycling mismatches
                    job_id_after = await card.get_attribute("data-occludable-job-id") or await card.get_attribute("data-job-id")
                    if job_id_after != job_id_attr:
                        log_event(
                            session_id, "warning", "search",
                            f"Job ID changed from {job_id_attr} to {job_id_after} during scroll. Skipping card to prevent mismatch."
                        )
                        continue
                        
                    # Extract title and company text using locator
                    title_text = ""
                    title_loc = card.locator("a.job-card-list__title, a.job-card-container__link").first
                    if await title_loc.count() > 0:
                        # Safety check: make sure the title link href actually contains our job ID
                        href = await title_loc.get_attribute("href") or ""
                        if job_id_attr not in href:
                            log_event(
                                session_id, "warning", "search",
                                f"Job card link href ({href}) does not contain job ID {job_id_attr}. Skipping card to prevent mismatch."
                            )
                            continue
                            
                        title_text = (await title_loc.inner_text()).strip()
                        if "\n" in title_text:
                            title_text = title_text.split("\n")[0].strip()
                        
                    company_text = ""
                    company_loc = card.locator(".job-card-container__company-name, .job-card-container__primary-description, .job-card-container__company-link, .artdeco-entity-lockup__subtitle").first
                    if await company_loc.count() > 0:
                        company_text = (await company_loc.inner_text()).strip()
                        if "\n" in company_text:
                            company_text = company_text.split("\n")[0].strip()
                        
                    location_text = ""
                    location_loc = card.locator(".job-card-container__metadata-item, .job-card-container__metadata-wrapper li").first
                    if await location_loc.count() > 0:
                        location_text = (await location_loc.inner_text()).strip()
                        if "\n" in location_text:
                            location_text = location_text.split("\n")[0].strip()
                        
                    if not title_text or not company_text:
                        continue
                        
                    # Check company blacklist
                    is_blacklisted = False
                    skip_reason = None
                    
                    company_lower = company_text.lower()
                    for bc in blacklist_companies:
                        if bc in company_lower:
                            is_blacklisted = True
                            skip_reason = f"Blacklisted company: {company_text}"
                            break
                            
                    # Check title keywords blacklist
                    title_lower = title_text.lower()
                    if not is_blacklisted:
                        for bk in blacklist_keywords:
                            if bk in title_lower:
                                is_blacklisted = True
                                skip_reason = f"Blacklisted title keyword: {bk}"
                                break
                                
                    if is_blacklisted:
                        log_event(
                            session_id, "info", "search", 
                            f"Job skipped (blacklist) — {title_text} @ {company_text}",
                            company=company_text, job_title=title_text, job_url=job_url
                        )
                        continue
                        
                    # Create job record
                    new_job = Job(
                        linkedin_id=job_id_attr,
                        title=title_text,
                        company=company_text,
                        location=location_text,
                        url=job_url,
                        easy_apply=True,
                        status="discovered",
                        search_id=criteria.id,
                        skip_reason=None
                    )
                    
                    db.add(new_job)
                    db.commit()
                    db.refresh(new_job)
                    
                    discovered_jobs.append(new_job)
                    jobs_count += 1
                    log_event(
                        session_id, "info", "search", 
                        f"New job discovered — {title_text} @ {company_text}",
                        company=company_text, job_title=title_text, job_url=job_url, job_id=new_job.id
                    )
                        
                except Exception as e:
                    if is_browser_closed_exception(e) or isinstance(e, BrowserClosedException) or type(e).__name__ == "BrowserClosedException":
                        raise e
                    # Skip errors on individual card parse
                    continue
            
            # Check scroll behavior
            scroll_working = True
            if scroll_info_before and scroll_info_after:
                is_scrollable = scroll_info_after['scrollHeight'] > scroll_info_after['clientHeight']
                scroll_changed = scroll_info_after['scrollTop'] != scroll_info_before['scrollTop']
                if not is_scrollable:
                    scroll_working = False
                elif scroll_attempts > 1 and not scroll_changed:
                    at_bottom = scroll_info_after['scrollTop'] + scroll_info_after['clientHeight'] >= scroll_info_after['scrollHeight'] - 10
                    if not at_bottom:
                        scroll_working = False
            else:
                scroll_working = False

            if not scroll_working and new_cards_found == 0:
                log_event(session_id, "info", "search", "Scroll is not working or list container is not scrollable. Falling back to pagination via start parameter.")
                break

            if new_cards_found > 0:
                last_new_card_time = time.time()
            else:
                elapsed = time.time() - last_new_card_time
                if elapsed > 5.0:
                    log_event(session_id, "info", "search", f"No new jobs loaded via scrolling for {elapsed:.1f}s (> 5s). Falling back to pagination via start parameter.")
                    break
                    
            if scroll_attempts >= max_scroll_attempts:
                log_event(session_id, "info", "search", "Max scroll attempts reached for this page. Falling back to pagination via start parameter.")
                break
                
        # Move to next results page (25 items per page)
        page_num += 1
        need_url_navigation = True
        
    db.commit()
    return discovered_jobs
