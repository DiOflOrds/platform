"""BCK-Mailer (SWR-023, D004): E-Mail-Benachrichtigung via SMTP.
Konfiguration ausschließlich über Umgebungsvariablen (kein Secret in Git):
  SMTP_HOST, SMTP_PORT (Default 587), SMTP_USER, SMTP_PASS, MAIL_TO
Ausfalltolerant: nie eine Exception nach außen — Rückgabe (ok, meldung);
der API-Betrieb hängt nicht am Versand.
"""
import os
import smtplib
from email.message import EmailMessage

MAIL_TO_DEFAULT = "geraldine.john90@gmail.com"  # D004


def konfiguriert():
    return bool(os.environ.get("SMTP_HOST"))


def sende(betreff, text, an=None):
    """(ok, meldung). Loggt statt zu werfen (SWR-023)."""
    if not konfiguriert():
        return False, "SMTP nicht konfiguriert (SMTP_HOST fehlt) — Versand übersprungen"
    try:
        msg = EmailMessage()
        msg["Subject"] = betreff
        msg["From"] = os.environ.get("SMTP_USER", "aspice-team@localhost")
        msg["To"] = an or os.environ.get("MAIL_TO", MAIL_TO_DEFAULT)
        msg.set_content(text)
        with smtplib.SMTP(os.environ["SMTP_HOST"],
                          int(os.environ.get("SMTP_PORT", "587")), timeout=15) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
            s.send_message(msg)
        return True, f"gesendet an {msg['To']}"
    except Exception as e:  # noqa: BLE001 — bewusst breit (SWR-023: nie crashen)
        return False, f"Versand fehlgeschlagen: {e}"
