"""
Post-merge acceptance tests.

These tests define the expected end-state after merging
feature/campaign-controls-phone-login + feature/ui-ux-polish-campaigns
into development. They cover:

  1. backend control endpoints (pause, resume, cancel, resend)
  2. ui rendering — badges, buttons, visibility rules
  3. ux workflow — edit-resend without creating duplicates
  4. code quality — no conflict markers, no dead code, no duplicate imports
  5. infrastructure — correct evolution api config keys
"""

import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import (
    UserModel,
    InstanceModel,
    CampaignModel,
    StatusCampaignModel,
    BroadcastCampaignModel,
    ProductModel,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client, db_session, email):
    """create user + set auth cookie. returns UserModel."""
    auth = AuthService()
    user = UserModel(email=email, hashed_password=auth.hash_password("x"))
    db_session.add(user)
    db_session.commit()
    token = auth.create_access_token(data={"sub": email})
    client.cookies.set("access_token", token)
    return user


def _instance(db_session, user_id, name="inst"):
    inst = InstanceModel(user_id=user_id, name=name, status="connected")
    db_session.add(inst)
    db_session.commit()
    return inst


def _product(db_session, user_id):
    p = ProductModel(
        user_id=user_id, name="Prod", description="d",
        price=1.0, affiliate_link="http://x.com",
    )
    db_session.add(p)
    db_session.commit()
    return p


def _status_campaign(db_session, user_id, instance_id, status, **kw):
    c = StatusCampaignModel(
        user_id=user_id, instance_id=instance_id,
        title=kw.get("title", f"SC-{status}"),
        status=status, **{k: v for k, v in kw.items() if k != "title"},
    )
    db_session.add(c)
    db_session.commit()
    return c


def _broadcast_campaign(db_session, user_id, instance_id, status, **kw):
    c = BroadcastCampaignModel(
        user_id=user_id, instance_id=instance_id,
        title=kw.get("title", f"BC-{status}"),
        target_type="contacts", message="hello",
        status=status, **{k: v for k, v in kw.items() if k != "title"},
    )
    db_session.add(c)
    db_session.commit()
    return c


def _product_campaign(db_session, user_id, instance_id, product_id, status, **kw):
    c = CampaignModel(
        user_id=user_id, instance_id=instance_id, product_id=product_id,
        title=kw.get("title", f"PC-{status}"),
        status=status, **{k: v for k, v in kw.items() if k != "title"},
    )
    db_session.add(c)
    db_session.commit()
    return c


# ============================================================================
# SECTION 1 — STATUS LIST: badge rendering for ALL states
# ============================================================================


class TestStatusListBadges:
    """every campaign status must display a correct, distinguishable badge."""

    def _get_list(self, client, db_session, status, email_suffix):
        user = _login(client, db_session, f"badge_{status}_{email_suffix}@t.com")
        inst = _instance(db_session, user.id, f"i_b_{status}")
        _status_campaign(db_session, user.id, inst.id, status)
        return client.get("/status_campaigns")

    def test_sent_shows_enviado(self, client, db_session):
        r = self._get_list(client, db_session, "sent", "s")
        assert r.status_code == 200
        assert "ENVIADO" in r.text

    def test_failed_shows_falhou(self, client, db_session):
        r = self._get_list(client, db_session, "failed", "f")
        assert r.status_code == 200
        assert "FALHOU" in r.text

    def test_scheduled_shows_agendado(self, client, db_session):
        r = self._get_list(client, db_session, "scheduled", "sc")
        assert r.status_code == 200
        assert "AGENDADO" in r.text

    def test_draft_shows_rascunho(self, client, db_session):
        r = self._get_list(client, db_session, "draft", "d")
        assert r.status_code == 200
        assert "RASCUNHO" in r.text

    def test_processing_shows_enviando(self, client, db_session):
        r = self._get_list(client, db_session, "processing", "p")
        assert r.status_code == 200
        assert "ENVIANDO" in r.text

    def test_paused_shows_pausado(self, client, db_session):
        """BUG: paused falls through to 'AGENDADO' — must show 'PAUSADO'."""
        r = self._get_list(client, db_session, "paused", "pa")
        assert r.status_code == 200
        assert "PAUSADO" in r.text

    def test_canceled_shows_cancelado(self, client, db_session):
        """BUG: canceled falls through to 'AGENDADO' — must show 'CANCELADO'."""
        r = self._get_list(client, db_session, "canceled", "ca")
        assert r.status_code == 200
        assert "CANCELADO" in r.text


