import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_global_branding_consistency(client):
    """
    Verify that 'WhatSeller Pro' (with gradient-text for 'Seller')
    is rendered on key public and auth pages.
    """
    targets = ["/", "/login", "/register", "/terms"]
    for path in targets:
        response = client.get(path)
        assert response.status_code == 200
        # Check for the standardized branding pattern
        assert "What" in response.text
        assert "Seller" in response.text
        assert "Pro" in response.text
        # Allow either the class or the equivalent inline style for the 'Seller' gradient
        assert ("gradient-text" in response.text or "background: linear-gradient" in response.text)


def test_no_rocket_icons(client):
    """
    Assert that the rocket emoji (🚀) has been completely removed
    from the rendered HTML of key pages.
    """
    targets = ["/", "/login", "/dashboard", "/terms"]
    for path in targets:
        # Note: We skip Auth check as it redirects if not logged in,
        # but we check the rendered content if possible.
        response = client.get(path, follow_redirects=True)
        assert "🚀" not in response.text
        assert "&#128640;" not in response.text  # HTML entity for rocket


def test_public_layout_conditional_navigation(client):
    """
    Verify the navigation logic in public_layout.html:
    - The Landing page (/) should show marketing links.
    - Legal pages (/terms) should show the 'Voltar ao Início' button.
    """
    # 1. Landing Page
    res_landing = client.get("/")
    assert "Preços" in res_landing.text
    assert "Entrar" in res_landing.text
    assert "Começar Grátis" in res_landing.text
    assert "Voltar para o Início" not in res_landing.text

    # 2. Terms Page
    res_terms = client.get("/terms")
    assert "Voltar para o Início" in res_terms.text
    # Marketing links should NOT be present in the legal header
    assert "Preços" not in res_terms.text


def test_mobile_header_css_classes(client):
    """
    Verify that the mobile-specific CSS classes are present in the landing page,
    ensuring responsiveness support.
    """
    response = client.get("/")
    assert "nav-landing" in response.text
    assert "mobile-nav" in response.text or "menu-mobile" in response.text
