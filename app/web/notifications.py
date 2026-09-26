from datetime import datetime

from app.db.database import SessionLocal
from app.db.models import NotificationDB
from app.web.data import get_alerts


def sync_notifications(user_id: int) -> int:
    """Transforme les alertes actives en notifications persistantes sans doublons."""
    alerts = [a for a in get_alerts(user_id) if a.get("level") != "success"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    created = 0
    with SessionLocal() as db:
        for alert in alerts:
            # Le titre/badge/message identifient l'événement courant. Quand l'état
            # change (J-2 -> demain -> aujourd'hui), une nouvelle notification naît.
            source_key = "|".join([
                str(alert.get("level", "info")),
                str(alert.get("badge", "")),
                str(alert.get("title", "")),
                str(alert.get("message", "")),
            ])[:900]
            exists = db.query(NotificationDB).filter(
                NotificationDB.user_id == user_id,
                NotificationDB.source_key == source_key,
            ).first()
            if exists:
                continue
            db.add(NotificationDB(
                user_id=user_id,
                level=alert.get("level", "info"),
                icon=alert.get("icon", "🔔"),
                title=alert.get("title", "Notification"),
                message=alert.get("message", ""),
                source_key=source_key,
                is_read=0,
                created_at=now,
            ))
            created += 1
        if created:
            db.commit()
    return created


def unread_notification_count(user_id: int) -> int:
    sync_notifications(user_id)
    with SessionLocal() as db:
        return db.query(NotificationDB).filter(
            NotificationDB.user_id == user_id,
            NotificationDB.is_read == 0,
        ).count()
