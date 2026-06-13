"""
Unit tests for SQLTargetRepository.upsert_sync — covering the
name-preservation logic and Evolution API field variations.
"""
from unittest.mock import MagicMock
from core.infrastructure.database.repositories import SQLTargetRepository
from core.infrastructure.database.models import WhatsAppTargetModel


def _make_db(existing=None):
    """Creates a mock db session that returns `existing` for queries."""
    db = MagicMock()
    q = db.query.return_value
    # instance_id filter chain
    q.filter.return_value = q
    q.first.return_value = existing
    return db


# ── name resolution from various fields ──────────────────────────────────────


def test_upsert_uses_subject_for_groups():
    """Groups from Evolution API use 'subject' as the name."""
    db = _make_db(existing=None)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"id": "12345@g.us", "subject": "Meu Grupo VIP"}],
        user_id=1,
        instance_id=1,
    )
    added = db.add.call_args[0][0]
    assert added.name == "Meu Grupo VIP"
    assert added.type == "group"


def test_upsert_uses_pushname_for_contacts():
    """Contacts from messages.upsert use 'pushName'."""
    db = _make_db(existing=None)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"remoteJid": "5511999990000@s.whatsapp.net", "pushName": "Carlos"}],
        user_id=1,
        instance_id=1,
    )
    added = db.add.call_args[0][0]
    assert added.name == "Carlos"
    assert added.phone == "5511999990000"
    assert added.type == "chat"


def test_upsert_uses_notify_for_contacts_upsert_event():
    """contacts.upsert events from Evolution API use 'notify' as the name."""
    db = _make_db(existing=None)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"id": "5521988880000@s.whatsapp.net", "notify": "Fernanda"}],
        user_id=1,
        instance_id=1,
    )
    added = db.add.call_args[0][0]
    assert added.name == "Fernanda"


def test_upsert_falls_back_to_jid_prefix_when_no_name():
    """When no name field is present, the JID number is used as fallback name."""
    db = _make_db(existing=None)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"id": "5531977770000@s.whatsapp.net"}],
        user_id=1,
        instance_id=1,
    )
    added = db.add.call_args[0][0]
    assert added.name == "5531977770000"


# ── name preservation logic ───────────────────────────────────────────────────


def test_upsert_preserves_existing_real_name_when_new_is_generic():
    """
    When a contact already has a real name in the DB and the new payload
    only carries the JID number as the name (no pushName), the existing
    name must NOT be overwritten.
    """
    existing = MagicMock(spec=WhatsAppTargetModel)
    existing.name = "Roberta Lima"
    existing.instance_id = 1

    db = _make_db(existing=existing)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"remoteJid": "5511999990000@s.whatsapp.net"}],  # no pushName
        user_id=1,
        instance_id=1,
    )
    # name must remain unchanged
    assert existing.name == "Roberta Lima"


def test_upsert_overwrites_generic_name_with_real_name():
    """
    When a contact exists with only a numeric name (the JID prefix),
    it should be overwritten by a real pushName.
    """
    existing = MagicMock(spec=WhatsAppTargetModel)
    existing.name = "5511999990000"  # generic / numeric name
    existing.instance_id = 1

    db = _make_db(existing=existing)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"remoteJid": "5511999990000@s.whatsapp.net", "pushName": "Rodrigo"}],
        user_id=1,
        instance_id=1,
    )
    assert existing.name == "Rodrigo"


def test_upsert_overwrites_real_name_when_better_name_arrives():
    """
    When a contact has a real name and a better (different) real name
    arrives via pushName, the name should be updated.
    """
    existing = MagicMock(spec=WhatsAppTargetModel)
    existing.name = "Joao"
    existing.instance_id = 1

    db = _make_db(existing=existing)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"remoteJid": "5511999990000@s.whatsapp.net", "pushName": "Joao Silva"}],
        user_id=1,
        instance_id=1,
    )
    assert existing.name == "Joao Silva"


# ── skip logic ────────────────────────────────────────────────────────────────


def test_upsert_skips_broadcast_jids():
    """broadcast@broadcast and status@broadcast must be silently skipped."""
    db = _make_db(existing=None)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [
            {"remoteJid": "status@broadcast", "pushName": "Status"},
            {"remoteJid": "broadcast@s.whatsapp.net", "pushName": "Broadcast"},
        ],
        user_id=1,
        instance_id=1,
    )
    db.add.assert_not_called()


def test_upsert_skips_newsletter_jids():
    """newsletter JIDs must be silently skipped."""
    db = _make_db(existing=None)
    repo = SQLTargetRepository(db)
    repo.upsert_sync(
        [{"remoteJid": "123456@newsletter", "pushName": "Canal"}],
        user_id=1,
        instance_id=1,
    )
    db.add.assert_not_called()
