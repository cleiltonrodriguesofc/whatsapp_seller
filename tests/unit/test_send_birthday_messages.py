import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import date

from core.application.use_cases.send_birthday_messages import SendBirthdayMessages
from core.infrastructure.database.models import (
    BirthdayContactModel,
    BirthdayTemplateModel,
    InstanceModel,
    BirthdayLogModel
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def use_case(mock_db):
    return SendBirthdayMessages(db=mock_db, user_id=1)


@pytest.fixture
def mock_now():
    with patch("core.application.use_cases.send_birthday_messages.now_sp") as mock_now_sp:
        # Define today as Oct 10, 2026
        mock_now_sp.return_value.date.return_value = date(2026, 10, 10)
        yield mock_now_sp


@pytest.mark.asyncio
async def test_execute_no_active_template(use_case, mock_db, mock_now):
    # Mock template query to return None
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    result = await use_case.execute()
    
    assert result["sent"] == 0
    assert result["failed"] == 0
    assert "no active template" in result.get("error", "")


@pytest.mark.asyncio
async def test_execute_no_birthday_contacts_today(use_case, mock_db, mock_now):
    # Mock template
    template = BirthdayTemplateModel(user_id=1, is_enabled=True, content="Happy birthday {nome}!")
    
    # Mock contacts (none with birthday today)
    contact1 = BirthdayContactModel(id=1, name="John", birth_date=date(1990, 10, 11), is_active=True)
    
    def side_effect(*args, **kwargs):
        mock_query = MagicMock()
        if args[0] == BirthdayTemplateModel:
            mock_query.filter.return_value.first.return_value = template
        elif args[0] == BirthdayContactModel:
            mock_query.filter.return_value.all.return_value = [contact1]
        return mock_query
        
    mock_db.query.side_effect = side_effect
    
    result = await use_case.execute()
    
    assert result["sent"] == 0
    assert result["skipped"] == 0


@pytest.mark.asyncio
@patch("core.application.use_cases.send_birthday_messages.EvolutionWhatsAppService")
@patch("core.application.use_cases.send_birthday_messages.asyncio.sleep")
async def test_execute_success(mock_sleep, mock_wa_class, use_case, mock_db, mock_now):
    template = BirthdayTemplateModel(user_id=1, is_enabled=True, content="Parabéns {nome}!", media_url=None)
    contact = BirthdayContactModel(id=1, name="John Doe", phone="5511999999999", birth_date=date(1990, 10, 10), is_active=True)
    instance = InstanceModel(id=1, user_id=1, name="test_inst", apikey="key")
    
    # WhatsApp Mock
    mock_wa_instance = AsyncMock()
    mock_wa_instance.send_text.return_value = True
    mock_wa_class.return_value = mock_wa_instance
    
    def side_effect(*args, **kwargs):
        mock_query = MagicMock()
        if args[0] == BirthdayTemplateModel:
            mock_query.filter.return_value.first.return_value = template
        elif args[0] == BirthdayContactModel:
            mock_query.filter.return_value.all.return_value = [contact]
        elif args[0] == InstanceModel:
            mock_query.filter.return_value.first.return_value = instance
        elif args[0] == BirthdayLogModel:
            # First query for already_sent, second for failed_logs
            mock_query.filter.return_value.all.return_value = []
        return mock_query
        
    mock_db.query.side_effect = side_effect
    
    result = await use_case.execute()
    
    assert result["sent"] == 1
    assert result["failed"] == 0
    
    # Verify whatsapp was called
    mock_wa_instance.set_presence.assert_called_with("5511999999999", "composing")
    mock_wa_instance.send_text.assert_called_with("5511999999999", "Parabéns John!")
    
    # Verify log was created
    assert mock_db.add.called
    assert mock_db.commit.called


@pytest.mark.asyncio
@patch("core.application.use_cases.send_birthday_messages.EvolutionWhatsAppService")
async def test_execute_already_sent_today(mock_wa_class, use_case, mock_db, mock_now):
    template = BirthdayTemplateModel(user_id=1, is_enabled=True, content="Parabéns {nome}!", media_url=None)
    contact = BirthdayContactModel(id=1, name="John Doe", phone="5511999999999", birth_date=date(1990, 10, 10), is_active=True)
    instance = InstanceModel(id=1, user_id=1, name="test_inst", apikey="key")
    
    # Existing log sent today
    log = BirthdayLogModel(contact_id=1, status="sent", sent_at=mock_now.return_value)
    
    def side_effect(*args, **kwargs):
        mock_query = MagicMock()
        if args[0] == BirthdayTemplateModel:
            mock_query.filter.return_value.first.return_value = template
        elif args[0] == BirthdayContactModel:
            mock_query.filter.return_value.all.return_value = [contact]
        elif args[0] == InstanceModel:
            mock_query.filter.return_value.first.return_value = instance
        elif args[0] == BirthdayLogModel:
            mock_query.filter.return_value.all.return_value = [log]
        return mock_query
        
    mock_db.query.side_effect = side_effect
    
    result = await use_case.execute()
    
    assert result["sent"] == 0
    assert result["skipped"] == 1
    assert not mock_wa_class.return_value.send_text.called