# ============================================================================
# SECTION 2 — STATUS LIST: campaign visibility (no orphaned campaigns)
# ============================================================================


class TestStatusListVisibility:
    """campaigns must NEVER vanish from the UI regardless of their status."""

    def _all_states(self, client, db_session, email):
        user = _login(client, db_session, email)
        inst = _instance(db_session, user.id, f"i_{email.split('@')[0]}")
        states = ["draft", "scheduled", "processing", "sent", "failed", "paused", "canceled"]
        campaigns = {}
        for s in states:
            campaigns[s] = _status_campaign(db_session, user.id, inst.id, s, title=f"Vis-{s}")
        return campaigns, client.get("/status_campaigns")

    def test_paused_campaign_visible_in_list(self, client, db_session):
        """BUG: paused campaigns disappear — not in any section."""
        camps, r = self._all_states(client, db_session, "vis_paused@t.com")
        assert r.status_code == 200
        assert "Vis-paused" in r.text

    def test_canceled_campaign_visible_in_list(self, client, db_session):
        """BUG: canceled campaigns disappear — not in any section."""
        camps, r = self._all_states(client, db_session, "vis_canceled@t.com")
        assert r.status_code == 200
        assert "Vis-canceled" in r.text

    def test_all_7_states_visible(self, client, db_session):
        """every single campaign must appear somewhere in the page."""
        camps, r = self._all_states(client, db_session, "vis_all@t.com")
        assert r.status_code == 200
        for status, camp in camps.items():
            assert f"Vis-{status}" in r.text, f"campaign with status '{status}' is invisible"


# ============================================================================
# SECTION 3 — STATUS LIST: action buttons per state
# ============================================================================


class TestStatusListButtons:
    """correct action buttons must render for each campaign state."""

    def _render(self, client, db_session, status, suffix):
        user = _login(client, db_session, f"btn_{status}_{suffix}@t.com")
        inst = _instance(db_session, user.id, f"i_btn_{status}_{suffix}")
        camp = _status_campaign(db_session, user.id, inst.id, status)
        r = client.get("/status_campaigns")
        return r, camp

    def test_scheduled_has_pause_button(self, client, db_session):
        r, c = self._render(client, db_session, "scheduled", "1")
        assert "pause" in r.text.lower()
        assert f"controlCampaign('status_campaigns', 'pause', {c.id}" in r.text

    def test_scheduled_has_cancel_button(self, client, db_session):
        r, c = self._render(client, db_session, "scheduled", "2")
        assert f"controlCampaign('status_campaigns', 'cancel', {c.id}" in r.text

    def test_paused_has_resume_button(self, client, db_session):
        r, c = self._render(client, db_session, "paused", "1")
        assert f"controlCampaign('status_campaigns', 'resume', {c.id}" in r.text

    def test_paused_has_cancel_button(self, client, db_session):
        r, c = self._render(client, db_session, "paused", "2")
        assert f"controlCampaign('status_campaigns', 'cancel', {c.id}" in r.text

    def test_sent_has_resend_button(self, client, db_session):
        r, c = self._render(client, db_session, "sent", "1")
        assert f"controlCampaign('status_campaigns', 'resend', {c.id}" in r.text

    def test_failed_has_resend_button(self, client, db_session):
        r, c = self._render(client, db_session, "failed", "1")
        assert f"controlCampaign('status_campaigns', 'resend', {c.id}" in r.text

    def test_canceled_has_resend_button(self, client, db_session):
        r, c = self._render(client, db_session, "canceled", "1")
        assert f"controlCampaign('status_campaigns', 'resend', {c.id}" in r.text

    def test_edit_visible_for_sent(self, client, db_session):
        r, c = self._render(client, db_session, "sent", "e1")
        assert f"/status_campaigns/edit/{c.id}" in r.text

    def test_edit_visible_for_failed(self, client, db_session):
        r, c = self._render(client, db_session, "failed", "e2")
        assert f"/status_campaigns/edit/{c.id}" in r.text

    def test_edit_visible_for_canceled(self, client, db_session):
        r, c = self._render(client, db_session, "canceled", "e3")
        assert f"/status_campaigns/edit/{c.id}" in r.text

    def test_edit_visible_for_scheduled(self, client, db_session):
        r, c = self._render(client, db_session, "scheduled", "e4")
        assert f"/status_campaigns/edit/{c.id}" in r.text

    def test_edit_visible_for_paused(self, client, db_session):
        r, c = self._render(client, db_session, "paused", "e5")
        assert f"/status_campaigns/edit/{c.id}" in r.text

    def test_edit_visible_for_draft(self, client, db_session):
        r, c = self._render(client, db_session, "draft", "e6")
        assert f"/status_campaigns/edit/{c.id}" in r.text

    def test_delete_always_visible(self, client, db_session):
        """delete form must exist for every campaign."""
        r, c = self._render(client, db_session, "sent", "del")
        assert f"/status_campaigns/delete/{c.id}" in r.text

    def test_no_duplicate_button(self, client, db_session):
        """the old 'Duplicar' link must NOT exist anymore."""
        r, c = self._render(client, db_session, "sent", "nodup")
        assert "/status_campaigns/duplicate/" not in r.text


