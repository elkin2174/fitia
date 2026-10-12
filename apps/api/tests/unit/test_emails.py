from app.modules.auth.emails import build_verification_email, verification_link


def test_enlace_apunta_a_pagina_del_frontend_con_el_token() -> None:
    assert verification_link("https://fitia.app/", "abc-_123") == "https://fitia.app/verificar-correo?token=abc-_123"


def test_correo_incluye_enlace_y_escapa_el_apodo_en_html() -> None:
    message = build_verification_email("a@correounivalle.edu.co", "<b>x</b>", "https://f/verificar-correo?token=t", 24)

    assert "https://f/verificar-correo?token=t" in message.text
    assert "24 horas" in message.text
    assert "<b>x</b>" not in message.html
    assert "&lt;b&gt;x&lt;/b&gt;" in message.html
