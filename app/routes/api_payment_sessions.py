from flask import Blueprint, request, jsonify, current_app
from app.security.signing import verify_hmac
from app.models.payment_session import PaymentSession
from app.models.api_key import ClientApiKey
import json, time, decimal

payment_sessions_api = Blueprint("payment_sessions_api", __name__, url_prefix="/api/v1")

def _as_decimal(x):
    try:
        return decimal.Decimal(str(x))
    except Exception:
        return None

@payment_sessions_api.route("/payment_sessions", methods=["POST"])
def create_payment_session():
    raw = request.get_data() or b"{}"
    ts = request.headers.get("X-Paycrypt-Timestamp", "")
    sig = request.headers.get("X-Paycrypt-Signature", "")
    key = request.headers.get("X-Paycrypt-Key", "")

    key_record: ClientApiKey = ClientApiKey.query.filter_by(key=key, is_active=True).first()
    if not key_record or not key_record.secret_key:
        return jsonify({"error": "invalid key"}), 401

    if key_record.allowed_ips and request.remote_addr not in (key_record.allowed_ips or []):
        return jsonify({"error": "ip_not_allowed"}), 403

    try:
        verify_hmac(key_record.secret_key.encode(), raw, ts, sig)
    except Exception as e:
        return jsonify({"error": "bad_signature", "detail": str(e)}), 401

    data = json.loads(raw.decode() or "{}")
    required = ["order_id", "amount", "currency", "success_url", "cancel_url"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    amt = _as_decimal(data.get("amount"))
    if not amt or amt <= 0:
        return jsonify({"error": "invalid_amount"}), 400

    data["currency"] = (data.get("currency") or "USD").upper()
    # Idempotency by (order_id, client_id) if still open
    existing = PaymentSession.query.filter_by(order_id=data["order_id"], client_id=key_record.client_id).first()
    if existing and existing.status in ("created","pending") and not existing.is_expired():
        checkout_host = (current_app.config.get("CHECKOUT_HOST") or request.host_url.rstrip("/"))
        return jsonify({
            "id": existing.public_id,
            "status": existing.status,
            "checkout_url": f"{checkout_host}/checkout/{existing.public_id}",
            "expires_at": int(existing.expires_at.timestamp())
        }), 200

    ps = PaymentSession.create_from_request(data, client_id=key_record.client_id)
    checkout_host = (current_app.config.get("CHECKOUT_HOST") or request.host_url.rstrip("/"))
    checkout_url = f"{checkout_host}/checkout/{ps.public_id}"
    return jsonify({
        "id": ps.public_id,
        "status": ps.status,
        "checkout_url": checkout_url,
        "expires_at": int(time.time()) + 1800
    }), 201