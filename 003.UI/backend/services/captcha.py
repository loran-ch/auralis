"""无第三方依赖、一次性使用的注册图片验证码。"""
import base64
import hashlib
import html
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.user import VerificationCode


CAPTCHA_EXPIRE_SECONDS = 300
CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _captcha_svg(code: str) -> str:
    colors = ("#005ea1", "#006e1c", "#874e00", "#5d3f91")
    characters = []
    for index, character in enumerate(code):
        x = 24 + index * 36 + secrets.randbelow(7)
        y = 43 + secrets.randbelow(9)
        angle = secrets.randbelow(25) - 12
        color = colors[secrets.randbelow(len(colors))]
        characters.append(
            f'<text x="{x}" y="{y}" fill="{color}" '
            f'transform="rotate({angle} {x} {y})">{html.escape(character)}</text>'
        )
    noise = []
    for _ in range(6):
        noise.append(
            f'<line x1="{secrets.randbelow(170)}" y1="{secrets.randbelow(58)}" '
            f'x2="{secrets.randbelow(170)}" y2="{secrets.randbelow(58)}" '
            'stroke="#7d8790" stroke-width="1" opacity=".28"/>'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="170" height="58" '
        'viewBox="0 0 170 58">'
        '<rect width="170" height="58" rx="12" fill="#f1f6f9"/>'
        f'{"".join(noise)}'
        '<g font-family="Arial,sans-serif" font-size="32" font-weight="800">'
        f'{"".join(characters)}</g></svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_registration_captcha(db: Session) -> dict:
    code = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(4))
    token = secrets.token_urlsafe(32)
    db.add(VerificationCode(
        target=_token_hash(token),
        target_type="email",
        code=code,
        scene="register",
        expires_at=datetime.now(timezone.utc) + timedelta(
            seconds=CAPTCHA_EXPIRE_SECONDS
        ),
    ))
    db.commit()
    return {
        "captcha_token": token,
        "image": _captcha_svg(code),
        "expires_in": CAPTCHA_EXPIRE_SECONDS,
    }


def verify_registration_captcha(db: Session, token: str, answer: str) -> bool:
    if not token or not answer:
        return False
    captcha = db.query(VerificationCode).filter(
        VerificationCode.target == _token_hash(token),
        VerificationCode.scene == "register",
        VerificationCode.used == False,
        VerificationCode.expires_at > datetime.now(timezone.utc),
    ).order_by(VerificationCode.created_at.desc()).first()
    if not captcha:
        return False
    captcha.used = True
    db.commit()
    return secrets.compare_digest(
        str(captcha.code).upper(), answer.strip().upper()
    )
