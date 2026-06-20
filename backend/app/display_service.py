import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.display_transform import DEFAULT_CONFIG, DisplayRules
from app.models import DisplayConfig
from app.timezone_util import now_utc_naive

LOG_DIR = Path("/app/logs")


def get_display_rules(db: Session) -> DisplayRules:
    row = db.query(DisplayConfig).filter(DisplayConfig.id == 1).first()
    if not row:
        row = DisplayConfig(
            id=1,
            config_json=json.dumps(DEFAULT_CONFIG),
            updated_by="system",
            updated_at=now_utc_naive(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return DisplayRules.from_dict(json.loads(row.config_json))


def save_display_rules(db: Session, rules: DisplayRules, updated_by: str) -> DisplayRules:
    row = db.query(DisplayConfig).filter(DisplayConfig.id == 1).first()
    payload = rules.to_dict()
    if not row:
        row = DisplayConfig(id=1, config_json=json.dumps(payload), updated_by=updated_by)
        db.add(row)
    else:
        row.config_json = json.dumps(payload)
        row.updated_by = updated_by
    row.updated_at = now_utc_naive()
    db.commit()
    return rules
