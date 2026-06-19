import datetime
import sqlalchemy
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Setting
from backend.schemas import SettingUpdate

router = APIRouter(prefix="/api/settings", tags=["Settings"])

DEFAULT_SETTINGS = {
    "bot_mode": "review",                # review | auto (submission preview toggle)
    "auto_submit_delay_ms": "2000",      # pause before clicking submit
    "min_action_delay_ms": "800",        # minimum wait during human typing/clicks
    "max_action_delay_ms": "3000",       # maximum wait
    "fuzzy_match_threshold": "1.0",      # difflib score filter
    "session_limit": "10",               # max applications before pausing session
    "headless_mode": "false",            # show chromium browser UI
    "auto_open_browser": "false",        # open frontend automatically
    "log_level": "info",                 # debug | info
    "popup_mode": "web",                 # web | desktop (popups display interface)
    "easy_apply_limit_reached": "false", # track daily limit reached status
    "connect_hiring_team": "false"       # connect with hiring team members before applying
}

def get_all_settings(db: Session) -> dict:
    settings = db.query(Setting).all()
    setting_dict = {s.key: s.value for s in settings}
    
    initialized_any = False
    for key, val in DEFAULT_SETTINGS.items():
        if key not in setting_dict:
            setting = Setting(key=key, value=val)
            db.add(setting)
            setting_dict[key] = val
            initialized_any = True
            
    if initialized_any:
        try:
            db.commit()
        except sqlalchemy.exc.IntegrityError:
            db.rollback()
            # If another thread inserted it, we just return the latest
            settings = db.query(Setting).all()
            setting_dict = {s.key: s.value for s in settings}
        
    return setting_dict

@router.get("")
def list_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)

@router.put("/{key}")
def update_setting(key: str, payload: SettingUpdate, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting:
        setting = Setting(key=key, value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
        setting.updated_at = datetime.datetime.utcnow()
    db.commit()
    return {key: setting.value}
