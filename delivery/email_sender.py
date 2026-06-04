import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER


def send(text: str, subject: str = "📊 StocksInfo 모닝 브리핑", to: str = None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = to or EMAIL_RECEIVER

    # plain text 버전 (마크다운 기호 제거)
    plain = text.replace("*", "").replace("`", "").replace("━", "-")
    msg.attach(MIMEText(plain, "plain", "utf-8"))

    # HTML 버전 (줄바꿈 유지)
    html_body = text.replace("\n", "<br>").replace("*", "<b>", 1)
    html = f"<html><body><pre style='font-family:monospace;font-size:14px'>{text}</pre></body></html>"
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to or EMAIL_RECEIVER, msg.as_string())


def send_error(error: str):
    send(f"⚠️ StocksInfo 오류\n\n{error[:1000]}", subject="❌ StocksInfo 오류 발생")