# ============================================================================
# SECTION 4 — STATUS DETAIL PAGE: badges + controls
# ============================================================================


class TestStatusDetailPage:
    """detail page must mirror the same control logic as the list."""

    def _detail(self, client, db_session, status, suffix):
        user = _login(client, db_session, f"det_{status}_{suffix}@t.com")
        inst = _instance(db_session, user.id, f"i_det_{status}_{suffix}")
        c = _status_campaign(db_session, user.id, inst.id, status)
        return client.get(f"/status_campaigns/{c.id}"), c

    def test_paused_badge_on_detail(self, client, db_session):
        r, c = self._detail(client, db_session, "paused", "b")
        assert r.status_code == 200
        assert "PAUSADO" in r.text

    def test_canceled_badge_on_detail(self, client, db_session):
        r, c = self._detail(client, db_session, "canceled", "b")
        assert r.status_code == 200
        assert "CANCELADO" in r.text

    def test_detail_edit_always_present(self, client, db_session):
        for status in ["sent", "failed", "canceled", "paused"]:
            r, c = self._detail(client, db_session, status, f"ed_{status}")
            assert f"/status_campaigns/edit/{c.id}" in r.text, \
                f"edit link missing for status '{status}' on detail page"

    def test_detail_resend_for_terminal_states(self, client, db_session):
        for status in ["sent", "failed", "canceled"]:
            r, c = self._detail(client, db_session, status, f"rs_{status}")
            assert "resend" in r.text.lower(), \
                f"resend button missing for status '{status}' on detail page"

    def test_detail_resume_for_paused(self, client, db_session):
        r, c = self._detail(client, db_session, "paused", "res")
        assert "resume" in r.text.lower()


# ============================================================================
# SECTION 5 — BROADCAST LIST: badge + control consistency
# ============================================================================


class TestBroadcastListControls:
    """broadcast list must have the same universal control pattern."""

    def _render(self, client, db_session, status, suffix):
        user = _login(client, db_session, f"bc_{status}_{suffix}@t.com")
        inst = _instance(db_session, user.id, f"i_bc_{status}_{suffix}")
        c = _broadcast_campaign(db_session, user.id, inst.id, status)
        return client.get("/broadcast/campaigns"), c

    def test_paused_badge(self, client, db_session):
        r, c = self._render(client, db_session, "paused", "b")
        assert r.status_code == 200
        assert "PAUSADO" in r.text

    def test_canceled_badge(self, client, db_session):
        r, c = self._render(client, db_session, "canceled", "b")
        assert r.status_code == 200
        assert "CANCELADO" in r.text

    def test_edit_always_visible(self, client, db_session):
        for status in ["sent", "failed", "canceled", "paused", "scheduled"]:
            r, c = self._render(client, db_session, status, f"ed_{status}")
            assert f"/broadcast/campaigns/edit/{c.id}" in r.text, \
                f"edit link missing for broadcast status '{status}'"

    def test_resend_for_sent(self, client, db_session):
        r, c = self._render(client, db_session, "sent", "rs")
        assert f"controlCampaign('broadcast', 'resend', {c.id}" in r.text

    def test_pause_for_scheduled(self, client, db_session):
        r, c = self._render(client, db_session, "scheduled", "pa")
        assert f"controlCampaign('broadcast', 'pause', {c.id}" in r.text


