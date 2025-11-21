from datetime import timedelta

from flask import Blueprint, render_template, current_app, request
from sqlalchemy import func

from app.extensions import db
from app.utils.timezone import now_eest


def _get_demo_branch():
    from app.models import Branch

    demo_branch = (
        Branch.query.filter(Branch.name.ilike('%demo%')).order_by(Branch.created_at.asc()).first()
    )
    return demo_branch


def _get_demo_client():
    from app.models import Client

    demo_client = (
        Client.query.filter(Client.company_name.ilike('%demo%'))
        .order_by(Client.created_at.asc())
        .first()
    )
    return demo_client


def _get_demo_stats(branch):
    from app.models import Client, Payment, Withdrawal
    from app.models.enums import PaymentStatus, WithdrawalStatus

    thirty_days_ago = now_eest() - timedelta(days=30)

    total_clients = branch.clients.filter_by(is_active=True).count()

    deposit_volume_query = (
        db.session.query(func.sum(Payment.fiat_amount), func.sum(Payment.amount))
        .join(Client)
        .filter(
            Client.branch_id == branch.id,
            Payment.status == PaymentStatus.APPROVED,
            Payment.created_at >= thirty_days_ago,
        )
    )
    fiat_sum, legacy_sum = deposit_volume_query.first() or (0, 0)
    deposit_volume = float(fiat_sum or legacy_sum or 0)

    withdrawal_volume = (
        db.session.query(func.coalesce(func.sum(Withdrawal.amount), 0))
        .join(Client)
        .filter(
            Client.branch_id == branch.id,
            Withdrawal.status == WithdrawalStatus.APPROVED,
            Withdrawal.created_at >= thirty_days_ago,
        )
        .scalar()
        or 0
    )

    pending_withdrawals = (
        Withdrawal.query.join(Client)
        .filter(
            Client.branch_id == branch.id,
            Withdrawal.status == WithdrawalStatus.PENDING,
        )
        .count()
    )

    recent_payments = (
        Payment.query.join(Client)
        .filter(Client.branch_id == branch.id)
        .order_by(Payment.created_at.desc())
        .limit(6)
        .all()
    )

    recent_withdrawals = (
        Withdrawal.query.join(Client)
        .filter(Client.branch_id == branch.id)
        .order_by(Withdrawal.created_at.desc())
        .limit(6)
        .all()
    )

    recent_transactions = []
    for payment in recent_payments:
        recent_transactions.append(
            {
                'type': 'Deposit',
                'client': payment.client.company_name if payment.client else 'Unknown client',
                'amount': float(payment.fiat_amount or payment.amount or 0),
                'currency': payment.fiat_currency or payment.currency or payment.crypto_currency or 'USDT',
                'status': payment.status.value if payment.status else 'unknown',
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
            }
        )

    for withdrawal in recent_withdrawals:
        recent_transactions.append(
            {
                'type': 'Withdrawal',
                'client': withdrawal.client.company_name if withdrawal.client else 'Unknown client',
                'amount': float(withdrawal.amount or 0),
                'currency': withdrawal.currency or 'USDT',
                'status': withdrawal.status.value if withdrawal.status else 'unknown',
                'created_at': withdrawal.created_at.isoformat() if withdrawal.created_at else None,
            }
        )

    recent_transactions.sort(
        key=lambda item: item['created_at'] or now_eest().isoformat(), reverse=True
    )

    top_clients = (
        db.session.query(
            Client.company_name,
            func.coalesce(func.sum(Payment.fiat_amount), 0).label('fiat_total'),
            func.coalesce(func.sum(Payment.amount), 0).label('legacy_total'),
        )
        .join(Payment, Payment.client_id == Client.id)
        .filter(
            Client.branch_id == branch.id,
            Payment.status == PaymentStatus.APPROVED,
            Payment.created_at >= thirty_days_ago,
        )
        .group_by(Client.company_name)
        .all()
    )

    top_clients_formatted = [
        {
            'name': row[0],
            'deposit_total': float(row[1] or row[2] or 0),
        }
        for row in top_clients
    ]
    top_clients_formatted.sort(key=lambda item: item['deposit_total'], reverse=True)
    top_clients_formatted = top_clients_formatted[:5]

    balance_snapshot = float(deposit_volume) - float(withdrawal_volume)

    return {
        'total_clients': total_clients,
        'deposit_volume': float(deposit_volume),
        'withdrawal_volume': float(withdrawal_volume),
        'commission_estimate': float(deposit_volume) * 0.035,
        'pending_withdrawals': pending_withdrawals,
        'recent_transactions': recent_transactions[:6],
        'top_clients': top_clients_formatted,
        'demo_balance': balance_snapshot,
    }


def _get_demo_api_key(client):
    if not client:
        return None

    from app.models import ApiKey

    return (
        ApiKey.query.filter_by(client_id=client.id, is_active=True)
        .order_by(ApiKey.created_at.asc())
        .first()
    )


demo_gateway_bp = Blueprint("demo_gateway", __name__, url_prefix="/demo/gateway")


@demo_gateway_bp.route("/")
def landing():
    """Public landing page introducing the demo gateway experience."""
    return render_template("demo/gateway/landing.html")


@demo_gateway_bp.route("/wallet")
def wallet_demo():
    """Player-facing demo wallet with login, deposit, and withdrawal examples."""
    demo_branch = _get_demo_branch()
    demo_client = _get_demo_client()
    demo_stats = None
    api_key = _get_demo_api_key(demo_client)

    if demo_branch:
        try:
            demo_stats = _get_demo_stats(demo_branch)
        except Exception as exc:  # pragma: no cover - best effort demo data
            current_app.logger.warning("Demo branch stats unavailable: %s", exc)

    demo_config = {
        'api_url': request.url_root.rstrip('/') + '/api/v1',
        'api_key': api_key.key if api_key else 'demo_live_pk_xxxx',
        'client_id': getattr(demo_client, 'id', None),
        'client_company': getattr(demo_client, 'company_name', None),
        'user_id': 'demo_user_001',
        'demo_stats': demo_stats,
    }

    return render_template(
        "demo/gateway/wallet.html",
        demo_branch=demo_branch,
        demo_stats=demo_stats,
        demo_client=demo_client,
        demo_config=demo_config,
    )


@demo_gateway_bp.route("/branch")
def branch_tour():
    """Read-only tour of the branch dashboard metrics for the demo client."""
    demo_branch = _get_demo_branch()
    stats = None

    if demo_branch:
        try:
            stats = _get_demo_stats(demo_branch)
        except Exception as exc:  # pragma: no cover - best effort demo data
            current_app.logger.warning("Demo branch stats unavailable: %s", exc)

    return render_template(
        "demo/gateway/branch.html",
        demo_branch=demo_branch,
        stats=stats,
    )
