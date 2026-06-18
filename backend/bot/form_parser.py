import re
from enum import Enum
from typing import List, Optional, Dict, Any
from playwright.async_api import Page, Locator

class FieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    NUMBER = "number"
    FILE = "file"

class FormField:
    def __init__(
        self,
        label: str,
        field_type: FieldType,
        selector: str,                # CSS selector or unique query locator
        is_required: bool = False,
        options: List[str] = None,
        current_value: Optional[str] = None,
        options_hash: Optional[str] = None,
        file_hint: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        self.label = label
        self.field_type = field_type
        self.selector = selector
        self.is_required = is_required
        self.options = options or []
        self.current_value = current_value
        self.options_hash = options_hash
        self.file_hint = file_hint
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "field_type": self.field_type.value,
            "selector": self.selector,
            "is_required": self.is_required,
            "options": self.options,
            "current_value": self.current_value,
            "options_hash": self.options_hash,
            "file_hint": self.file_hint,
            "error_message": self.error_message
        }

def deduplicate_string(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    
    # 1. Normalize whitespaces to single space
    normalized = " ".join(text.split())
    
    # 2. Check word-level split halves
    words = normalized.split()
    n_words = len(words)
    if n_words >= 2:
        for half in range(n_words // 2, 0, -1):
            part1 = " ".join(words[:half])
            part2 = " ".join(words[half:2*half])
            
            norm1 = re.sub(r'[^a-zA-Z0-9]', '', part1).lower()
            norm2 = re.sub(r'[^a-zA-Z0-9]', '', part2).lower()
            
            if norm1 == norm2 and norm1:
                remaining = words[2*half:]
                if remaining:
                    return part1 + " " + " ".join(remaining)
                return part1

    # 3. Check character-level split halves
    n_chars = len(normalized)
    for half_len in range(n_chars // 2, 2, -1):
        part1 = normalized[:half_len].strip()
        part2 = normalized[half_len:2*half_len].strip()
        
        norm1 = re.sub(r'[^a-zA-Z0-9]', '', part1).lower()
        norm2 = re.sub(r'[^a-zA-Z0-9]', '', part2).lower()
        
        if norm1 == norm2 and norm1:
            remaining = normalized[2*half_len:].strip()
            if remaining:
                return part1 + " " + remaining
            return part1
            
    return text

def clean_label(label: str) -> str:
    """
    Cleans label text by removing asterisks, 'Required' text, helper hints,
    stripping whitespace, and deduplicating repeated questions/sentences.
    """
    if not label:
        return ""
    # Remove "Required"
    label = re.sub(r"\bRequired\b", "", label, flags=re.IGNORECASE)
    # Remove asterisks
    label = label.replace("*", "")
    # Remove multiple whitespaces/newlines
    label = " ".join(label.split())
    label = label.strip()

    # Deduplicate repeated questions/sentences/phrases using robust deduplication helper
    label = deduplicate_string(label)

    return label.strip()

def is_placeholder_value(val: Optional[str]) -> bool:
    if not val:
        return True
    val_clean = val.strip().lower()
    if not val_clean:
        return True
    
    # Check for empty-like placeholders
    if val_clean in ["-", "--", "---", "....", "..."]:
        return True
        
    # Check if it starts with or contains placeholder phrases
    val_alpha = "".join(c for c in val_clean if c.isalnum() or c.isspace()).strip()
    
    # Common placeholder phrases & words (normalized, lowercase, alphanumeric + spaces only)
    placeholder_phrases = {
        "select",
        "choose",
        "selecionar",
        "selecione",
        "selecciona",
        "seleccionar",
        "selectionner",
        "auswahlen",
        "seleziona",
        "wybierz",
        "select an option",
        "select option",
        "select one",
        "choose an option",
        "choose option",
        "choose one",
        "selecionar opcao",
        "selecionar uma opcao",
        "selecione uma opcao",
        "selecione a opcao",
        "select-one",
        "choose-one",
        "seleccionar una opcion",
        "seleccionar opcion",
        "selectionner une option"
    }
    
    # Also handle strings with accents/diacritics: e.g. "selecionar opção" -> "selecionar opcao"
    def normalize_str(s: str) -> str:
        s = s.replace("ç", "c").replace("ã", "a").replace("á", "a").replace("à", "a").replace("â", "a")
        s = s.replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o").replace("õ", "o")
        s = s.replace("ô", "o").replace("ú", "u").replace("ü", "u")
        s = s.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
        return s

    val_norm = normalize_str(val_alpha)
    if val_norm in placeholder_phrases:
        return True
        
    prefixes = ("select ", "choose ", "selecionar ", "selecione ", "selecciona ", "seleccionar ", "sélectionner ")
    if val_norm.startswith(prefixes) and len(val_norm) < 30:
        return True
        
    # Let's also check if it contains "-- select" or similar
    if "select" in val_norm and len(val_norm) < 20 and ("--" in val_clean or "-" in val_clean):
        return True

    return False

def clean_filename(text: str) -> str:
    text = text.strip()
    text = text.replace('"', '').replace("'", "")
    # Replace non-breaking spaces and multiple whitespaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # List of regex patterns to strip from the beginning case-insensitively
    patterns = [
        r'^deselect\s+resume[:\s]*',
        r'^deselect\s+file[:\s]*',
        r'^deselect[:\s]*',
        r'^remove\s+resume[:\s]*',
        r'^remove\s+file[:\s]*',
        r'^remove[:\s]*',
        r'^delete\s+resume[:\s]*',
        r'^delete\s+file[:\s]*',
        r'^delete[:\s]*',
        r'^deseleccionar\s+currículum[:\s]*',
        r'^deseleccionar[:\s]*',
        r'^desmarcar\s+currículo[:\s]*',
        r'^desmarcar\s+curriculo[:\s]*',
        r'^desmarcar[:\s]*',
        r'^remover\s+currículo[:\s]*',
        r'^remover\s+curriculo[:\s]*',
        r'^remover[:\s]*',
        r'^excluir\s+currículo[:\s]*',
        r'^excluir\s+curriculo[:\s]*',
        r'^excluir[:\s]*',
        r'^currículo[:\s]*',
        r'^curriculo[:\s]*',
        r'^resume[:\s]*'
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text.strip()

async def detect_preselected_file(container_locator: Locator) -> Optional[str]:
    """
    Detects if there is already a checked/selected resume/file in the given container locator
    or its parent containers.
    Returns the file name if found, otherwise None.
    """
    try:
        current_loc = container_locator
        for depth in range(5):  # 0 = container itself, 1-4 = ancestors
            try:
                if await current_loc.locator("input[type='file']").count() > 1:
                    break
            except Exception:
                pass
            checked_selectors = [
                "input[type='radio']:checked",
                "input[type='checkbox']:checked",
                "[aria-checked='true']",
                "[aria-selected='true']",
                "div[class*='active']",
                "div[class*='selected']",
                "li[class*='active']",
                "li[class*='selected']",
                "button[class*='active']",
                "button[class*='selected']",
                "label[class*='active']",
                "label[class*='selected']"
            ]
            
            for sel in checked_selectors:
                elements = current_loc.locator(sel)
                count = await elements.count()
                for i in range(count):
                    el = elements.nth(i)
                    # Get the text of the element or its parent
                    text_content = await el.evaluate(
                        "el => { let parent = el.closest('li, div, label'); return parent ? parent.innerText : ''; }"
                    )
                    if text_content:
                        text_upper = text_content.upper()
                        # Check if it has a file extension or file keywords
                        has_file_indicator = any(ext in text_upper for ext in [
                            ".PDF", ".DOC", ".DOCX", ".TXT", ".JPG", ".PNG", ".JPEG",
                            "CV", "RESUME", "CURRÍCULO", "CURRICULO", "CURRICULUM", "FILE", "DOCUMENT", "UPLOADING"
                        ])
                        if has_file_indicator:
                            lines = [l.strip() for l in text_content.split("\n") if l.strip()]
                            for line in lines:
                                if any(ext in line.upper() for ext in [".PDF", ".DOC", ".DOCX", ".TXT", ".JPG", ".PNG", ".JPEG"]):
                                    return clean_filename(line)
                            return "Preselected File"
            
            # If the current locator is a form section container, do not go up to its ancestors
            # because that will leak into other sections (like Resume).
            try:
                is_section = await current_loc.evaluate(
                    "el => el.classList.contains('jobs-easy-apply-form-section') || "
                    "el.classList.contains('fb-dash-form-element') || "
                    "el.classList.contains('fb-choice-control-group')"
                )
                if is_section:
                    break
            except Exception:
                pass

            # Go up one level
            current_loc = current_loc.locator("xpath=..")
    except Exception:
        pass
    return None

async def extract_file_options(container_locator: Locator) -> List[str]:
    """
    Extracts all available file/resume options inside the container or its ancestors.
    """
    try:
        current_loc = container_locator
        for depth in range(5):  # 0 = container, 1-4 = ancestors
            try:
                if await current_loc.locator("input[type='file']").count() > 1:
                    break
            except Exception:
                pass
            options = await current_loc.evaluate(r"""
                el => {
                    let files = [];
                    let allElems = el.querySelectorAll('div, span, label, p, li, button, h3, a');
                    for (let elem of allElems) {
                        let txt = elem.innerText ? elem.innerText.trim() : '';
                        if (txt) {
                            let lines = txt.split('\n');
                            for (let line of lines) {
                                line = line.trim();
                                if (/\.(pdf|docx|doc|txt|jpg|png|jpeg)$/i.test(line)) {
                                    let cleaned = line.replace(/['"]/g, '').trim();
                                    let prefixes = [
                                        "deselect resume", "deselect file", "deselect",
                                        "remove resume", "remove file", "remove",
                                        "delete resume", "delete file", "delete",
                                        "deseleccionar currículum", "deseleccionar",
                                        "desmarcar currículo", "desmarcar curriculo", "desmarcar",
                                        "remover currículo", "remover curriculo", "remover",
                                        "excluir currículo", "excluir curriculo", "excluir",
                                        "currículo", "curriculo", "resume"
                                    ];
                                    for (let prefix of prefixes) {
                                        let regex = new RegExp('^' + prefix.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&') + '[:\\s]+', 'i');
                                        cleaned = cleaned.replace(regex, '');
                                    }
                                    cleaned = cleaned.trim();
                                    if (cleaned && !files.includes(cleaned)) {
                                        files.push(cleaned);
                                    }
                                }
                            }
                        }
                    }
                    return files;
                }
            """)
            if options:
                return options
            
            # If the current locator is a form section container, do not go up to its ancestors
            # because that will leak into other sections (like Resume).
            try:
                is_section = await current_loc.evaluate(
                    "el => el.classList.contains('jobs-easy-apply-form-section') || "
                    "el.classList.contains('fb-dash-form-element') || "
                    "el.classList.contains('fb-choice-control-group')"
                )
                if is_section:
                    break
            except Exception:
                pass

            current_loc = current_loc.locator("xpath=..")
    except Exception:
        pass
    return []

async def parse_form(page: Page) -> List[FormField]:
    """
    Scrapes the open LinkedIn Easy Apply dialog container for all interactive form inputs.
    """
    fields = []
    
    # Target outer Easy Apply modal
    dialog = page.locator("div.jobs-easy-apply-content, div[role='dialog']").first
    if await dialog.count() == 0:
        return []

    # Find all form elements (using class hooks that LinkedIn Form Builder uses)
    # We filter to keep only leaf-most elements (elements that don't contain other elements of these classes)
    try:
        leaf_count = await dialog.evaluate("""
            dialogEl => {
                let elements = Array.from(dialogEl.querySelectorAll('.jobs-easy-apply-form-section, .fb-dash-form-element, .fb-choice-control-group'));
                let leafElements = elements.filter(el => {
                    return !elements.some(otherEl => otherEl !== el && el.contains(otherEl));
                });
                
                // Assign a temporary data attribute to identify them
                leafElements.forEach((el, idx) => {
                    el.setAttribute('data-bot-leaf-section', idx.toString());
                });
                return leafElements.length;
            }
        """)
        if leaf_count > 0:
            form_sections = await dialog.locator("[data-bot-leaf-section]").all()
        else:
            form_sections = []
    except Exception:
        # Fallback to original logic
        form_sections = await dialog.locator(".jobs-easy-apply-form-section, .fb-dash-form-element, .fb-choice-control-group").all()
    
    for section in form_sections:
        # Check if this section has a validation error
        error_message = None
        error_selectors = [
            ".artdeco-inline-feedback--error",
            ".fb-form-element__error-message",
            ".fb-dash-form-element__error-message",
            "p.artdeco-inline-feedback__message",
            "[role='alert']"
        ]
        for err_sel in error_selectors:
            err_loc = section.locator(err_sel)
            if await err_loc.count() > 0:
                for i in range(await err_loc.count()):
                    el = err_loc.nth(i)
                    if await el.is_visible():
                        txt = (await el.inner_text()).strip()
                        if txt:
                            error_message = txt
                            break
                if error_message:
                    break

        # Determine the field type by inspecting DOM elements in the section
        
        # 1. Check for File Upload (Resume)
        file_input = section.locator("input[type='file']")
        if await file_input.count() > 0:
            label_text = "Resume"
            label_loc = section.locator("h3, label, .fb-file__title")
            if await label_loc.count() > 0:
                label_text = await label_loc.first.inner_text()
            
            selector = f"input[type='file']"
            # Note: file inputs are usually not multiple in Easy Apply, but let's locate precisely
            id_attr = await file_input.first.get_attribute("id")
            if id_attr:
                selector = f'[id="{id_attr}"]'
                
            # Scrape file requirements hint from the section text
            file_hint = ""
            section_text = await section.inner_text()
            if section_text:
                lines = [l.strip() for l in section_text.split("\n") if l.strip()]
                for line in lines:
                    if any(kw in line.upper() for kw in ["MB", "KB", "PDF", "DOC", "TXT", "JPG", "PNG", "GIF", "JPEG"]):
                        if clean_label(line) != clean_label(label_text):
                            file_hint = line
                            break
                            
            options = await extract_file_options(section)

            preselected_file = await detect_preselected_file(section)
            fields.append(FormField(
                label=clean_label(label_text),
                field_type=FieldType.FILE,
                selector=selector,
                is_required=True, # Resumes are typically mandatory
                options=options,
                current_value=preselected_file,
                file_hint=file_hint,
                error_message=error_message
            ))
            continue
            
        # 2. Check for Dropdowns (Select / Custom Combobox)
        # Check native select
        native_select = section.locator("select")
        if await native_select.count() > 0:
            label_text = ""
            label_loc = section.locator("label")
            if await label_loc.count() > 0:
                label_text = await label_loc.first.inner_text()
                
            id_attr = await native_select.first.get_attribute("id")
            selector = f'select[id="{id_attr}"]' if id_attr else "select"
            
            # Extract options and selection atomically in the browser to prevent timeouts
            options = []
            current_val = None
            try:
                options_data = await native_select.first.evaluate("""
                    select => {
                        let opts = [];
                        for (let i = 0; i < select.options.length; i++) {
                            let opt = select.options[i];
                            opts.push({
                                text: opt.text ? opt.text.trim() : '',
                                selected: opt.selected
                            });
                        }
                        return opts;
                    }
                """)
                for opt_info in options_data:
                    val = opt_info["text"]
                    if val and not is_placeholder_value(val):
                        options.append(val)
                    if opt_info["selected"]:
                        if val and not is_placeholder_value(val):
                            current_val = val
            except Exception:
                pass
                    
            fields.append(FormField(
                label=clean_label(label_text),
                field_type=FieldType.SELECT,
                selector=selector,
                is_required=True,
                options=options,
                current_value=current_val,
                error_message=error_message
            ))
            continue
            
        # Check Custom Combobox (div[role="combobox"] or input[role="combobox"])
        combobox = section.locator("div[role='combobox'], input[role='combobox'], [data-autocomplete]").first
        if await combobox.count() > 0:
            label_text = ""
            label_loc = section.locator("label, span.fb-form-element-label")
            if await label_loc.count() > 0:
                label_text = await label_loc.first.inner_text()
                
            # Grab trigger selector
            id_attr = await combobox.get_attribute("id")
            selector = f'[id="{id_attr}"]' if id_attr else "div[role='combobox']"
            
            # Extract current value if any
            current_val = None
            try:
                input_elem = combobox if await combobox.evaluate("el => el.tagName === 'INPUT'") else combobox.locator("input").first
                if await input_elem.count() > 0:
                    current_val = await input_elem.input_value()
                else:
                    current_val = await combobox.inner_text()
                
                if current_val:
                    current_val = current_val.strip()
                    if is_placeholder_value(current_val):
                        current_val = None
            except Exception:
                pass
                
            fields.append(FormField(
                label=clean_label(label_text),
                field_type=FieldType.SELECT,
                selector=selector,
                is_required=True,
                options=[], # Loaded dynamically during filling if empty
                current_value=current_val,
                error_message=error_message
            ))
            continue

        # 3. Check for Radio Buttons (Grouped)
        radios = await section.locator("input[type='radio']").all()
        if radios:
            # Group label is inside fieldset legend or a custom header element
            label_text = ""
            legend_loc = section.locator("legend, span.fb-choice-control-group__label, h3")
            if await legend_loc.count() > 0:
                label_text = await legend_loc.first.inner_text()
            
            # Extract options from individual radio labels
            options = []
            radio_selectors = []
            for r in radios:
                # Find label associated with this radio
                r_id = await r.get_attribute("id")
                r_name = await r.get_attribute("name")
                opt_label = ""
                if r_id:
                    lbl = section.locator(f"label[for='{r_id}']")
                    if await lbl.count() > 0:
                        opt_label = await lbl.inner_text()
                
                opt_label = opt_label.strip()
                if opt_label:
                    options.append(opt_label)
                    radio_selectors.append(f"input[type='radio'][id='{r_id}']")
            
            # Group selector is typically based on name attribute
            group_name = await radios[0].get_attribute("name")
            selector = f"input[type='radio'][name='{group_name}']" if group_name else radio_selectors[0]
            
            # Find selected radio option
            current_val = None
            for r, opt_lbl in zip(radios, options):
                if await r.is_checked():
                    current_val = opt_lbl
                    break
            
            fields.append(FormField(
                label=clean_label(label_text),
                field_type=FieldType.RADIO,
                selector=selector,
                is_required=True,
                options=options,
                current_value=current_val,
                error_message=error_message
            ))
            continue

        # 4. Check for Checkbox
        checkboxes = await section.locator("input[type='checkbox']").all()
        if checkboxes:
            label_text = ""
            label_loc = section.locator("legend, span.fb-choice-control-group__label, h3")
            if await label_loc.count() > 0:
                label_text = await label_loc.first.inner_text()
            
            if not label_text.strip():
                label_loc2 = section.locator("label")
                if await label_loc2.count() > 0:
                    label_text = await label_loc2.first.inner_text()

            if len(checkboxes) == 1:
                cb = checkboxes[0]
                cb_id = await cb.get_attribute("id")
                selector = f'input[type="checkbox"][id="{cb_id}"]' if cb_id else "input[type='checkbox']"
                is_checked = await cb.is_checked()
                current_val = "checked" if is_checked else None
                
                fields.append(FormField(
                    label=clean_label(label_text),
                    field_type=FieldType.CHECKBOX,
                    selector=selector,
                    is_required=False,
                    current_value=current_val,
                    error_message=error_message
                ))
            else:
                # Multiple checkboxes -> Checklist group!
                options = []
                cb_selectors = []
                current_values = []
                for cb in checkboxes:
                    cb_id = await cb.get_attribute("id")
                    opt_label = ""
                    if cb_id:
                        lbl = section.locator(f"label[for='{cb_id}']")
                        if await lbl.count() > 0:
                            opt_label = await lbl.inner_text()
                    if not opt_label.strip():
                        parent = cb.locator("xpath=..")
                        lbl = parent.locator("label").first
                        if await lbl.count() > 0:
                            opt_label = await lbl.inner_text()
                            
                    opt_label = opt_label.strip()
                    if opt_label:
                        options.append(opt_label)
                        cb_selectors.append(f"input[type='checkbox'][id='{cb_id}']")
                        if await cb.is_checked():
                            current_values.append(opt_label)
                
                group_name = await checkboxes[0].get_attribute("name")
                selector = f"input[type='checkbox'][name='{group_name}']" if group_name else cb_selectors[0]
                
                import json
                current_val = json.dumps(current_values) if current_values else None
                
                fields.append(FormField(
                    label=clean_label(label_text),
                    field_type=FieldType.CHECKBOX,
                    selector=selector,
                    is_required=False,
                    options=options,
                    current_value=current_val,
                    error_message=error_message
                ))
            continue

        # 5. Check for Textarea
        textarea = section.locator("textarea").first
        if await textarea.count() > 0:
            label_text = ""
            label_loc = section.locator("label")
            if await label_loc.count() > 0:
                label_text = await label_loc.first.inner_text()
                
            ta_id = await textarea.get_attribute("id")
            selector = f'textarea[id="{ta_id}"]' if ta_id else "textarea"
            current_val = await textarea.input_value()
            
            fields.append(FormField(
                label=clean_label(label_text),
                field_type=FieldType.TEXTAREA,
                selector=selector,
                is_required=True,
                current_value=current_val,
                error_message=error_message
            ))
            continue

        # 6. Check for Text/Number Input
        text_input = section.locator("input[type='text'], input[type='number'], input[type='tel']").first
        if await text_input.count() > 0:
            label_text = ""
            label_loc = section.locator("label")
            if await label_loc.count() > 0:
                label_text = await label_loc.first.inner_text()
                
            input_id = await text_input.get_attribute("id")
            selector = f'input[id="{input_id}"]' if input_id else "input[type='text']"
            
            current_val = await text_input.input_value()
            input_type = await text_input.get_attribute("type")
            
            # Heuristic: Check if this is a numerical input
            # If input type is 'number', or if label contains keywords like "years", "anos", "months", "experiência"
            label_cleaned_lower = clean_label(label_text).lower()
            is_numeric = input_type == "number" or any(word in label_cleaned_lower for word in ["years", "anos", "months", "experiencia", "experiência", "ctc", "salary", "pretensão", "pretensao", "salário", "salario"])
            
            fields.append(FormField(
                label=clean_label(label_text),
                field_type=FieldType.NUMBER if is_numeric else FieldType.TEXT,
                selector=selector,
                is_required=True,
                current_value=current_val,
                error_message=error_message
            ))
            continue

    # Fallback / safety check: Make sure we didn't miss any file inputs
    all_file_inputs = await dialog.locator("input[type='file']").all()
    for file_input in all_file_inputs:
        id_attr = await file_input.get_attribute("id")
        selector = f'[id="{id_attr}"]' if id_attr else "input[type='file']"
        
        # Check if already parsed in fields
        already_parsed = False
        for f in fields:
            if f.selector == selector or (id_attr and id_attr in f.selector):
                already_parsed = True
                break
                
        if not already_parsed:
            # Determine label by looking at ancestor elements
            label_text = ""
            parent_container = file_input.locator("xpath=..")
            for _ in range(4): # Check up to 4 levels up
                label_loc = parent_container.locator("h3, label, .fb-file__title, .fb-form-element-label, span.fb-file__title, p.fb-file__title, [class*='title'], [class*='label']")
                count = await label_loc.count()
                for i in range(count):
                    text = (await label_loc.nth(i).inner_text()).strip()
                    if text:
                        label_text = text
                        break
                if label_text:
                    break
                parent_container = parent_container.locator("xpath=..")
                
            # If still empty, fall back to first non-empty text line of parent
            if not label_text:
                parent_text = await file_input.locator("xpath=..").inner_text()
                if parent_text:
                    lines = [l.strip() for l in parent_text.split("\n") if l.strip()]
                    if lines:
                        label_text = lines[0]
                        
            label_text = clean_label(label_text)
            if not label_text or label_text.lower() in ["upload", "browse"]:
                label_text = "Upload File"
                
            # Search for hints like "MB", "KB", "PDF", "JPG" in the parent text
            file_hint = ""
            parent_text = await file_input.locator("xpath=..").inner_text()
            if parent_text:
                lines = [l.strip() for l in parent_text.split("\n") if l.strip()]
                for line in lines:
                    if any(kw in line.upper() for kw in ["MB", "KB", "PDF", "DOC", "TXT", "JPG", "PNG", "GIF", "JPEG"]):
                        if clean_label(line) != clean_label(label_text):
                            file_hint = line
                            break
                            
            # Check for validation error in parent container hierarchy
            error_message = None
            parent_container = file_input.locator("xpath=..")
            for _ in range(4):
                for err_sel in [".artdeco-inline-feedback--error", ".fb-form-element__error-message", ".fb-dash-form-element__error-message", "[role='alert']"]:
                    err_loc = parent_container.locator(err_sel)
                    if await err_loc.count() > 0:
                        for i in range(await err_loc.count()):
                            el = err_loc.nth(i)
                            if await el.is_visible():
                                txt = (await el.inner_text()).strip()
                                if txt:
                                    error_message = txt
                                    break
                        if error_message:
                            break
                if error_message:
                    break
                parent_container = parent_container.locator("xpath=..")

            # Find containing section for the fallback file input
            containing_section = file_input.locator("xpath=ancestor::div[contains(@class, 'jobs-easy-apply-form-section') or contains(@class, 'fb-dash-form-element') or contains(@class, 'fb-choice-control-group')]").first
            # Fallback if ancestor is not found: use parent's parent
            if await containing_section.count() == 0:
                containing_section = file_input.locator("xpath=..").locator("xpath=..")
            
            options = await extract_file_options(containing_section)

            preselected_file = await detect_preselected_file(containing_section)
            fields.append(FormField(
                label=label_text,
                field_type=FieldType.FILE,
                selector=selector,
                is_required=True,
                options=options,
                current_value=preselected_file,
                file_hint=file_hint,
                error_message=error_message
            ))

    return fields