# ============================================================================
# SECTION 6 — RESEND WORKFLOW (no duplicate records)
# ============================================================================


class TestResendWorkflow:
    """resend must reset status to scheduled on the SAME record — no copies."""

    def test_status_resend_reuses_record(self, client, db_session):
        user = _login(client, db_session, "wf_sc_resend@t.com")
        inst = _instance(db_session, user.id, "i_wf_sc")
        camp = _status_campaign(
            db_session, user.id, inst.id, "sent",
            sent_at=datetime(2026, 1, 1, 12, 0),
        )
        original_id = camp.id
        count_before = db_session.query(StatusCampaignModel).filter(
            StatusCampaignModel.user_id == user.id
        ).count()

        r = client.post(f"/status_campaigns/resend/{camp.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "scheduled"

        count_after = db_session.query(StatusCampaignModel).filter(
            StatusCampaignModel.user_id == user.id
        ).count()
        assert count_after == count_before, "resend must NOT create a new record"

        db_session.expire_all()
        updated = db_session.query(StatusCampaignModel).get(original_id)
        assert updated.status == "scheduled"
        assert updated.sent_at is None

    def test_broadcast_resend_reuses_record(self, client, db_session):
        user = _login(client, db_session, "wf_bc_resend@t.com")
        inst = _instance(db_session, user.id, "i_wf_bc")
        camp = _broadcast_campaign(
            db_session, user.id, inst.id, "sent",
            sent_at=datetime(2026, 1, 1, 12, 0), sent_count=5, failed_count=1,
        )
        original_id = camp.id

        r = client.post(f"/broadcast/campaigns/{camp.id}/resend")
        assert r.status_code == 200

        db_session.expire_all()
        updated = db_session.query(BroadcastCampaignModel).get(original_id)
        assert updated.status == "scheduled"
        assert updated.sent_at is None
        assert updated.sent_count == 0
        assert updated.failed_count == 0

    def test_product_resend_reuses_record(self, client, db_session):
        user = _login(client, db_session, "wf_pc_resend@t.com")
        inst = _instance(db_session, user.id, "i_wf_pc")
        prod = _product(db_session, user.id)
        camp = _product_campaign(
            db_session, user.id, inst.id, prod.id, "sent",
            sent_at=datetime(2026, 1, 1, 12, 0),
        )
        original_id = camp.id

        r = client.post(f"/campaign/resend/{camp.id}")
        assert r.status_code == 200

        db_session.expire_all()
        updated = db_session.query(CampaignModel).get(original_id)
        assert updated.status == "scheduled"
        assert updated.sent_at is None


# ============================================================================
# SECTION 7 — GLOBAL JS UTILITIES (base.html)
# ============================================================================


class TestBaseTemplateJS:
    """base.html must provide these global JS utilities on every page."""

    def _page(self, client, db_session):
        _login(client, db_session, "js@t.com")
        return client.get("/status_campaigns")

    def test_controlCampaign_defined(self, client, db_session):
        r = self._page(client, db_session)
        assert "function controlCampaign" in r.text

    def test_showToast_defined(self, client, db_session):
        r = self._page(client, db_session)
        assert "function showToast" in r.text

    def test_showConfirm_defined(self, client, db_session):
        r = self._page(client, db_session)
        assert "function showConfirm" in r.text

    def test_controlCampaign_handles_all_three_modules(self, client, db_session):
        """the JS must route to the correct paths for each module type."""
        r = self._page(client, db_session)
        # broadcast uses /{id}/{action}
        assert "broadcast/campaigns/${id}/${action}" in r.text
        # status uses /{action}/{id}
        assert "status_campaigns/${action}/${id}" in r.text or \
               "/status_campaigns/${action}/${id}" in r.text
        # product uses /{action}/{id}
        assert "campaign/${action}/${id}" in r.text or \
               "/campaign/${action}/${id}" in r.text

    def test_toast_container_exists(self, client, db_session):
        r = self._page(client, db_session)
        assert 'id="toast-container"' in r.text

    def test_confirm_modal_exists(self, client, db_session):
        r = self._page(client, db_session)
        assert 'id="global-confirm-modal"' in r.text


# ============================================================================
# SECTION 8 — CODE QUALITY (static analysis)
# ============================================================================


class TestCodeQuality:
    """source files must be free of merge artifacts and dead code."""

    PROJECT_ROOT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )

    def _read(self, relpath):
        with open(os.path.join(self.PROJECT_ROOT, relpath), "r", encoding="utf-8") as f:
            return f.read()

    # --- conflict markers ---

    @pytest.mark.parametrize("relpath", [
        "core/presentation/web/routers/whatsapp.py",
        "core/infrastructure/notifications/evolution_whatsapp.py",
        "core/presentation/web/templates/base.html",
        "core/presentation/web/templates/status_list.html",
        "core/presentation/web/templates/broadcast_campaign_list.html",
        "core/presentation/web/templates/dashboard.html",
        "core/presentation/web/templates/status_campaign_detail.html",
        "core/presentation/web/routers/status_campaigns.py",
        "core/presentation/web/routers/broadcast.py",
        "core/presentation/web/routers/campaigns.py",
    ])
    def test_no_conflict_markers(self, relpath):
        content = self._read(relpath)
        for marker in ["<<<<<<<", "=======", ">>>>>>>"]:
            assert marker not in content, \
                f"conflict marker '{marker}' found in {relpath}"

    # --- whatsapp.py specific bugs ---

    def test_no_duplicate_imports_in_whatsapp_router(self):
        """BUG: the merge script left a duplicate import block at line ~237."""
        content = self._read("core/presentation/web/routers/whatsapp.py")
        # count occurrences of the models import block
        count = content.count("from core.infrastructure.database.models import")
        # top-level import at line ~19 is fine.
        # inside delete_whatsapp there should be at most ONE local import.
        assert count <= 2, \
            f"models import appears {count} times (expected ≤ 2: 1 top-level + 1 local)"

    def test_no_unreachable_return_in_pairing_code(self):
        """BUG: line 152 has a return after another return — dead code."""
        content = self._read("core/presentation/web/routers/whatsapp.py")
        # there must not be two consecutive 'return {' within the pairing func
        assert 'return {"success": False, "error": "Failed to generate QR code"}' \
            not in content, \
            "dead return statement still present in pairing code endpoint"

    # --- evolution_whatsapp.py config ---

    def test_create_instance_uses_snake_case_keys(self):
        """BUG: merge accepted camelCase keys from the wrong branch."""
        content = self._read(
            "core/infrastructure/notifications/evolution_whatsapp.py"
        )
        # find the create_instance method payload
        # the correct keys from the feature branch are snake_case
        assert '"reject_call"' in content, \
            "create_instance payload missing 'reject_call' (has wrong camelCase keys)"
        assert '"read_messages"' in content, \
            "create_instance payload missing 'read_messages'"
        assert '"sync_full_history"' in content, \
            "create_instance payload missing 'sync_full_history'"
        # the wrong keys should NOT be present
        assert '"readMessages"' not in content, \
            "create_instance still has wrong camelCase key 'readMessages'"
        assert '"syncFullHistory"' not in content, \
            "create_instance still has wrong camelCase key 'syncFullHistory'"


