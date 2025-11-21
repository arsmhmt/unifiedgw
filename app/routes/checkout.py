from datetime import datetime
from ..utils.timezone import now_eest
from flask import Blueprint, render_template, abort, request, redirect, jsonify
from app.models.api_key import ClientApiKey
from app.security.signing import sign_body
from app.models.payment_session import PaymentSession, PaymentSessionEvent
from app.models.payment import Payment
from app.extensions import db
from app.utils.exchange import get_exchange_rate, convert_fiat_to_crypto
from app.utils import generate_address, create_qr
from app.models.enums import PaymentStatus
from sqlalchemy.orm import joinedload
import json, requests, time

checkout_bp = Blueprint("checkout", __name__)

def _build_session_object(session: PaymentSession, overrides: dict | None = None) -> dict:
    base = {
        "id": session.public_id,
        "order_id": session.order_id,
        "status": session.status,
        "fiat_amount": float(session.amount or 0),
        "fiat_currency": session.currency,
        "customer_email": session.customer_email,
        "expires_at": int(session.expires_at.timestamp()) if session.expires_at else None,
    }
    if session.meta:
        base["metadata"] = session.meta
    if overrides:
        base.update({k: v for k, v in overrides.items() if v is not None})
    return base

def _fire_session_event(session: PaymentSession, event_type: str, overrides: dict | None = None):
    """Persist an event record and attempt webhook delivery if configured."""
    payload_object = _build_session_object(session, overrides)
    payload = {
        "type": event_type,
        "id": f"evt_{session.id}",
        "data": {"object": payload_object},
        "created": int(time.time()),
    }

    event = PaymentSessionEvent(
        payment_session_id=session.id,
        event_type=event_type,
        payload=payload,
    )
    db.session.add(event)
    db.session.flush()  # ensure event has an ID before attempting delivery

    if not session.webhook_url:
        return event

    key_record = ClientApiKey.query.filter_by(client_id=session.client_id, is_active=True).first()
    if not key_record or not key_record.secret_key:
        return event

    body = json.dumps(payload).encode()
    ts, sig = sign_body(key_record.secret_key.encode(), body)

    try:
        response = requests.post(
            session.webhook_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Paycrypt-Key": key_record.key,
                "X-Paycrypt-Timestamp": ts,
                "X-Paycrypt-Signature": sig,
            },
            timeout=5,
        )
        event.mark_delivered(response.status_code, response.text[:2000] if response.text else None)
    except Exception as exc:
        event.mark_failed(None, str(exc))

    return event

@checkout_bp.route("/checkout/<ps_id>", methods=["GET", "POST"])
def checkout(ps_id):
    ps = (
        PaymentSession.query.options(joinedload(PaymentSession.events))
        .filter_by(public_id=ps_id)
        .first()
    )
    if not ps or ps.is_expired():
        abort(404)

    if request.method == 'POST' and request.is_json:
        payload = request.get_json(silent=True) or {}
        target_status = (payload.get('status') or '').lower()

        if target_status not in ('confirmed', 'failed'):
            return jsonify({"error": "invalid_status"}), 400

        if ps.status in ('completed', 'failed'):
            return jsonify({"error": "session_finalized"}), 409

        payment = Payment.query.filter_by(transaction_id=ps.public_id).first()
        if not payment:
            payment = Payment(
                client_id=ps.client_id,
                fiat_amount=ps.amount,
                fiat_currency=ps.currency,
                crypto_currency=(payload.get('crypto_currency') or 'USDT').upper(),
                payment_method=payload.get('network', 'unknown'),
                transaction_id=ps.public_id,
                status=PaymentStatus.PENDING,
            )
            db.session.add(payment)

        if target_status == 'confirmed':
            payment.status = PaymentStatus.COMPLETED
            ps.status = 'completed'
        else:
            payment.status = PaymentStatus.FAILED
            ps.status = 'failed'

        if payload.get('crypto_amount') is not None:
            payment.crypto_amount = payload['crypto_amount']
        if payload.get('crypto_currency'):
            payment.crypto_currency = payload['crypto_currency'].upper()
        if payload.get('network'):
            payment.payment_method = payload['network']
        if payload.get('exchange_rate') is not None:
            payment.exchange_rate = payload['exchange_rate']

        overrides = {
            "status": ps.status,
            "crypto_amount": float(payment.crypto_amount or 0) if payment.crypto_amount is not None else None,
            "crypto_currency": payment.crypto_currency,
            "payment_method": payment.payment_method,
            "transaction_id": payment.transaction_id,
            "tx_hash": payload.get('tx_hash'),
            "failure_reason": payload.get('failure_reason') if target_status == 'failed' else None,
        }

        _fire_session_event(ps, f"payment.{target_status}", overrides)
        db.session.commit()

        return jsonify({
            "id": ps.public_id,
            "status": ps.status,
        })

    # Fiat to Crypto Conversion (live)
    fiat_amount = float(ps.amount or 0)
    selected_coin = (request.values.get('coin') or 'USDT').upper()
    selected_network = (request.values.get('network') or 'TRC20').upper()

    rate = get_exchange_rate(crypto_currency=selected_coin, fiat_currency=ps.currency or 'USD')
    if not rate:
        # Graceful fallback: use 1:1 to not block page, but warn in UI
        rate = 1.0
    crypto_amount = float(convert_fiat_to_crypto(fiat_amount, ps.currency or 'USD', selected_coin) or 0)

    # Generate Deposit Address & QR
    deposit_address = generate_address(ps.client_id, coin=selected_coin)
    qr_code = create_qr(deposit_address)

    # Countdown
    expires_at = ps.expires_at
    now = now_eest()
    seconds_left = max(0, int((expires_at - now).total_seconds()))

    if request.method == 'POST':
        # Create/update Payment record (idempotent per session)
        payment = Payment.query.filter_by(transaction_id=ps.public_id).first()
        if not payment:
            payment = Payment(
                client_id=ps.client_id,
                amount=None,  # using fiat/crypto fields instead
                currency=selected_coin,
                fiat_amount=ps.amount,
                fiat_currency=ps.currency or 'USD',
                crypto_amount=crypto_amount,
                crypto_currency=selected_coin,
                exchange_rate=rate,
                payment_method=f"{selected_coin}-{selected_network}",
                transaction_id=ps.public_id,  # link to session
                status='pending',
            )
            db.session.add(payment)
        else:
            payment.crypto_amount = crypto_amount
            payment.exchange_rate = rate
            payment.payment_method = f"{selected_coin}-{selected_network}"
            payment.status = 'pending'

        ps.status = 'pending'

        overrides = {
            "status": ps.status,
            "crypto_currency": selected_coin,
            "crypto_amount": crypto_amount,
            "exchange_rate": float(rate) if rate else None,
            "payment_method": f"{selected_coin}-{selected_network}",
            "transaction_id": ps.public_id,
        }

        _fire_session_event(ps, "payment.pending", overrides)
        db.session.commit()

        return redirect(ps.success_url)

    return render_template(
        "checkout.html",
        session=ps,
        fiat_amount=fiat_amount,
        selected_coin=selected_coin,
        selected_network=selected_network,
        crypto_amount=crypto_amount,
        deposit_address=deposit_address,
        qr_code=qr_code,
        seconds_left=seconds_left,
        rate=float(rate) if rate else None
    )