# ============================================================================
# SECTION 9 — WHATSAPP ROUTER: pairing code endpoint
# ============================================================================


class TestWhatsAppPairingEndpoint:
    """the phone pairing code endpoint must exist and be functional."""

    def test_pairing_endpoint_exists(self, client, db_session):
        """POST /whatsapp/connect-phone/{id} must be routed."""
        user = _login(client, db_session, "pair@t.com")
        inst = _instance(db_session, user.id, "i_pair")
        # will fail because evolution api is not running, but should NOT 404
        r = client.post(
            f"/whatsapp/connect-phone/{inst.id}",
            data={"phone": "5511999999999"},
        )
        # anything but 404/405 means the route exists
        assert r.status_code not in [404, 405], \
            "pairing code endpoint is not registered"


# ============================================================================
# SECTION 10 — DASHBOARD: universal controls
# ============================================================================


class TestDashboardCampaignControls:
    """dashboard recent campaigns must show the universal control set."""

    def test_dashboard_has_controlCampaign_calls(self, client, db_session):
        user = _login(client, db_session, "dash@t.com")
        inst = _instance(db_session, user.id, "i_dash")
        prod = _product(db_session, user.id)
        _product_campaign(db_session, user.id, inst.id, prod.id, "scheduled")
        r = client.get("/")
        assert r.status_code == 200
        assert "controlCampaign" in r.text

    def test_dashboard_edit_always_visible(self, client, db_session):
        user = _login(client, db_session, "dash_ed@t.com")
        inst = _instance(db_session, user.id, "i_dash_ed")
        prod = _product(db_session, user.id)
        camp = _product_campaign(db_session, user.id, inst.id, prod.id, "sent")
        r = client.get("/")
        assert r.status_code == 200
        assert f"/campaigns/edit/{camp.id}" in r.text

    def test_dashboard_paused_badge(self, client, db_session):
        user = _login(client, db_session, "dash_pa@t.com")
        inst = _instance(db_session, user.id, "i_dash_pa")
        prod = _product(db_session, user.id)
        _product_campaign(db_session, user.id, inst.id, prod.id, "paused")
        r = client.get("/")
        assert r.status_code == 200
        assert "PAUSADO" in r.text

    def test_dashboard_canceled_badge(self, client, db_session):
        user = _login(client, db_session, "dash_ca@t.com")
        inst = _instance(db_session, user.id, "i_dash_ca")
        prod = _product(db_session, user.id)
        _product_campaign(db_session, user.id, inst.id, prod.id, "canceled")
        r = client.get("/")
        assert r.status_code == 200
        assert "CANCELADO" in r.text


# ============================================================================
# SECTION 11 — BACKEND CONTROL IDEMPOTENCY & EDGE CASES
# ============================================================================


class TestControlEdgeCases:
    """edge cases that must be handled gracefully."""

    def test_resend_from_canceled(self, client, db_session):
        """a canceled campaign should be resendable."""
        user = _login(client, db_session, "edge_rc@t.com")
        inst = _instance(db_session, user.id, "i_edge_rc")
        camp = _status_campaign(db_session, user.id, inst.id, "canceled")
        r = client.post(f"/status_campaigns/resend/{camp.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "scheduled"

    def test_resend_from_failed(self, client, db_session):
        user = _login(client, db_session, "edge_rf@t.com")
        inst = _instance(db_session, user.id, "i_edge_rf")
        camp = _status_campaign(db_session, user.id, inst.id, "failed")
        r = client.post(f"/status_campaigns/resend/{camp.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "scheduled"

    def test_pause_then_resume_roundtrip(self, client, db_session):
        """pause → resume should return to scheduled without data loss."""
        user = _login(client, db_session, "edge_pr@t.com")
        inst = _instance(db_session, user.id, "i_edge_pr")
        camp = _status_campaign(db_session, user.id, inst.id, "scheduled")

        r1 = client.post(f"/status_campaigns/pause/{camp.id}")
        assert r1.json()["status"] == "paused"

        r2 = client.post(f"/status_campaigns/resume/{camp.id}")
        assert r2.json()["status"] == "scheduled"

        db_session.expire_all()
        final = db_session.query(StatusCampaignModel).get(camp.id)
        assert final.status == "scheduled"

    def test_cancel_then_resend_roundtrip(self, client, db_session):
        """cancel → resend should re-enqueue the same record."""
        user = _login(client, db_session, "edge_cr@t.com")
        inst = _instance(db_session, user.id, "i_edge_cr")
        camp = _status_campaign(db_session, user.id, inst.id, "scheduled")

        r1 = client.post(f"/status_campaigns/cancel/{camp.id}")
        assert r1.json()["status"] == "canceled"

        r2 = client.post(f"/status_campaigns/resend/{camp.id}")
        assert r2.json()["status"] == "scheduled"

    def test_wrong_user_cannot_control(self, client, db_session):
        """user A must NOT be able to control user B's campaign."""
        user_a = _login(client, db_session, "edge_a@t.com")
        inst = _instance(db_session, user_a.id, "i_edge_a")
        camp = _status_campaign(db_session, user_a.id, inst.id, "scheduled")

        # switch to user B
        _login(client, db_session, "edge_b@t.com")
        r = client.post(f"/status_campaigns/pause/{camp.id}")
        assert r.status_code == 404

    def test_nonexistent_campaign_returns_404(self, client, db_session):
        _login(client, db_session, "edge_404@t.com")
        r = client.post("/status_campaigns/pause/999999")
        assert r.status_code == 404
